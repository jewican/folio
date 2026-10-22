# Live RAG evaluation

Use Python 3.13 with the repository's pinned backend dependencies. From the root
on Windows (the existing `backend/.env` supplies the approved model settings):

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python313/python.exe" -m venv eval/.venv
.\eval\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements-dev.txt
.\eval\.venv\Scripts\python.exe -m pytest -q eval/test_evaluator.py
.\eval\.venv\Scripts\python.exe eval/run_eval.py
```

On systems where `python` already has those dependencies, use
`python eval/run_eval.py`. No running backend server is needed: FastAPI's
TestClient invokes the actual production app in process. Network access is needed
for the configured Gemini API. Evaluation makes up to 12 real application
requests and a separate real semantic grading call for each valid response.
The explicit Python 3.13 path above is the installed runtime used on this machine;
adjust it for another installation. Python 3.14 cannot use this project's pinned
Pydantic wheel, so changing the runtime avoids changing backend dependencies.

The schedule is seven initial questions plus two initial controls, then the
held-out October 13 upload, then the insufficient-evidence question and two real
`/compare` calls. A missing endpoint is a measured failure, never replaced by an
`/ask` answer. Every run creates fresh temporary SQLite/uploads and clears the
storage/index cache; the application's usual dataset stays untouched.

`results.md` summarizes pass/fail, client/server latency, phase inventory and
failures. `results.json` preserves full requests, actual responses, retrieved
passages, exact citation checks and per-criterion semantic judgments. These files
are replaced on rerun; use `--output eval/another-run.md` to preserve another run.
Exit code 1 means at least one case/control failed or the run was blocked.

Semantic grading uses the same approved model in a separate request and may vary;
it is not human certification. All rubric criteria and all claim-support checks
must pass. Deterministic checks independently require real stored passage IDs,
selected-document membership, retrieved-context membership, exact quotes within
the 4,000-character generation context, correct metadata and uncached BM25.
Gold excerpt coverage is recorded as a retrieval diagnostic, not used as a
mandatory string match when alternative passages support an answer.
The separate judge has a 120-second timeout and 8,192-token output limit because
its input includes all rubric items and evidence. Production generation settings
are unchanged. There are no automatic retries or retries seeking a passing grade.

Windows CRLF checkout normalization is allowed only when LF bytes match the
manifest SHA-256 exactly. No corpus or RAG implementation files are modified.
The evaluator guard tests validate scheduling, content hashes and fail-closed
judge parsing; their results are separate from live model evaluation scores.
