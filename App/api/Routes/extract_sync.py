"""Endpoint síncrono POST /extract exigido por el TP.

Recibe el PDF binario directo (multipart/form-data con campo `file`, o el PDF
crudo en el body) y devuelve {"content", "page_count"} con HTTP 200.
Usa el pool de extracción con backpressure + caché (app.state.extraction_pool).

Límite de entrada (prompt 6): el cuerpo se lee por partes y se corta apenas
supera el máximo, ANTES de entregarlo al parser multipart o al extractor de PDF.
No se confía solo en Content-Length: si el header miente, el conteo real corta igual.
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.datastructures import UploadFile
from starlette.types import Message

from App.config.settings import settings
from App.schemas.extraction import SyncExtractionResponse
from App.services.extract_pool import ExtractionOverloaded

router = APIRouter(tags=["extract-sync"])

# Margen para los encabezados y separadores de multipart/form-data.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"El PDF supera el tamaño máximo ({settings.max_pdf_bytes} bytes).",
    )


async def _read_body_limited(request: Request, limit: int) -> bytes:
    """Lee el cuerpo por partes y corta con 413 apenas supera `limit` bytes."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise _too_large()
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


def _replay(body: bytes) -> Callable[[], Awaitable[Message]]:
    """`receive` ASGI que entrega un cuerpo ya leído (para parsear el multipart)."""
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


async def _pdf_from_multipart(request: Request, body: bytes) -> bytes:
    form = await Request(request.scope, _replay(body)).form(max_files=1, max_fields=5)
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            return b""
        try:
            return await upload.read(settings.max_pdf_bytes + 1)
        finally:
            await upload.close()
    finally:
        await form.close()


@router.post(
    "/extract",
    response_model=SyncExtractionResponse,
    summary="Convertir un PDF a Markdown",
    description=(
        "Recibe el PDF (campo `file` en multipart/form-data, o el PDF crudo en el body "
        "con `Content-Type: application/pdf`) y devuelve el contenido en Markdown y la "
        "cantidad de páginas. El header `X-Cache` indica si salió de caché (HIT) o no (MISS)."
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                },
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
            }
        }
    },
    responses={
        400: {"description": "No se recibió ningún PDF"},
        413: {"description": "El PDF supera el tamaño máximo (MAX_PDF_BYTES)"},
        401: {"description": "El PDF está protegido con contraseña"},
        422: {"description": "El archivo no es un PDF válido"},
        503: {"description": "Servicio saturado o apagándose (backpressure); reintentar"},
    },
)
async def extract_sync(request: Request, response: Response) -> SyncExtractionResponse:
    is_multipart = request.headers.get("content-type", "").startswith("multipart/form-data")
    limit = settings.max_pdf_bytes + (MULTIPART_OVERHEAD_BYTES if is_multipart else 0)
    body = await _read_body_limited(request, limit)

    pdf_bytes = await _pdf_from_multipart(request, body) if is_multipart and body else body

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No se recibió ningún PDF.")
    if len(pdf_bytes) > settings.max_pdf_bytes:
        raise _too_large()

    pool = request.app.state.extraction_pool
    try:
        result, from_cache = await pool.extract(pdf_bytes)
    except ExtractionOverloaded as exc:
        response.headers["Retry-After"] = "1"
        raise HTTPException(
            status_code=503,
            detail="Servicio saturado: reintente en unos instantes.",
            headers={"Retry-After": "1"},
        ) from exc

    response.headers["X-Cache"] = "HIT" if from_cache else "MISS"
    return SyncExtractionResponse(**result)
