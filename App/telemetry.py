from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

TRACE_ID_HEADER = "x-trace-id"
TRACEPARENT_HEADER = "traceparent"
TRACE_ID_VAR: ContextVar[str] = ContextVar("trace_id", default="")

REQUESTS = Counter(
    "http_requests_total",
    "Total de peticiones HTTP por servicio, método, ruta y estado.",
    labelnames=("service", "method", "route", "status"),
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latencia de peticiones HTTP por servicio, método, ruta y estado.",
    labelnames=("service", "method", "route", "status"),
)


def _generate_trace_id() -> str:
    return uuid.uuid4().hex


def _extract_trace_id(raw_trace: str | None) -> str | None:
    if not raw_trace:
        return None
    if raw_trace.startswith("00-"):
        parts = raw_trace.split("-")
        if len(parts) == 4 and len(parts[1]) == 32:
            return parts[1]
    if len(raw_trace) >= 8:
        return raw_trace
    return None


def get_current_trace_id() -> str:
    trace_id = TRACE_ID_VAR.get()
    if trace_id:
        return trace_id
    trace_id = _generate_trace_id()
    TRACE_ID_VAR.set(trace_id)
    return trace_id


def request_headers_for_outgoing() -> dict[str, str]:
    trace_id = get_current_trace_id()
    span_id = uuid.uuid4().hex[:16]
    return {
        TRACE_ID_HEADER: trace_id,
        TRACEPARENT_HEADER: f"00-{trace_id}-{span_id}-01",
    }


def set_trace_context(request: Request) -> tuple[str, object]:
    incoming = request.headers.get(TRACEPARENT_HEADER) or request.headers.get(TRACE_ID_HEADER)
    trace_id = _extract_trace_id(incoming) or _generate_trace_id()
    token = TRACE_ID_VAR.set(trace_id)
    request.state.trace_id = trace_id
    return trace_id, token


def install_telemetry(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        route = request.scope.get("route")
        route_name = getattr(route, "path", request.url.path)
        trace_id, token = set_trace_context(request)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            status = "500"
            REQUESTS.labels(service=service_name, method=request.method, route=route_name, status=status).inc()
            REQUEST_LATENCY.labels(
                service=service_name, method=request.method, route=route_name, status=status
            ).observe(time.perf_counter() - started)
            raise
        else:
            status = str(response.status_code)
            REQUESTS.labels(service=service_name, method=request.method, route=route_name, status=status).inc()
            REQUEST_LATENCY.labels(
                service=service_name, method=request.method, route=route_name, status=status
            ).observe(time.perf_counter() - started)
            response.headers[TRACE_ID_HEADER] = trace_id
            response.headers["x-service"] = service_name
            return response
        finally:
            TRACE_ID_VAR.reset(token)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Any:
        from fastapi.responses import Response

        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
