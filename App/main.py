"""Entrypoint del microservicio de Extracción de texto."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

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


# Documentación de la API: solo con DEBUG=true o DOCS_ENABLED=true.
_docs = settings.debug or settings.docs_enabled
docs_url = "/docs" if _docs else None
redoc_url = "/redoc" if _docs else None
openapi_url = "/openapi.json" if _docs else None

configurar_logging()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Microservicio de extracción de texto de PDF. `POST /extract` recibe un PDF "
        "y devuelve su contenido en Markdown en la misma respuesta (síncrono)."
    ),
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


_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def front() -> FileResponse:
    """Página web para probar /extract desde el navegador."""
    return FileResponse(_INDEX, media_type="text/html")


@app.get("/health")
def health() -> dict:
    """Health check para orquestadores (Docker/Traefik)."""
    return {"status": "ok", "service": settings.app_name}
