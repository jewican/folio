"""Local UTF-8 TXT extraction; no OCR, fetching, or persistence."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

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


def _chunks(text: str, max_chars: int):
    """Contiguous, lossless slices, preferring paragraph/word boundaries."""
    while text:
        end = min(len(text), max_chars)
        if end < len(text):
            boundary = text.rfind("\n\n", 0, end)
            if boundary >= end // 2:
                end = boundary + 2
            else:
                spaces = list(re.finditer(r"\s+", text[:end]))
                if spaces and spaces[-1].end() >= end // 2:
                    end = spaces[-1].end()
        yield text[:end]
        text = text[end:]


def extract_passages(
    doc_id: str,
    path: str | Path,
    *,
    title: str,
    report_date: date | str,
    source_url: str | None = None,
    max_chars: int = 1600,
) -> list[Passage]:
    """Return shared Passage models for W1 to store, using TXT page=None.

    No passage crosses an explicit transcript page marker. IDs bind document,
    position, text and metadata; rebuilding retrieval uses stored IDs unchanged.
    Report date must be provided by the uploader, never inferred from content.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 100:
        raise ValueError("max_chars must be an integer of at least 100")
    if not title.strip() or len(title) > 200:
        raise ValueError("title must contain 1–200 characters and not be blank")
    passages = []
    for page in extract_text_pages(doc_id, path):
        for text in _chunks(page.text, max_chars):
            if not text.strip():
                continue
            passage = Passage(
                passage_id="pending", doc_id=doc_id, title=title,
                report_date=report_date, source_url=source_url, page=None, text=text,
            )
            identity = [len(passages), passage.model_dump(mode="json")]
            digest = sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            passage.passage_id = "pas_" + digest
            passages.append(passage)
    return passages
