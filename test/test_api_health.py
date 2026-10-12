"""Tests de /health (liveness) y /ready (readiness) según el estado de Redis (TDD).

Redis es una caché opcional: su caída degrada el servicio pero no lo tumba.
"""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from App.config.settings import settings
from App.main import app


class FakeRedis:
    """Cliente Redis falso: ping/get/set configurables, sin red."""

    def __init__(self, fail: bool = False):
        self.fail = fail

    async def ping(self):
        if self.fail:
            raise ConnectionError("redis caído")
        return True

    async def get(self, key):
        if self.fail:
            raise ConnectionError("redis caído")
        return None

    async def set(self, key, value, ex=None):
        if self.fail:
            raise ConnectionError("redis caído")

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def _config_de_test():
    original_cache_enabled = settings.cache_enabled
    original_extractor_backend = settings.extractor_backend
    settings.cache_enabled = False
    # El CI instala [dev], no el extra fast que incluye PyMuPDF.
    settings.extractor_backend = "pypdf"
    yield
    settings.cache_enabled = original_cache_enabled
    settings.extractor_backend = original_extractor_backend


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _con_redis(client, redis):
    client.app.state.extraction_pool._redis = redis


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_health_es_liveness_y_no_consulta_redis(client):
    _con_redis(client, FakeRedis(fail=True))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_sin_cache_informa_disabled(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["cache"] == "disabled"
    assert resp.json()["status"] == "ok"


def test_ready_con_redis_sano_informa_up(client):
    _con_redis(client, FakeRedis())
    body = client.get("/ready").json()
    assert body["cache"] == "up"
    assert body["status"] == "ok"


def test_ready_con_redis_caido_sigue_200_pero_degraded(client):
    _con_redis(client, FakeRedis(fail=True))
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["cache"] == "down"
    assert resp.json()["status"] == "degraded"


def test_extract_sigue_funcionando_con_redis_caido(client):
    _con_redis(client, FakeRedis(fail=True))
    resp = client.post("/extract", files={"file": ("x.pdf", _pdf_bytes(), "application/pdf")})
    assert resp.status_code == 200
    assert resp.headers["X-Cache"] == "MISS"
