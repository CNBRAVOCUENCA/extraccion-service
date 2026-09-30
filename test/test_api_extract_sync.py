"""Tests del endpoint síncrono POST /extract (TDD)."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from App.config.settings import settings
from App.main import app


def _pdf_bytes(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _no_cache():
    # Los tests corren sin Redis: caché desactivado.
    original = settings.cache_enabled
    settings.cache_enabled = False
    yield
    settings.cache_enabled = original


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_extract_multipart_devuelve_content_y_page_count(client):
    pdf = _pdf_bytes(pages=3)
    resp = client.post("/extract", files={"file": ("x.pdf", pdf, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"content", "page_count"}
    assert body["page_count"] == 3
    assert isinstance(body["content"], str)


def test_extract_body_crudo_tambien_funciona(client):
    pdf = _pdf_bytes(pages=1)
    resp = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 200
    assert resp.json()["page_count"] == 1


def test_extract_sin_archivo_devuelve_400(client):
    resp = client.post("/extract", content=b"", headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 400


def test_extract_pdf_invalido_devuelve_422(client):
    resp = client.post("/extract", content=b"no soy un pdf", headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 422
