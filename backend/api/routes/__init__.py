from api.routes.health import router as health_router
from api.routes.brands import router as brands_router
from api.routes.settings import router as settings_router

__all__ = ["health_router", "brands_router", "settings_router"]