# W2 handoff

This first implementation supports local UTF-8 TXT files only. It uses the
existing shared `Passage` model and adds no dependencies. PDF parsing is not
implemented. The supplied local sample is already a transcript; no OCR is run.

```python
from app.ingestion import extract_passages
from app.retrieval import BM25Index

passages = extract_passages(
    doc_id=assigned_document_id,
    path=local_file,
    title=upload_title,
    report_date=upload_report_date,
    source_url=upload_source_url,  # None if unknown
)
# W1 persists these exact Passage models along with the original file.
index = BM25Index(stored_passages)
evidence = index.retrieve(question, doc_ids=selected_ids, top_k=5)
# For comparison, retrieve independently for each selected version:
older = index.retrieve(question, doc_ids=[older_doc_id], top_k=5)
newer = index.retrieve(question, doc_ids=[newer_doc_id], top_k=5)
```

W1 owns MIME validation, metadata validation at upload, ready-document checks,
comparison date ordering, atomic persistence/publication and HTTP error mapping.
`ExtractionError.code` uses the shared `invalid_document`, `upload_too_large`,
and `unsupported_file_type` values. File I/O errors propagate to W1; do not expose
their internal paths in HTTP errors. Rebuild `BM25Index` from stored passages on
restart or upload and publish the replacement index with the ready document.
Unknown document selections return no matches here; W1 must return the contract's
404 before retrieval. No lexical match returns an empty list, with no fallback
to unrelated evidence. Generic comparison questions may need a more specific
topic to retrieve useful evidence; empty retrieval does not prove no change.

`extract_text_pages(doc_id, path)` returns immutable `ExtractedPage` records with
`doc_id`, `page`, and exact `text`. It recognizes the sample's explicit
`---------- SOURCE PDF PAGE N / TOTAL ----------` markers, preserving source
page labels and a separate unpaged preamble. These labels are transcript claims,
not validated physical PDF pages. Ordinary TXT is a single unpaged record.

The shared contract explicitly requires TXT `Passage.page` to be null. Therefore
`extract_passages` keeps page markers in the text and chunks within their
boundaries, but sets the wire page field to null. Do not silently reinterpret TXT
markers as physical PDF metadata. Changing that would require W1 coordination.
UTF-8 BOM is removed; all other text, including line endings, is preserved in
contiguous chunks (whitespace-only chunks are omitted). Default chunks are at
most 1,600 characters. No OCR correction or legal-content interpretation occurs.

Passage IDs deterministically hash the assigned document ID, passage position,
exact text and metadata. Re-upload must use a new assigned document ID. Retrieval
always preserves persisted IDs/text; it neither regenerates nor rechunks them.
The index snapshots passages and returns copies to protect it from caller edits.
BM25 uses Unicode word tokens, case folding, k1=1.5, b=0.75, positive IDF and
statistics computed only within the explicit selection. No embeddings are used.

Run from `backend/`: `python -m pytest -q`. Tests include an optional local-sample
check; `.local` data is never required in CI or committed. Test metadata dates
are synthetic and do not assert the sample's publication date.
