"""FastAPI application entry point for Scheme Saathi."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import chat, voice, upload, form, health
from utils.model_router import ModelRouter

logger = logging.getLogger("scheme_saathi")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

_model_router: ModelRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm up ModelRouter health check."""
    global _model_router
    logger.info("🚀 Scheme Saathi starting up...")
    _model_router = ModelRouter()
    health_list = _model_router.health_check()
    for entry in health_list:
        role = entry.get("role", "?")
        model = entry.get("model", "?")
        status = entry.get("status", "unknown")
        logger.info(f"  [{role}] {model} → {status}")
    logger.info("✅ Startup complete.")
    yield
    logger.info("🛑 Scheme Saathi shutting down.")


app = FastAPI(
    title="Scheme Saathi API",
    description="Voice-first welfare scheme assistant for low-literacy users.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins in dev; tighten in production via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(upload.router)
app.include_router(form.router)
app.include_router(health.router)

# Serve static frontend if the directory exists
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
