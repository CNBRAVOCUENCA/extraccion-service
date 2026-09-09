"""Cliente HTTP para consumir documentos-service.

Nota de arquitectura: esta es la pieza de comunicación entre microservicios.
Es el punto donde, al integrar el patrón Saga, se agregarían Retry y
Circuit Breaker.
"""

import base64
import binascii

import httpx
from pydantic import ValidationError

from App.exceptions import DocumentFetchError, DocumentNotFoundUpstreamError
from App.schemas.extraction import DocumentFileResponse


class DocumentosClient:
    """Cliente para el microservicio documentos-service."""

    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def get_document_file(self, document_id: int) -> bytes:
        """Obtiene el contenido binario del PDF de un documento."""
        url = f"{self.base_url}/api/v1/documents/{document_id}/file"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http_client:
            try:
                response = await http_client.get(url)
            except httpx.HTTPError as exc:
                raise DocumentFetchError(f"No se pudo contactar a documentos-service: {exc}") from exc

        if response.status_code == 404:
            raise DocumentNotFoundUpstreamError(f"Documento {document_id} no encontrado en documentos-service")
        if response.status_code >= 400:
            raise DocumentFetchError(
                f"documentos-service respondió {response.status_code} al pedir el documento {document_id}"
            )
        try:
            upstream_file = DocumentFileResponse.model_validate(response.json())
            return base64.b64decode(upstream_file.file_base64, validate=True)
        except (ValueError, TypeError, binascii.Error, ValidationError) as exc:
            raise DocumentFetchError(
                f"documentos-service devolvió un archivo Base64 inválido para el documento {document_id}"
            ) from exc
