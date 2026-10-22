"""SQLite records; each operation has its own connection and transaction."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from app.contracts import Document, Passage

BACKEND_DIR = Path(__file__).resolve().parents[2]


def local_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BACKEND_DIR / path


class Storage:
    def __init__(self, data_dir: Path, database_path: Path):
        self.upload_dir = data_dir / "uploads"
        self.database_path = database_path
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY, report_date TEXT NOT NULL,
                    original_path TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS passages (
                    passage_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS passages_document ON passages(doc_id);
            """)

    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def save(self, document: Document, passages: list[Passage], original: Path):
        with closing(self.connect()) as connection, connection:
            connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?)", (
                document.doc_id, document.report_date.isoformat(), str(original),
                document.model_dump_json(),
            ))
            connection.executemany("INSERT INTO passages VALUES (?, ?, ?)", [
                (p.passage_id, p.doc_id, p.model_dump_json()) for p in passages
            ])

    def list_documents(self) -> list[Document]:
        with closing(self.connect()) as connection:
            return [Document.model_validate_json(row[0]) for row in connection.execute(
                "SELECT payload FROM documents ORDER BY report_date, doc_id"
            )]

    def get_passage(self, passage_id: str) -> Passage | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM passages WHERE passage_id = ?", (passage_id,)
            ).fetchone()
        return Passage.model_validate_json(row[0]) if row else None


def get_storage() -> Storage:
    return Storage(
        local_path(os.getenv("FOLIO_DATA_DIR", "data")),
        local_path(os.getenv("FOLIO_DATABASE_PATH", "data/folio.sqlite3")),
    )
