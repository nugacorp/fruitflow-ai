"""Consultas de saldos: cajas retornables, cuentas por cobrar y por pagar."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.domain.common.tipos import DatosIncompletos, Dinero, EstadoOperacion
from backend.domain.finanzas.modelo import DireccionPago

_DESDE_SIEMPRE = date(2000, 1, 1)
_HASTA_SIEMPRE = date(2100, 1, 1)


@dataclass(frozen=True, slots=True)
class SaldoCajasContraparte:
    contraparte_id: uuid.UUID
    nombre: str
    por_tipo_caja: dict[uuid.UUID, int]

    @property
    def total(self) -> int:
        return sum(self.por_tipo_caja.values())


@dataclass(frozen=True, slots=True)
class SaldoDinero:
    contraparte_id: uuid.UUID
    nombre: str
    facturado: Dinero
    pagado: Dinero

    @property
    def pendiente(self) -> Dinero:
        return self.facturado - self.pagado


async def saldo_cajas(uow: UnidadDeTrabajo, contraparte_id: uuid.UUID) -> SaldoCajasContraparte:
    """RN-03: saldo > 0 la contraparte me debe; < 0 yo le debo."""
    contraparte = await uow.contrapartes.obtener(contraparte_id)
    if contraparte is None:
        raise DatosIncompletos("No conozco a esa contraparte.")
    saldos = await uow.movimientos_caja.saldos_de(contraparte_id)
    return SaldoCajasContraparte(
        contraparte_id=contraparte_id,
        nombre=contraparte.nombre,
        por_tipo_caja={tipo: saldo for tipo, saldo in saldos.items() if saldo != 0},
    )


async def tablero_cajas(uow: UnidadDeTrabajo) -> list[SaldoCajasContraparte]:
    """Saldo de cajas de TODAS las contrapartes con saldo distinto de cero,
    ordenado por magnitud. Alimenta /cajas del bot y el panel web."""
    tablero: list[SaldoCajasContraparte] = []
    for contraparte in await uow.contrapartes.listar():
        saldos = await uow.movimientos_caja.saldos_de(contraparte.id)
        con_saldo = {tipo: saldo for tipo, saldo in saldos.items() if saldo != 0}
        if con_saldo:
            tablero.append(
                SaldoCajasContraparte(
                    contraparte_id=contraparte.id,
                    nombre=contraparte.nombre,
                    por_tipo_caja=con_saldo,
                )
            )
    return sorted(tablero, key=lambda s: abs(s.total), reverse=True)


async def cuentas_por_cobrar(uow: UnidadDeTrabajo, cliente_id: uuid.UUID) -> SaldoDinero:
    """Lo facturado en ventas confirmadas menos los cobros recibidos."""
    cliente = await uow.contrapartes.obtener(cliente_id)
    if cliente is None:
        raise DatosIncompletos("No conozco a ese cliente.")

    facturado = Dinero.cero()
    for venta in await uow.ventas.listar_por_fechas(_DESDE_SIEMPRE, _HASTA_SIEMPRE):
        if venta.cliente_id == cliente_id and venta.estado is EstadoOperacion.CONFIRMADO:
            facturado = facturado + venta.total

    cobrado = Dinero.cero()
    for pago in await uow.pagos.listar_por_contraparte(cliente_id):
        if pago.direccion is DireccionPago.COBRO:
            cobrado = cobrado + pago.monto

    return SaldoDinero(
        contraparte_id=cliente_id, nombre=cliente.nombre, facturado=facturado, pagado=cobrado
    )


async def cuentas_por_pagar(uow: UnidadDeTrabajo, proveedor_id: uuid.UUID) -> SaldoDinero:
    """Lo comprado confirmado menos los pagos que ya le hice."""
    proveedor = await uow.contrapartes.obtener(proveedor_id)
    if proveedor is None:
        raise DatosIncompletos("No conozco a ese proveedor.")

    facturado = Dinero.cero()
    for compra in await uow.compras.listar_por_fechas(_DESDE_SIEMPRE, _HASTA_SIEMPRE):
        if compra.proveedor_id == proveedor_id and compra.estado is EstadoOperacion.CONFIRMADO:
            facturado = facturado + compra.total

    pagado = Dinero.cero()
    for pago in await uow.pagos.listar_por_contraparte(proveedor_id):
        if pago.direccion is DireccionPago.PAGO:
            pagado = pagado + pago.monto

    return SaldoDinero(
        contraparte_id=proveedor_id, nombre=proveedor.nombre, facturado=facturado, pagado=pagado
    )
