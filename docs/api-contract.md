# Folio API contract v1

Status: agreed foundation for W1–W4. Base URL: `http://localhost:8000`.
No `/api` prefix, authentication, pagination, streaming, or asynchronous jobs in v1.
JSON uses snake_case and UTF-8. Only upload uses `multipart/form-data`.

W1 owns this contract and `backend/app/contracts.py`; running FastAPI publishes
those schemas at `/openapi.json` and `/docs`. This document defines semantics that
schemas alone cannot enforce. Coordinate changes with W2–W4 before editing.
Unknown JSON request fields are rejected. Clients must use the shapes below.

**Current implementation:** health, document upload/listing, passage lookup, and
`/ask` work with local SQLite/files, W2 PDF/TXT extraction and selection-scoped
BM25 with backend-configured Gemini Embedding 2 hybrid ranking, and the configured
Gemini Flash client. Upload builds a replacement index
before committing; retrieval rebuilds from saved passages after restart. Answers
validate citation IDs and exact quotes against supplied passages and use stored
metadata. Unsupported questions return `insufficient_evidence`; invalid model
output returns 502. Retrieved rows are checked against canonical storage and
selected document membership before being sent to the provider. Generation uses
JSON output mode. Billing/quota, credential/access and rate-limit rejections
return safe, actionable 502 messages; timeouts return 504. There is no mock or
saved-answer fallback. Valid `/compare` requests still return 501. FastAPI performs
request shape validation (422).

## Operations

| Method and path | Request | Success | Purpose |
| --- | --- | --- | --- |
| `GET /health` | None | 200 `Health` | Check backend process |
| `GET /documents` | None | 200 `DocumentList` | List successfully uploaded reports |
| `POST /documents` | Multipart upload | 201 `Document` | Upload text-based PDF/TXT and metadata |
| `POST /ask` | `AskRequest` JSON | 200 `AskResponse` | Retrieve selected evidence and answer |
| `POST /compare` | `CompareRequest` JSON | 200 `CompareResponse` | Compare explicitly selected versions |
| `GET /passages/{id}` | Passage ID in path | 200 `Passage` | Fetch exact stored supporting text |

## Shared identifiers and evidence

| Field | Type | Meaning |
| --- | --- | --- |
| `doc_id` | string, 1–128 characters | Backend-assigned opaque immutable document-version ID. Never filename/title. Re-upload is a new version/ID; no v1 deduplication. |
| `passage_id` | string, 1–128 characters | Backend-assigned globally unique immutable passage ID, bound to exactly one document and stored text. Rebuilding BM25 preserves these IDs; never invent or reuse them for different text. |
| `report_date` | `YYYY-MM-DD` string | Required publication/report date supplied on upload, not upload time. Never inferred from filename or current time. |
| `source_url` | absolute HTTP(S) URL or null | Optional original publisher link supplied by user. Metadata only; never crawled or fetched. Omit multipart field when unknown. JSON responses always include the key, using null if unknown. |
| `page` | positive integer or null | 1-based physical PDF page, not printed page label. Null for TXT. Split at PDF page boundaries so each passage has one page. |
| `uploaded_at` | RFC 3339 UTC datetime | Upload completion time, separate from report date. |
| `citations` | array of `Citation` | Exact passage references attached to a specific answer claim, not bare model-provided URLs. |

Every non-optional response key shown below is present; nullable keys remain
present as null. `Document`, `Passage`, and `Citation` carry the same stored title,
report date, and source URL for a given `doc_id`. `filename` is a display basename,
never a local filesystem path. No internal paths or secrets are exposed.

A `Citation` object:

```json
{
  "passage_id": "pas_older_001",
  "doc_id": "doc_older",
  "title": "River response — first report",
  "report_date": "2026-10-20",
  "source_url": "https://example.org/reports/river-2026-10-20",
  "page": 2,
  "quote": "Ten shelters are open in the northern district."
}
```

`quote` is a nonempty exact contiguous substring of the referenced passage's
stored `text`. If generated wording matches except for whitespace (for example,
flattened OCR line breaks), restore the exact stored substring before returning
the citation. Changes to words or punctuation are rejected. IDs must resolve
through `GET /passages/{id}`. W1 validates
citations against the exact retrieved passages supplied to the model, including
selected document membership and metadata; reject invalid generated evidence
rather than returning invented IDs. W4 checks actual claim support. Citation
existence alone does not establish that a claim is true.

## GET /health

No request body or query. 200:

```json
{"status": "ok"}
```

Process liveness only; no model, index, database, or internet readiness claim.

## GET /documents

No query parameters. Return all ready documents, sorted by `report_date` ascending,
then `doc_id` ascending for ties. Empty corpus returns `{"documents":[]}`.
200 `DocumentList`:

```json
{
  "documents": [
    {
      "doc_id": "doc_older",
      "title": "River response — first report",
      "filename": "river-2026-10-20.pdf",
      "media_type": "application/pdf",
      "report_date": "2026-10-20",
      "source_url": "https://example.org/reports/river-2026-10-20",
      "uploaded_at": "2026-10-22T03:05:00Z",
      "passage_count": 4,
      "status": "ready"
    }
  ]
}
```

`Document` is the object inside `documents`. Only `ready` is supported in v1;
`passage_count` is positive. Failed/incomplete uploads never appear in this list.

## POST /documents

Synchronous multipart request. Exactly one file per request:

| Form field | Required | Shape |
| --- | --- | --- |
| `file` | yes | Nonempty text-based `.pdf` (`application/pdf`) or UTF-8 `.txt` (`text/plain`), at most 10 MiB (10,485,760 file bytes) |
| `title` | yes | Nonblank string, 1–200 characters |
| `report_date` | yes | ISO calendar date, `YYYY-MM-DD` |
| `source_url` | no | Absolute HTTP(S) publisher URL; omit when unknown |

Title and source URL are the v1 metadata fields. Filename/media type come from the
file; arbitrary metadata dictionaries are outside v1. Do not accept archives,
remote URLs as uploads, image-only/scanned PDFs, password-protected PDFs, or OCR.
Check content as well as declared extension/MIME. Reject empty or whitespace-only
extracted text. Validate before publishing a document as ready.

```sh
curl -X POST http://localhost:8000/documents \
  -F 'file=@samples/river-2026-10-20.pdf;type=application/pdf' \
  -F 'title=River response — first report' \
  -F 'report_date=2026-10-20' \
  -F 'source_url=https://example.org/reports/river-2026-10-20'
```

The filename above is illustrative; W4 supplies real public samples.
201 body is a `Document` (same fields as the listing entry, without a wrapper).
Success means the original file, document record, passages, and BM25 availability
are ready together. No background job or polling contract. Re-upload creates a
new `doc_id`; existing citations keep resolving to the original stored text.

## GET /passages/{id}

`id` is the exact `passage_id` from a citation. 200 `Passage`:

```json
{
  "passage_id": "pas_older_001",
  "doc_id": "doc_older",
  "title": "River response — first report",
  "report_date": "2026-10-20",
  "source_url": "https://example.org/reports/river-2026-10-20",
  "page": 2,
  "text": "Ten shelters are open in the northern district."
}
```

Return the complete exact stored passage, not a regenerated summary, retrieval
snippet, or normalized quote. TXT uses `page: null`; missing source uses
`source_url: null`. Unknown ID is 404. The publisher source link is available;
a local original-file download route is not defined in v1.

## POST /ask

`AskRequest`:

```json
{
  "question": "How many shelters were reported open?",
  "doc_ids": ["doc_older"]
}
```

`question` is nonblank, 1–2000 characters. `doc_ids` is required, 1–5 distinct
existing ready IDs. There is no implicit “all documents” selection. Retrieve only
within this selection; never leak held-out or newer evidence into earlier answers.
The request has no retrieval-mode field. Backend `FOLIO_RETRIEVAL_MODE` selects
`hybrid` (default) or `bm25`, with automatic BM25 fallback on embedding failure.
Both use a small bounded context chosen by W1/W2 internally.

200 `AskResponse` (all fields required):

```json
{
  "question": "How many shelters were reported open?",
  "doc_ids": ["doc_older"],
  "status": "answered",
  "answer": "The October 20 report states that ten shelters were open in the northern district.",
  "claims": [
    {
      "text": "The October 20 report states that ten shelters were open in the northern district.",
      "citations": [
        {
          "passage_id": "pas_older_001",
          "doc_id": "doc_older",
          "title": "River response — first report",
          "report_date": "2026-10-20",
          "source_url": "https://example.org/reports/river-2026-10-20",
          "page": 2,
          "quote": "Ten shelters are open in the northern district."
        }
      ]
    }
  ],
  "meta": {"retrieval_mode": "bm25", "elapsed_ms": 850, "cached": false}
}
```

`answer` is display prose; `claims` provides the claim-to-citation mapping. Each
claim requires at least one citation and every factual assertion in `answer`
must be covered by a claim. The server echoes the question and selected IDs.
Return `status: "insufficient_evidence"`, an explanatory `answer`, and
`claims: []` when there is no supported answer; never invent evidence. This is a
normal 200 result, distinct from provider failure. Unknown selected ID is 404.

Shared `meta`: `retrieval_mode` remains `"bm25"` for v1 wire compatibility, including
when hybrid ranking is enabled; actual mode/fallback are recorded in backend logs.
`elapsed_ms` is a nonnegative
integer of server wall-clock time for the request; `cached` is a boolean. Initially
it may always be false. Future cache keys include selected versions, question,
corpus/index revision, model ID, prompt version, and retrieval mode.

## POST /compare

`CompareRequest`:

```json
{
  "older_doc_id": "doc_older",
  "newer_doc_id": "doc_newer",
  "question": "What changed in the reported shelter count?"
}
```

Both IDs are required, distinct, ready, and explicitly selected. Enforce
`older.report_date < newer.report_date`; equal/reversed dates are 422, and unknown
IDs are 404. Never auto-select or silently swap versions. Optional `question`
defaults to `"What changed between these reports?"`; when supplied it is nonblank,
1–2000 characters. Retrieval must obtain evidence independently from both IDs;
no third document may support a comparison claim.

200 `CompareResponse` (all fields required):

```json
{
  "older_doc_id": "doc_older",
  "newer_doc_id": "doc_newer",
  "question": "What changed in the reported shelter count?",
  "status": "compared",
  "summary": "The reported number of open shelters increased from ten to twelve.",
  "changes": [
    {
      "kind": "updated",
      "summary": "The reported number increased by two in the northern district.",
      "before": "Ten shelters were reported open on October 20.",
      "after": "Twelve shelters were reported open on October 21.",
      "older_citations": [
        {
          "passage_id": "pas_older_001",
          "doc_id": "doc_older",
          "title": "River response — first report",
          "report_date": "2026-10-20",
          "source_url": "https://example.org/reports/river-2026-10-20",
          "page": 2,
          "quote": "Ten shelters are open in the northern district."
        }
      ],
      "newer_citations": [
        {
          "passage_id": "pas_newer_001",
          "doc_id": "doc_newer",
          "title": "River response — update",
          "report_date": "2026-10-21",
          "source_url": "https://example.org/reports/river-2026-10-21",
          "page": 1,
          "quote": "Twelve shelters are open in the northern district."
        }
      ]
    }
  ],
  "meta": {"retrieval_mode": "bm25", "elapsed_ms": 1100, "cached": false}
}
```

`changes` items always contain `kind`, `summary`, `before`, `after`,
`older_citations`, and `newer_citations`. Each citation uses the shared shape.

| `kind` | Meaning | Required evidence |
| --- | --- | --- |
| `updated` | Supported before/after change in the same scope | Nonempty `before` and `after`; at least one older and one newer citation |
| `unresolved` | Evidence on both sides differs but cannot establish a comparable change | Nonempty `before` and `after`; at least one citation from each version; explain uncertainty |
| `added` | Information newly reported in the newer document; no factual earlier state asserted | `before: null`, `older_citations: []`, nonempty `after` and newer citations |

**Any before/after assertion, including in summaries, requires passage citations
from both selected document versions.** Older citations must have
`doc_id == older_doc_id`; newer citations must have `doc_id == newer_doc_id`.
An `added` item must not assert absence, zero, an increase, a decrease, or a prior
state. A missing retrieved passage does not prove absence from an older report.
“Removed” is not a supported v1 kind because silence is not evidence of removal.
Compare dates, location, units, and scope before claiming a change; a later value
is not automatically a contradiction. Summary assertions must be covered by the
cited `changes`; no uncited numeric deltas or conclusions.

If both reports support an answer but no changes, return `status: "compared"`,
`changes: []`, and a non-factual explanatory summary such as “No supported changes
identified.” If retrieval cannot support a comparison, return 200 with
`status: "insufficient_evidence"`, `changes: []`, and explain the limitation.
Do not present absence of evidence as “nothing changed.”

## Errors and implementation obligations

Non-validation errors use FastAPI's `detail` envelope:

```json
{
  "detail": {
    "code": "document_not_found",
    "message": "A selected document was not found."
  }
}
```

| HTTP | `detail.code` | When |
| --- | --- | --- |
| 404 | `document_not_found` / `passage_not_found` | Unknown selected ID or passage |
| 413 | `upload_too_large` | File exceeds 10 MiB |
| 415 | `unsupported_file_type` | Unsupported extension, MIME, or actual content |
| 422 | `invalid_document` | Empty, unreadable, encrypted, scanned, or invalid UTF-8 content |
| 422 | `invalid_selection` | Dates reversed/equal or selection not ready |
| 500 | `storage_failed` | Local filesystem or SQLite operation failed |
| 502 | `generation_failed` | Provider failed or generated citations cannot be validated |
| 504 | `generation_timeout` | Bounded provider call exceeded deadline |
| 501 | `not_implemented` | Foundation stub only; removed per implemented operation |

FastAPI request validation uses its standard `{"detail":[{"loc":[...],"msg":"...","type":"..."}]}`
422 shape (additional diagnostic keys may appear), including missing fields,
invalid dates/URLs, unknown JSON keys, blank questions, duplicate ask IDs, and
identical comparison IDs. UI handles both forms of `detail`. No stack traces,
provider secrets, or internal paths in messages. Provider failure never appears
as an uncited successful answer or a disguised saved example.

Feature owners must enforce semantic rules not yet enforced by the scaffold:
file limits/content checks and atomic upload publication (W1/W2); immutable
stored IDs/text and selection-aware BM25 (W1/W2); strict comparison date ordering,
claim support, citation side/membership/quotes, and insufficient-evidence states
(W1 with W4); public sample provenance and expected passage support (W4).
Treat document content as evidence, never as instructions to the model.
