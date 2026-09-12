"""Entrypoint del microservicio de Extracción de texto."""

from fastapi import FastAPI

from App.api import extraction_router
from App.api.exception_handlers import register_exception_handlers
from App.config.settings import settings

# Disable API documentation in production (when debug=False)
docs_url = "/docs" if settings.debug else None
redoc_url = "/redoc" if settings.debug else None
openapi_url = "/openapi.json" if settings.debug else None

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

register_exception_handlers(app)
app.include_router(extraction_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health() -> dict:
    """Health check para orquestadores (Docker/Traefik)."""
    return {"status": "ok", "service": settings.app_name}
