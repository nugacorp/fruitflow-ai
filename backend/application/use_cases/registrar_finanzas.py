"""Casos de uso financieros: pagos, gastos y prorrateo (RN-06, RN-10).

Los `ejecutar_*` asumen transaccion abierta; los reutiliza confirmar_borrador.
"""

from __future__ import annotations

from backend.application.dto.comandos import (
    ComandoRegistrarGasto,
    ComandoRegistrarPago,
    ResultadoOperacion,
)
from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.domain.common.tipos import DatosIncompletos, EventoDominio
from backend.domain.finanzas.modelo import Gasto, Pago


async def registrar_pago(uow: UnidadDeTrabajo, cmd: ComandoRegistrarPago) -> ResultadoOperacion:
    async with uow:
        return await ejecutar_pago(uow, cmd)


async def ejecutar_pago(uow: UnidadDeTrabajo, cmd: ComandoRegistrarPago) -> ResultadoOperacion:
    contraparte = await uow.contrapartes.obtener(cmd.contraparte_id)
    if contraparte is None:
        raise DatosIncompletos("No conozco a esa contraparte.")

    pago = Pago(
        contraparte_id=cmd.contraparte_id,
        direccion=cmd.direccion,
        monto=cmd.monto,
        fecha=cmd.fecha,
        metodo=cmd.metodo,
        referencia=cmd.referencia,
        nota=cmd.nota,
    )
    await uow.pagos.agregar(pago)
    uow.registrar(
        EventoDominio(
            agregado_tipo="pago",
            agregado_id=pago.id,
            tipo_evento="pago_registrado",
            datos_despues={
                "contraparte_id": str(cmd.contraparte_id),
                "direccion": cmd.direccion.value,
                "monto": str(cmd.monto.monto),
            },
            actor_usuario_id=cmd.actor_id,
        )
    )
    return ResultadoOperacion(id=pago.id, folio=None)


async def registrar_gasto(uow: UnidadDeTrabajo, cmd: ComandoRegistrarGasto) -> ResultadoOperacion:
    async with uow:
        return await ejecutar_gasto(uow, cmd)


async def ejecutar_gasto(uow: UnidadDeTrabajo, cmd: ComandoRegistrarGasto) -> ResultadoOperacion:
    """RN-06: un gasto imputado a un lote se prorratea entre sus cajas."""
    gasto = Gasto(
        categoria=cmd.categoria,
        monto=cmd.monto,
        fecha=cmd.fecha,
        descripcion=cmd.descripcion,
        contraparte_id=cmd.contraparte_id,
        imputable_tipo=cmd.imputable_tipo,
        imputable_id=cmd.imputable_id,
    )
    await uow.gastos.agregar(gasto)

    if cmd.imputable_tipo == "lote" and cmd.imputable_id is not None:
        lote = await uow.lotes.obtener(cmd.imputable_id)
        if lote is None:
            raise DatosIncompletos("No encontre ese lote para imputar el gasto.")
        lote.prorratear_gasto(cmd.monto)
        await uow.lotes.guardar(lote)

    uow.registrar(
        EventoDominio(
            agregado_tipo="gasto",
            agregado_id=gasto.id,
            tipo_evento="gasto_registrado",
            datos_despues={
                "categoria": cmd.categoria,
                "monto": str(cmd.monto.monto),
                "imputable_tipo": cmd.imputable_tipo,
            },
            actor_usuario_id=cmd.actor_id,
        )
    )
    return ResultadoOperacion(id=gasto.id, folio=None)
