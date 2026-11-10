"""Pruebas de integración de la API de Extracción, mockeando documentos-service."""


import httpx
import pytest
import respx
from App.config.settings import settings
from fastapi.testclient import TestClient

DOCUMENTOS_URL = "http://documentos-service-test:9999"
DOCUMENTOS_API_KEY = "test-internal-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "documentos_service_url", DOCUMENTOS_URL)
    monkeypatch.setattr(settings, "documentos_service_api_key", DOCUMENTOS_API_KEY)
    from App.main import app
    return TestClient(app)


@respx.mock
def test_extract_success(client, valid_pdf_bytes, monkeypatch):
    from App.utils.pdf_extractor import PdfTextExtractor

    monkeypatch.setattr(PdfTextExtractor, "extract", staticmethod(lambda _: "Texto extraído"))
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/1/file").mock(
        return_value=httpx.Response(200, content=valid_pdf_bytes)
    )
    persistence = respx.put(f"{DOCUMENTOS_URL}/api/v1/documents/1/extraction").mock(
        return_value=httpx.Response(
            200,
            json={"id": 1, "extracted_text": "Texto extraído", "is_processed": True},
        )
    )
    response = client.post("/api/v1/extract", json={"document_id": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == 1
    assert body["extracted_text"] == "Texto extraído"
    assert persistence.called
    assert persistence.calls.last.request.headers["X-Internal-API-Key"] == DOCUMENTOS_API_KEY
    assert persistence.calls.last.request.content == '{"extracted_text":"Texto extraído"}'.encode()


@respx.mock
def test_extract_document_not_found_returns_404(client):
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/999/file").mock(return_value=httpx.Response(404))
    response = client.post("/api/v1/extract", json={"document_id": 999})
    assert response.status_code == 404


@respx.mock
def test_extract_upstream_error_returns_502(client):
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/1/file").mock(return_value=httpx.Response(500))
    response = client.post("/api/v1/extract", json={"document_id": 1})
    assert response.status_code == 502


@respx.mock
def test_extract_does_not_report_success_when_persistence_fails(client, valid_pdf_bytes):
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/1/file").mock(
        return_value=httpx.Response(200, content=valid_pdf_bytes)
    )
    respx.put(f"{DOCUMENTOS_URL}/api/v1/documents/1/extraction").mock(
        return_value=httpx.Response(503, json={"detail": "internal auth not configured"})
    )

    response = client.post("/api/v1/extract", json={"document_id": 1})

    assert response.status_code == 502
    assert "persistir" in response.json()["detail"]


@respx.mock
def test_extract_document_missing_during_persistence_returns_404(client, valid_pdf_bytes):
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/1/file").mock(
        return_value=httpx.Response(200, content=valid_pdf_bytes)
    )
    respx.put(f"{DOCUMENTOS_URL}/api/v1/documents/1/extraction").mock(return_value=httpx.Response(404))

    response = client.post("/api/v1/extract", json={"document_id": 1})

    assert response.status_code == 404


def test_health_check(client):
    assert client.get("/health").status_code == 200
