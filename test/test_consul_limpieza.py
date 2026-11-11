"""Limpieza de registros viejos en Consul antes de registrar la instancia (prompt 8)."""

import asyncio

import httpx
from App.services.consul_registration import purge_stale_instances


def _con_transporte(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        "App.services.consul_registration.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_borra_solo_los_registros_viejos_con_la_misma_ip_y_puerto(monkeypatch):
    pedidos = []

    def handler(request):
        pedidos.append((request.method, request.url.path))
        if request.url.path == "/v1/agent/services":
            return httpx.Response(
                200,
                json={
                    "yo": {"Address": "10.0.0.5", "Port": 8000},
                    "viejo": {"Address": "10.0.0.5", "Port": 8000},
                    "otro-servicio-misma-ip": {"Address": "10.0.0.5", "Port": 8000},
                    "otra-ip": {"Address": "10.0.0.9", "Port": 8000},
                    "otro-puerto": {"Address": "10.0.0.5", "Port": 9000},
                },
            )
        return httpx.Response(200)

    _con_transporte(monkeypatch, handler)
    borrados = asyncio.run(purge_stale_instances("http://consul:8500", {}, "10.0.0.5", 8000, "yo"))

    assert borrados == 2
    assert [p for m, p in pedidos if m == "PUT"] == [
        "/v1/agent/service/deregister/viejo",
        "/v1/agent/service/deregister/otro-servicio-misma-ip",
    ]


def test_si_consul_no_responde_no_rompe_el_arranque(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("sin consul")

    _con_transporte(monkeypatch, handler)
    assert asyncio.run(purge_stale_instances("consul:8500", {}, "10.0.0.5", 8000, "yo")) == 0
