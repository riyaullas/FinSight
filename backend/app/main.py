import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import auth, company, dashboard, setup, users
from app.core.config import get_settings
from app.core.database import get_db
from app.core.middleware import CSRFMiddleware, SecurityHeadersMiddleware

__version__ = "0.1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()

app = FastAPI(
    title=f"{settings.product_name} API",
    version=__version__,
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

# Order: the last added middleware runs first.
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["content-type", "x-csrf-token"],
    )
if settings.allowed_host_list and "*" not in settings.allowed_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

api = APIRouter(prefix="/api")


@api.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@api.get("/ready", tags=["health"])
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


for module in (setup, auth, company, users, dashboard):
    api.include_router(module.router)

app.include_router(api)
