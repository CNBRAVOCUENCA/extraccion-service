"""Extracción de texto desde los bytes de un PDF.

Dos backends intercambiables (patrón Strategy, principio Open/Closed):
- "pypdf": puro Python, ya venía en el proyecto.
- "pymupdf": mucho más rápido y de menor consumo de CPU (recomendado para
  superar el benchmark del profesor). Se usa solo si está instalado.

Todos exponen la misma interfaz: extract(bytes) -> str y
extract_with_pages(bytes) -> (content, page_count).
"""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError

from App.exceptions import PdfExtractionError, PdfPasswordRequiredError


class PdfTextExtractor:
    """Extrae texto con pypdf (backend por defecto)."""

    @staticmethod
    def extract(pdf_bytes: bytes) -> str:
        content, _ = PdfTextExtractor.extract_with_pages(pdf_bytes)
        return content

    @staticmethod
    def extract_with_pages(pdf_bytes: bytes) -> tuple[str, int]:
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            pages_text = [page.extract_text() or "" for page in reader.pages]
            content = "\n\n".join(pages_text).strip()
            return content, page_count
        except FileNotDecryptedError as exc:
            raise PdfPasswordRequiredError("El PDF requiere una contraseña") from exc
        except (PdfExtractionError, PdfPasswordRequiredError):
            raise
        except Exception as exc:
            raise PdfExtractionError(f"No se pudo extraer el texto del PDF: {exc}") from exc


class PyMuPdfExtractor:
    """Extrae texto con PyMuPDF (fitz). Más rápido y liviano en CPU."""

    @staticmethod
    def extract_with_pages(pdf_bytes: bytes) -> tuple[str, int]:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover
            raise PdfExtractionError(
                "El backend 'pymupdf' no está instalado (pip install pymupdf)"
            ) from exc
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise PdfPasswordRequiredError("El PDF requiere una contraseña")
                page_count = doc.page_count
                parts = [page.get_text() for page in doc]
            content = "\n\n".join(parts).strip()
            return content, page_count
        except PdfPasswordRequiredError:
            raise
        except Exception as exc:
            raise PdfExtractionError(f"No se pudo extraer el texto del PDF: {exc}") from exc


def extract_content(pdf_bytes: bytes, backend: str = "pypdf") -> tuple[str, int]:
    """Despacha al backend elegido y devuelve (content, page_count)."""
    if backend == "pymupdf":
        return PyMuPdfExtractor.extract_with_pages(pdf_bytes)
    return PdfTextExtractor.extract_with_pages(pdf_bytes)
