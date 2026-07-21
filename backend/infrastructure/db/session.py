"""Motor y sesiones async de SQLAlchemy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings


@lru_cache
def motor() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.env == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


@lru_cache
def fabrica_de_sesiones() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor(), expire_on_commit=False, class_=AsyncSession)


async def obtener_sesion() -> AsyncIterator[AsyncSession]:
    async with fabrica_de_sesiones()() as sesion:
        yield sesion
