"""Casos de uso de registro: compra, venta y devolucion de cajas.

Cada `registrar_*` es una transaccion (UnidadDeTrabajo). Los `ejecutar_*`
contienen el cuerpo y asumen transaccion abierta: los reutiliza
confirmar_borrador para que operacion y borrador se guarden juntos.
"""

from __future__ import annotations

from backend.application.dto.comandos import (
    Advertencia,
    ComandoRegistrarCompra,
    ComandoRegistrarDevolucionCajas,
    ComandoRegistrarVenta,
    ResultadoOperacion,
)
from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.domain.cajas.politica import (
    MovimientoCaja,
    TipoMovimientoCaja,
    aplicar,
    movimientos_de_compra,
    movimientos_de_venta,
)
from backend.domain.common.tipos import DatosIncompletos, EventoDominio
from backend.domain.operaciones.compra import armar_compra
from backend.domain.operaciones.venta import armar_venta


async def registrar_compra(uow: UnidadDeTrabajo, cmd: ComandoRegistrarCompra) -> ResultadoOperacion:
    async with uow:
        return await ejecutar_compra(uow, cmd)


async def ejecutar_compra(uow: UnidadDeTrabajo, cmd: ComandoRegistrarCompra) -> ResultadoOperacion:
    """RN-05: cada linea crea un lote. RN-03: quedo debiendo las cajas."""
    proveedor = await uow.contrapartes.obtener(cmd.proveedor_id)
    if proveedor is None:
        raise DatosIncompletos("No conozco a ese proveedor.")

    compra = armar_compra(
        proveedor_id=cmd.proveedor_id,
        fecha=cmd.fecha,
        items=cmd.items,
        origen_id=cmd.origen_id,
        transportista_id=cmd.transportista_id,
        folio_externo=cmd.folio_externo,
        nota=cmd.nota,
    )
    compra.folio = await uow.compras.agregar(compra)
    await uow.lotes.agregar(*compra.lotes)

    movimientos = movimientos_de_compra(
        proveedor_id=cmd.proveedor_id,
        compra_id=compra.id,
        fecha=cmd.fecha,
        cajas_por_tipo=compra.cajas_por_tipo,
        cajas_retornables=proveedor.cajas_retornables,
    )
    if movimientos:
        await uow.movimientos_caja.agregar(*movimientos)

    uow.registrar(compra.evento_creacion(cmd.actor_id))
    return ResultadoOperacion(id=compra.id, folio=compra.folio)


async def registrar_venta(uow: UnidadDeTrabajo, cmd: ComandoRegistrarVenta) -> ResultadoOperacion:
    async with uow:
        return await ejecutar_venta(uow, cmd)


async def ejecutar_venta(uow: UnidadDeTrabajo, cmd: ComandoRegistrarVenta) -> ResultadoOperacion:
    """RN-05/RN-06: consume lotes FIFO y calcula costo. RN-03: el cliente
    queda debiendo cajas. Si falta inventario no bloquea: advierte."""
    cliente = await uow.contrapartes.obtener(cmd.cliente_id)
    if cliente is None:
        raise DatosIncompletos("No conozco a ese cliente.")

    lotes = []
    for producto_id in dict.fromkeys(item.producto_id for item in cmd.items):
        lotes.extend(await uow.lotes.disponibles_de(producto_id))

    venta = armar_venta(
        cliente_id=cmd.cliente_id,
        fecha=cmd.fecha,
        items=cmd.items,
        lotes_disponibles=lotes,
        destino_id=cmd.destino_id,
        transportista_id=cmd.transportista_id,
        nota=cmd.nota,
    )
    venta.folio = await uow.ventas.agregar(venta)

    consumidos = {asignacion.lote_id for linea in venta.lineas for asignacion in linea.asignaciones}
    if consumidos:
        await uow.lotes.guardar(*[lote for lote in lotes if lote.id in consumidos])

    movimientos = movimientos_de_venta(
        cliente_id=cmd.cliente_id,
        venta_id=venta.id,
        fecha=cmd.fecha,
        cajas_por_tipo=venta.cajas_por_tipo,
        cajas_retornables=cliente.cajas_retornables,
    )
    if movimientos:
        await uow.movimientos_caja.agregar(*movimientos)

    advertencias = [
        Advertencia(
            codigo="inventario_insuficiente",
            datos={"producto_id": linea.producto_id, "cajas": linea.cajas_faltantes},
        )
        for linea in venta.lineas
        if linea.cajas_faltantes > 0
    ]
    uow.registrar(venta.evento_creacion(cmd.actor_id))
    return ResultadoOperacion(id=venta.id, folio=venta.folio, advertencias=advertencias)


async def registrar_devolucion_cajas(
    uow: UnidadDeTrabajo,
    cmd: ComandoRegistrarDevolucionCajas,
    *,
    permitir_saldo_negativo: bool = True,
) -> ResultadoOperacion:
    async with uow:
        return await ejecutar_devolucion_cajas(
            uow, cmd, permitir_saldo_negativo=permitir_saldo_negativo
        )


async def ejecutar_devolucion_cajas(
    uow: UnidadDeTrabajo,
    cmd: ComandoRegistrarDevolucionCajas,
    *,
    permitir_saldo_negativo: bool = True,
) -> ResultadoOperacion:
    """RN-04: una devolucion mayor al saldo se registra igual y se advierte.

    DECISION-1: `permitir_saldo_negativo` viene de configuracion; el default
    es advertir en vez de bloquear.
    """
    contraparte = await uow.contrapartes.obtener(cmd.contraparte_id)
    if contraparte is None:
        raise DatosIncompletos("No conozco a esa contraparte.")

    movimiento = MovimientoCaja(
        contraparte_id=cmd.contraparte_id,
        tipo_caja_id=cmd.tipo_caja_id,
        tipo=(
            TipoMovimientoCaja.DEVOLUCION_RECIBIDA
            if cmd.recibida
            else TipoMovimientoCaja.DEVOLUCION_ENTREGADA
        ),
        cantidad=cmd.cantidad,
        fecha=cmd.fecha,
        nota=cmd.nota,
    )
    saldo_actual = await uow.movimientos_caja.saldo(cmd.contraparte_id, cmd.tipo_caja_id)
    saldo_nuevo, requiere_revision = aplicar(
        saldo_actual, movimiento, permitir_negativo=permitir_saldo_negativo
    )
    await uow.movimientos_caja.agregar(movimiento)

    advertencias = []
    if requiere_revision:
        advertencias.append(
            Advertencia(
                codigo="saldo_cajas_negativo",
                datos={"contraparte_id": cmd.contraparte_id, "saldo": saldo_nuevo},
            )
        )
    uow.registrar(
        EventoDominio(
            agregado_tipo="movimiento_caja",
            agregado_id=movimiento.id,
            tipo_evento="devolucion_registrada",
            datos_despues={
                "contraparte_id": str(cmd.contraparte_id),
                "cantidad": cmd.cantidad,
                "saldo_nuevo": saldo_nuevo,
            },
            actor_usuario_id=cmd.actor_id,
        )
    )
    return ResultadoOperacion(id=movimiento.id, folio=None, advertencias=advertencias)
