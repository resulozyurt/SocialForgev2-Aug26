from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import check_db_health, engine
from core.security import require_admin
from api.routes import (
    health_router,
    brands_router,
    settings_router,
    research_router,
    competitors_router,
    calendar_router,
    copy_router,
    visuals_router,
    references_router,
    boards_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_ok = await check_db_health()
    if not db_ok:
        raise RuntimeError("Cannot reach database. Aborting startup.")
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="SocialForge AI",
    description="Multi-brand social media automation system.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /health stays public for platform health probes.
app.include_router(health_router)

# Everything else is behind admin HTTP Basic auth.
_admin = [Depends(require_admin)]
app.include_router(brands_router, prefix="/api/v1", dependencies=_admin)
app.include_router(settings_router, prefix="/api/v1", dependencies=_admin)
app.include_router(research_router, prefix="/api/v1", dependencies=_admin)
app.include_router(competitors_router, prefix="/api/v1", dependencies=_admin)
app.include_router(calendar_router, prefix="/api/v1", dependencies=_admin)
app.include_router(copy_router, prefix="/api/v1", dependencies=_admin)
app.include_router(visuals_router, prefix="/api/v1", dependencies=_admin)
app.include_router(references_router, prefix="/api/v1", dependencies=_admin)
app.include_router(boards_router, prefix="/api/v1", dependencies=_admin)
