"""Registro directo de operaciones. El cliente (bot) ya confirmo (RN-01)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.application.dto.comandos import ComandoAnularOperacion
from backend.application.use_cases.anular_operacion import anular_operacion
from backend.application.use_cases.borradores import registrar_desde_payload
from backend.config import get_settings
from backend.interfaces.http.dependencias import LlaveInterna, Uow
from backend.interfaces.http.esquemas import (
    AnulacionEntrada,
    CompraEntrada,
    DevolucionEntrada,
    GastoEntrada,
    PagoEntrada,
    ResultadoSalida,
    VentaEntrada,
)

router = APIRouter(prefix="/v1", tags=["operaciones"], dependencies=[LlaveInterna])


async def _registrar(uow, intencion: str, payload: dict) -> ResultadoSalida:
    resultado = await registrar_desde_payload(
        uow,
        intencion=intencion,
        payload=payload,
        permitir_saldo_negativo=get_settings().permitir_saldo_cajas_negativo,
    )
    return ResultadoSalida.de(resultado)


@router.post("/compras", status_code=201)
async def crear_compra(entrada: CompraEntrada, uow: Uow) -> ResultadoSalida:
    return await _registrar(uow, "compra", entrada.model_dump())


@router.post("/ventas", status_code=201)
async def crear_venta(entrada: VentaEntrada, uow: Uow) -> ResultadoSalida:
    return await _registrar(uow, "venta", entrada.model_dump())


@router.post("/devoluciones-cajas", status_code=201)
async def crear_devolucion(entrada: DevolucionEntrada, uow: Uow) -> ResultadoSalida:
    return await _registrar(uow, "devolucion_cajas", entrada.model_dump())


@router.post("/pagos", status_code=201)
async def crear_pago(entrada: PagoEntrada, uow: Uow) -> ResultadoSalida:
    return await _registrar(uow, "pago", entrada.model_dump())


@router.post("/gastos", status_code=201)
async def crear_gasto(entrada: GastoEntrada, uow: Uow) -> ResultadoSalida:
    return await _registrar(uow, "gasto", entrada.model_dump())


@router.post("/anulaciones")
async def anular(entrada: AnulacionEntrada, uow: Uow) -> ResultadoSalida:
    resultado = await anular_operacion(
        uow,
        ComandoAnularOperacion(tipo=entrada.tipo, folio=entrada.folio, motivo=entrada.motivo),
    )
    return ResultadoSalida.de(resultado)
