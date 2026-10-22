# Folio

A four-person hackathon project for catching up on a developing story using dated
reports, cited answers, and evidence from both versions of a report comparison.

**Foundation only:** Next.js App Router lives in `web/`, FastAPI in `backend/`.
Health works; feature endpoints are typed 501 stubs. There is no upload storage,
text extraction, BM25 index, model call, or feature UI yet.

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

Backend secrets belong only in `backend/.env`. W1 must confirm the approved Gemini
Flash model ID with the team's key before generation work; setup needs no key.
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
