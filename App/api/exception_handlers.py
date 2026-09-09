"""Traduce excepciones de dominio a respuestas HTTP, en un solo lugar (DRY)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from App.exceptions import (
    DocumentFetchError,
    DocumentNotFoundUpstreamError,
    PdfExtractionError,
    PdfPasswordRequiredError,
)

_STATUS_MAP = {
    DocumentNotFoundUpstreamError: 404,
    PdfPasswordRequiredError: 401,
    PdfExtractionError: 422,
    DocumentFetchError: 502,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_class, status_code in _STATUS_MAP.items():
        app.add_exception_handler(exc_class, _make_handler(status_code))


def _make_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})
    return handler
