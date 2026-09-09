"""Pruebas de integración de la API de Extracción, mockeando documentos-service."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

DOCUMENTOS_URL = "http://documentos-service-test:9999"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DOCUMENTOS_SERVICE_URL", DOCUMENTOS_URL)
    from App.main import app
    return TestClient(app)


@respx.mock
def test_extract_success(client, valid_pdf_bytes):
    respx.get(f"{DOCUMENTOS_URL}/api/v1/documents/1/file").mock(
        return_value=httpx.Response(200, content=valid_pdf_bytes)
    )
    response = client.post("/api/v1/extract", json={"document_id": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == 1
    assert "Hola mundo" in body["extracted_text"]


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


def test_health_check(client):
    assert client.get("/health").status_code == 200
