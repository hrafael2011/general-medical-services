from fastapi import APIRouter
from sqlalchemy import text

from backend.app.infrastructure.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """Lightweight health check — no DB dependency."""
    return {"status": "ok"}


@router.get("/health/ready")
def health_readiness() -> dict:
    """Readiness check — verifies DB connectivity."""
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": str(exc)}
    finally:
        session.close()
