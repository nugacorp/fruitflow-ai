"""Anulacion de operaciones (RN-08): nunca DELETE, siempre contra-asiento."""

from __future__ import annotations

from backend.application.dto.comandos import ComandoAnularOperacion, ResultadoOperacion
from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.domain.cajas.politica import movimientos_inversos
from backend.domain.common.tipos import (
    DatosIncompletos,
    ErrorDominio,
    EstadoOperacion,
    EventoDominio,
    OperacionYaAnulada,
)


async def anular_operacion(uow: UnidadDeTrabajo, cmd: ComandoAnularOperacion) -> ResultadoOperacion:
    if cmd.tipo == "compra":
        return await _anular_compra(uow, cmd)
    if cmd.tipo == "venta":
        return await _anular_venta(uow, cmd)
    raise DatosIncompletos(f"No se puede anular una operacion de tipo {cmd.tipo!r}.")


async def _anular_compra(uow: UnidadDeTrabajo, cmd: ComandoAnularOperacion) -> ResultadoOperacion:
    """Anular una compra retira sus lotes del inventario. Si alguna caja ya
    se vendio, se bloquea: primero hay que anular esas ventas."""
    async with uow:
        compra = await uow.compras.buscar_por_folio(cmd.folio)
        if compra is None:
            raise DatosIncompletos(f"No encontre la compra con folio {cmd.folio}.")
        if compra.estado is EstadoOperacion.ANULADO:
            raise OperacionYaAnulada(f"La compra {cmd.folio} ya estaba anulada.")

        for lote in compra.lotes:
            if lote.cajas_disponibles < lote.cajas_iniciales:
                vendidas = lote.cajas_iniciales - lote.cajas_disponibles
                raise ErrorDominio(
                    f"No puedo anular la compra {cmd.folio}: ya se vendieron "
                    f"{vendidas} cajas de ese inventario.",
                    sugerencia="Anula primero las ventas que consumieron esas cajas.",
                )

        for lote in compra.lotes:
            lote.consumir(lote.cajas_disponibles)
        await uow.lotes.guardar(*compra.lotes)

        originales = await uow.movimientos_caja.de_referencia("compra", compra.id)
        inversos = movimientos_inversos(originales)
        if inversos:
            await uow.movimientos_caja.agregar(*inversos)

        await uow.compras.actualizar_estado(compra.id, EstadoOperacion.ANULADO.value)
        uow.registrar(
            EventoDominio(
                agregado_tipo="compra",
                agregado_id=compra.id,
                tipo_evento="compra_anulada",
                datos_antes={"estado": compra.estado.value},
                datos_despues={"estado": "anulado", "motivo": cmd.motivo},
                actor_usuario_id=cmd.actor_id,
            )
        )
    return ResultadoOperacion(id=compra.id, folio=cmd.folio)


async def _anular_venta(uow: UnidadDeTrabajo, cmd: ComandoAnularOperacion) -> ResultadoOperacion:
    """Anular una venta regresa las cajas a sus lotes y revierte las cajas
    retornables entregadas al cliente."""
    async with uow:
        venta = await uow.ventas.buscar_por_folio(cmd.folio)
        if venta is None:
            raise DatosIncompletos(f"No encontre la venta con folio {cmd.folio}.")
        if venta.estado is EstadoOperacion.ANULADO:
            raise OperacionYaAnulada(f"La venta {cmd.folio} ya estaba anulada.")

        for linea in venta.lineas:
            for asignacion in linea.asignaciones:
                lote = await uow.lotes.obtener(asignacion.lote_id)
                if lote is None:  # pragma: no cover - inconsistencia de datos
                    raise ErrorDominio(f"El lote {asignacion.lote_id} no existe.")
                lote.liberar(asignacion.cajas)
                await uow.lotes.guardar(lote)

        originales = await uow.movimientos_caja.de_referencia("venta", venta.id)
        inversos = movimientos_inversos(originales)
        if inversos:
            await uow.movimientos_caja.agregar(*inversos)

        await uow.ventas.actualizar_estado(venta.id, EstadoOperacion.ANULADO.value)
        uow.registrar(
            EventoDominio(
                agregado_tipo="venta",
                agregado_id=venta.id,
                tipo_evento="venta_anulada",
                datos_antes={"estado": venta.estado.value},
                datos_despues={"estado": "anulado", "motivo": cmd.motivo},
                actor_usuario_id=cmd.actor_id,
            )
        )
    return ResultadoOperacion(id=venta.id, folio=cmd.folio)
