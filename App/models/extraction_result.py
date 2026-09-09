"""Modelo de dominio para el resultado de una extracción."""

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    document_id: int
    extracted_text: str
    char_count: int
