<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

Read docs/sprint-plan.md and docs/api-contract.md. We are building Folio in a four-person hackathon. Use Next.js App Router for the frontend, FastAPI for the backend, local SQLite/files, BM25 retrieval, and the approved model API. Work only in your assigned files. Implement the simplest working version first, test it, and commit your changes. Don't modify another person's subsystem without coordination. No Supabase, authentication, crawling, OCR, or unnecessary infrastructure.

File ownership and coordination rules are in docs/sprint-plan.md. Resolve the installed Next.js guides from web/ (or the hoisted root node_modules/).
