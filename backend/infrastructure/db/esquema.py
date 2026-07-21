"""Inicializacion del esquema al arranque.

Crea la extension pg_trgm, las tablas que falten y la empresa por defecto.
Es idempotente: en una base ya inicializada no cambia nada.

TODO(fase-2): cuando exista alembic, las migraciones reemplazan create_all;
este modulo quedara solo para pg_trgm y la empresa semilla.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text

from backend.config import get_settings
from backend.infrastructure.db.models import Base, Empresa
from backend.infrastructure.db.session import fabrica_de_sesiones, motor

log = logging.getLogger("fruitflow.db")


async def inicializar_esquema() -> None:
    settings = get_settings()
    async with motor().begin() as conexion:
        try:
            await conexion.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:  # pragma: no cover - depende de permisos del servidor
            log.warning("No se pudo crear pg_trgm; la busqueda difusa SQL fallara")
        await conexion.run_sync(Base.metadata.create_all)

    empresa_id = uuid.UUID(settings.empresa_id)
    async with fabrica_de_sesiones()() as sesion:
        if await sesion.get(Empresa, empresa_id) is None:
            sesion.add(Empresa(id=empresa_id, nombre="FruitFlow"))
            await sesion.commit()
            log.info("Empresa por defecto creada (%s)", empresa_id)
