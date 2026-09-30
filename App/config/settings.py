"""Configuración del microservicio, vía variables de entorno (Twelve-Factor)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "extraccion-service"
    app_version: str = "0.1.0"
    debug: bool = False

    # Flujo asíncrono existente (Saga): busca el PDF en documentos-service.
    documentos_service_url: str = "http://localhost:8001"
    api_v1_prefix: str = "/api/v1"

    # --- Endpoint síncrono POST /extract (Test de carga/estrés) ---
    # Backend de extracción: "pypdf" (por defecto) o "pymupdf" (más rápido).
    extractor_backend: str = "pypdf"
    # Workers del pool que corre la extracción fuera del event loop.
    extract_workers: int = 1
    # Máximo de peticiones simultáneas admitidas (corriendo + en cola).
    # Al superarlo se responde 503 rápido en vez de encolar y expirar.
    max_inflight: int = 8

    # --- Caché de resultados en Redis ---
    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600


settings = Settings()
