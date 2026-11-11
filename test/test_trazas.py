"""Trazas OpenTelemetry (prompt 9): spans por petición y x-trace-id correlacionado."""

from App.telemetry import install_telemetry
from App.tracing import configurar_trazas
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _app_con_trazas():
    app = FastAPI()
    install_telemetry(app, "servicio-prueba")

    @app.get("/eco")
    def eco() -> dict:
        return {"ok": True}

    exporter = InMemorySpanExporter()
    configurar_trazas(app, "servicio-prueba", exporter=exporter, processor_factory=SimpleSpanProcessor)
    return app, exporter


def test_sin_endpoint_las_trazas_quedan_desactivadas(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert configurar_trazas(FastAPI(), "x") is None


def test_cada_peticion_genera_un_span_y_el_x_trace_id_coincide():
    app, exporter = _app_con_trazas()
    try:
        respuesta = TestClient(app).get("/eco")
        spans = exporter.get_finished_spans()
        assert respuesta.status_code == 200
        assert spans, "no se exportó ningún span"
        trace_ids = {format(s.context.trace_id, "032x") for s in spans}
        assert respuesta.headers["x-trace-id"] in trace_ids
        assert all(s.resource.attributes["service.name"] == "servicio-prueba" for s in spans)
    finally:
        HTTPXClientInstrumentor().uninstrument()


def test_continua_la_traza_que_llega_en_traceparent():
    app, exporter = _app_con_trazas()
    try:
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        respuesta = TestClient(app).get("/eco", headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"})
        assert respuesta.headers["x-trace-id"] == trace_id
        assert any(format(s.context.trace_id, "032x") == trace_id for s in exporter.get_finished_spans())
    finally:
        HTTPXClientInstrumentor().uninstrument()


def test_health_y_metrics_no_generan_spans():
    app, exporter = _app_con_trazas()
    try:
        cliente = TestClient(app)
        cliente.get("/metrics")
        assert exporter.get_finished_spans() == ()
    finally:
        HTTPXClientInstrumentor().uninstrument()


def test_backend_caido_no_frena_el_servicio():
    """Exporter real apuntando a un puerto sin nada: la petición responde igual."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    app = FastAPI()
    install_telemetry(app, "servicio-prueba")

    @app.get("/eco")
    def eco() -> dict:
        return {"ok": True}

    provider = configurar_trazas(
        app, "servicio-prueba", exporter=OTLPSpanExporter(endpoint="http://127.0.0.1:9/v1/traces", timeout=1)
    )
    try:
        assert TestClient(app).get("/eco").status_code == 200
    finally:
        provider.shutdown()
        HTTPXClientInstrumentor().uninstrument()


def test_metricas_usan_la_plantilla_de_ruta_y_no_la_url_concreta():
    """Evita alta cardinalidad: /items/1 y /items/2 cuentan en la misma serie."""
    from prometheus_client import REGISTRY

    app = FastAPI()
    install_telemetry(app, "servicio-cardinalidad")

    @app.get("/items/{item_id}")
    def item(item_id: int) -> dict:
        return {"id": item_id}

    cliente = TestClient(app)
    cliente.get("/items/1")
    cliente.get("/items/2")
    cliente.get("/no-existe/123")
    muestras = [
        m.labels["route"]
        for metrica in REGISTRY.collect()
        if metrica.name == "http_requests"
        for m in metrica.samples
        if m.labels.get("service") == "servicio-cardinalidad" and m.name == "http_requests_total"
    ]
    assert set(muestras) == {"/items/{item_id}", "sin_ruta"}
