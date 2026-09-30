"""Tests del pool de extracción: caché y backpressure."""

from io import BytesIO

import pytest
from pypdf import PdfWriter

import App.services.extract_pool as ep
from App.services.extract_pool import ExtractionOverloaded, ExtractionPool


def _pdf_bytes(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class _FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def aclose(self):
        pass


async def test_cache_miss_luego_hit():
    pdf = _pdf_bytes(2)
    pool = ExtractionPool(workers=1, max_inflight=8, backend="pypdf", redis_client=_FakeRedis())
    result1, from_cache1 = await pool.extract(pdf)
    result2, from_cache2 = await pool.extract(pdf)
    assert from_cache1 is False
    assert from_cache2 is True
    assert result1 == result2
    assert result2["page_count"] == 2
    await pool.aclose()


async def test_backpressure_rechaza_con_overloaded(monkeypatch):
    import asyncio
    import time

    def slow(_bytes, backend="pypdf"):
        time.sleep(0.3)
        return ("texto", 1)

    monkeypatch.setattr(ep, "extract_content", slow)
    pool = ExtractionPool(workers=1, max_inflight=2, backend="pypdf", redis_client=None)

    async def call(i):
        try:
            await pool.extract(_pdf_bytes(1) + bytes([i]))
            return "ok"
        except ExtractionOverloaded:
            return "503"

    resultados = await asyncio.gather(*[call(i) for i in range(6)])
    await pool.aclose()
    assert resultados.count("ok") == 2
    assert resultados.count("503") == 4
