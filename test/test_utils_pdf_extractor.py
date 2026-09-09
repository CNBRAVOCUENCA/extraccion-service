"""Pruebas unitarias para PdfTextExtractor."""

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from App.exceptions import PdfExtractionError, PdfPasswordRequiredError
from App.utils.pdf_extractor import PdfTextExtractor


def test_extract_returns_text_from_valid_pdf(valid_pdf_bytes):
    text = PdfTextExtractor.extract(valid_pdf_bytes)
    assert "Hola mundo" in text


def test_extract_raises_on_invalid_pdf():
    with pytest.raises(PdfExtractionError):
        PdfTextExtractor.extract(b"esto no es un pdf")


def test_extract_raises_401_domain_error_for_password_protected_pdf(valid_pdf_bytes):
    reader = PdfReader(BytesIO(valid_pdf_bytes))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt("secret")
    protected_pdf = BytesIO()
    writer.write(protected_pdf)

    with pytest.raises(PdfPasswordRequiredError):
        PdfTextExtractor.extract(protected_pdf.getvalue())
