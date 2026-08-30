from api.routes.health import router as health_router
from api.routes.brands import router as brands_router
from api.routes.settings import router as settings_router
from api.routes.research import router as research_router
from api.routes.competitors import router as competitors_router
from api.routes.calendar import router as calendar_router
from api.routes.copy import router as copy_router
from api.routes.visuals import router as visuals_router

__all__ = [
    "health_router",
    "brands_router",
    "settings_router",
    "research_router",
    "competitors_router",
    "calendar_router",
    "copy_router",
    "visuals_router",
]