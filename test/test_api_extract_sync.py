"""Tests del endpoint síncrono POST /extract (TDD)."""

from io import BytesIO

import pytest
from App.config.settings import settings
from App.main import app
from fastapi.testclient import TestClient
from pypdf import PdfWriter


def _pdf_bytes(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


try:  # PyMuPDF es opcional (extra "fast"); sin él se prueba con pypdf.
    import pymupdf  # noqa: F401

    _BACKEND = "pymupdf"
except ImportError:  # pragma: no cover - depende del entorno
    _BACKEND = "pypdf"


@pytest.fixture(autouse=True)
def _no_cache():
    # Los tests corren sin Redis: caché desactivado.
    original = (settings.cache_enabled, settings.extractor_backend)
    settings.cache_enabled = False
    settings.extractor_backend = _BACKEND
    yield
    settings.cache_enabled, settings.extractor_backend = original


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


def test_front_se_sirve_en_la_raiz(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/extract" in resp.text


def test_extract_rechaza_pdf_demasiado_grande_con_413(client, monkeypatch):
    monkeypatch.setattr(settings, "max_pdf_bytes", 100)
    resp = client.post("/extract", content=b"%PDF-" + b"0" * 200, headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 413


# --- Prompt 6: límite de entrada en ambos formatos ---


def test_pdf_justo_en_el_limite_se_acepta_en_ambos_formatos(client, monkeypatch):
    pdf = _pdf_bytes(pages=1)
    monkeypatch.setattr(settings, "max_pdf_bytes", len(pdf))
    crudo = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    multipart = client.post("/extract", files={"file": ("x.pdf", pdf, "application/pdf")})
    assert crudo.status_code == 200, crudo.text
    assert multipart.status_code == 200, multipart.text


def test_un_byte_por_encima_del_limite_da_413_en_ambos_formatos(client, monkeypatch):
    pdf = _pdf_bytes(pages=1)
    monkeypatch.setattr(settings, "max_pdf_bytes", len(pdf) - 1)
    crudo = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    multipart = client.post("/extract", files={"file": ("x.pdf", pdf, "application/pdf")})
    assert crudo.status_code == 413
    assert multipart.status_code == 413


def test_no_confia_en_content_length_cuerpo_sin_largo_declarado(client, monkeypatch):
    """Cuerpo enviado por partes (chunked, sin Content-Length): se corta igual."""
    monkeypatch.setattr(settings, "max_pdf_bytes", 1000)

    def partes():
        for _ in range(10):
            yield b"0" * 500

    resp = client.post("/extract", content=partes(), headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 413


def test_multipart_enorme_se_corta_antes_del_parser(client, monkeypatch):
    monkeypatch.setattr(settings, "max_pdf_bytes", 1000)
    from App.api.Routes import extract_sync as ruta

    llamado = []
    monkeypatch.setattr(ruta, "_pdf_from_multipart", lambda *a: llamado.append(1))
    grande = b"%PDF-" + b"0" * (1000 + ruta.MULTIPART_OVERHEAD_BYTES + 10)
    resp = client.post("/extract", files={"file": ("x.pdf", grande, "application/pdf")})
    assert resp.status_code == 413
    assert llamado == []


def test_multipart_sin_campo_file_da_400(client):
    resp = client.post("/extract", data={"otro": "valor"}, files={"x": ("a.txt", b"hola", "text/plain")})
    assert resp.status_code == 400


def test_saturacion_responde_503_con_retry_after(client, monkeypatch):
    from App.services.extract_pool import ExtractionOverloaded

    async def saturado(_pdf):
        raise ExtractionOverloaded()

    monkeypatch.setattr(client.app.state.extraction_pool, "extract", saturado)
    resp = client.post("/extract", content=_pdf_bytes(1), headers={"Content-Type": "application/pdf"})
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "1"
