# Folio

**Catch up on a developing story. Understand what changed. Follow the evidence.**

Folio helps you make sense of a story across dated reports. Upload your sources,
get a concise briefing, ask follow-up questions, and compare earlier reporting
with newer updates. Generated claims link to the passages behind them, so you can
read the evidence in context.

| Slides | Business Plan | Demo Video |
| :---: | :---: | :---: |
| [View](https://drive.google.com/file/d/1OvrtAIxMQ_YCJIGa1Z0xb9IvXflOQp2F/view?usp=drive_link) | [View](https://drive.google.com/file/d/14vPPITAEuaf6VaYoBpopxnMhoU9mzAAj/view?usp=drive_link) | [Watch](https://drive.google.com/file/d/17Q3dbk6T3XcBNkhT6EgEn_o5A6-PK21O/view?usp=drive_link) |

## Features

- **Catch Me Up.** Get a briefing with key takeaways from your selected reports,
  organized by report date, with citations and unresolved questions.
- **What Changed.** Compare an older and a newer report to explore updated claims,
  newly reported information, and differences that remain unresolved. Before/after
  assertions include evidence from both reports.
- **Ask Folio.** Ask about a detail, date, or claim across up to five selected
  reports. Answers use only the sources you choose.
- **Inspect the evidence.** Open a citation to read the exact quote or the full
  stored passage with the quote highlighted. Check the document title, report
  date, PDF page when available, and optional publisher link. Copy quotes or move
  between citations without leaving the story.
- **Follow the reporting over time.** Browse a publication timeline and choose
  which reports to include in a briefing, answer, or comparison.
- **Build a lasting source collection.** Upload text-based PDFs or UTF-8 TXT files
  up to 10 MiB each, with a title, publication date, and optional source URL.
  Documents and passages remain available after a restart.

## From reports to context

1. **Add your sources.** Upload dated reports about one developing story.
2. **Open the story room.** Select reports from the timeline or source list.
3. **Get oriented.** Use **Catch Me Up** for the story so far, or **Ask Folio** for
   a specific question.
4. **Explore an update.** Upload a newer report and use **What Changed** to compare
   it with an earlier report.
5. **Check the source.** Open any citation to inspect the supporting passage.

For example, start with two reports on an unfolding event and ask what was known
at the time. Add a later report, compare it with an earlier one, and inspect the
passages supporting each reported change.

## Answers you can check

Folio checks citation IDs and exact quotes against the stored passages supplied
to the model. Source metadata comes from the uploaded document records. When the
selected evidence cannot support an answer or comparison, Folio explains what is
missing. Provider failures appear as errors.

These checks make answers traceable to your sources; they do not independently
verify the sources or establish that every cited claim is correct. Report dates
refer to publication dates and may differ from event dates.

## How it runs

Folio uses a **Next.js App Router** interface and a **FastAPI** backend. Original
files, extracted passages, and cached embeddings are stored locally using files
and **SQLite**. Retrieval combines **BM25** keyword search with **Gemini Embedding
2**, falling back to BM25 if embeddings are unavailable. **Gemini Flash** generates
structured answers and comparisons from the retrieved passages.

The app runs locally; generation and semantic retrieval require internet access
and send selected text to the configured model API. Source URLs are metadata:
Folio works with uploaded files. Scanned or encrypted PDFs are unsupported.

## Quick start

Requires Node.js 20.9+ and Python 3.12+. Run from the repo root.

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
cp .env.example backend/.env      # add GEMINI_API_KEY here
```

Create `web/.env.local` containing only:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Start two terminals:

```sh
# Terminal 1, repo root
npm run dev
```

```sh
# Terminal 2, repo root, virtualenv activated
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| What | Where |
| --- | --- |
| App | <http://localhost:3000> |
| Backend health | <http://localhost:8000/health> |
| Interactive API docs | <http://localhost:8000/docs> |
| OpenAPI schema | <http://localhost:8000/openapi.json> |

> **Keys stay on the backend.** Put secrets only in `backend/.env`. Never copy them to `web/` or use a `NEXT_PUBLIC_` prefix. Setup and health checks need no key.

For keyword-only retrieval, set `FOLIO_RETRIEVAL_MODE=bm25` in `backend/.env`.
Other model, storage, timeout, and upload settings are listed in
[`.env.example`](.env.example). Storage paths are relative to `backend/`.

## Development

The [API contract](docs/api-contract.md) documents upload, questions, comparisons,
and passage lookup. The [sprint plan](docs/sprint-plan.md) covers file ownership
and team coordination. See [corpus notes](docs/evaluation.md) for sample source
provenance and [live evaluation instructions](eval/README.md) for answer-quality
checks.

<details>
<summary>Developer verification and live workflow results</summary>

The full workflow browser check uses the production UI, real FastAPI, temporary
SQLite/files, live Gemini embeddings and generation. It never intercepts requests
or supplies fixture responses. Separate unit and selection regression tests use
mocks to exercise failures and UI state predictably.

```sh
npm run lint
npm run typecheck
npm run build
cd backend && python -m pytest
```

**Full workflow acceptance — October 22, 2026: PASS.** Production build, lint and
typecheck passed. Backend/corpus checks: **183 passed, 2 skipped** (optional private
sample files are unavailable). Browser suite: **3 passed**, comprising one complete
live workflow and two selection regressions.

| Check | Result |
| --- | --- |
| News feed → four initial reports → multi-report Catch Me Up | PASS |
| Single-report and multi-report Ask Folio; selection/timeline synchronization | PASS |
| Canonical citation IDs, selected-document membership, metadata and exact quotes | PASS |
| Evidence drawer, publisher links and quote highlighting on desktop/mobile | PASS |
| Held-out newer upload; older-only answers exclude its evidence | PASS |
| What Changed with correctly ordered versions and inspectable citations from each | PASS |
| Actual hybrid ranking, confirmed in eight production retrieval logs; no fallback | PASS |
| Backend process restart: five documents, 194 passages, originals and 194 cached vectors unchanged | PASS |
| Scoped Ask Folio and comparison after restart | PASS |
| Insufficient evidence, rejected empty upload, unknown IDs, reversed dates and offline UI | PASS |

Thirteen distinct cited passages were checked through the evidence API. The live
comparison took approximately 20–21 seconds in this run. These checks validate
the supplied local corpus; they do not independently verify publisher originals.
The latest local receipt and backend logs are under
`web/test-results/*/workflow-receipt.json` and `web/test-results/*/backend.log`.

<details>
<summary><strong>Reproduce the checks</strong></summary>

**Browser checks** (stop anything already running on ports 3000 and 8000 first):

```sh
npx playwright install chromium
npm run test:live --workspace @folio/web
```

This starts the production Next.js server. The full workflow test owns an isolated
FastAPI process and temporary SQLite/files, stops and restarts that process with
the same storage, then checks hashes and runs Ask/Compare again. It refuses to
reuse an existing backend. It uses the root `.venv` on Unix, `eval/.venv` on Windows,
or the executable in `FOLIO_TEST_PYTHON`. Rebuild the frontend after changing public
API URL settings, since they are bundled at build time. Set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to use an installed Chrome. Traces, screenshots,
responses and retrieval logs go to the ignored `web/test-results/`, with the suite
report at `web/test-results/live-report.json`.

To avoid occupied development ports, build with
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8012`, then run the suite with
`FOLIO_TEST_WEB_PORT=3100 FOLIO_TEST_API_PORT=8012`. An isolated checkout's built
`web/` directory can be selected with `FOLIO_TEST_WEB_DIR` so a running development
server's build files remain untouched. The API URL bundled into that build must
match `FOLIO_TEST_API_PORT`.

**Full API path:**

```sh
cd backend
python -m app.generation.api_smoke
```

Uses temporary storage and the real model client, refuses dependency overrides, and stops on the first generation failure. Only `success: true` in the ignored `backend/data/api-smoke.json` receipt confirms the complete live path.

**Single genuine model request:**

```sh
cd backend
python -m app.generation.smoke
```

Records UTC time, model ID, returned `modelVersion`, response, and elapsed ms in `backend/data/model-smoke.json`. Failed records include a safe `error.reason` (`network_error`, `configuration`, or `output_token_limit`) and the provider HTTP status when available.

</details>

</details>
