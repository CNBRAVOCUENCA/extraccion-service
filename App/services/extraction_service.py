"""Servicio de extracción: orquesta obtener el PDF y extraer su texto.

No persiste nada: recibe un document_id, le pide el PDF a documentos-service,
extrae el texto y devuelve el resultado. La persistencia del resultado se
resuelve al integrar la Saga.
"""

from App.models.extraction_result import ExtractionResult
from App.services.documentos_client import DocumentosClient
from App.utils.pdf_extractor import PdfTextExtractor


class ExtractionService:
    """Lógica de negocio de extracción, con el cliente HTTP inyectado (DIP)."""

    def __init__(self, documentos_client: DocumentosClient):
        self.documentos_client = documentos_client

    async def extract_document_text(self, document_id: int) -> ExtractionResult:
        pdf_bytes = await self.documentos_client.get_document_file(document_id)
        text = PdfTextExtractor.extract(pdf_bytes)
        return ExtractionResult(document_id=document_id, extracted_text=text, char_count=len(text))
