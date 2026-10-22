"""Dependency-free BM25 over stored shared Passage objects."""

from collections import Counter
from collections.abc import Iterable, Sequence
from math import log
import re

from app.contracts import Passage


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


class BM25Index:
    """Build once from W1's stored passages; rebuild after uploads/restart.

    Selection-scoped statistics ensure unselected reports cannot affect ranking.
    W1 validates ready document existence and comparison date ordering.
    """

    def __init__(self, passages: Iterable[Passage]):
        self._rows = []
        seen = set()
        for passage in passages:
            if passage.passage_id in seen:
                raise ValueError("Duplicate passage_id in index")
            seen.add(passage.passage_id)
            stored = passage.model_copy(deep=True)
            counts = Counter(_tokens(stored.text))
            self._rows.append((stored, counts, sum(counts.values())))

    def retrieve(self, question: str, doc_ids: Sequence[str], top_k: int = 5) -> list[Passage]:
        """Return ranked exact passages with positive lexical matches only."""
        if isinstance(doc_ids, str) or not doc_ids or len(set(doc_ids)) != len(doc_ids):
            raise ValueError("Explicit distinct doc_ids are required")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if not question.strip():
            raise ValueError("question must not be blank")
        selected = set(doc_ids)
        rows = [row for row in self._rows if row[0].doc_id in selected]
        if not rows:
            return []
        terms = set(_tokens(question))
        avg_length = sum(row[2] for row in rows) / len(rows)
        if not avg_length:
            return []
        frequency = Counter(term for _, counts, _ in rows for term in counts if term in terms)
        ranked = []
        for passage, counts, length in rows:
            score = 0.0
            for term in sorted(terms & counts.keys()):
                idf = log(1 + (len(rows) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                tf = counts[term]
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / avg_length))
            if score > 0:
                ranked.append((score, passage))
        ranked.sort(key=lambda item: (-item[0], item[1].passage_id))
        return [passage.model_copy(deep=True) for _, passage in ranked[:top_k]]
