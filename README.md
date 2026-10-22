# Folio

A four-person hackathon project for catching up on a developing story using dated
reports, cited answers, and evidence from both versions of a report comparison.

Next.js App Router lives in `web/`, FastAPI in `backend/`. Health, document upload,
document listing, and passage lookup work with local SQLite and original files.
W2's TXT/PDF extraction and selection-scoped BM25 power `/ask`, which uses the
configured Gemini Flash model and validates passage IDs and exact citation quotes.
Unsupported questions return an explicit insufficient-evidence response.
`/compare` remains a typed 501 stub. A backend-only live model smoke command is available.

Read [the sprint plan](docs/sprint-plan.md) and [API contract v1](docs/api-contract.md)
before starting. The sprint plan was promoted from `.local/` and updated to Next.js.

## Local setup

Use Node.js 20.9+ and Python 3.12+. Run from the repo root unless noted.

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
cp .env.example backend/.env
```

Create `web/.env.local` with only:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Backend secrets belong only in `backend/.env`. The Gemini client reads
`GEMINI_API_KEY` (or `GOOGLE_API_KEY` as a fallback) from the backend environment.
Shell variables override `backend/.env`. Never copy keys to `web/` or use a
`NEXT_PUBLIC_` prefix for them. Setup and health checks need no key.
Storage variables use paths relative to
`backend/`. Keep SQLite, uploaded files, and the BM25 index under `backend/data/`.
SQLite tables and the upload directory are created on the first storage request.

Start two terminals:

```sh
# Terminal 1, repo root
npm run dev
```

```sh
# Terminal 2, repo root, virtual environment activated
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend: <http://localhost:3000>. Backend health: <http://localhost:8000/health>.
Interactive schemas: <http://localhost:8000/docs>; machine-readable:
<http://localhost:8000/openapi.json>. Default CORS allows `http://localhost:3000`;
set `FOLIO_CORS_ORIGINS` to comma-separated origins if using other local ports.

## Verify

To make one genuine, uncached Gemini request, activate the virtual environment,
set a backend key and `GEMINI_MODEL`, then run:

```sh
cd backend
python -m app.generation.smoke
```

The command prints and records the UTC test time, configured model ID, returned
`modelVersion`, response text and elapsed milliseconds in the ignored local file
`backend/data/model-smoke.json`. It exits nonzero and records a safe error on
failure. Only a successful record confirms a working model ID. The default
`gemini-3.8-flash` is an unconfirmed candidate, not a claim of availability.
`GEMINI_TIMEOUT_SECONDS` defaults to 30 (maximum 120); `GEMINI_MAX_OUTPUT_TOKENS`
defaults to 1024 (maximum 8192). Calls have network timeouts and no automatic retries.

Failed smoke records include a backend-only `error.reason` and, when Google
returns an HTTP error, `error.provider_http_status`. `network_error` means no
usable provider response; `configuration` means local settings are invalid;
`output_token_limit` means the reply was truncated (try a larger output limit).
HTTP 400 indicates a rejected request (including possible key/configuration
issues), 401/403 credential or access problems, 404 an unavailable model/endpoint,
and 429 quota/rate limiting. Provider response bodies and headers are never recorded.

Backend routes can use `Depends(get_model_client)` from
`app.generation.client`, then `client.generate(prompt)` in a synchronous route (FastAPI runs it in its thread pool). The client follows
the [Gemini REST API](https://ai.google.dev/api/generate-content) and sends the key
in a header to Google's fixed HTTPS endpoint. Provider errors are mapped to the
contract's safe 502/504 envelopes by FastAPI. No public model test route or settings
endpoint is added. `GET /health` remains process liveness only.

Setup attempt on 2026-10-22 at 04:15:53 UTC: a genuine request using the available
backend key and candidate `gemini-2.5-flash` failed in **23 ms** because this
workspace could not resolve Google's hostname. No provider response or confirmed
working model ID was obtained. The local smoke record has `success: false`;
rerun the command with internet access to complete Gate A.

Updated check on 2026-10-22 at 04:23:47 UTC: Google's authenticated model listing
returned HTTP 200 and included `gemini-3.8-flash`. The client and environment
template now default to that model, following Google's
[recommendation for new projects](https://ai.google.dev/gemini-api/docs/deprecations).
A genuine generation request returned HTTP **402** in **461 ms**. Network access
and model discovery work; generation and a working model version remain
unconfirmed until the API connection's payment/access issue is resolved.

```sh
npm run lint
npm run typecheck
npm run build
# With the Python virtual environment activated:
cd backend
python -m pytest
```

`npm run start` serves a built frontend. Root npm commands delegate to the `web`
workspace; use the single root `package-lock.json` and run `npm ci` at the root.

## Ownership

| Lane | Owner fills in name in sprint plan | Files |
| --- | --- | --- |
| W1 | Backend, AI, integration | API, contracts, generation, storage, root config/docs |
| W2 | Ingestion and retrieval | `backend/app/ingestion/`, `backend/app/retrieval/`, lane tests |
| W3 | Frontend and experience | `web/` |
| W4 | Corpus, evaluation, demo | `samples/`, `fixtures/`, `evaluation/`, demo/evaluation docs |

Exact file boundaries, dependency handoffs, and checkpoints are in the sprint plan.
Claim a lane, work on its branch, test and commit small changes. W1 integrates;
coordinate before changing another lane or the shared contract. Frontend dependency
changes require W1 coordination for the root lockfile.

## API v1

Upload a public report using the backend's synchronous endpoint:

```sh
curl -X POST http://localhost:8000/documents \
  -F 'file=@report.txt;type=text/plain' \
  -F 'title=Example report' \
  -F 'report_date=2026-10-20' \
  -F 'source_url=https://example.org/report'
curl http://localhost:8000/documents
```

Omit `source_url` when unknown. Uploads accept UTF-8 TXT or text-based PDF with
matching extension/MIME, up to 10 MiB. `FOLIO_MAX_UPLOAD_BYTES` can lower that cap.
Empty, invalid UTF-8, encrypted, and textless documents are rejected. Files use
generated local names; document metadata retains only the display basename.
Document/passages are saved in one SQLite transaction after extraction succeeds;
failed uploads remove their original file and do not appear in the document list.
Passage IDs and exact text survive restarts and repeat uploads.

W1's `app.storage.ingestion` adapter calls W2's `ingest_document`; W1 owns
persistence. Upload builds a replacement W2 `BM25Index` before committing records,
so indexing failures also roll back the upload. The in-memory index rebuilds from
stored passages on the first retrieval after restart and detects new uploads from
other workers. IDs and text remain unchanged.

`POST /ask` accepts `{"question":"How many shelters opened?","doc_ids":["doc_ID"]}`.
It ranks each selected document independently and interleaves up to six passages,
sends evidence to the configured model, and builds answer prose from validated
cited claims.
Citation metadata comes from storage. Invalid IDs, quotes, or output produce 502;
provider timeouts produce 504. Empty retrieval or a model finding of insufficient
evidence returns 200 with `status: "insufficient_evidence"` and no claims.

| Operation | Purpose |
| --- | --- |
| `GET /health` | Check backend |
| `GET /documents` | List uploaded documents |
| `POST /documents` | Upload PDF/TXT with report date and metadata |
| `POST /ask` | Retrieve evidence and generate answer |
| `POST /compare` | Compare explicitly selected older/newer documents |
| `GET /passages/{id}` | Return exact supporting passage |

The [contract](docs/api-contract.md) defines identifiers, dates, metadata, all
request/response shapes, and citation rules. Every asserted before/after change
requires supporting passages from **both** selected report versions.

Use local SQLite/files, BM25, and the approved model API. No Supabase,
authentication, crawling, OCR, or unnecessary infrastructure. Use public sample
reports and keep keys out of Git and browser code.
