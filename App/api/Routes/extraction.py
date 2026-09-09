"""Rutas REST del microservicio de Extracción de texto."""

from fastapi import APIRouter, Depends

from App.config.settings import settings
from App.schemas.extraction import ExtractionResponse, ExtractRequest
from App.services.documentos_client import DocumentosClient
from App.services.extraction_service import ExtractionService

router = APIRouter(tags=["extraction"])


def _get_service() -> ExtractionService:
    client = DocumentosClient(base_url=settings.documentos_service_url)
    return ExtractionService(documentos_client=client)


@router.post("/extract", response_model=ExtractionResponse)
async def extract(payload: ExtractRequest, service: ExtractionService = Depends(_get_service)) -> ExtractionResponse:
    """Obtiene el PDF desde documentos-service y extrae su texto."""
    result = await service.extract_document_text(payload.document_id)
    return ExtractionResponse(
        document_id=result.document_id,
        extracted_text=result.extracted_text,
        char_count=result.char_count,
    )
