"""Extracción de texto plano desde los bytes de un PDF."""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError

from App.exceptions import PdfExtractionError, PdfPasswordRequiredError


class PdfTextExtractor:
    """Extrae el texto de todas las páginas de un PDF."""

    @staticmethod
    def extract(pdf_bytes: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages_text).strip()
        except FileNotDecryptedError as exc:
            raise PdfPasswordRequiredError("El PDF requiere una contraseña") from exc
        except Exception as exc:
            raise PdfExtractionError(f"No se pudo extraer el texto del PDF: {exc}") from exc
