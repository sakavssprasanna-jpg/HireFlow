from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ...db.base import get_db
from ...domain.schemas import HealthCheckResponse
from ...config import settings

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint validating database connectivity and AI provider status."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthCheckResponse(
        status="healthy" if db_ok else "degraded",
        version="0.1.0",
        database_connected=db_ok,
        ai_mode=settings.DEFAULT_AI_MODE
    )
