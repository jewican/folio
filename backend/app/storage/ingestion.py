"""W1 fallback adapter. W2 can replace get_ingestor without changing routes.

The callable receives an assigned document ID, local original, and metadata;
it returns complete Passage objects. It must not publish to storage itself.
"""
from datetime import date
from pathlib import Path
from typing import Protocol

from pydantic import HttpUrl
from pypdf import PdfReader

from app.contracts import Passage


class InvalidDocument(ValueError):
    """Unreadable, empty, encrypted, or otherwise unusable document."""


class Ingestor(Protocol):
    def __call__(self, *, doc_id: str, path: Path, title: str,
                 report_date: date, source_url: HttpUrl | None,
                 media_type: str) -> list[Passage]: ...


def basic_ingest(*, doc_id: str, path: Path, title: str, report_date: date,
                 source_url: HttpUrl | None, media_type: str) -> list[Passage]:
    try:
        if media_type == "text/plain":
            text = path.read_text(encoding="utf-8-sig")
            if any(ord(char) < 32 and char not in "\n\r\t\f" for char in text):
                raise InvalidDocument()
            pages = [(None, text)]
        else:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise InvalidDocument()
            pages = [(number, page.extract_text() or "")
                     for number, page in enumerate(reader.pages, start=1)]
    except Exception as exc:
        raise InvalidDocument() from exc

    passages = []
    for page, text in pages:
        # A small fallback only: preserve exact text and PDF page boundaries.
        for offset in range(0, len(text), 2000):
            chunk = text[offset:offset + 2000]
            if chunk.strip():
                passages.append(Passage(
                    passage_id=f"pas_{doc_id}_{len(passages) + 1}", doc_id=doc_id,
                    title=title, report_date=report_date, source_url=source_url,
                    page=page, text=chunk,
                ))
    if not passages:
        raise InvalidDocument()
    return passages


def get_ingestor() -> Ingestor:
    return basic_ingest
