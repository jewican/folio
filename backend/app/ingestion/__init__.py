"""Local PDF/TXT extraction; no OCR, fetching, or persistence."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader
from pydantic import BaseModel, Field, HttpUrl

from app.contracts import Passage

MAX_FILE_BYTES = 10_485_760
_PAGE_MARKER = re.compile(r"^-{10} SOURCE PDF PAGE ([1-9]\d*) / ([1-9]\d*) -{10}[^\S\r\n]*\r?$", re.MULTILINE)


class ExtractionError(ValueError):
    """W1 can map code to the corresponding shared API error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExtractedPage:
    doc_id: str
    page: int | None
    text: str


def extract_text_pages(doc_id: str, path: str | Path) -> list[ExtractedPage]:
    """Preserve text and explicit transcript source-page labels.

    These labels describe the transcript, not verified physical PDF pages.
    Preamble/plain TXT has page=None. Markers remain in text for provenance.
    """
    if not isinstance(doc_id, str) or not 1 <= len(doc_id) <= 128:
        raise ValueError("doc_id must contain 1–128 characters")
    path = Path(path)
    if path.suffix.lower() != ".txt":
        raise ExtractionError("unsupported_file_type", "Only UTF-8 TXT is supported by this extractor.")
    with path.open("rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ExtractionError("upload_too_large", "File exceeds 10 MiB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("invalid_document", "TXT must be valid UTF-8.") from exc
    if data.startswith((b"%PDF-", b"PK\x03\x04")) or any(ord(c) < 32 and c not in "\t\r\n\f" for c in text):
        raise ExtractionError("unsupported_file_type", "Content is not plain text.")
    if not text.strip():
        raise ExtractionError("invalid_document", "Document contains no text.")
    markers = list(_PAGE_MARKER.finditer(text))
    if not markers:
        return [ExtractedPage(doc_id, None, text)]
    pages = []
    if markers[0].start():
        pages.append(ExtractedPage(doc_id, None, text[:markers[0].start()]))
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        pages.append(ExtractedPage(doc_id, int(marker[1]), text[marker.start():end]))
    return pages


def extract_pdf_pages(doc_id: str, path: str | Path) -> list[ExtractedPage]:
    """Extract physical 1-based pages; reject encrypted or textless PDFs."""
    with Path(path).open("rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ExtractionError("upload_too_large", "File exceeds 10 MiB.")
    if not data.startswith(b"%PDF-"):
        raise ExtractionError("unsupported_file_type", "Content is not PDF.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("invalid_document", "Encrypted PDFs are unsupported.")
        pages = [ExtractedPage(doc_id, number, page.extract_text() or "")
                 for number, page in enumerate(reader.pages, 1)]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("invalid_document", "PDF could not be read.") from exc
    if not any(page.text.strip() for page in pages):
        raise ExtractionError("invalid_document", "PDF contains no extractable text; OCR is unsupported.")
    return pages


def _chunks(text: str):
    """Lossless slices near 400 words, preferring paragraphs within 300–500.

    Short pages/tails stay short. Oversized paragraphs split at word boundaries.
    """
    words = list(re.finditer(r"\S+", text))
    start_word = 0
    start_char = 0
    while len(words) - start_word > 500:
        candidates = []
        for size in range(300, 501):
            left = words[start_word + size - 1].end()
            right = words[start_word + size].start()
            if re.search(r"\r?\n[^\S\r\n]*\r?\n", text[left:right]):
                candidates.append(size)
        # Balance an unstructured long paragraph to avoid tiny final fragments.
        remaining = len(words) - start_word
        target = min(400, max(300, remaining // ((remaining + 499) // 500)))
        size = min(candidates, key=lambda n: (abs(n - target), n)) if candidates else target
        end_char = words[start_word + size].start()
        yield text[start_char:end_char]
        start_word += size
        start_char = end_char
    if text[start_char:].strip():
        yield text[start_char:]


class IngestionMetadata(BaseModel):
    """Upload metadata supplied by W1; additional Document fields are ignored."""

    doc_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    report_date: date
    source_url: HttpUrl | None = None


def ingest_document(file_path: str | Path, metadata: dict | BaseModel) -> list[Passage]:
    """Extract contract passages without publishing them to storage or retrieval."""
    if isinstance(metadata, BaseModel):
        metadata = metadata.model_dump()
    meta = IngestionMetadata.model_validate(metadata)
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = extract_pdf_pages(meta.doc_id, path)
    elif suffix == ".txt":
        pages = extract_text_pages(meta.doc_id, path)
    else:
        raise ExtractionError("unsupported_file_type", "Only PDF and UTF-8 TXT are supported.")
    passages = []
    for page in pages:
        for text in _chunks(page.text):
            passage = Passage(
                passage_id="pending", **meta.model_dump(),
                page=page.page if suffix == ".pdf" else None, text=text,
            )
            identity = [len(passages), passage.model_dump(mode="json")]
            digest = sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            passage.passage_id = "pas_" + digest
            passages.append(passage)
    return passages


def extract_passages(
    doc_id: str,
    path: str | Path,
    *,
    title: str,
    report_date: date | str,
    source_url: str | None = None,
) -> list[Passage]:
    """Return shared Passage models for W1 to store, using TXT page=None.

    No passage crosses an explicit transcript page marker. IDs bind document,
    position, text and metadata; rebuilding retrieval uses stored IDs unchanged.
    Report date must be provided by the uploader, never inferred from content.
    """
    return ingest_document(path, dict(doc_id=doc_id, title=title,
                                     report_date=report_date, source_url=source_url))
