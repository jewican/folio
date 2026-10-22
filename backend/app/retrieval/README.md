# Version-scoped hybrid retrieval

`HybridRetriever.rank(question, passages, index, doc_ids, k=6)` filters the supplied
snapshot to explicit, distinct document IDs before reading the vector cache or
sending text to Gemini. Each document has an independent BM25/semantic ranking
and reciprocal rank fusion. Unselected documents cannot supply evidence or alter
selected-document BM25 scores. An empty selection is invalid; unknown IDs yield
empty rankings without contacting Gemini. Results preserve exact stored passage
IDs, text, dates, title, source URL and page.

For a dated pair, use the optional retrieval-layer handoff:

```python
older, newer = retriever.compare(
    question, saved_passages, bm25_index,
    older_doc_id="z-older", newer_doc_id="a-newer", k=3,
    mode="hybrid",  # or "bm25"
)
```

This returns two separate evidence lists in requested version order, independently
of document-ID ordering. Both documents must exist, have consistent stored report
dates, and satisfy `older.report_date < newer.report_date`. Equal/reversed dates
and identical IDs raise `ValueError` before provider calls. A missing match is
unknown, never proof of absence. Embedding errors propagate to the caller's
existing BM25 fallback. This helper does not replace the existing API wiring:
`/compare` already validates dates and uses storage's independently ranked,
balanced context. No frontend, route, storage or wire-contract changes are needed.

Storage already builds a replacement BM25 index before upload commit, embeds new
passages after commit, backfills missing vectors on demand, and detects uploads
from another worker on subsequent queries. Restart rebuilds from exact saved
passages and reuses persisted vectors. Failed embeddings retain BM25 availability.

## Real earlier/newer pair

`examples/` contains verbatim bulletin-header, summary and watch/warning excerpts
from two public NOAA/NWS National Hurricane Center reports about Kristy:

- [Advisory 5, October 22, 2024](https://www.nhc.noaa.gov/archive/2024/ep12/ep122024.public.005.shtml): maximum sustained winds 75 MPH; minimum central pressure 988 MB.
- [Advisory 24, October 27, 2024](https://www.nhc.noaa.gov/archive/2024/ep12/ep122024.public.024.shtml): maximum sustained winds 45 MPH; minimum central pressure 1003 MB.

Sources were checked against the publisher archive on October 22, 2026. These are
excerpts, not complete bulletins or paraphrases. `manifest.json` supplies upload
metadata and SHA-256 checksums. Dates are the bulletin's publication dates, not
upload dates. TXT passages use `page: null`. Ingest only the older file initially;
keep the newer file outside the index until its explicit upload. Ask:
“What changed in maximum sustained winds and minimum central pressure?”
The supported change is 75 to 45 MPH and 988 to 1003 MB across those dated reports.
These excerpts alone do not establish the cyclone's intervening peak intensity.

## Focused verification

Run only the retrieval tests from the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -c backend/pytest.ini backend/tests/test_retrieval.py
```

The real-pair check ingests these files, publishes the older document, primes a
second worker's index, uploads the held-out newer document, and verifies fresh
retrieval and restart with canonical metadata/IDs. It checks both BM25 and hybrid,
strict date order, version ordering and future-value exclusion. Gemini embeddings
are deterministic mocked responses; this verifies filtering, ranking plumbing and
index/cache lifecycle, not live Gemini relevance or answer generation.
