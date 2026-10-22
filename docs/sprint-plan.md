# FOLIO — Team Build Plan

**Source:** `.local/FOLIO_TEAM_SPRINT_PLAN.md`; this committed copy is authoritative. Next.js replaces the source plan’s React/Vite choice. Setup creates contracts and route stubs only; feature milestones below are future work.

**Team:** Shane-nanigans · 4 people, each with Codex / Claude Code  
**Build window:** 11:00 AM–2:00 PM · All times local  
**Target:** A working news document-RAG demo by 2 PM. Slides and presentation preparation follow this build window.

## What we are building

Folio helps someone catch up on a developing story and understand **what changed, when it was reported, and which documents support it**.

Our demonstration starts with two dated reports. We ask a question, inspect its evidence, upload a newer report, and show the changes with evidence from both versions.

**MVP:** one story, 3–5 documents, cited questions and answers, report comparison, and an evidence viewer. Use text-based PDFs or text files.

**Success:** the complete workflow works live. Originality and relevance are 15% each; demo and presentation are 35% each. Spend effort on changes that make the demonstration clearer or more reliable.

## Architecture and fixed decisions

| Part | Decision |
| --- | --- |
| Interface | Next.js App Router in `web/`. Document list, upload, question panel, comparison, and evidence drawer. |
| Application | Python / FastAPI. One backend coordinates ingestion, retrieval, Gemini, and saved results. |
| Documents | Original files and SQLite stored locally. Preserve source titles, URLs, report dates, pages, and passage IDs. |
| Retrieval | Local BM25 keyword search. Optional Jev work in the original plan is deferred; it is not part of contract v1. |
| Generation | Gemini Flash, using a model ID confirmed with our keys during setup. Generate from retrieved passages and return structured citations. |

The application and index run on the demo laptop. Gemini and optional Jev still require internet access and receive selected document excerpts.

- **Latency:** index each document once, retrieve a small context, and use one Gemini call per answer or comparison. Measure uncached response times. Jev must have a timeout and a baseline fallback.
- **Cost:** cap context and output, use sample responses during UI development, and cache repeated requests. Cache keys must include the selected document versions, retrieval mode, model, and prompt version.
- **Security:** keys stay in backend environment variables, outside Git and frontend code. Use public sample documents, restrict upload type/size, and treat document text as evidence rather than instructions.
- **Scope:** hosted databases, login, crawling, OCR, and automatic background news monitoring are outside this sprint. Add no new infrastructure after setup.

## How we work

1. **Claim W1–W4.** Each person owns one workstream from setup through final fixes. W1 owns integration and merges into the main branch.
2. **Work in parallel immediately.** W1 uses sample passages; W2 uses the first available document; W3 uses sample responses; W4 assembles the corpus and expected answers.
3. **Agree on interfaces by 11:15.** W1 owns shared contracts. Announce changes before another lane depends on them.
4. **Keep agents within their lane.** Give Codex / Claude Code this brief, the lane's file ownership, and its acceptance check. Shared configuration changes go through the responsible owner.
5. **Integrate small working changes at checkpoints.** A missed gate means fixing the core flow before adding optional features. Unblocked teammates continue their lane or help the blocking owner.

## Team checkpoints

| Gate | Time | Pass condition |
| --- | --- | --- |
| A — Foundation | 11:15 | Repo and run instructions shared; interfaces agreed; sample responses available; one real Gemini request succeeds. |
| B — Baseline | 12:00 | Upload a document, ask a question, receive a real answer, and open its supporting passage through the UI. |
| C — Main feature | 12:45 | Upload the held-out newer report and show what changed, with older and newer evidence. |
| D — Feature freeze | 1:30 | Core demo works. Keep or remove Jev based on evidence. Only blocker fixes after this point. |
| E — Ready | 2:00 | Complete demo succeeds twice on the demo laptop, including a fresh restart/reset. |

---

## W1 — Backend, AI, and integration

**Owner:** Codex (model client setup for this task)
**Owns:** API routes, generation, storage, shared contracts, root configuration, and integration.

| Time | Bundled responsibility |
| --- | --- |
| **11–12** | Create the private repo, invite the team, push the starter structure, and provide run commands, an environment template, and ignore rules for secrets/runtime files. Finish the shared contracts and prove a Gemini call by 11:15. Build upload, document listing, question answering, and evidence endpoints; connect W2's retrieval before noon. |
| **12–1** | Build report comparison using explicit older/newer document selections. Return changes with evidence from both sides. Validate returned citation IDs against the passages actually supplied. Reach Gate C by 12:45. |
| **1–2** | Add bounded retries/timeouts, cache invalidation, and timing/usage logs. Merge working branches, resolve integration issues, and verify startup on the demo laptop. After 1:30, fix blockers only. |

**Done:** the backend supports the entire live workflow, keeps secrets private, and reports failures clearly.

**Dependency:** use sample passages until W2 is ready. Give W3 stable response formats before real AI integration is finished.

## W2 — Document ingestion and retrieval

**Owner:** ____________________  
**Owns:** ingestion and retrieval modules, source metadata extraction, indexing, and optional Jev reranking.

| Time | Bundled responsibility |
| --- | --- |
| **11–12** | Extract text from the first sample document, split it into readable passages, and preserve document/page identifiers. Build BM25 retrieval with document filtering. Give W1 a callable retrieval function by approximately 11:35. |
| **12–1** | Support earlier/later document selections and retrieve evidence from each side for comparison. Keep the held-out report outside the initial index until it is uploaded. After Gate C passes, try Jev as an optional reranking mode. |
| **1–2** | Fix misses identified by W4. Keep baseline and Jev behind one mode switch, using the same underlying corpus. Enforce a timeout/fallback for Jev and support rebuilding the index from saved documents. Stop optional work at 1:30. |

**Done:** retrieved passages are relevant and traceable, comparison includes both versions, and earlier answers cannot use later documents.

**Dependency:** begin with one document; do not wait for the complete corpus. Jev must never block baseline integration.

## W3 — Frontend and user experience

**Owner:** ____________________  
**Owns:** frontend code, frontend dependencies, user interactions, and visual presentation.

| Time | Bundled responsibility |
| --- | --- |
| **11–12** | Build the document list, upload, question panel, answer display, and evidence drawer against sample responses. Connect the actual backend as endpoints become available. Complete the visible baseline flow before noon. |
| **12–1** | Build the report comparison experience: earlier claim, updated claim, dates, and supporting evidence. Make the newly uploaded report and its contribution easy to see. Reach Gate C by 12:45. |
| **1–2** | Improve readability, loading feedback, empty states, and failure recovery. Clearly display insufficient evidence and cached results. Check the layout on the demo laptop; after 1:30, fix blockers only. |

**Done:** someone can upload, ask, compare, and inspect evidence without developer assistance.

**Dependency:** sample responses unblock all initial UI work. Keep backend calls in one frontend adapter so integration changes stay contained.

## W4 — Corpus, evaluation, and demo reliability

**Owner:** ____________________  
**Owns:** sample documents, source manifest, response fixtures, evaluation cases, and the demo reset/check procedure.

| Time | Bundled responsibility |
| --- | --- |
| **11–12** | Collect 3–5 dated documents about one developing story. Share one usable document immediately. Record titles, URLs, and report dates; check text extraction. Keep one newer report out of the initial upload. Provide sample responses for W3 and approximately ten questions with expected supporting passages. |
| **12–1** | Check the live baseline and comparison against the documents. Cover direct questions, dated questions, changes, and insufficient evidence. Report reproducible failures with the question and expected passage. |
| **1–2** | If Jev is ready, compare it with baseline using the same questions, corpus, Gemini model, prompt, and context budget. Record evidence quality and uncached latency. Run the full workflow, reset, restart, and error checks on the demo laptop. |

**Done:** we have a repeatable demo, verified evidence, and measured support for any improvement we claim.

**Dependency:** corpus preparation and expected answers start immediately. Switch to live checks as each gate becomes available.

---

## Shared handoffs

W1 records these shapes in the shared contracts; W2–W4 build against them.

| Handoff | Required information |
| --- | --- |
| Document / passage | Stable document and passage IDs, text, title, source URL, report date, and page number where available. Keep upload time separate from report date. |
| Retrieval | Question + selected document IDs + mode → ranked passages with source metadata. |
| Answer | Answer text + citations pointing to supplied passages + timing and cache status. |
| Comparison | Older/newer document selections → added or updated claims, unresolved differences, and evidence for each side. |
| Evidence viewer | Passage ID → exact stored text, document details, page, and original file link. |

**Evidence rule:** a later report changing a number is not automatically a contradiction. Compare dates, locations, units, and scope. Missing information means unknown, not zero. Citation existence can be checked in code; W4 also checks whether the passage actually supports the claim.

## Cut rules

- **Behind at noon:** pause Jev and visual extras; complete the baseline flow.
- **Behind at 12:45:** narrow comparison to the chosen story and selected reports; retain evidence on both sides.
- **Jev adds delay or no demonstrated benefit:** leave baseline as the default and report the result honestly.
- **API failure:** show a clear error and bounded retry. A saved example may support the presentation only if visibly labeled as saved.
- **After 1:30:** fix demo blockers only. At 2 PM, hand the stable build and evaluation notes over for slides and rehearsal.


## Assigned files and coordination

Claim one lane by replacing its blank owner name before feature work. Until names
are filled in, W1–W4 are the ownership identifiers. These boundaries supersede
broad responsibility descriptions above. This setup change establishes all lanes;
subsequent feature work stays inside the claimed lane.

| Lane | Exclusive files / directories | Checks owned |
| --- | --- | --- |
| W1 — backend/AI/integration | `backend/app/main.py`, `backend/app/api/`, `backend/app/contracts.py`, `backend/app/generation/`, `backend/app/storage/`, `backend/app/__init__.py`, `backend/requirements*.txt`, `backend/pytest.ini`, `backend/tests/test_contract.py`; root `package.json`, `package-lock.json`, `.gitignore`, `.env.example`, `README.md`, `AGENTS.md`, `docs/api-contract.md`, `docs/sprint-plan.md` | API contract, model setup, backend routes, storage, final integration |
| W2 — ingestion/retrieval | `backend/app/ingestion/`, `backend/app/retrieval/`, `backend/tests/test_ingestion.py`, `backend/tests/test_retrieval.py` | Text extraction, stable passage IDs/pages, BM25 and selection filtering |
| W3 — frontend | All of `web/` | Frontend lint, typecheck, build, visible workflow |
| W4 — corpus/evaluation | `samples/`, `fixtures/`, `evaluation/`, `docs/demo-checklist.md`, `docs/evaluation.md` | Public corpus provenance, contract fixtures, evidence correctness, repeatable demo |

- W3 owns frontend dependency choices in `web/package.json`; coordinate with W1
  to regenerate the shared root lockfile. W2 requests Python dependency changes
  from W1. Avoid concurrent edits to shared configuration.
- W1 owns persistence and route wiring. W2 returns extracted passages/retrieval
  results; W2 does not edit routes or implement a second database layer.
- W1 and W2 agree on callable Python handoffs before implementation: extraction
  receives the assigned `doc_id` plus local file/metadata and returns passages;
  retrieval receives question, explicit `doc_ids`, and `top_k`, and returns ranked
  stored passages. No UI imports backend Python; W3 uses one adapter at
  `web/lib/api.ts` when implementation begins.
- `docs/api-contract.md` is the shared v1 wire contract. W1 maintains matching
  Pydantic models in `backend/app/contracts.py` and `/openapi.json`. W3 may define
  TypeScript types under `web/lib/`; W4 owns mock JSON under `fixtures/`.
- Propose contract changes to all affected owners before editing; update the
  contract, schemas, fixtures, clients, and relevant checks together. No silent
  field renames or route changes after Gate A.
- Use `w1/...`, `w2/...`, `w3/...`, `w4/...` branches. Commit small tested changes
  inside your lane; W1 integrates at gates. Coordinate explicitly before editing
  any other lane. Do not commit keys, local runtime files, or private corpus data.
- BM25 and the approved model API are the MVP. Historical optional Jev tasks above
  remain deferred unless the team coordinates a later contract change after Gate C.

### Foundation acceptance (this setup)

`npm ci`, frontend lint/typecheck/build, and backend contract tests pass.
`GET /health` responds; all five feature route operations are registered in
OpenAPI with request/response shapes and return explicit 501 stubs for valid
requests. No extraction, retrieval, model calls, upload persistence, or feature UI
is implemented. Gate A's real model request and W4 fixtures remain assigned work.
