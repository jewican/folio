"""Application wiring only; feature routes deliberately remain unimplemented."""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Folio API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "FOLIO_CORS_ORIGINS", "http://localhost:3000"
    ).split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
