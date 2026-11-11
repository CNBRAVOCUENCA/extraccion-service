"""Pool de extracción síncrona con backpressure y caché.

Responsabilidades:
- Separar el runtime HTTP (event loop async) de la extracción de PDF, que es
  CPU-bound, corriéndola en un ThreadPoolExecutor (pool de workers).
- Aplicar backpressure: limitar cuántas peticiones se admiten a la vez; si se
  supera el límite se levanta ExtractionOverloaded para responder 503 al toque,
  en vez de encolar peticiones que van a expirar por timeout.
- Cachear el resultado en Redis por hash del PDF. Como el test de carga rota
  unos pocos PDFs, la mayoría de las peticiones salen de caché (rápidas), y el
  caché es compartido por todas las réplicas.
"""

import asyncio
import contextlib
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from App.config.settings import settings
from App.utils.pdf_extractor import extract_content

try:  # redis es opcional: si no está, el servicio corre sin caché.
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover
    Redis = None

logger = logging.getLogger(__name__)


class ExtractionOverloaded(Exception):
    """El servicio está saturado; hay que responder 503 (backpressure)."""


class ExtractionPool:
    """Admisión + pool de workers + caché para el endpoint POST /extract."""

    def __init__(
        self,
        workers: int | None = None,
        max_inflight: int | None = None,
        backend: str | None = None,
        redis_client=None,
    ):
        self.workers = workers if workers is not None else settings.extract_workers
        self.max_inflight = max_inflight if max_inflight is not None else settings.max_inflight
        self.backend = backend if backend is not None else settings.extractor_backend

        self._executor = ThreadPoolExecutor(max_workers=self.workers)
        self._cpu = asyncio.Semaphore(self.workers)
        self._inflight = 0
        self._closing = False
        self._idle = asyncio.Event()
        self._idle.set()

        self._redis = redis_client
        if self._redis is None and settings.cache_enabled and Redis is not None:
            try:
                self._redis = Redis.from_url(settings.redis_url)
            except Exception:  # pragma: no cover - conexión perezosa
                self._redis = None

    async def extract(self, pdf_bytes: bytes) -> tuple[dict, bool]:
        """Devuelve ({content, page_count}, from_cache).

        Levanta ExtractionOverloaded si no hay cupo (backpressure).
        """
        key = "extract:md:v1:" + hashlib.sha256(pdf_bytes).hexdigest()

        cached = await self._cache_get(key)
        if cached is not None:
            return cached, True

        # Admisión: sin await entre la comprobación y el incremento, así que es
        # atómico dentro del event loop de un solo hilo.
        if self._closing or self._inflight >= self.max_inflight:
            raise ExtractionOverloaded()
        self._inflight += 1
        self._idle.clear()
        try:
            async with self._cpu:
                loop = asyncio.get_running_loop()
                content, page_count = await loop.run_in_executor(
                    self._executor, extract_content, pdf_bytes, self.backend
                )
        finally:
            self._inflight -= 1
            if self._inflight == 0:
                self._idle.set()

        result = {"content": content, "page_count": page_count}
        await self._cache_set(key, result)
        return result, False

    async def _cache_get(self, key: str):
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    async def _cache_set(self, key: str, result: dict) -> None:
        if self._redis is None:
            return
        with contextlib.suppress(Exception):  # caché opcional: si falla, se sigue sin ella
            await self._redis.set(key, json.dumps(result), ex=settings.cache_ttl_seconds)

    async def cache_status(self) -> str:
        """Estado del caché para el readiness: "disabled", "up" o "down".

        Redis es una caché opcional: este estado es informativo y nunca debe
        tumbar la disponibilidad del servicio.
        """
        if self._redis is None:
            return "disabled"
        try:
            await asyncio.wait_for(self._redis.ping(), timeout=1.0)
        except Exception:
            return "down"
        return "up"

    @property
    def inflight(self) -> int:
        return self._inflight

    async def aclose(self, timeout_seconds: float | None = None) -> bool:
        """Apagado ordenado. Devuelve True si todas las extracciones terminaron a tiempo.

        1. Deja de admitir: las peticiones nuevas reciben 503 (ExtractionOverloaded).
        2. Espera las extracciones en curso hasta `timeout_seconds`
           (SHUTDOWN_TIMEOUT_SECONDS, 10 s por defecto).
        3. Cierra el pool: las tareas encoladas que no empezaron se cancelan. Si se
           agotó el plazo, una extracción que ya está corriendo NO se puede cancelar
           (Python no detiene un hilo en ejecución): sigue hasta terminar o hasta que
           el proceso finalice, y su resultado se descarta. Se registra un aviso.
        4. Cierra la conexión a Redis.
        """
        self._closing = True
        plazo = settings.shutdown_timeout_seconds if timeout_seconds is None else timeout_seconds
        drained = True
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=plazo)
        except TimeoutError:
            drained = False
            logger.warning(
                "Apagado: %d extracción(es) seguían en curso tras %.1f s; no se pueden "
                "cancelar y su resultado se descarta",
                self._inflight,
                plazo,
            )
        self._executor.shutdown(wait=False, cancel_futures=True)
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
        return drained
