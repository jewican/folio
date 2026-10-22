"""Gemini Embedding 2 semantic ranking, fused with the existing BM25 index."""
from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
from time import perf_counter
from typing import Protocol

import httpx
from dotenv import load_dotenv
from pydantic import SecretStr

from app.contracts import Passage
from app.retrieval import BM25Index

MODEL = "gemini-embedding-2"
DIMENSIONS = 768
NAMESPACE = f"{MODEL}:{DIMENSIONS}:search-v1"


class EmbeddingError(Exception):
    """A safe diagnostic; never contains provider bodies, URLs, or credentials."""


def normalize(values: list[float]) -> list[float]:
    if (not isinstance(values, list) or len(values) != DIMENSIONS
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
        raise EmbeddingError("invalid_vector")
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingError("invalid_vector")
    return [v / norm for v in values]


def document_input(passage: Passage) -> str:
    return f"title: {passage.title} | text: {passage.text}"


def fingerprint(passage: Passage) -> str:
    return sha256(document_input(passage).encode("utf-8")).hexdigest()


class VectorStore(Protocol):
    def load(self, passages: list[Passage]) -> dict[str, list[float]]: ...
    def save(self, passages: list[Passage], vectors: list[list[float]]) -> None: ...


@dataclass(frozen=True)
class EmbeddingClient:
    api_key: SecretStr
    timeout_seconds: float = 8

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        try:
            timeout = float(os.getenv("GEMINI_EMBEDDING_TIMEOUT_SECONDS", "8"))
        except ValueError:
            raise EmbeddingError("configuration") from None
        if not key or not 0 < timeout <= 20:
            raise EmbeddingError("configuration")
        return cls(SecretStr(key), timeout)

    def embed(self, texts: list[str], *, timeout: float) -> list[list[float]]:
        """Separate requests per chunk: multiple parts would aggregate vectors."""
        try:
            with httpx.Client(timeout=min(timeout, self.timeout_seconds)) as client:
                response = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents",
                    headers={"x-goog-api-key": self.api_key.get_secret_value()},
                    json={"requests": [
                        {"model": f"models/{MODEL}", "outputDimensionality": DIMENSIONS,
                         "content": {"parts": [{"text": text}]}}
                        for text in texts
                    ]},
                )
                response.raise_for_status()
                embeddings = response.json()["embeddings"]
            if len(embeddings) != len(texts):
                raise EmbeddingError("invalid_response")
            return [normalize(item["values"]) for item in embeddings]
        except httpx.TimeoutException:
            raise EmbeddingError("timeout") from None
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(f"provider_http_{exc.response.status_code}") from None
        except (httpx.RequestError, ValueError, KeyError, TypeError):
            raise EmbeddingError("invalid_response") from None


def rrf(rankings: list[list[Passage]], k: int) -> list[Passage]:
    """Reciprocal rank fusion with constant 60 and deterministic ID tie breaks."""
    scores: dict[str, float] = {}
    passages = {}
    for ranking in rankings:
        seen = set()
        for rank, passage in enumerate(ranking, 1):
            if passage.passage_id in seen:
                continue
            seen.add(passage.passage_id)
            passages[passage.passage_id] = passage
            scores[passage.passage_id] = scores.get(passage.passage_id, 0) + 1 / (60 + rank)
    ordered = sorted(scores, key=lambda pid: (-scores[pid], pid))
    return [passages[pid].model_copy(deep=True) for pid in ordered[:k]]


class HybridRetriever:
    def __init__(self, store: VectorStore):
        self.store = store

    def prepare(self, passages: list[Passage], client: EmbeddingClient,
                deadline: float) -> dict[str, list[float]]:
        vectors = self.store.load(passages)
        missing = [p for p in passages if p.passage_id not in vectors]
        for start in range(0, len(missing), 32):
            remaining = deadline - perf_counter()
            if remaining <= 0:
                raise EmbeddingError("deadline")
            batch = missing[start:start + 32]
            generated = client.embed([document_input(p) for p in batch], timeout=remaining)
            self.store.save(batch, generated)
            vectors.update((p.passage_id, vector) for p, vector in zip(batch, generated))
        return vectors

    def rank(self, question: str, passages: list[Passage], index: BM25Index,
             doc_ids: list[str], k: int = 6) -> list[list[Passage]]:
        """Fuse independently per document, preserving W1's balanced context."""
        deadline = perf_counter() + 20
        client = EmbeddingClient.from_env()
        vectors = self.prepare(passages, client, deadline)
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise EmbeddingError("deadline")
        query = client.embed([f"task: search result | query: {question}"], timeout=remaining)[0]
        rankings = []
        for doc_id in sorted(doc_ids):
            rows = [p for p in passages if p.doc_id == doc_id]
            semantic = sorted(rows, key=lambda p: (
                -sum(a * b for a, b in zip(query, vectors[p.passage_id])), p.passage_id))
            candidates = max(20, k)
            rankings.append(rrf([index.retrieve(question, [doc_id], k=candidates),
                                 semantic[:candidates]], k))
        return rankings
