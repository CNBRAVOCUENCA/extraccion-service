# extraccion-service

Microservicio de **extracción de texto de PDFs**, segundo de la migración del monolito
`El-Destripador-de-PDFs` hacia microservicios.

Recibe el ID de un documento, le pide el archivo PDF al microservicio
`documentos-service` por HTTP, extrae el texto plano con `pypdf`, y lo devuelve.
**No persiste nada** (no tiene base de datos propia).

## Arquitectura (capas)

```
App/
├── api/Routes/extraction.py      # POST /extract
├── api/exception_handlers.py     # excepciones de dominio -> HTTP
├── services/documentos_client.py # cliente HTTP hacia documentos-service
├── services/extraction_service.py# orquesta cliente + extractor
├── utils/pdf_extractor.py        # extracción con pypdf
├── models/ · schemas/            # dominio y DTOs
└── config/settings.py
test/                              # 11 tests (unitarios + integración)
```

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/extract` | Recibe `{"document_id": N}`, devuelve `{document_id, extracted_text, char_count}` |
| GET | `/health` | Health check |

## Errores

| Situación | HTTP |
|---|---|
| Documento inexistente en documentos-service | 404 |
| PDF corrupto / no se puede leer | 422 |
| documentos-service caído o con error 5xx | 502 |

El cliente HTTP (`documentos_client.py`) es el punto donde se agregarán Retry y
Circuit Breaker al integrar la Saga.

## Configuración

Copiar `.env.example` a `.env`. Variable clave: `DOCUMENTOS_SERVICE_URL`
(por defecto `http://localhost:8001`).

## Correr los tests

Con **uv** (recomendado, más rápido y con `uv.lock` para versiones reproducibles):

```bash
uv sync --extra dev
uv run --extra dev pytest test/ -v
```

O con pip tradicional:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest test/ -v
```

## Stack

Python 3.12+ · FastAPI · pypdf · httpx · pytest + respx
