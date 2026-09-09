"""Configuración del microservicio, vía variables de entorno."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "extraccion-service"
    app_version: str = "0.1.0"
    debug: bool = False

    documentos_service_url: str = "http://localhost:8001"
    api_v1_prefix: str = "/api/v1"


settings = Settings()
