"""Entrypoint del microservicio de Extracción de texto."""

from fastapi import FastAPI

from App.api import extraction_router
from App.api.exception_handlers import register_exception_handlers
from App.config.settings import settings

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)

register_exception_handlers(app)
app.include_router(extraction_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health() -> dict:
    """Health check para orquestadores (Docker/Traefik)."""
    return {"status": "ok", "service": settings.app_name}
