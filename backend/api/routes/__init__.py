from api.routes.health import router as health_router
from api.routes.brands import router as brands_router
from api.routes.settings import router as settings_router
from api.routes.research import router as research_router
from api.routes.competitors import router as competitors_router

__all__ = ["health_router", "brands_router", "settings_router", "research_router", "competitors_router"]