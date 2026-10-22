# Folio live BM25 evaluation

Run: 2026-10-22T06:45:04.051838+00:00 (UTC). Commit: `2d53150cd8c8b404023c930500581a25917bcd26`.

Primary cases: **6/10 PASS**. Requests include two additional initial controls.

Production FastAPI TestClient → real uploads/SQLite → BM25 → configured Gemini. No Jev, mocks, dependency overrides or saved answers. API latency excludes retrieval replay and grading.

Every run uses a new temporary dataset, rebuilds the index from that dataset at each phase, and removes its uploads/database afterward. The normal application dataset is never reset or used.

Fresh empty dataset: True. Temporary dataset removed: True.

Semantic correctness and claim support are model-graded (same approved model in a separate call), not human-certified. Code separately checks schemas, status, uncached BM25, selected IDs, actual retrieved context, exact quotes and canonical stored metadata. Failed/unavailable grading cannot pass. All case criteria are mandatory. Gold quote retrieval coverage is diagnostic; other supporting passages may be valid.

Configuration: `{"id": "gemini-3.8-flash", "max_output_tokens": 8192, "timeout_seconds": 30.0}`.
Separate judge configuration: `{"id": "gemini-3.8-flash", "max_output_tokens": 8192, "timeout_seconds": 120}`.

| Case | Role | Phase | Result | HTTP | API ms | Server ms |
| --- | --- | --- | --- | ---: | ---: | ---: |
| FOLIO-01 | primary | before_upload | PASS | 200 | 12097 | 12092 |
| FOLIO-02 | primary | before_upload | PASS | 200 | 8821 | 8816 |
| FOLIO-03 | primary | before_upload | PASS | 200 | 7936 | 7929 |
| FOLIO-04 | primary | before_upload | PASS | 200 | 12256 | 12246 |
| FOLIO-05 | primary | before_upload | FAIL | 200 | 14309 | 14305 |
| FOLIO-06 | primary | before_upload | FAIL | 200 | 12598 | 12595 |
| FOLIO-07 | primary | before_upload | PASS | 200 | 7973 | 7970 |
| FOLIO-09 | control | before_upload | PASS | 200 | 13988 | 13983 |
| FOLIO-10 | control | before_upload | PASS | 200 | 16233 | 16228 |
| FOLIO-08 | primary | after_upload | PASS | 200 | 4895 | 4892 |
| FOLIO-09 | primary | after_upload | FAIL | 504 | 30865 | — |
| FOLIO-10 | primary | after_upload | FAIL | 504 | 31832 | — |

## Phase isolation

- {"stage": "before_upload", "manifest_ids": ["articles-2026", "committee-report-261", "sara-duterte-answer-2026", "sc-press-briefer-2026-08-05"], "passage_count": 193, "isolation": "PASS"}
- {"stage": "after_upload", "manifest_ids": ["articles-2026", "committee-report-261", "sara-duterte-answer-2026", "sc-press-briefer-2026-08-05", "house-press-10322-2026-10-13"], "passage_count": 194, "isolation": "PASS"}

## Failures and blockers

- FOLIO-05 (primary): criteria[3]: The actual response fails to cite committee page 3 and Answer page 13.
- FOLIO-06 (primary): support[3]: The citation quotes omit the sentence stating the SC dismissed the petition, failing to fully support the assertion of dismissal.
- FOLIO-09 (primary): HTTP 504: {'code': 'generation_timeout', 'message': 'The model request timed out.'}
- FOLIO-10 (primary): HTTP 504: {'code': 'generation_timeout', 'message': 'The model request timed out.'}

## Evidence and reproducibility

Full requests, responses, retrieved passages, gold coverage and per-criterion/support reasons: [fix-02.json](fix-02.json).
Input SHA-256: `917152e14aa58d949095ae5d4bc7863776c266f96d9752030c36ea1e6992bb4b`. Runtime: `3.13.9`.

Run from repository root: `python eval/run_eval.py` (install `backend/requirements-dev.txt`; backend/.env supplies the approved model). Exit 0 requires every primary and control to pass; otherwise exit 1. A rerun replaces this report and its receipt.

Scope: local supplied TXT only. Publisher originals, OCR/transcription fidelity and real-world allegations remain unverified. October text is a demo-authored paraphrase. No source websites are fetched.

Windows Git CRLF checkouts are uploaded as LF only when that conversion exactly matches the manifest SHA-256. The receipt records checkout and upload hashes. Corpus files are unchanged.
