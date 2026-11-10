"""Registro de esta instancia en el agente HTTP local de Consul."""

import ipaddress
import logging
import os
import socket
from urllib.parse import quote, urlsplit

import httpx

from App.config.settings import Settings

logger = logging.getLogger(__name__)

CONSUL_REQUEST_TIMEOUT_SECONDS = 2.0
HEALTH_CHECK_INTERVAL = "10s"
HEALTH_CHECK_TIMEOUT = "2s"
HEALTH_CHECK_DEREGISTER_AFTER = "1m"


class ConsulRegistrationError(RuntimeError):
    """Error de registro que no expone configuración sensible."""


class ConsulServiceRegistration:
    """Registra y elimina el servicio asociado a este proceso."""

    def __init__(self, settings: Settings):
        self.http_addr = settings.consul_http_addr.strip().rstrip("/")
        self.http_token = settings.consul_http_token
        self.service_name = settings.consul_service_name or settings.app_name
        self.service_port = settings.consul_service_port
        self.service_tags = [tag.strip() for tag in settings.consul_service_tags.split(",") if tag.strip()]
        self.service_address = settings.consul_service_address.strip()
        self.service_id = f"{self.service_name}-{socket.gethostname()}-{os.getpid()}"
        self._registered = False

    async def register(self) -> None:
        """Register with Consul; an empty address disables discovery."""
        if not self.http_addr:
            return

        try:
            if not self.service_address:
                self.service_address = _determine_routable_ip(self.http_addr)
            payload = {
                "Name": self.service_name,
                "ID": self.service_id,
                "Address": self.service_address,
                "Port": self.service_port,
                "Tags": self.service_tags,
                "Check": {
                    "HTTP": _health_check_url(self.service_address, self.service_port),
                    "Interval": HEALTH_CHECK_INTERVAL,
                    "Timeout": HEALTH_CHECK_TIMEOUT,
                    "DeregisterCriticalServiceAfter": HEALTH_CHECK_DEREGISTER_AFTER,
                },
            }
            await self._put("/v1/agent/service/register", json=payload)
        except Exception as exc:
            raise ConsulRegistrationError("Consul service registration failed") from exc

        self._registered = True

    async def deregister(self) -> None:
        """Remove the service during shutdown, logging failures without details."""
        if not self._registered:
            return

        try:
            await self._put(f"/v1/agent/service/deregister/{quote(self.service_id, safe='')}")
        except Exception as exc:
            logger.warning("Consul service deregistration failed (%s)", type(exc).__name__)
        finally:
            self._registered = False

    async def _put(self, path: str, *, json: dict | None = None) -> None:
        headers = {"X-Consul-Token": self.http_token} if self.http_token else None
        async with httpx.AsyncClient(timeout=CONSUL_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.put(f"{self.http_addr}{path}", json=json, headers=headers)
            response.raise_for_status()


def _health_check_url(address: str, port: int) -> str:
    """Format an HTTP health URL, including brackets for IPv6 literals."""
    host = f"[{address}]" if ":" in address and not address.startswith("[") else address
    return f"http://{host}:{port}/health"


def _determine_routable_ip(consul_http_addr: str) -> str:
    """Find the local interface selected for reaching the configured agent."""
    parsed = urlsplit(consul_http_addr)
    if not parsed.hostname:
        raise ValueError("CONSUL_HTTP_ADDR must include a host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    for family, socktype, protocol, _, sockaddr in socket.getaddrinfo(
        parsed.hostname, port, type=socket.SOCK_DGRAM
    ):
        try:
            with socket.socket(family, socktype, protocol) as probe:
                probe.connect(sockaddr)
                address = probe.getsockname()[0]
            local_ip = ipaddress.ip_address(address)
            if not local_ip.is_loopback and not local_ip.is_unspecified:
                return address
        except (OSError, ValueError):
            continue

    raise OSError("could not determine a routable local address for Consul")
