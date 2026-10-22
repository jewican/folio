"""Optional embedding cache in the authoritative local SQLite database."""
from contextlib import closing
import json

from app.retrieval.hybrid import NAMESPACE, EmbeddingError, fingerprint, normalize


class EmbeddingStore:
    def __init__(self, connect):
        self.connect = connect
        with closing(connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS passage_embeddings (
                passage_id TEXT NOT NULL REFERENCES passages(passage_id),
                namespace TEXT NOT NULL, content_hash TEXT NOT NULL, vector TEXT NOT NULL,
                PRIMARY KEY (passage_id, namespace)
            )""")

    def load(self, passages):
        if not passages:
            return {}
        selected = {p.passage_id: p for p in passages}
        result = {}
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT passage_id, content_hash, vector FROM passage_embeddings WHERE namespace = ?",
                (NAMESPACE,),
            )
            for pid, digest, payload in rows:
                if pid not in selected or digest != fingerprint(selected[pid]):
                    continue
                try:
                    result[pid] = normalize(json.loads(payload))
                except (ValueError, TypeError, EmbeddingError):
                    continue  # Corrupt cache entries are regenerated from canonical text.
        return result

    def save(self, passages, vectors):
        with closing(self.connect()) as db, db:
            db.executemany("""INSERT INTO passage_embeddings VALUES (?, ?, ?, ?)
                ON CONFLICT(passage_id, namespace) DO UPDATE SET
                content_hash=excluded.content_hash, vector=excluded.vector""", [
                (p.passage_id, NAMESPACE, fingerprint(p), json.dumps(normalize(vector)))
                for p, vector in zip(passages, vectors)
            ])
