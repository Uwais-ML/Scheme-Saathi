"""Health-check routes."""

from fastapi import APIRouter, Query
from api.schemas import HealthResponse
from utils.model_router import ModelRouter
from config.settings import settings

router = APIRouter(tags=["health"])

# Shared router instance (lazy initialised)
_model_router: ModelRouter | None = None


def _get_model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router


@router.get("/api/health", response_model=HealthResponse)
def health():
    """Return simple liveness status."""
    mr = _get_model_router()
    health_list = mr.health_check()
    any_degraded = any(
        e.get("status", "").lower() != "ok" for e in health_list
    )
    return HealthResponse(
        status="degraded" if any_degraded else "ok",
        degraded=any_degraded,
    )


@router.get("/api/admin/status")
def admin_status(dev: int = Query(0)):
    """Full ModelRouter health table — only available in dev mode."""
    if dev != 1:
        return {"detail": "Not available in production mode."}
    mr = _get_model_router()
    return {
        "version": "1.0",
        "health": mr.health_check(),
    }
