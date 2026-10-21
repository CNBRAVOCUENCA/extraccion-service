# Pruebas de carga y estrés del extractor

Reproduce los dos escenarios del TP contra el endpoint síncrono `POST /extract`.

## 0. Levantar el sistema (5 réplicas + Traefik + Redis)

Desde la raíz de `extraccion-service`:

```powershell
docker compose up --build
```

El endpoint queda en `http://localhost/extract`. Verificá salud:

```powershell
curl.exe http://localhost/health
```

## 1. Prueba de carga fija — Vegeta (modelo abierto)

50 req/s durante 30s (1500 solicitudes) rotando los 4 PDFs base. Desde la raiz
de `extraccion-service`:

```powershell
.\tests\stress\vegeta\run-vegeta.ps1
```

Parametros: `-Rate`, `-Duration`, `-Timeout`, `-Target` y `-AdditionalPdfPath`.
El parametro opcional agrega un PDF externo como quinto caso, montado en Docker
en modo solo lectura. No copia el archivo al repo.

Ejemplo con un PDF local adicional:

```powershell
.\tests\stress\vegeta\run-vegeta.ps1 `
  -AdditionalPdfPath "D:\Panchito_Memori\Descargas\Microservicios _ un enfoque integrado -- RA-MA .pdf"
```

Para probar exclusivamente ese PDF y no rotar los cuatro del corpus:

```powershell
$bookPdf = "D:\Panchito_Memori\Descargas\Microservicios _ un enfoque integrado -- RA-MA .pdf"
.\tests\stress\vegeta\run-vegeta.ps1 -AdditionalPdfPath $bookPdf -OnlyAdditionalPdf
```

## 2. Prueba Spike — k6 (modelo cerrado)

Rampa a 100 VUs en 10s, 20s sostenidos, rampa a 0 en 10s:

```powershell
.\k6\run-k6.ps1
```

Tambien acepta `-AdditionalPdfPath` para rotar ese mismo PDF adicional:

```powershell
.\tests\stress\k6\run-k6.ps1 `
  -AdditionalPdfPath "D:\Panchito_Memori\Descargas\Microservicios _ un enfoque integrado -- RA-MA .pdf" `
  -OnlyAdditionalPdf
```

## Qué mirar

- **Vegeta**: `Success ratio`, `Requests/sec` (throughput), latencias
  (`mean`, `p95`, `p99`) y `Status Codes`. Los `503` son backpressure (rechazo
  rápido y controlado); los `code 0` son timeouts del cliente (lo que hay que
  evitar).
- **k6**: `http_req_duration` (med/p90/p95/max), `http_req_failed` y las
  peticiones completadas.

## Palancas para optimizar (ver INFORME.md)

En `docker-compose.yml`, variables del servicio `extractor`:

- `EXTRACTOR_BACKEND`: `pymupdf` (rápido) vs `pypdf` (baseline).
- `MAX_INFLIGHT`: cuántas peticiones admite cada réplica antes de responder 503.
- `EXTRACT_WORKERS`: workers de extracción por réplica.
- `CACHE_ENABLED`: prende/apaga el caché de Redis.
- `deploy.replicas`: cantidad de réplicas (máx. 5).
