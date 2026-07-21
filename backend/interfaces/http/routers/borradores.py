"""Ciclo de vida del borrador via API (RN-01)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from backend.application.use_cases.borradores import (
    cancelar_borrador,
    confirmar_borrador,
    crear_borrador,
    editar_borrador,
)
from backend.config import get_settings
from backend.interfaces.http.dependencias import LlaveInterna, Uow
from backend.interfaces.http.esquemas import (
    BorradorEdicion,
    BorradorEntrada,
    BorradorSalida,
    ResultadoSalida,
)

router = APIRouter(prefix="/v1/borradores", tags=["borradores"], dependencies=[LlaveInterna])


@router.post("", status_code=201)
async def crear(entrada: BorradorEntrada, uow: Uow) -> BorradorSalida:
    borrador = await crear_borrador(
        uow,
        intencion=entrada.intencion,
        payload=entrada.payload,
        faltantes=entrada.faltantes,
        preguntas=entrada.preguntas,
        confianza=entrada.confianza,
        mensaje_id=entrada.mensaje_id,
    )
    return BorradorSalida.de(borrador)


@router.get("/pendientes")
async def pendientes(uow: Uow) -> list[BorradorSalida]:
    return [BorradorSalida.de(b) for b in await uow.borradores.pendientes()]


@router.get("/{borrador_id}")
async def obtener(borrador_id: uuid.UUID, uow: Uow) -> BorradorSalida:
    borrador = await uow.borradores.obtener(borrador_id)
    if borrador is None:
        raise HTTPException(status_code=404, detail="Borrador no encontrado")
    return BorradorSalida.de(borrador)


@router.patch("/{borrador_id}")
async def editar(borrador_id: uuid.UUID, entrada: BorradorEdicion, uow: Uow) -> BorradorSalida:
    borrador = await editar_borrador(uow, borrador_id, entrada.cambios)
    return BorradorSalida.de(borrador)


@router.post("/{borrador_id}/confirmar")
async def confirmar(borrador_id: uuid.UUID, uow: Uow) -> ResultadoSalida:
    resultado = await confirmar_borrador(
        uow,
        borrador_id,
        permitir_saldo_negativo=get_settings().permitir_saldo_cajas_negativo,
    )
    return ResultadoSalida.de(resultado)


@router.post("/{borrador_id}/cancelar")
async def cancelar(borrador_id: uuid.UUID, uow: Uow) -> BorradorSalida:
    borrador = await cancelar_borrador(uow, borrador_id)
    return BorradorSalida.de(borrador)
