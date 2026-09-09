"""Pruebas unitarias para PdfTextExtractor."""

import pytest

from App.exceptions import PdfExtractionError
from App.utils.pdf_extractor import PdfTextExtractor


def test_extract_returns_text_from_valid_pdf(valid_pdf_bytes):
    text = PdfTextExtractor.extract(valid_pdf_bytes)
    assert "Hola mundo" in text


def test_extract_raises_on_invalid_pdf():
    with pytest.raises(PdfExtractionError):
        PdfTextExtractor.extract(b"esto no es un pdf")
