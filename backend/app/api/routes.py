"""Six agreed endpoints; W1 replaces feature stubs after foundation setup."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import HttpUrl

from app.contracts import (
    AskRequest, AskResponse, CompareRequest, CompareResponse,
    Document, DocumentList, Health, Passage,
)

router = APIRouter()
STUB_RESPONSE = {501: {"description": "Feature implementation has not started"}}


def not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail={"code": "not_implemented", "message": "Contract defined; feature not implemented."},
    )


@router.get("/health", response_model=Health, tags=["system"])
def health():
    return Health()


@router.get("/documents", response_model=DocumentList, responses=STUB_RESPONSE, tags=["documents"])
def list_documents():
    not_implemented()


@router.post("/documents", response_model=Document, status_code=201, responses=STUB_RESPONSE, tags=["documents"])
def upload_document(
    file: Annotated[UploadFile, File(description="Text-based PDF or UTF-8 TXT, at most 10 MiB")],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    report_date: Annotated[date, Form(description="Report publication date, YYYY-MM-DD")],
    source_url: Annotated[HttpUrl | None, Form()] = None,
):
    not_implemented()


@router.post("/ask", response_model=AskResponse, responses=STUB_RESPONSE, tags=["answers"])
def ask(request: AskRequest):
    not_implemented()


@router.post("/compare", response_model=CompareResponse, responses=STUB_RESPONSE, tags=["answers"])
def compare(request: CompareRequest):
    not_implemented()


@router.get("/passages/{id}", response_model=Passage, responses=STUB_RESPONSE, tags=["evidence"])
def get_passage(id: str):
    not_implemented()
