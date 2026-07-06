from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_db_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse | JSONResponse:
    settings = get_settings()
    db_ok = check_db_connection()

    payload = HealthResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.app_name,
        environment=settings.app_env,
        database="connected" if db_ok else "disconnected",
        version="0.1.0",
    )

    if not db_ok:
        return JSONResponse(status_code=503, content=payload.model_dump())

    return payload
