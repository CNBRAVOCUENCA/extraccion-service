"""Configuración de logging (12-factor XI: logs como flujo de eventos a stdout).

Los logs salen por stdout en un formato consistente; el orquestador de
contenedores (Docker) los captura. No se escriben a archivos ni se rotan
desde la app — eso es responsabilidad del entorno de ejecución.
"""

import logging
import sys

from App.telemetry import get_current_trace_id


class TraceContextFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = get_current_trace_id() or "-"
        return True


def configurar_logging(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceContextFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] trace_id=%(trace_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)
