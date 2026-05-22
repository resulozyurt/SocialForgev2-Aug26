from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.database import check_db_health

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    db_healthy = await check_db_health()

    return JSONResponse(
        status_code=200 if db_healthy else 503,
        content={
            "status": "ok" if db_healthy else "degraded",
            "services": {
                "database": "ok" if db_healthy else "unreachable",
            },
        },
    )