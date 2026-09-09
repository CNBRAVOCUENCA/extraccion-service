"""Schemas (DTOs) de la API de Extracción."""

from pydantic import BaseModel


class ExtractRequest(BaseModel):
    document_id: int


class DocumentFileResponse(BaseModel):
    file_base64: str


class ExtractionResponse(BaseModel):
    document_id: int
    extracted_text: str
    char_count: int
