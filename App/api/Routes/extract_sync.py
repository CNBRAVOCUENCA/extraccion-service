"""Endpoint síncrono POST /extract exigido por el TP.

Recibe el PDF binario directo (multipart/form-data con campo `file`, o el PDF
crudo en el body) y devuelve {"content", "page_count"} con HTTP 200.
Usa el pool de extracción con backpressure + caché (app.state.extraction_pool).
"""

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile

from App.schemas.extraction import SyncExtractionResponse
from App.services.extract_pool import ExtractionOverloaded

router = APIRouter(tags=["extract-sync"])


@router.post("/extract", response_model=SyncExtractionResponse)
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

    pool = request.app.state.extraction_pool
    try:
        result, from_cache = await pool.extract(pdf_bytes)
    except ExtractionOverloaded:
        response.headers["Retry-After"] = "1"
        raise HTTPException(
            status_code=503,
            detail="Servicio saturado: reintente en unos instantes.",
        )

    response.headers["X-Cache"] = "HIT" if from_cache else "MISS"
    return SyncExtractionResponse(**result)
