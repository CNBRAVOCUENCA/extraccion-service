"""Trazas distribuidas con OpenTelemetry (prompt 9).

- Cada petición HTTP entrante crea un span (instrumentación de FastAPI) y cada
  llamada saliente con httpx crea un span hijo e inyecta el header estándar W3C
  `traceparent`, así una misma traza recorre orquestador -> servicios.
- Los spans se exportan por OTLP/HTTP al backend configurado en
  `OTEL_EXPORTER_OTLP_ENDPOINT` (Jaeger en el stack). Sin esa variable las trazas
  quedan desactivadas y el servicio funciona igual.
- La exportación es en segundo plano (BatchSpanProcessor) con timeout corto: si el
  backend de observabilidad está caído, los spans se descartan y el flujo de
  negocio no se frena.
- No se registran cuerpos, PDFs, textos, prompts ni headers: solo método, ruta,
  código de estado y duración. /health, /ready y /metrics no generan spans.
"""

import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

logger = logging.getLogger(__name__)

RUTAS_EXCLUIDAS = "health,ready,metrics"
EXPORT_TIMEOUT_SECONDS = 2


def configurar_trazas(
    app: FastAPI,
    service_name: str,
    exporter: SpanExporter | None = None,
    processor_factory=BatchSpanProcessor,
) -> TracerProvider | None:
    """Activa las trazas si hay endpoint OTLP (o un exporter inyectado en tests)."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
    if exporter is None and not endpoint:
        return None
    if exporter is None:
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", timeout=EXPORT_TIMEOUT_SECONDS)

    provider = TracerProvider(
        resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME") or service_name})
    )
    provider.add_span_processor(processor_factory(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=RUTAS_EXCLUIDAS)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    logger.info("Trazas OpenTelemetry activas para %s", service_name)
    return provider


def trace_id_actual() -> str | None:
    """Trace id (32 hex) del span activo, o None si no hay traza activa."""
    contexto = trace.get_current_span().get_span_context()
    if not contexto.is_valid:
        return None
    return format(contexto.trace_id, "032x")
