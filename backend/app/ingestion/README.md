# W2 ingestion and retrieval handoff

W2 exposes the requested callables using the shared `Passage` schema. Work stays
inside the W2 lane; W1 owns persistence, routes, ready-document validation and
atomic publication. No embeddings, OCR, crawling or database layer are added.

## Dependencies and setup

From the repository root, install into the backend environment:

```sh
python -m pip install -r backend/requirements-dev.txt -r backend/app/ingestion/requirements.txt
```

Use Python 3.13 with the current shared Pydantic pin. W1 dependency request:
include `-r app/ingestion/requirements.txt` in `backend/requirements.txt` during
integration. That W1-owned file has not been edited. W2 pins pypdf 6.21.2 and
rank-bm25 0.2.2 in its own directory.

## Callable API

Run with `backend/` on the Python import path:

```python
from app.ingestion import ingest_document
from app.retrieval import rebuild_index, retrieve

passages = ingest_document(local_file_path, {
    "doc_id": assigned_document_id,
    "title": upload_title,
    "report_date": upload_report_date,
    "source_url": upload_source_url,  # optional; defaults to None
})
# W1 persists the original file and exact Passage models, then publishes all
# ready passages as one replacement snapshot. Do this on restart as well.
rebuild_index(all_saved_ready_passages)
results = retrieve(question, document_ids=selected_ids, k=6, mode="bm25")
older = retrieve(question, [older_doc_id])
newer = retrieve(question, [newer_doc_id])
```

`metadata` accepts a mapping or a Pydantic model, including shared `Document`.
The assigned `doc_id`, title and report date are required. No report date or title
is guessed from the filename. Additional document fields are ignored. Results
are shared `Passage` objects with `doc_id`, `passage_id`, `page`, `text`, `title`,
`report_date`, and nullable `source_url`; use `model_dump(mode="json")` for JSON.
The prior `extract_passages(doc_id, path, title=..., report_date=...,
source_url=...)` remains as a wrapper; its old character limit is replaced by
word-based chunks. `BM25Index(passages).retrieve(...)` supports an isolated index
with the same new retrieval arguments (`document_ids`, `k`, `mode`).

Ingestion does not automatically index unpublished documents. Module-level
retrieval searches the last `rebuild_index` snapshot, initially empty. W1 must
serialize snapshot replacement with upload publication to avoid stale updates.
A failed rebuild keeps the previous snapshot. Unknown selected IDs produce no
matches here; W1 must validate existing ready IDs and return the shared 404.
W1 also validates MIME and comparison date ordering. `ExtractionError.code`
maps to the shared upload error codes; metadata raises Pydantic validation
errors. File I/O errors propagate; never expose their internal paths in HTTP.

## Text, pages and chunking

PDF extraction uses pypdf and 1-based physical page numbers. Blank pages are
skipped without renumbering subsequent pages. Encrypted, corrupt and wholly
textless PDFs are rejected. Mixed PDFs return their extractable text; images
are never OCR'd. Extraction does not guarantee complex table reading order.
TXT requires UTF-8 (optional BOM), and both formats have a 10 MiB file limit.
Extensions and recognizable content are checked; empty text is rejected.

Chunks target approximately 400 words, prefer blank-line paragraph boundaries
between 300 and 500 words, and split oversized paragraphs at word boundaries.
Short pages/final fragments can be below 300 words. No passage spans PDF pages
or explicit source-page markers in the local transcript. Text is kept as exact
contiguous slices of extracted text, including internal whitespace and line
endings; a UTF-8 BOM and whitespace-only chunks are omitted.

`extract_text_pages(doc_id, path)` exposes the local transcript's explicit
source-page labels internally. Per the shared contract, TXT `Passage.page` is
always null, with transcript markers retained in text. These labels are not
verified physical PDF pages. The original scanned PDF is not available locally;
PDF parsing is tested with generated, text-bearing PDF fixtures.

Passage IDs deterministically hash the document ID, position, text, page and
source metadata. Re-upload must receive a new document ID. Rebuilding retrieval
uses persisted IDs/text unchanged; do not re-extract documents with published
citations when changing chunking rules.

## Retrieval

Uses rank-bm25's `BM25Plus` with `delta=0`, k1=1.5 and b=0.75, so IDF remains
positive even for a one-passage selection. Unicode words are case-folded with
the same tokenizer for documents and queries. Nonmatching passages are excluded;
punctuation-only/no-match queries return an empty list. Only mode `bm25` is
accepted. Ties sort by passage ID, and returned models are defensive copies.

Tokenization happens on snapshot creation. Selection-specific rank-bm25 indexes
are cached for up to 32 selections per snapshot. Held-out/unselected reports
cannot affect scores. Comparison retrieves each selected side independently;
no matches mean insufficient lexical evidence, not proof that nothing changed.

## Verification

From `backend/`, run `python -X utf8 -m pytest -q`. UTF-8 mode avoids the existing
contract test's Windows default-encoding failure. Tests cover physical PDF pages,
corrupt/encrypted/textless files, UTF-8, exact text and metadata, paragraph and
word boundaries, stable IDs, rank-bm25 scores, filtering, snapshot rebuilds and
both requested callables. Optional real-document tests use the first transcript
in `.local`; no private corpus data is committed. Their report date is synthetic,
not a claim about the sample's actual publication date.

Verified locally: 32 backend tests pass. The real transcript produces 30 passages
(median 365 words, maximum 491; 24 in the 300–500 range). Short preamble/page
fragments account for the remaining six. The query `confidential funds liquidation`
returns six passages from the explicitly selected real document. No PDF source
of that real document was available; PDF checks use parser fixtures.

Implementation references: [pypdf extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
and [rank-bm25](https://github.com/dorianbrown/rank_bm25).
