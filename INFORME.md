# Informe técnico — Test de carga, estrés y optimización del extractor

**Materia:** Desarrollo de Software — UTN FRSR — Ingeniería en Sistemas
**Microservicio:** `extraccion-service` (extracción de texto de PDF)

---

## 1. Objetivo

Convertir el microservicio de extracción en un servicio **síncrono** que reciba
un PDF binario y devuelva su texto, y optimizarlo para soportar condiciones
extremas de concurrencia (pruebas con **Vegeta** y **k6**), aplicando patrones
de microservicios, Twelve-Factor App y técnicas de mitigación de saturación
(backpressure, colas, paralelismo, caché).

## 2. Endpoint requerido

```
POST /extract
Entrada : PDF binario (multipart/form-data campo "file", o el PDF crudo en el body)
Salida  : 200 application/json  ->  {"content": "<texto>", "page_count": N}
```

Se **mantiene** el endpoint asíncrono anterior (`POST /api/v1/extract` con
`document_id`, usado por la Saga del orquestador) para no romper el sistema que
ya funcionaba. El nuevo `/extract` convive con él.

## 3. Arquitectura de la solución

```
          ┌─────────────┐        ┌──────────────────────────────┐
  cliente │   Traefik   │  ───▶  │  extractor ×5 (réplicas)      │
 (Vegeta/ │  (balanceo) │        │  FastAPI + pool de workers    │
   k6)    └─────────────┘        │  + backpressure               │
                                  └──────────────┬───────────────┘
                                                 │  (caché compartido)
                                          ┌───────────────┐
                                          │     Redis     │
                                          └───────────────┘
```

Cada petición en el extractor pasa por tres capas de control:

1. **Caché (Redis):** clave = `sha256(pdf)`. Si el PDF ya fue procesado, se
   devuelve el resultado al instante (sin CPU). Como las pruebas **rotan pocos
   PDFs**, casi todas las peticiones terminan siendo *cache hit*. El caché es
   **compartido por las 5 réplicas**, así que la primera que procesa un PDF lo
   deja listo para todas.
2. **Admisión / backpressure:** un contador de peticiones en vuelo
   (`MAX_INFLIGHT`). Si se supera, se responde **503** de inmediato (con
   `Retry-After`), en vez de encolar peticiones que van a expirar por timeout.
3. **Pool de workers:** la extracción (CPU-bound) corre en un
   `ThreadPoolExecutor`, **separada del event loop** de FastAPI. Así el runtime
   HTTP sigue libre para aceptar/rechazar rápido mientras los workers procesan.

## 4. Decisiones de diseño (framework y estructuras)

- **Framework (FastAPI + Uvicorn):** async de base, ideal para separar el I/O
  (recibir el PDF, hablar con Redis) del trabajo CPU, que se delega al pool.
  El endpoint devuelve un modelo Pydantic chico (`content`, `page_count`), sin
  estructuras intermedias innecesarias.
- **Cuidado con las estructuras / diccionarios:** el PDF se maneja como
  `bytes` una sola vez y se lee con un `BytesIO` **en memoria, sin volcar a
  disco ni duplicar buffers**. No se arma una lista de páginas en dicts; se
  concatena el texto directo. En caché se guarda un JSON mínimo
  (`{"content","page_count"}`), no el binario ni estructuras grandes.
- **Backend de extracción intercambiable (Strategy / Open-Closed):**
  `EXTRACTOR_BACKEND` elige entre `pypdf` (baseline) y `pymupdf` (más rápido y
  de menor consumo de CPU). Se puede cambiar por variable de entorno, sin tocar
  el código.
- **Twelve-Factor:** toda la configuración por variables de entorno, procesos
  sin estado (el estado compartido vive en Redis), logs a stdout, port binding.

## 5. Cuello de botella identificado

El límite es la **CPU de extracción**: con 1.0 CPU por réplica, cada worker
procesa un PDF por vez. A 50 req/s sostenidas (modelo abierto de Vegeta) la
tasa de llegada supera lo que la CPU puede procesar, y sin control las
peticiones se acumulan y expiran (es lo que le pasó al servicio del profesor:
~33% de timeouts).

Las tres mitigaciones atacan justamente eso:

- **Caché** → elimina el costo de CPU en las peticiones repetidas (la mayoría).
- **Backpressure** → convierte el exceso en 503 rápidos (latencia baja y
  controlada) en lugar de timeouts de 30s.
- **Réplicas + balanceo** → 5 CPUs en paralelo en vez de 1.

## 6. Comparativa antes vs. después

> Completar con los números reales de tus corridas (ver `tests/stress/`).

| Métrica (Vegeta 50 req/s, 30s) | Profesor | Nuestro baseline | Nuestro optimizado |
|--------------------------------|----------|------------------|--------------------|
| Throughput efectivo (req/s)    | 16.65    |                  |                    |
| Peticiones exitosas            | 66.53%   |                  |                    |
| Timeouts (code 0)              | 33.40%   |                  |                    |
| Latencia P50                   | 14.89 s  |                  |                    |

| Métrica (k6 Spike, 100 VUs)    | Profesor | Nuestro optimizado |
|--------------------------------|----------|--------------------|
| Peticiones procesadas          | 1.037    |                    |
| Throughput sostenido (req/s)   | 25.35    |                    |
| Tasa de error                  | 0.00%    |                    |
| Latencia P50 / P90 / P95       | 1.88 / 7.83 / 8.80 s |          |

**Cómo medir baseline vs optimizado:** correr la prueba dos veces cambiando en
`docker-compose.yml` el servicio `extractor`:

- *Baseline*: `EXTRACTOR_BACKEND=pypdf`, `CACHE_ENABLED=false`, `replicas: 1`.
- *Optimizado*: `EXTRACTOR_BACKEND=pymupdf`, `CACHE_ENABLED=true`, `replicas: 5`.

## 7. Proceso de investigación (a completar)

Documentar acá qué se fue probando y por qué se llegó a la configuración final:
elección de `MAX_INFLIGHT`, cantidad de réplicas, backend, efecto del caché,
etc. (imprescindible para el puntaje ganador según el TP).

## 8. Metodología: Code First + TDD

El micro se desarrolló con enfoque **Code First**: primero la lógica de negocio
(extracción, pool, backpressure, caché) cubierta con **tests unitarios** siguiendo
**TDD**, y recién en la última capa el **endpoint**. El **contrato** de ese
endpoint es el JSON que se recibe/devuelve: la respuesta `{"content", "page_count"}`
que exige el TP. Los tests no son un extra: son lo que garantiza que el endpoint
haga lo que dice su contrato (multipart y body crudo devuelven 200 con el formato
correcto; PDF inválido → 422; servicio saturado → 503).

> *Nota:* en **Code First** el contrato (Swagger/OpenAPI) lo genera FastAPI a
> partir del código. La alternativa, **API First**, es diseñar primero ese
> contrato y después programar contra él. Acá se usó Code First, que es lo que
> el proyecto ya venía aplicando con FastAPI.

## 9. Cómo reproducir

```powershell
# 1. Levantar
docker compose up --build

# 2. Prueba fija (Vegeta) y Spike (k6), desde tests/stress
.\vegeta\run-vegeta.ps1
.\k6\run-k6.ps1
```
