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


_BULLETS = ("•", "·", "●", "▪", "■", "◦", "‣", "–", "-", "*")
_BOLD_FLAG = 16  # bit de negrita en los spans de PyMuPDF


class PyMuPdfExtractor:
    """Convierte el PDF a Markdown con PyMuPDF (fitz). Rápido y liviano en CPU.

    Heurística (sin librerías extra):
    - El tamaño de letra más frecuente es el cuerpo del texto.
    - Líneas con letra bastante más grande que el cuerpo -> títulos #, ## o ###.
    - Spans en negrita -> **texto**.
    - Líneas que empiezan con viñeta -> ítems de lista "- ".
    - Cada bloque de texto del PDF es un párrafo.
    """

    @staticmethod
    def extract_with_pages(pdf_bytes: bytes) -> tuple[str, int]:
        try:
            import pymupdf  # PyMuPDF
        except ImportError as exc:  # pragma: no cover
            raise PdfExtractionError(
                "El backend 'pymupdf' no está instalado (pip install pymupdf)"
            ) from exc
        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise PdfPasswordRequiredError("El PDF requiere una contraseña")
                page_count = doc.page_count
                pages = [page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT) for page in doc]
            content = _pages_to_markdown(pages)
            return content, page_count
        except PdfPasswordRequiredError:
            raise
        except Exception as exc:
            raise PdfExtractionError(f"No se pudo extraer el texto del PDF: {exc}") from exc


def _body_font_size(pages: list[dict]) -> float:
    """Tamaño de letra más frecuente (ponderado por cantidad de caracteres)."""
    counts: dict[float, int] = {}
    for page in pages:
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 0), 1)
                    counts[size] = counts.get(size, 0) + len(span.get("text", "").strip())
    return max(counts, key=counts.get) if counts else 0.0


def _heading_prefix(size: float, body: float) -> str:
    if body <= 0:
        return ""
    ratio = size / body
    if ratio >= 1.6:
        return "# "
    if ratio >= 1.3:
        return "## "
    if ratio >= 1.15:
        return "### "
    return ""


def _line_to_markdown(line: dict) -> tuple[str, float]:
    """Devuelve (texto Markdown de la línea, tamaño de letra máximo)."""
    parts: list[str] = []
    max_size = 0.0
    for span in line.get("spans", []):
        text = span.get("text", "")
        if not text.strip():
            parts.append(text)
            continue
        max_size = max(max_size, span.get("size", 0))
        if span.get("flags", 0) & _BOLD_FLAG:
            lead = text[: len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            text = f"{lead}**{text.strip()}**{trail}"
        parts.append(text)
    return "".join(parts).strip(), max_size


def _pages_to_markdown(pages: list[dict]) -> str:
    body = _body_font_size(pages)
    out: list[str] = []
    for page in pages:
        for block in page.get("blocks", []):
            lines = [_line_to_markdown(line) for line in block.get("lines", [])]
            lines = [(text, size) for text, size in lines if text]
            if not lines:
                continue
            first_size = max(size for _, size in lines)
            prefix = _heading_prefix(first_size, body)
            if prefix:
                title = " ".join(text.replace("**", "") for text, _ in lines)
                out.append(prefix + title)
                continue
            paragraph: list[str] = []
            for text, _ in lines:
                plain = text.replace("**", "").lstrip()
                if plain[:1] in _BULLETS and len(plain) > 1 and plain[1:2] == " ":
                    if paragraph:
                        out.append(" ".join(paragraph))
                        paragraph = []
                    out.append("- " + plain[2:].strip())
                else:
                    paragraph.append(text)
            if paragraph:
                out.append(" ".join(paragraph))
    return "\n\n".join(out).strip()


def extract_content(pdf_bytes: bytes, backend: str = "pypdf") -> tuple[str, int]:
    """Despacha al backend elegido y devuelve (content, page_count)."""
    if backend == "pymupdf":
        return PyMuPdfExtractor.extract_with_pages(pdf_bytes)
    return PdfTextExtractor.extract_with_pages(pdf_bytes)
