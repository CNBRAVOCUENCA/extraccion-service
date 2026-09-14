"""Configuración de logging (12-factor XI: logs como flujo de eventos a stdout).

Los logs salen por stdout en un formato consistente; el orquestador de
contenedores (Docker) los captura. No se escriben a archivos ni se rotan
desde la app — eso es responsabilidad del entorno de ejecución.
"""

import logging
import sys


def configurar_logging(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)
