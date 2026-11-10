"""Servicio de extracción: obtiene, procesa y persiste el texto del documento."""

import asyncio

from App.models.extraction_result import ExtractionResult
from App.services.documentos_client import DocumentosClient
from App.utils.pdf_extractor import PdfTextExtractor


class ExtractionService:
    """Lógica de negocio de extracción, con el cliente HTTP inyectado (DIP)."""

    def __init__(self, documentos_client: DocumentosClient):
        self.documentos_client = documentos_client

    async def extract_document_text(self, document_id: int) -> ExtractionResult:
        pdf_bytes = await self.documentos_client.get_document_file(document_id)
        # La extracción es CPU: se corre en un hilo para no frenar el event loop.
        text = await asyncio.to_thread(PdfTextExtractor.extract, pdf_bytes)
        await self.documentos_client.persist_extracted_text(document_id, text)
        return ExtractionResult(document_id=document_id, extracted_text=text, char_count=len(text))
