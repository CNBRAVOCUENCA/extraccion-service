# extraccion-service

Microservicio de **extracción de texto de PDFs**, segundo de la migración del monolito
`El-Destripador-de-PDFs` hacia microservicios.

Tiene **dos modos de uso**:

1. **Síncrono** (`POST /extract`): recibe el **PDF binario directo** y devuelve el
   texto extraído en la misma respuesta. Es el endpoint usado en el Trabajo
   Práctico de test de carga/estrés.
2. **Asíncrono** (`POST /api/v1/extract`): recibe un `document_id`, le pide el PDF
   a `documentos-service` por HTTP y extrae el texto. Es el que usa la Saga del
   orquestador.

**No persiste nada** (no tiene base de datos propia). El caché de resultados es
opcional y vive en Redis.

## Arquitectura (capas)

```
App/
├── api/Routes/extract_sync.py     # POST /extract (síncrono, PDF directo)
├── api/Routes/extraction.py       # POST /api/v1/extract (asíncrono, document_id)
├── api/exception_handlers.py      # excepciones de dominio -> HTTP
├── services/extract_pool.py       # pool de workers + backpressure + caché Redis
├── services/documentos_client.py  # cliente HTTP hacia documentos-service
├── services/extraction_service.py # orquesta cliente + extractor (flujo Saga)
├── utils/pdf_extractor.py         # extracción con pypdf / pymupdf (intercambiable)
├── models/ · schemas/             # dominio y DTOs
└── config/settings.py             # configuración por variables de entorno
test/                              # tests unitarios + integración
tests/stress/                      # pruebas de carga (k6 y Vegeta) + PDFs
```

## Endpoints

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| POST | `/extract` | PDF binario (multipart `file` o body crudo) | `{"content": "<Markdown>", "page_count"}` |
| POST | `/api/v1/extract` | `{"document_id": N}` | `{document_id, extracted_text, char_count}` |
| GET | `/health` | — | `{status, service}` |
| GET | `/` | — | Página web para probar `/extract` |

El endpoint síncrono responde con header `X-Cache: HIT|MISS` y, si el servicio
está saturado, con **503** (backpressure) en lugar de encolar y expirar.

## Test de carga y estrés (TP)

Sistema completo (5 réplicas + Traefik + Redis, con límites de CPU/RAM):

```powershell
docker compose up --build
```

Pruebas (ver `tests/stress/README.md` e `INFORME.md`):

```powershell
cd tests/stress
.\vegeta\run-vegeta.ps1   # carga fija: 50 req/s durante 30s, rotando 4 PDFs
.\k6\run-k6.ps1           # spike: rampa a 100 VUs
```

## Probarlo a mano

**Página web.** Con el stack levantado, abrir **http://localhost**: se elige un PDF
(o se arrastra), se envía a `/extract` y se ve el Markdown renderizado y en crudo,
junto con las páginas, el tiempo de respuesta y si salió de caché. Abajo muestra
la tabla de resultados de las pruebas de carga.

**Postman.** Importar `tests/postman/extractor.postman_collection.json`
(Import → archivo) y usar *Run collection*. Prueba el contrato del endpoint con
11 validaciones automáticas: health, extracción multipart y binaria, PDF
inválido (422) y petición sin archivo (400). Si Postman no encuentra los PDFs,
en las peticiones 2 y 3 hay que volver a elegir el archivo de `tests/stress/pdfs`.

## Configuración (Twelve-Factor)

Copiar `.env.example` a `.env`. Variables principales:

| Variable | Default | Para qué |
|---|---|---|
| `EXTRACTOR_BACKEND` | `pymupdf` | `pymupdf` (Markdown, rápido) o `pypdf` (texto plano, baseline) |
| `EXTRACT_WORKERS` | `1` | workers de extracción por réplica |
| `MAX_INFLIGHT` | `8` | peticiones simultáneas antes de responder 503 |
| `CACHE_ENABLED` | `true` | caché de resultados en Redis |
| `REDIS_URL` | `redis://localhost:6379` | conexión a Redis |
| `DOCUMENTOS_SERVICE_URL` | `http://localhost:8001` | flujo asíncrono (Saga) |

## Correr los tests

Con **uv**:

```bash
uv sync --extra dev
uv run --extra dev pytest test/ -v
```

O con pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest test/ -v
```

## Stack

Python 3.12+ · FastAPI · pypdf / pymupdf · Redis · httpx · pytest + respx ·
Docker + Traefik · k6 + Vegeta
