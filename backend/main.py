"""
SocialForge AI — FastAPI entry point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import check_db_health, engine
from api.routes import health_router, brands_router, settings_router, research_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_ok = await check_db_health()
    if not db_ok:
        raise RuntimeError("Cannot reach database. Aborting startup.")
    yield
    await engine.dispose()


app = FastAPI(
    title="SocialForge AI",
    description="Multi-brand social media automation system.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(brands_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")

