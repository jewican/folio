"""W1 adapter for W2's extraction handoff."""
from datetime import date
from pathlib import Path
from typing import Protocol

from pydantic import HttpUrl

from app.contracts import Passage
from app.ingestion import ExtractionError, ingest_document


class InvalidDocument(ValueError):
    """Unreadable, empty, encrypted, or otherwise unusable document."""


class Ingestor(Protocol):
    def __call__(self, *, doc_id: str, path: Path, title: str,
                 report_date: date, source_url: HttpUrl | None,
                 media_type: str) -> list[Passage]: ...


def ingest(*, doc_id: str, path: Path, title: str, report_date: date,
           source_url: HttpUrl | None, media_type: str) -> list[Passage]:
    return ingest_document(path, dict(doc_id=doc_id, title=title,
                                     report_date=report_date, source_url=source_url))


def get_ingestor() -> Ingestor:
    return ingest
