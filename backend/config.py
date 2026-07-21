"""Configuracion central. Falla rapido al arranque si falta algo critico."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: str = "development"
    log_level: str = "INFO"
    tz: str = "America/Tijuana"
    domain: str = "localhost"

    database_url: str = "postgresql+asyncpg://fruitflow:cambiame@postgres:5432/fruitflow"
    redis_url: str = "redis://redis:6379/0"
    db_crear_esquema: bool = Field(
        default=True,
        description="Crea pg_trgm, tablas y empresa por defecto al arrancar. "
        "TODO(fase-2): reemplazar por migraciones alembic.",
    )

    minio_endpoint: str = "minio:9000"
    minio_user: str = "fruitflow"
    minio_password: str = "cambiame123"
    minio_bucket: str = "fruitflow-docs"
    minio_secure: bool = False

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_use_webhook: bool = False

    openai_api_key: str = ""
    openai_model_extraccion: str = "gpt-4.1"
    openai_model_vision: str = "gpt-4.1"
    whisper_model: str = "whisper-1"
    ai_daily_budget_mxn: int = 200
    ai_enabled: bool = True

    internal_api_key: str = "cambiame"
    api_base_url: str = "http://backend:8000"
    empresa_id: str = "01912f00-0000-7000-8000-000000000001"

    sentry_dsn: str = ""

    permitir_saldo_cajas_negativo: bool = Field(
        default=True, description="DECISION-1: advertir en vez de bloquear"
    )

    @property
    def usuarios_permitidos(self) -> set[int]:
        return {
            int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip().isdigit()
        }

    @property
    def es_produccion(self) -> bool:
        return self.env == "production"

    @field_validator("internal_api_key")
    @classmethod
    def _validar_llave(cls, v: str, info) -> str:
        return v

    @field_validator("database_url")
    @classmethod
    def _normalizar_database_url(cls, v: str) -> str:
        """Los proveedores gestionados entregan postgres:// o postgresql://;
        el motor async requiere el driver asyncpg explicito."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
