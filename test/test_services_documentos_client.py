"""Pruebas unitarias para DocumentosClient (llamada HTTP a documentos-service)."""

import json

import httpx
import pytest
import respx
from App.exceptions import DocumentFetchError, DocumentNotFoundUpstreamError
from App.services.documentos_client import DocumentosClient

BASE_URL = "http://documentos-service:8000"


@respx.mock
async def test_get_document_file_returns_bytes():
    respx.get(f"{BASE_URL}/api/v1/documents/1/file").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4...")
    )
    client = DocumentosClient(base_url=BASE_URL)
    content = await client.get_document_file(1)
    assert content == b"%PDF-1.4..."


@respx.mock
async def test_get_document_file_raises_not_found_on_404():
    respx.get(f"{BASE_URL}/api/v1/documents/999/file").mock(return_value=httpx.Response(404))
    client = DocumentosClient(base_url=BASE_URL)
    with pytest.raises(DocumentNotFoundUpstreamError):
        await client.get_document_file(999)


@respx.mock
async def test_get_document_file_raises_fetch_error_on_5xx():
    respx.get(f"{BASE_URL}/api/v1/documents/1/file").mock(return_value=httpx.Response(500))
    client = DocumentosClient(base_url=BASE_URL)
    with pytest.raises(DocumentFetchError):
        await client.get_document_file(1)

@respx.mock
async def test_persist_extracted_text_sends_internal_key_and_validates_confirmation():
    route = respx.put(f"{BASE_URL}/api/v1/documents/1/extraction").mock(
        return_value=httpx.Response(
            200,
            json={"id": 1, "extracted_text": "texto extraído", "is_processed": True},
        )
    )
    client = DocumentosClient(base_url=BASE_URL, api_key="internal-secret")

    await client.persist_extracted_text(1, "texto extraído")

    assert route.calls.last.request.headers["X-Internal-API-Key"] == "internal-secret"
    assert json.loads(route.calls.last.request.content) == {"extracted_text": "texto extraído"}


@respx.mock
async def test_persist_extracted_text_maps_missing_document():
    respx.put(f"{BASE_URL}/api/v1/documents/999/extraction").mock(return_value=httpx.Response(404))
    client = DocumentosClient(base_url=BASE_URL, api_key="internal-secret")

    with pytest.raises(DocumentNotFoundUpstreamError):
        await client.persist_extracted_text(999, "texto")


@respx.mock
async def test_persist_extracted_text_maps_upstream_error():
    respx.put(f"{BASE_URL}/api/v1/documents/1/extraction").mock(return_value=httpx.Response(503))
    client = DocumentosClient(base_url=BASE_URL, api_key="internal-secret")

    with pytest.raises(DocumentFetchError):
        await client.persist_extracted_text(1, "texto")
