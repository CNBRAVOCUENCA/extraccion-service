"""Entrypoint del microservicio de Extracción de texto."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from App.logging_config import configurar_logging
from App.api import extract_sync_router, extraction_router
from App.api.exception_handlers import register_exception_handlers
from App.config.settings import settings
from App.services.extract_pool import ExtractionPool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un único pool por proceso: separa el HTTP de la extracción CPU y cachea.
    app.state.extraction_pool = ExtractionPool()
    try:
        yield
    finally:
        await app.state.extraction_pool.aclose()


# Disable API documentation in production (when debug=False)
docs_url = "/docs" if settings.debug else None
redoc_url = "/redoc" if settings.debug else None
openapi_url = "/openapi.json" if settings.debug else None

configurar_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
    lifespan=lifespan,
)

register_exception_handlers(app)

# Flujo asíncrono existente (Saga): /api/v1/extract con document_id.
app.include_router(extraction_router, prefix=settings.api_v1_prefix)
# Endpoint síncrono exigido por el TP: /extract con el PDF directo.
app.include_router(extract_sync_router)


@app.get("/health")
def health() -> dict:
    """Health check para orquestadores (Docker/Traefik)."""
    return {"status": "ok", "service": settings.app_name}
