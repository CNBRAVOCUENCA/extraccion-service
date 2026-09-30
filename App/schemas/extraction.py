"""Schemas (DTOs) de la API de Extracción."""

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    """Entrada del flujo asíncrono (Saga): referencia a un documento ya subido."""

    document_id: int


class ExtractionResponse(BaseModel):
    """Salida del flujo asíncrono (Saga)."""

    document_id: int
    extracted_text: str
    char_count: int


class SyncExtractionResponse(BaseModel):
    """Salida del endpoint síncrono POST /extract, según pide el TP."""

    content: str
    page_count: int
