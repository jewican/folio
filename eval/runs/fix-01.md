# Folio live BM25 evaluation

Run: 2026-10-22T06:37:21.658454+00:00 (UTC). Commit: `2d53150cd8c8b404023c930500581a25917bcd26`.

Primary cases: **9/10 PASS**. Requests include two additional initial controls.

Production FastAPI TestClient → real uploads/SQLite → BM25 → configured Gemini. No Jev, mocks, dependency overrides or saved answers. API latency excludes retrieval replay and grading.

Every run uses a new temporary dataset, rebuilds the index from that dataset at each phase, and removes its uploads/database afterward. The normal application dataset is never reset or used.

Fresh empty dataset: True. Temporary dataset removed: True.

Semantic correctness and claim support are model-graded (same approved model in a separate call), not human-certified. Code separately checks schemas, status, uncached BM25, selected IDs, actual retrieved context, exact quotes and canonical stored metadata. Failed/unavailable grading cannot pass. All case criteria are mandatory. Gold quote retrieval coverage is diagnostic; other supporting passages may be valid.

Configuration: `{"id": "gemini-3.8-flash", "max_output_tokens": 4096, "timeout_seconds": 30.0}`.
Separate judge configuration: `{"id": "gemini-3.8-flash", "max_output_tokens": 8192, "timeout_seconds": 120}`.

| Case | Role | Phase | Result | HTTP | API ms | Server ms |
| --- | --- | --- | --- | ---: | ---: | ---: |
| FOLIO-01 | primary | before_upload | PASS | 200 | 11890 | 11883 |
| FOLIO-02 | primary | before_upload | PASS | 200 | 7130 | 7114 |
| FOLIO-03 | primary | before_upload | PASS | 200 | 4909 | 4904 |
| FOLIO-04 | primary | before_upload | PASS | 200 | 10334 | 10330 |
| FOLIO-05 | primary | before_upload | PASS | 200 | 13477 | 13473 |
| FOLIO-06 | primary | before_upload | PASS | 200 | 12205 | 12202 |
| FOLIO-07 | primary | before_upload | PASS | 200 | 6553 | 6524 |
| FOLIO-09 | control | before_upload | PASS | 200 | 13831 | 13824 |
| FOLIO-10 | control | before_upload | PASS | 200 | 15208 | 15201 |
| FOLIO-08 | primary | after_upload | PASS | 200 | 6341 | 6338 |
| FOLIO-09 | primary | after_upload | PASS | 200 | 21804 | 21797 |
| FOLIO-10 | primary | after_upload | FAIL | 200 | 23217 | 23214 |

## Phase isolation

- {"stage": "before_upload", "manifest_ids": ["articles-2026", "committee-report-261", "sara-duterte-answer-2026", "sc-press-briefer-2026-08-05"], "passage_count": 193, "isolation": "PASS"}
- {"stage": "after_upload", "manifest_ids": ["articles-2026", "committee-report-261", "sara-duterte-answer-2026", "sc-press-briefer-2026-08-05", "house-press-10322-2026-10-13"], "passage_count": 194, "isolation": "PASS"}

## Failures and blockers

- A semantic judge request failed; affected cases cannot pass.
- FOLIO-10 (primary): Semantic judge unavailable: The model response was too long to complete. Try a narrower question.; {'reason': 'output_token_limit'}

## Evidence and reproducibility

Full requests, responses, retrieved passages, gold coverage and per-criterion/support reasons: [fix-01.json](fix-01.json).
Input SHA-256: `917152e14aa58d949095ae5d4bc7863776c266f96d9752030c36ea1e6992bb4b`. Runtime: `3.13.9`.

Run from repository root: `python eval/run_eval.py` (install `backend/requirements-dev.txt`; backend/.env supplies the approved model). Exit 0 requires every primary and control to pass; otherwise exit 1. A rerun replaces this report and its receipt.

Scope: local supplied TXT only. Publisher originals, OCR/transcription fidelity and real-world allegations remain unverified. October text is a demo-authored paraphrase. No source websites are fetched.

Windows Git CRLF checkouts are uploaded as LF only when that conversion exactly matches the manifest SHA-256. The receipt records checkout and upload hashes. Corpus files are unchanged.
