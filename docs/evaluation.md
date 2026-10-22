# W4 corpus integration check

`origin/w4-2`, `origin/w2`, and the completed W1 answer integration are merged
into `integration-branch`. The local corpus is ready
for W2 ingestion. This is an offline validation of local files and metadata,
not independent verification of publisher originals or real-world claims.

Run from the repository root with backend development dependencies plus
`backend/app/ingestion/requirements.txt` installed:

```sh
python -m pytest -q -c backend/pytest.ini backend/tests evaluation/test_corpus.py
```

## Corpus handoff

`corpus/manifest.json` is the authoritative inventory. Its `file` paths resolve
relative to `corpus/`; `eval/questions.json` paths resolve relative to repository
root. Keep the existing `commitee-report-261.txt` spelling: the manifest and all
evaluation references point to that exact tracked filename.

| Manifest ID | Bytes | W2 passages | Embedded page markers | Stage |
| --- | ---: | ---: | ---: | --- |
| articles-2026 | 67,586 | 30 | 23/23 | Initial |
| committee-report-261 | 217,983 | 106 | 93/93 | Initial |
| sara-duterte-answer-2026 | 134,060 | 56 | 51/51 | Initial |
| sc-press-briefer-2026-08-05 | 3,056 | 1 | None | Initial |
| house-press-10322-2026-10-13 | 2,774 | 1 | None | Held out |

All five files are nonempty UTF-8 TXT, below the 10 MiB limit. Each manifest entry
includes title, report date, source URL, held-out flag, text provenance, MIME,
encoding, byte count and SHA-256. All 194 extracted passages retain exact local
text and metadata, deterministic IDs, and `page: null`. Embedded transcript
markers are labels, not verified physical PDF pages. W2 recognizes all three Articles, committee and defense marker formats, so no
chunk crosses a labeled source-page boundary. Do not expose transcript labels
as API PDF page numbers.

Manifest `doc_id` values are evaluation keys. On upload, map each key to the
backend-assigned document ID returned by `POST /documents`. Do not send manifest
keys as API selections without that mapping. `status: ready` in this inventory
means the local input is ingestible; it is not proof of a database upload.
Pass only title, report_date, optional source_url and the file to the upload API;
the remaining fields describe the local corpus. W2's ingestion metadata model
accepts the full manifest entry and ignores the extra inventory fields.

Upload the four `heldout: false` documents first. Keep the October file out of
initial ingestion/indexing. Upload it only for the after-update stage. Validation
confirms the held-out document cannot appear in the initial index and cannot
change retrieval results for an unchanged initial selection.

## Checks and limits

The repeatable checks cover inventory completeness, unique IDs/paths, valid dates
and URL syntax, hashes, contiguous page-marker sequences, ten evaluation cases,
exact local quotes within their cited line ranges, selection/date rules,
W2 extraction/BM25, and all five files through FastAPI upload and exact passage
lookup. The upload test injects the W2 adapter using the existing ingestion
dependency; it does not change application route wiring or call the model.

Original scanned PDFs and the signed defense filing are not present. OCR and
AI-assisted transcription fidelity are unverified. The committee header says
261 while page 1 OCR says 201; supplied report date May 5 differs from a May 4
date inside the document. The Articles' May 11 date is supplied metadata.
These values are preserved with explicit provenance notes, not silently corrected.
The SC embedded ID is an alias of its manifest ID. The held-out update is a
paraphrased demo summary, not a verbatim official release. Its local text can be
quoted as local evidence but must not be presented as original publisher wording.
Full flags and attribution criteria remain in `eval/questions.json`.

URL syntax is validated; network reachability and original-source authenticity
are not certified. No crawling, OCR, or downloads are performed by these checks.

## W2 retrieval and citation integration

W1 now uses W2 ingestion in normal uploads and BM25 retrieval in `/ask`. Common
question/function words are excluded from keyword scoring. Each selected document
is ranked independently and W1 interleaves the results into at most six passages.
This prevents long reports from displacing the other selected document's evidence.
Passages retain exact local wording; filtering only changes search tokens.

All annotated supporting excerpts for W4's seven answerable question cases are
present in the context actually sent to the model. Tests upload the real corpus,
map manifest keys to API IDs, lose the process-local index, and resolve every
returned citation through `/passages/{id}` with matching metadata and exact quotes.
Separate checks validate full-text reconstruction, 500-word chunk limits,
transcript boundaries, stored-passage refresh, and index save/load without ID or
metadata changes. Existing tests reject invented, unselected or unretrieved IDs,
invalid quotes and uncited model output.

Generation is mocked in these checks. They validate evidence retrieval and API
citation integrity, not model answer quality or legal/source authenticity. The
comparison endpoint is still unimplemented; the two comparison cases remain for
that workstream. The insufficient-evidence API path is covered separately; keyword
matches alone cannot determine whether the evidence answers the question.

Changed chunk boundaries apply to new ingestion only. Rebuild indexes from saved
passages to preserve all already-published citation IDs and text.
