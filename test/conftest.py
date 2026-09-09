"""Fixtures compartidos para los tests del microservicio de Extracción."""

import pytest


@pytest.fixture
def valid_pdf_bytes():
    """PDF real mínimo con texto extraíble, generado con reportlab."""
    from io import BytesIO
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Hola mundo, este es un PDF de prueba.")
    c.save()
    return buf.getvalue()
