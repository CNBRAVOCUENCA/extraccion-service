"""Pruebas unitarias para ExtractionService: orquesta cliente + extractor."""

from unittest.mock import AsyncMock

import pytest
from App.exceptions import DocumentNotFoundUpstreamError
from App.services.extraction_service import ExtractionService


async def test_extract_document_text_success(valid_pdf_bytes):
    fake_client = AsyncMock()
    fake_client.get_document_file.return_value = valid_pdf_bytes
    service = ExtractionService(documentos_client=fake_client)

    result = await service.extract_document_text(document_id=1)

    assert "Hola mundo" in result.extracted_text
    assert result.document_id == 1
    assert result.char_count > 0
    fake_client.get_document_file.assert_awaited_once_with(1)


async def test_extract_document_text_propagates_not_found():
    fake_client = AsyncMock()
    fake_client.get_document_file.side_effect = DocumentNotFoundUpstreamError("no existe")
    service = ExtractionService(documentos_client=fake_client)
    with pytest.raises(DocumentNotFoundUpstreamError):
        await service.extract_document_text(document_id=999)


async def test_la_extraccion_no_bloquea_el_event_loop(valid_pdf_bytes, monkeypatch):
    # Extraer un PDF es trabajo de CPU: si corre en el hilo del event loop,
    # el servicio deja de atender otras peticiones mientras tanto.
    import threading

    from App.utils.pdf_extractor import PdfTextExtractor

    hilos = []
    original = PdfTextExtractor.extract

    def espia(pdf_bytes):
        hilos.append(threading.current_thread())
        return original(pdf_bytes)

    monkeypatch.setattr(PdfTextExtractor, "extract", staticmethod(espia))
    fake_client = AsyncMock()
    fake_client.get_document_file.return_value = valid_pdf_bytes

    await ExtractionService(documentos_client=fake_client).extract_document_text(1)

    assert hilos and hilos[0] is not threading.main_thread()
