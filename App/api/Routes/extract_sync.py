"""Endpoint síncrono POST /extract exigido por el TP.

Recibe el PDF binario directo (multipart/form-data con campo `file`, o el PDF
crudo en el body) y devuelve {"content", "page_count"} con HTTP 200.
Usa el pool de extracción con backpressure + caché (app.state.extraction_pool).
"""

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from App.config.settings import settings
from App.schemas.extraction import SyncExtractionResponse
from App.services.extract_pool import ExtractionOverloaded

router = APIRouter(tags=["extract-sync"])


@router.post(
    "/extract",
    response_model=SyncExtractionResponse,
    summary="Convertir un PDF a Markdown",
    description=(
        "Recibe el PDF (campo `file` en multipart/form-data, o el PDF crudo en el body "
        "con `Content-Type: application/pdf`) y devuelve el contenido en Markdown y la "
        "cantidad de páginas. El header `X-Cache` indica si salió de caché (HIT) o no (MISS)."
    ),
    responses={
        400: {"description": "No se recibió ningún PDF"},
        413: {"description": "El PDF supera el tamaño máximo (MAX_PDF_BYTES)"},
        401: {"description": "El PDF está protegido con contraseña"},
        422: {"description": "El archivo no es un PDF válido"},
        503: {"description": "Servicio saturado (backpressure); reintentar"},
    },
)
async def extract_sync(
    request: Request,
    response: Response,
    file: UploadFile | None = File(default=None),
) -> SyncExtractionResponse:
    if file is not None:
        pdf_bytes = await file.read()
    else:
        pdf_bytes = await request.body()

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No se recibió ningún PDF.")
    if len(pdf_bytes) > settings.max_pdf_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"El PDF supera el tamaño máximo ({settings.max_pdf_bytes} bytes).",
        )

    pool = request.app.state.extraction_pool
    try:
        result, from_cache = await pool.extract(pdf_bytes)
    except ExtractionOverloaded as exc:
        response.headers["Retry-After"] = "1"
        raise HTTPException(
            status_code=503,
            detail="Servicio saturado: reintente en unos instantes.",
        ) from exc

    response.headers["X-Cache"] = "HIT" if from_cache else "MISS"
    return SyncExtractionResponse(**result)
