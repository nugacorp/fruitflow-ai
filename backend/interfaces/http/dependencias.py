"""Dependencias de la API: autenticacion interna y unidad de trabajo."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.config import get_settings


async def verificar_llave(x_internal_key: Annotated[str, Header()] = "") -> None:
    """La API es interna: solo el bot y el worker la consumen."""
    esperada = get_settings().internal_api_key
    if not secrets.compare_digest(x_internal_key, esperada):
        raise HTTPException(status_code=401, detail="Llave interna invalida")


async def obtener_uow() -> AsyncIterator[UnidadDeTrabajo]:
    """Fabrica de UnidadDeTrabajo sobre SQLAlchemy (FASE 4).

    Las pruebas e2e la sustituyen con dependency_overrides.
    """
    from backend.infrastructure.db.session import fabrica_de_sesiones
    from backend.infrastructure.db.uow import UnitOfWorkSQLAlchemy

    async with fabrica_de_sesiones()() as sesion:
        yield UnitOfWorkSQLAlchemy(sesion)


LlaveInterna = Depends(verificar_llave)
Uow = Annotated[UnidadDeTrabajo, Depends(obtener_uow)]
