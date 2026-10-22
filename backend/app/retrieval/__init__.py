"""Selection-scoped rank-bm25 retrieval over stored shared Passage objects."""

from collections.abc import Callable, Iterable, Sequence
from functools import lru_cache
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from threading import RLock

from rank_bm25 import BM25Plus

from app.contracts import Passage


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


class BM25Index:
    """Snapshot saved passages; cache up to 32 explicitly selected corpora."""

    def __init__(self, passages: Iterable[Passage]):
        self._rows = []
        seen = set()
        for passage in passages:
            if passage.passage_id in seen:
                raise ValueError("Duplicate passage_id in index")
            seen.add(passage.passage_id)
            stored = passage.model_copy(deep=True)
            self._rows.append((stored, _tokens(stored.text)))
        self._selection = lru_cache(maxsize=32)(self._build_selection)

    def save(self, path: str | Path) -> None:
        """Atomically save a portable snapshot; BM25 is rebuilt from exact passages."""
        path = Path(path)
        payload = {"version": 1, "passages": [
            passage.model_dump(mode="json") for passage, _ in self._rows
        ]}
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    delete=False) as output:
                temporary = Path(output.name)
                json.dump(payload, output, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: str | Path) -> "BM25Index":
        """Load stored IDs/text/metadata without re-extracting original files."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload["version"] != 1:
            raise ValueError("Unsupported index snapshot version")
        return cls(Passage.model_validate(row) for row in payload["passages"])

    def _build_selection(self, document_ids: tuple[str, ...]):
        selected = set(document_ids)
        rows = [row for row in self._rows if row[0].doc_id in selected and row[1]]
        # BM25Plus has positive IDF even for a one-passage corpus. delta=0
        # removes its additive baseline; unmatched passages are excluded below.
        scorer = BM25Plus([row[1] for row in rows], delta=0) if rows else None
        return rows, scorer

    def retrieve(self, question: str, document_ids: Sequence[str], k: int = 6,
                 mode: str = "bm25") -> list[Passage]:
        if mode != "bm25":
            raise ValueError("Only bm25 retrieval is supported")
        if (isinstance(document_ids, str) or not document_ids
                or any(not isinstance(id, str) or not id for id in document_ids)
                or len(set(document_ids)) != len(document_ids)):
            raise ValueError("Explicit distinct document_ids are required")
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive integer")
        if not question.strip():
            raise ValueError("question must not be blank")
        rows, scorer = self._selection(tuple(sorted(document_ids)))
        terms = sorted(set(_tokens(question)))
        if scorer is None or not terms:
            return []
        scores = scorer.get_scores(terms)
        ranked = [(float(score), passage) for score, (passage, tokens) in zip(scores, rows)
                  if set(terms).intersection(tokens)]
        ranked.sort(key=lambda item: (-item[0], item[1].passage_id))
        return [passage.model_copy(deep=True) for _, passage in ranked[:k]]


class StoredPassageRetriever:
    """Callable W1 handoff over a loader of all committed ready passages.

    Refresh before every query so successful uploads need no index notification.
    W1 owns the loader and its transaction; no database or server is created here.
    Loading failures propagate instead of silently serving an outdated snapshot.
    """

    def __init__(self, load_passages: Callable[[], Iterable[Passage]]):
        self._load_passages = load_passages
        self._index = BM25Index([])
        self._saved_rows: list[Passage] = []
        self._lock = RLock()

    def rebuild(self) -> BM25Index:
        """Refresh from authoritative storage, preserving every passage field."""
        with self._lock:
            rows = sorted((p.model_copy(deep=True) for p in self._load_passages()),
                          key=lambda p: p.passage_id)
            if rows != self._saved_rows:
                replacement = BM25Index(rows)
                self._index = replacement
                self._saved_rows = rows
            return self._index

    def save(self, path: str | Path) -> None:
        self.rebuild().save(path)

    def retrieve(self, question: str, doc_ids: Sequence[str], top_k: int = 6,
                 mode: str = "bm25") -> list[Passage]:
        return self.rebuild().retrieve(question, doc_ids, top_k, mode)

    __call__ = retrieve


_index = BM25Index([])


def rebuild_index(passages: Iterable[Passage]) -> BM25Index:
    """W1 calls after loading/publishing saved passages, including on restart."""
    global _index
    replacement = BM25Index(passages)
    _index = replacement
    return replacement


def retrieve(question: str, document_ids: Sequence[str], k: int = 6,
             mode: str = "bm25") -> list[Passage]:
    """Return ranked contract passages from the current process-local index."""
    return _index.retrieve(question, document_ids, k, mode)
