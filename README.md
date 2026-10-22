# Folio

A four-person hackathon project for catching up on a developing story using dated
reports, cited answers, and evidence from both versions of a report comparison.

**Foundation only:** Next.js App Router lives in `web/`, FastAPI in `backend/`.
Health works; feature endpoints are typed 501 stubs. There is no upload storage,
text extraction, BM25 index, or feature UI yet. A backend-only Gemini client and
live smoke command are available; feature routes still return 501.

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
Storage variables are reserved for the implementation and use paths relative to
`backend/`. Keep SQLite, uploaded files, and the BM25 index under `backend/data/`.
No runtime files are created by this scaffold.

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
