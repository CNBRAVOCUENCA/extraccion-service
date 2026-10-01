"""Tests de la conversión PDF -> Markdown (backend pymupdf)."""

import pytest

pymupdf = pytest.importorskip("pymupdf")

from App.utils.pdf_extractor import extract_content  # noqa: E402


def _pdf_con_estructura() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Titulo Principal", fontsize=24)
    page.insert_text((72, 120), "Subtitulo", fontsize=15)
    page.insert_text((72, 150), "Texto normal del cuerpo del documento.", fontsize=11)
    page.insert_text((72, 175), "Mas texto del cuerpo para el parrafo.", fontsize=11)
    page.insert_text((72, 210), "Negrita aca", fontsize=11, fontname="hebo")
    return doc.tobytes()


def test_titulos_se_convierten_en_encabezados_markdown():
    content, page_count = extract_content(_pdf_con_estructura(), "pymupdf")
    assert page_count == 1
    assert "# Titulo Principal" in content
    assert "## Subtitulo" in content


def test_cuerpo_queda_como_parrafo_y_negrita_con_asteriscos():
    content, _ = extract_content(_pdf_con_estructura(), "pymupdf")
    assert "Texto normal del cuerpo del documento." in content
    assert "**Negrita aca**" in content
    assert "# Texto normal" not in content
