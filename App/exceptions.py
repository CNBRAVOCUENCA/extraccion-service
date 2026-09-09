"""Excepciones de dominio del microservicio de Extracción de texto."""


class ExtractionException(Exception):
    """Excepción base para errores de negocio de este servicio."""


class PdfExtractionError(ExtractionException):
    """No se pudo extraer texto del PDF (archivo corrupto o formato inválido)."""


class PdfPasswordRequiredError(ExtractionException):
    """El PDF requiere una contraseña para poder extraer su contenido."""


class DocumentFetchError(ExtractionException):
    """No se pudo obtener el documento desde documentos-service."""


class DocumentNotFoundUpstreamError(ExtractionException):
    """El documento solicitado no existe en documentos-service."""
