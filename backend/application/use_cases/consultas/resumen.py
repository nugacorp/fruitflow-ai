"""Consultas de periodo: resumen del dia y utilidad (RN-06)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.domain.common.tipos import Dinero, EstadoOperacion
from backend.domain.operaciones.costeo import margen_porcentual


@dataclass(frozen=True, slots=True)
class ResumenPeriodo:
    desde: date
    hasta: date
    compras_cantidad: int
    compras_total: Dinero
    compras_cajas: int
    ventas_cantidad: int
    ventas_total: Dinero
    ventas_cajas: int
    costo_ventas: Dinero
    gastos_total: Dinero

    @property
    def utilidad_bruta(self) -> Dinero:
        """Ingreso menos costo de la mercancia vendida."""
        return self.ventas_total - self.costo_ventas

    @property
    def utilidad_neta(self) -> Dinero:
        """RN-06: la bruta menos los gastos del periodo."""
        return self.utilidad_bruta - self.gastos_total

    @property
    def margen(self) -> Decimal:
        return margen_porcentual(self.ventas_total, self.utilidad_bruta)


async def resumen_periodo(uow: UnidadDeTrabajo, desde: date, hasta: date) -> ResumenPeriodo:
    """Numeros del periodo. Solo cuentan operaciones confirmadas."""
    compras = [
        compra
        for compra in await uow.compras.listar_por_fechas(desde, hasta)
        if compra.estado is EstadoOperacion.CONFIRMADO
    ]
    ventas = [
        venta
        for venta in await uow.ventas.listar_por_fechas(desde, hasta)
        if venta.estado is EstadoOperacion.CONFIRMADO
    ]
    gastos = await uow.gastos.listar_por_fechas(desde, hasta)

    compras_total = Dinero.cero()
    compras_cajas = 0
    for compra in compras:
        compras_total = compras_total + compra.total
        compras_cajas += sum(linea.cajas for linea in compra.lineas)

    ventas_total = Dinero.cero()
    costo_ventas = Dinero.cero()
    ventas_cajas = 0
    for venta in ventas:
        ventas_total = ventas_total + venta.total
        costo_ventas = costo_ventas + venta.costo_total
        ventas_cajas += sum(linea.cajas for linea in venta.lineas)

    gastos_total = Dinero.cero()
    for gasto in gastos:
        gastos_total = gastos_total + gasto.monto

    return ResumenPeriodo(
        desde=desde,
        hasta=hasta,
        compras_cantidad=len(compras),
        compras_total=compras_total,
        compras_cajas=compras_cajas,
        ventas_cantidad=len(ventas),
        ventas_total=ventas_total,
        ventas_cajas=ventas_cajas,
        costo_ventas=costo_ventas,
        gastos_total=gastos_total,
    )


async def resumen_dia(uow: UnidadDeTrabajo, dia: date) -> ResumenPeriodo:
    return await resumen_periodo(uow, dia, dia)
