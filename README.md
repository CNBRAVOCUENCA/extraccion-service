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

No tiene base de datos propia: al terminar una extracción solicita a
`documentos-service` que persista el texto y marque el documento como procesado.
Solo responde éxito si Documentos confirma la escritura. El caché de resultados
es opcional y vive en Redis.

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
| GET | `/docs` | — | Swagger (si `DOCS_ENABLED=true`) |

El endpoint síncrono responde con header `X-Cache: HIT|MISS` y, si el servicio
está saturado, con **503** (backpressure) en lugar de encolar y expirar.

## Test de carga y estrés (TP)

Sistema completo (5 réplicas + nginx + Redis, con límites de CPU/RAM):

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

**Swagger (documentación interactiva).** Abrir **http://localhost/docs**: muestra
todos los endpoints con su contrato y permite probarlos desde el navegador
(*Try it out* → elegir el PDF → *Execute*). Está habilitado en el compose con
`DOCS_ENABLED=true`; por defecto queda apagado por seguridad.

**Desde internet (opcional).** Para abrir la página desde otro dispositivo:

```powershell
docker compose --profile publico up -d
docker compose logs cloudflared | Select-String trycloudflare
```

La segunda línea muestra una URL `https://...trycloudflare.com` que sirve la
misma página (y `/docs`). La URL cambia cada vez que se levanta el túnel y
funciona mientras la PC y Docker estén encendidos. Para cortarlo:
`docker compose stop cloudflared`.

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
| `CONSUL_HTTP_ADDR` | — | URL del agente Consul; vacía desactiva el registro (si está configurada, un fallo impide el arranque) |
| `CONSUL_HTTP_TOKEN` | — | token opcional enviado como `X-Consul-Token`; nunca se incluye en logs |
| `CONSUL_SERVICE_NAME` | `APP_NAME` | nombre registrado en Consul |
| `CONSUL_SERVICE_PORT` | `8000` | puerto HTTP de esta instancia |
| `CONSUL_SERVICE_TAGS` | — | etiquetas separadas por coma, incluidas las que usa Traefik |
| `CONSUL_SERVICE_ADDRESS` | detección automática | IP de esta instancia accesible desde Consul; permite sobrescribirla |
| `MAX_PDF_BYTES` | `26214400` | tamaño máximo de PDF en `/extract` (25 MB); más grande → 413 |
| `CACHE_ENABLED` | `true` | caché de resultados en Redis |
| `REDIS_URL` | `redis://localhost:6379` | conexión a Redis |
| `DOCUMENTOS_SERVICE_URL` | `http://localhost:8001` | flujo asíncrono (Saga) |
| `DOCUMENTOS_SERVICE_API_KEY` | — | Secreto compartido para guardar el texto extraído en Documentos |

Con Consul habilitado, la instancia se registra al iniciar y se elimina al cerrar.
El registro usa un ID que incluye el hostname del proceso y anuncia una dirección
IP detectada desde la ruta hacia el agente, no un nombre DNS compartido por las
réplicas. Si esa IP no es alcanzable por el agente, configure
`CONSUL_SERVICE_ADDRESS`. Consul consulta `/health` cada 10 segundos; una
instancia crítica se elimina después de un minuto.

`POST /api/v1/extract` sigue este orden: leer el PDF desde Documentos, extraer el
texto, enviarlo con `PUT /api/v1/documents/{id}/extraction` usando el header
`X-Internal-API-Key` y solo entonces devolver 200. Un 404 al guardar indica que
el documento ya no existe; errores de persistencia se propagan como 502 y no se
reporta éxito. El `PUT` es idempotente para permitir que el emisor reintente la
misma escritura; no se reintenta automáticamente toda la extracción.

## Correr los tests

Con **uv**:

```bash
uv sync --extra dev          # agregar --extra fast para probar también con PyMuPDF
uv run --extra dev pytest test/ -v
```

O con pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest test/ -v
```

## Escaneo de seguridad

El workflow `Security scan` audita las dependencias de runtime fijadas en
`uv.lock` y construye/escanea la imagen Docker con Trivy. Se ejecuta en cada PR,
push a `main`/`master`, semanalmente (lunes 06:00 UTC) y manualmente desde
GitHub Actions. Un hallazgo HIGH o CRITICAL falla el job; los detalles quedan
visibles en el log del workflow. También verifica que la imagen se ejecute como
un usuario distinto de root.

## Stack

Python 3.12+ · FastAPI · pypdf / pymupdf · Redis · httpx · pytest + respx ·
Docker + nginx · k6 + Vegeta
