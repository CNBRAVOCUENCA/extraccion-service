"""Schemas (DTOs) de la API de Extracción."""

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    document_id: int


class ExtractionResponse(BaseModel):
    document_id: int
    extracted_text: str
    char_count: int
