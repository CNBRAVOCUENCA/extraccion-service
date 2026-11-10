"""Cliente HTTP para consumir documentos-service.

Nota de arquitectura: esta es la pieza de comunicación entre microservicios.
Es el punto donde, al integrar el patrón Saga, se agregarían Retry y
Circuit Breaker.
"""

import httpx

from App.exceptions import DocumentFetchError, DocumentNotFoundUpstreamError


class DocumentosClient:
    """Cliente para el microservicio documentos-service."""

    def __init__(self, base_url: str, timeout_seconds: float = 60.0, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key

    async def get_document_file(self, document_id: int) -> bytes:
        """Obtiene el contenido binario del PDF de un documento.

        documentos-service devuelve el PDF como bytes crudos (media_type
        application/pdf), no como JSON — por eso se leen directamente de
        response.content, sin decodificar nada.
        """
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
        return response.content

    async def persist_extracted_text(self, document_id: int, extracted_text: str) -> None:
        """Guarda el resultado en el servicio dueño antes de confirmar la extracción."""
        url = f"{self.base_url}/api/v1/documents/{document_id}/extraction"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http_client:
            try:
                response = await http_client.put(
                    url,
                    json={"extracted_text": extracted_text},
                    headers={"X-Internal-API-Key": self.api_key},
                )
            except httpx.HTTPError as exc:
                raise DocumentFetchError(
                    f"No se pudo persistir el resultado en documentos-service: {exc}"
                ) from exc

        if response.status_code == 404:
            raise DocumentNotFoundUpstreamError(
                f"Documento {document_id} no encontrado en documentos-service al persistir la extracción"
            )
        if response.status_code >= 400:
            raise DocumentFetchError(
                "documentos-service respondió "
                f"{response.status_code} al persistir el resultado del documento {document_id}"
            )

        try:
            persisted = response.json()
        except ValueError as exc:
            raise DocumentFetchError("documentos-service devolvió una confirmación inválida") from exc
        if (
            not isinstance(persisted, dict)
            or persisted.get("id") != document_id
            or persisted.get("extracted_text") != extracted_text
            or persisted.get("is_processed") is not True
        ):
            raise DocumentFetchError("documentos-service no confirmó la persistencia del resultado")
