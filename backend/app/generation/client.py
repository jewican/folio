"""Minimal Gemini REST client; usable as a FastAPI dependency."""
import os
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from pydantic import SecretStr

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Only safe, fixed messages may cross the API boundary."""

    def __init__(self, *, timed_out: bool = False,
                 reason: str = "invalid_response", provider_http_status: int | None = None):
        self.status_code = 504 if timed_out else 502
        self.code = "generation_timeout" if timed_out else "generation_failed"
        # Backend smoke diagnostics only; never include raw exception/provider text.
        self.diagnostics = {"reason": "timeout" if timed_out else reason}
        if provider_http_status is not None:
            self.diagnostics["provider_http_status"] = provider_http_status
        message = "The model request failed. Check backend configuration and provider availability."
        if timed_out:
            message = "The model request timed out."
        elif reason == "configuration":
            message = "The backend model configuration is missing or invalid."
        elif provider_http_status == 402:
            message = "The model provider rejected generation. Check provider billing and quota."
        elif provider_http_status in (401, 403):
            message = "The model provider rejected backend credentials or access."
        elif provider_http_status == 429:
            message = "The model provider is rate limited or out of quota. Try again later."
        elif reason == "output_token_limit":
            message = "The model response was too long to complete. Try a narrower question."
        elif reason == "invalid_evidence":
            message = "The model answer could not be validated against the selected evidence."
        super().__init__(message)


async def generation_error_handler(request, exc: GenerationError):
    logger.warning("Generation failed: reason=%s provider_status=%s",
                   exc.diagnostics["reason"], exc.diagnostics.get("provider_http_status"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


@dataclass(frozen=True)
class ModelResult:
    text: str
    model_id: str
    model_version: str
    elapsed_ms: int


@dataclass(frozen=True)
class GeminiClient:
    api_key: SecretStr
    model_id: str
    timeout_seconds: float = 30
    max_output_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "GeminiClient":
        # Match FastAPI's backend/.env path; shell values take precedence.
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        model = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()
        try:
            timeout = float(os.getenv("GEMINI_TIMEOUT_SECONDS") or "30")
            tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS") or "4096")
        except ValueError:
            raise GenerationError(reason="configuration") from None
        if (not key or not re.fullmatch(r"gemini-[a-z0-9.-]*flash[a-z0-9.-]*", model)
                or not 0 < timeout <= 120 or not 1 <= tokens <= 8192):
            raise GenerationError(reason="configuration")
        return cls(SecretStr(key), model, timeout, tokens)

    def generate(self, prompt: str, *, json_output: bool = False) -> ModelResult:
        """One uncached call, with network timeouts and no implicit retries."""
        if not prompt.strip():
            raise ValueError("Prompt must not be blank.")
        started = perf_counter()
        config = {"maxOutputTokens": self.max_output_tokens}
        if json_output:
            config["responseMimeType"] = "application/json"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent",
                    headers={"x-goog-api-key": self.api_key.get_secret_value()},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": config,
                    },
                )
                response.raise_for_status()
                data = response.json()
            candidate = data["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise GenerationError(reason=(
                    "output_token_limit" if candidate.get("finishReason") == "MAX_TOKENS"
                    else "incomplete_or_blocked_response"
                ))
            text = "".join(
                part["text"] for part in candidate["content"]["parts"]
                if "text" in part and not part.get("thought", False)
            ).strip()
            version = data["modelVersion"]
            if not text or not isinstance(version, str) or not version:
                raise GenerationError()
        except (TimeoutError, httpx.TimeoutException):
            raise GenerationError(timed_out=True) from None
        except httpx.HTTPStatusError as exc:
            raise GenerationError(reason="provider_http_error",
                                  provider_http_status=exc.response.status_code) from None
        except httpx.RequestError:
            raise GenerationError(reason="network_error") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            # Never include raw errors, request headers or provider bodies.
            raise GenerationError() from None
        return ModelResult(text, self.model_id, version, round((perf_counter() - started) * 1000))


def get_model_client() -> GeminiClient:
    """Use Depends(get_model_client) in generation routes when implemented."""
    return GeminiClient.from_env()
