"""SQLite records; each operation has its own connection and transaction."""
import os
import sqlite3
import logging
from contextlib import closing
from functools import lru_cache
from threading import RLock
from pathlib import Path
from time import perf_counter

from app.contracts import Document, Passage
from app.retrieval import BM25Index
from app.retrieval.hybrid import EmbeddingClient, EmbeddingError, HybridRetriever
from app.storage.embeddings import EmbeddingStore

BACKEND_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def retrieval_mode() -> str:
    mode = os.getenv("FOLIO_RETRIEVAL_MODE", "hybrid").strip().lower()
    if mode not in {"bm25", "hybrid"}:
        raise ValueError("FOLIO_RETRIEVAL_MODE must be bm25 or hybrid")
    return mode


def local_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BACKEND_DIR / path


class Storage:
    def __init__(self, data_dir: Path, database_path: Path):
        self._lock = RLock()
        self._index = None
        self._indexed_count = -1
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
        self._hybrid = HybridRetriever(EmbeddingStore(self.connect))

    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _build_index(connection):
        passages = [Passage.model_validate_json(row[0]) for row in connection.execute(
            "SELECT payload FROM passages ORDER BY passage_id"
        )]
        return BM25Index(passages), len(passages)

    def save(self, document: Document, passages: list[Passage], original: Path):
        mode = retrieval_mode()
        with self._lock:
            with closing(self.connect()) as connection, connection:
                connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?)", (
                    document.doc_id, document.report_date.isoformat(), str(original),
                    document.model_dump_json(),
                ))
                connection.executemany("INSERT INTO passages VALUES (?, ?, ?)", [
                    (p.passage_id, p.doc_id, p.model_dump_json()) for p in passages
                ])
                # Build before commit: failed indexing rolls back publication too.
                replacement, count = self._build_index(connection)
            self._index, self._indexed_count = replacement, count
        # Upload publication remains atomic and independent of optional embeddings.
        # Network requests run after commit, outside the storage lock.
        if mode == "hybrid":
            started = perf_counter()
            try:
                self._hybrid.prepare(passages, EmbeddingClient.from_env(), started + 20)
                outcome = "ready"
            except (EmbeddingError, sqlite3.Error):
                outcome = "deferred"
            logger.info("Embedding upload status=%s passages=%d elapsed_ms=%.2f",
                        outcome, len(passages), (perf_counter() - started) * 1000)

    def retrieve(self, question: str, doc_ids: list[str], mode: str | None = None) -> list[Passage]:
        started = perf_counter()
        requested = retrieval_mode() if mode is None else mode
        if requested not in {"bm25", "hybrid"}:
            raise ValueError("Only bm25 and hybrid retrieval are supported")
        with self._lock, closing(self.connect()) as connection, connection:
            # One read snapshot, also detecting uploads from another worker.
            connection.execute("BEGIN")
            count = connection.execute("SELECT count(*) FROM passages").fetchone()[0]
            if self._index is None or count != self._indexed_count:
                self._index, self._indexed_count = self._build_index(connection)
            index = self._index
            # Interleave independent document rankings: a long report must not
            # consume the entire context when several versions are selected.
            rankings = [index.retrieve(question, [doc_id], k=6)
                        for doc_id in sorted(doc_ids)]
            selected = []
            if requested == "hybrid":
                placeholders = ",".join("?" for _ in doc_ids)
                selected = [Passage.model_validate_json(row[0]) for row in connection.execute(
                    f"SELECT payload FROM passages WHERE doc_id IN ({placeholders}) ORDER BY passage_id",
                    doc_ids,
                )]
        actual, fallback = "bm25", "none"
        if requested == "hybrid" and selected:
            try:
                rankings = self._hybrid.rank(question, selected, index, doc_ids)
                actual = "hybrid"
            except (EmbeddingError, sqlite3.Error) as exc:
                # Provider and optional cache failures never break baseline retrieval.
                fallback = str(exc) if isinstance(exc, EmbeddingError) else "cache_error"
        result = [ranking[position] for position in range(6)
                  for ranking in rankings if position < len(ranking)][:6]
        logger.info("Retrieval requested=%s actual=%s fallback=%s passages=%d elapsed_ms=%.2f",
                    requested, actual, fallback, len(result), (perf_counter() - started) * 1000)
        return result

    def list_documents(self) -> list[Document]:
        with closing(self.connect()) as connection:
            return [Document.model_validate_json(row[0]) for row in connection.execute(
                "SELECT payload FROM documents ORDER BY report_date, doc_id"
            )]

    def list_passages(self) -> list[Passage]:
        """One committed snapshot for W2's StoredPassageRetriever handoff."""
        with closing(self.connect()) as connection:
            return [Passage.model_validate_json(row[0]) for row in connection.execute(
                "SELECT p.payload FROM passages p JOIN documents d ON p.doc_id = d.doc_id "
                "ORDER BY p.passage_id"
            )]

    def get_passage(self, passage_id: str) -> Passage | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM passages WHERE passage_id = ?", (passage_id,)
            ).fetchone()
        return Passage.model_validate_json(row[0]) if row else None


@lru_cache(maxsize=8)
def _storage(data_dir: Path, database_path: Path) -> Storage:
    return Storage(data_dir, database_path)


def get_storage() -> Storage:
    return _storage(
        local_path(os.getenv("FOLIO_DATA_DIR", "data")),
        local_path(os.getenv("FOLIO_DATABASE_PATH", "data/folio.sqlite3")),
    )
