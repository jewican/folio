"""Run from backend/: python -m app.generation.smoke (one real request)."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.generation.client import GenerationError, get_model_client

PROMPT = "Reply with exactly: Folio model connection OK"
RECORD_PATH = Path(__file__).resolve().parents[2] / "data" / "model-smoke.json"


def run() -> int:
    record = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "provider": "gemini",
        "prompt": PROMPT,
        "cached": False,
        "success": False,
    }
    started = perf_counter()
    try:
        client = get_model_client()
        record["model_id"] = client.model_id
        result = client.generate(PROMPT)
        record.update(asdict(result), success=True)
    except GenerationError as exc:
        record.update(error={"code": exc.code, "message": str(exc), **exc.diagnostics},
                      elapsed_ms=round((perf_counter() - started) * 1000))
    RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(record, indent=2) + "\n"
    RECORD_PATH.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
