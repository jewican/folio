"""Selection-scoped rank-bm25 retrieval over stored shared Passage objects."""

from collections.abc import Iterable, Sequence
from functools import lru_cache
import re

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
