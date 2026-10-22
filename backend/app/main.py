"""Application wiring and safe backend error responses."""
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.generation.client import GenerationError, generation_error_handler

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Folio API", version="1.0.0")
app.add_exception_handler(GenerationError, generation_error_handler)


@app.exception_handler(sqlite3.Error)
@app.exception_handler(OSError)
async def storage_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": {
        "code": "storage_failed", "message": "Local document storage is unavailable."
    }})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "FOLIO_CORS_ORIGINS", "http://localhost:3000"
    ).split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
