"""Pruebas del registro de instancias en Consul."""

import json
import re
import socket

import httpx
import pytest
import respx
from App.config.settings import Settings
from App.services import consul_registration
from App.services.consul_registration import ConsulRegistrationError, ConsulServiceRegistration
from fastapi import FastAPI

CONSUL_URL = "http://consul:8500"


def consul_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


@respx.mock
async def test_register_sends_service_check_tags_and_token():
    route = respx.put(f"{CONSUL_URL}/v1/agent/service/register").mock(return_value=httpx.Response(200))
    registration = ConsulServiceRegistration(
        consul_settings(
            app_name="extractor",
            consul_http_addr=CONSUL_URL,
            consul_http_token="private-consul-token",
            consul_service_tags="traefik.enable=true, edge,",
            consul_service_address="10.20.0.15",
        )
    )

    await registration.register()

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert request.headers["X-Consul-Token"] == "private-consul-token"
    assert payload == {
        "Name": "extractor",
        "ID": registration.service_id,
        "Address": "10.20.0.15",
        "Port": 8000,
        "Tags": ["traefik.enable=true", "edge"],
        "Check": {
            "HTTP": "http://10.20.0.15:8000/health",
            "Interval": "10s",
            "Timeout": "2s",
            "DeregisterCriticalServiceAfter": "1m",
        },
    }
    assert socket.gethostname() in payload["ID"]


@respx.mock
async def test_empty_consul_address_disables_registration():
    registration = ConsulServiceRegistration(consul_settings(consul_http_addr=""))

    await registration.register()
    await registration.deregister()

    assert not respx.calls


def test_routable_ip_comes_from_interface_selected_for_consul_route(monkeypatch):
    def resolve(host, port, **kwargs):
        assert host == "consul"
        assert kwargs == {"type": socket.SOCK_DGRAM}
        return [
            (socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP, "", ("192.0.2.1", port))
        ]

    monkeypatch.setattr(consul_registration.socket, "getaddrinfo", resolve)

    class ProbeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            assert exc_type is None and exc_value is None and traceback is None
            return None

        def connect(self, address):
            assert address == ("192.0.2.1", 8500)

        def getsockname(self):
            return ("172.20.0.8", 50000)

    def create_socket(family, socktype, protocol):
        assert (family, socktype, protocol) == (socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        return ProbeSocket()

    monkeypatch.setattr(consul_registration.socket, "socket", create_socket)

    assert consul_registration._determine_routable_ip(CONSUL_URL) == "172.20.0.8"


@respx.mock
async def test_register_uses_detected_routable_ip_for_service_and_health_check(monkeypatch):
    route = respx.put(f"{CONSUL_URL}/v1/agent/service/register").mock(return_value=httpx.Response(200))
    monkeypatch.setattr(consul_registration, "_determine_routable_ip", lambda _: "172.20.0.8")
    registration = ConsulServiceRegistration(consul_settings(consul_http_addr=CONSUL_URL))

    await registration.register()

    payload = json.loads(route.calls.last.request.content)
    assert payload["Address"] == "172.20.0.8"
    assert payload["Check"]["HTTP"] == "http://172.20.0.8:8000/health"


@respx.mock
async def test_app_lifespan_registers_then_deregisters_and_closes_pool(monkeypatch):
    registration_route = respx.put(
        re.compile(r"http://consul:8500/v1/agent/service/(register|deregister/.+)")
    ).mock(return_value=httpx.Response(200))
    monkeypatch.setattr(
        "App.main.settings",
        consul_settings(consul_http_addr=CONSUL_URL, consul_service_address="10.20.0.15"),
    )

    class Pool:
        closed = False

        async def aclose(self):
            self.closed = True

    pool = Pool()
    monkeypatch.setattr("App.main.ExtractionPool", lambda: pool)
    app = FastAPI()

    from App.main import lifespan

    async with lifespan(app):
        assert not pool.closed
        assert registration_route.call_count == 1

    assert pool.closed
    assert registration_route.call_count == 2
    assert "/service/deregister/" in str(registration_route.calls.last.request.url)


@respx.mock
async def test_registration_failure_surfaces_startup_error_without_token():
    respx.put(f"{CONSUL_URL}/v1/agent/service/register").mock(return_value=httpx.Response(500))
    registration = ConsulServiceRegistration(
        consul_settings(
            consul_http_addr=CONSUL_URL,
            consul_http_token="never-log-this-token",
            consul_service_address="10.20.0.15",
        )
    )

    with pytest.raises(ConsulRegistrationError) as exc_info:
        await registration.register()

    assert "never-log-this-token" not in str(exc_info.value)
    assert not registration._registered


@respx.mock
async def test_deregistration_failure_logs_only_sanitized_error(caplog):
    respx.put(f"{CONSUL_URL}/v1/agent/service/register").mock(return_value=httpx.Response(200))
    respx.put(re.compile(r"http://consul:8500/v1/agent/service/deregister/.+")).mock(
        return_value=httpx.Response(500)
    )
    registration = ConsulServiceRegistration(
        consul_settings(
            consul_http_addr=CONSUL_URL,
            consul_http_token="never-log-this-token",
            consul_service_address="10.20.0.15",
        )
    )
    await registration.register()

    await registration.deregister()

    assert "Consul service deregistration failed" in caplog.text
    assert "HTTPStatusError" in caplog.text
    assert "never-log-this-token" not in caplog.text
