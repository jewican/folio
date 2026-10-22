"""Document uploads, canonical evidence, grounded answers and report comparison."""
from datetime import date, datetime, timezone
import os
import re
from time import perf_counter
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BeforeValidator, HttpUrl

from app.contracts import (
    AskRequest, AskResponse, CompareRequest, CompareResponse,
    Document, DocumentList, Health, Passage, ResponseMeta,
)
from app.generation.answer import AnswerResult, generate_answer
from app.generation.compare import generate_comparison
from app.generation.client import GenerationError
from app.storage.database import Storage, get_storage
from app.storage.ingestion import Ingestor, InvalidDocument, ExtractionError, get_ingestor

router = APIRouter()


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Report date must use YYYY-MM-DD")
    return value


ReportDate = Annotated[date, BeforeValidator(iso_date)]


@router.get("/health", response_model=Health, tags=["system"])
def health():
    return Health()


@router.get("/documents", response_model=DocumentList, tags=["documents"])
def list_documents(storage: Annotated[Storage, Depends(get_storage)]):
    return DocumentList(documents=storage.list_documents())


def upload_error(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@router.post("/documents", response_model=Document, status_code=201, tags=["documents"])
def upload_document(
    file: Annotated[UploadFile, File(description="Text-based PDF or UTF-8 TXT, at most 10 MiB")],
    title: Annotated[str, Form(min_length=1, max_length=200, pattern=r"\S")],
    report_date: Annotated[ReportDate, Form(description="Report publication date, YYYY-MM-DD")],
    storage: Annotated[Storage, Depends(get_storage)],
    ingest: Annotated[Ingestor, Depends(get_ingestor)],
    source_url: Annotated[HttpUrl | None, Form()] = None,
):
    original = None
    saved = False
    try:
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        suffix = Path(filename).suffix.lower()
        media_type = {".pdf": "application/pdf", ".txt": "text/plain"}.get(suffix)
        if media_type is None or file.content_type != media_type:
            raise upload_error(415, "unsupported_file_type", "Upload a PDF or UTF-8 TXT file with its matching media type.")
        limit = min(10 * 1024 * 1024, max(1, int(os.getenv("FOLIO_MAX_UPLOAD_BYTES", "10485760"))))
        doc_id = f"doc_{uuid4().hex}"
        original = storage.upload_dir / f"{doc_id}{suffix}"
        size = 0
        prefix = b""
        with original.open("xb") as destination:
            while chunk := file.file.read(64 * 1024):
                size += len(chunk)
                if size > limit:
                    raise upload_error(413, "upload_too_large", "File exceeds the upload size limit.")
                if not prefix:
                    prefix = chunk[:8]
                destination.write(chunk)
        if not size:
            raise InvalidDocument()
        if (media_type == "application/pdf" and not prefix.startswith(b"%PDF-")) or (
            media_type == "text/plain" and prefix.startswith((b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff"))
        ):
            raise upload_error(415, "unsupported_file_type", "File content does not match its declared type.")
        passages = ingest(doc_id=doc_id, path=original, title=title.strip(),
                          report_date=report_date, source_url=source_url, media_type=media_type)
        if not passages or any(
            p.doc_id != doc_id or p.title != title.strip() or p.report_date != report_date
            or p.source_url != source_url or not p.text.strip()
            or (media_type == "text/plain" and p.page is not None)
            or (media_type == "application/pdf" and p.page is None)
            for p in passages
        ) or len({p.passage_id for p in passages}) != len(passages):
            raise InvalidDocument()
        document = Document(
            doc_id=doc_id, title=title.strip(), filename=filename, media_type=media_type,
            report_date=report_date, source_url=source_url,
            uploaded_at=datetime.now(timezone.utc), passage_count=len(passages),
        )
        storage.save(document, passages, original)
        saved = True
        return document
    except ExtractionError as exc:
        status = {"upload_too_large": 413, "unsupported_file_type": 415}.get(exc.code, 422)
        raise upload_error(status, exc.code, str(exc)) from None
    except InvalidDocument:
        raise upload_error(422, "invalid_document", "Document must contain readable text and must not be encrypted.") from None
    finally:
        file.file.close()
        if original is not None and not saved:
            original.unlink(missing_ok=True)


@router.post("/ask", response_model=AskResponse, tags=["answers"])
def ask(request: AskRequest, storage: Annotated[Storage, Depends(get_storage)]):
    started = perf_counter()
    ready = {document.doc_id for document in storage.list_documents()}
    if not set(request.doc_ids) <= ready:
        raise upload_error(404, "document_not_found", "A selected document was not found.")
    passages = storage.retrieve(request.question, request.doc_ids)
    # Enforce the boundary even if a retriever accidentally returns foreign or
    # altered rows. Only canonical stored evidence can reach the model.
    if any(p.doc_id not in request.doc_ids or storage.get_passage(p.passage_id) != p
           for p in passages):
        raise GenerationError(reason="invalid_evidence")
    result = generate_answer(request.question, passages) if passages else AnswerResult([])
    claims = result.claims
    return AskResponse(
        question=request.question, doc_ids=request.doc_ids,
        status="answered" if claims else "insufficient_evidence",
        answer=" ".join(claim.text for claim in claims) if claims else result.explanation or (
            "The selected documents do not provide enough evidence to answer this question."
        ),
        claims=claims,
        meta=ResponseMeta(elapsed_ms=round((perf_counter() - started) * 1000), cached=False),
    )


@router.post("/compare", response_model=CompareResponse, tags=["answers"])
def compare(request: CompareRequest, storage: Annotated[Storage, Depends(get_storage)]):
    started = perf_counter()
    documents = {d.doc_id: d for d in storage.list_documents()}
    selected = [request.older_doc_id, request.newer_doc_id]
    if not set(selected) <= documents.keys():
        raise upload_error(404, 'document_not_found', 'A selected document was not found.')
    if documents[selected[0]].report_date >= documents[selected[1]].report_date:
        raise upload_error(422, 'invalid_selection', 'Select an earlier and a later report date.')
    passages = storage.retrieve(request.question, selected)
    if any(p.doc_id not in selected or storage.get_passage(p.passage_id) != p for p in passages):
        raise GenerationError(reason='invalid_evidence')
    if {p.doc_id for p in passages} == set(selected):
        status, summary, changes = generate_comparison(request.question, passages, *selected)
    else:
        status, summary, changes = 'insufficient_evidence', 'Relevant evidence is needed from both selected reports.', []
    return CompareResponse(**request.model_dump(), status=status, summary=summary, changes=changes,
                           meta=ResponseMeta(elapsed_ms=round((perf_counter() - started) * 1000), cached=False))


@router.get("/passages/{id}", response_model=Passage, tags=["evidence"])
def get_passage(id: str, storage: Annotated[Storage, Depends(get_storage)]):
    passage = storage.get_passage(id)
    if passage is None:
        raise upload_error(404, "passage_not_found", "The requested passage was not found.")
    return passage
