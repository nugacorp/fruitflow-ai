"""API interna de FruitFlow AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.domain.common.tipos import ErrorDominio
from backend.interfaces.http.routers import borradores, consultas, operaciones, panel

log = logging.getLogger("fruitflow")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    settings = get_settings()
    log.info("Iniciando FruitFlow en entorno %s", settings.env)
    if settings.db_crear_esquema:
        try:
            from backend.infrastructure.db.esquema import inicializar_esquema

            await inicializar_esquema()
        except Exception:
            # La API arranca igual: /health reporta el detalle de Postgres.
            log.exception("No se pudo inicializar el esquema de la base")
    yield
    log.info("Deteniendo FruitFlow")


app = FastAPI(
    title="FruitFlow AI",
    version="0.1.0",
    description="ERP conversacional para comercializacion de fruta",
    lifespan=ciclo_de_vida,
)

app.include_router(operaciones.router)
app.include_router(consultas.router)
app.include_router(borradores.router)
app.include_router(panel.router)


@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(_: Request, exc: ErrorDominio) -> JSONResponse:
    """Los errores de negocio nunca son 500."""
    return JSONResponse(status_code=422, content=exc.a_dict())


@app.get("/health")
async def health() -> dict[str, Any]:
    """Verifica dependencias. Lo consume el healthcheck de Docker."""
    estado: dict[str, Any] = {
        "servicio": "ok",
        "postgres": "desconocido",
        "redis": "desconocido",
        "minio": "desconocido",
    }
    settings = get_settings()

    try:
        from sqlalchemy import text

        from backend.infrastructure.db.session import motor

        async with motor().connect() as conn:
            await conn.execute(text("SELECT 1"))
        estado["postgres"] = "ok"
    except Exception as exc:
        estado["postgres"] = f"error: {type(exc).__name__}"

    try:
        import redis.asyncio as aioredis

        cliente = aioredis.from_url(settings.redis_url)
        await cliente.ping()
        await cliente.aclose()
        estado["redis"] = "ok"
    except Exception as exc:
        estado["redis"] = f"error: {type(exc).__name__}"

    estado["saludable"] = all(
        v == "ok" for k, v in estado.items() if k in ("servicio", "postgres", "redis")
    )
    return estado


@app.get("/")
async def raiz() -> dict[str, str]:
    return {"servicio": "FruitFlow AI", "version": "0.1.0", "docs": "/docs"}
