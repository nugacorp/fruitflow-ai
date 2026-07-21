"""Costeo por lotes y calculo de utilidad (RN-05, RN-06, RN-07)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from backend.domain.common.tipos import (
    Dinero,
    InventarioInsuficiente,
    UnidadPrecio,
    nuevo_id,
)


@dataclass(slots=True)
class Lote:
    """Inventario creado por una linea de compra."""

    producto_id: uuid.UUID
    cajas_iniciales: int
    cajas_disponibles: int
    costo_unitario: Dinero
    fecha: date
    compra_linea_id: uuid.UUID | None = None
    costo_indirecto_unitario: Dinero = field(default_factory=Dinero.cero)
    id: uuid.UUID = field(default_factory=nuevo_id)

    @property
    def costo_total_unitario(self) -> Dinero:
        return self.costo_unitario + self.costo_indirecto_unitario

    def consumir(self, cajas: int) -> None:
        if cajas > self.cajas_disponibles:
            raise InventarioInsuficiente(
                f"El lote {self.id} solo tiene {self.cajas_disponibles} cajas."
            )
        self.cajas_disponibles -= cajas

    def liberar(self, cajas: int) -> None:
        self.cajas_disponibles = min(self.cajas_disponibles + cajas, self.cajas_iniciales)

    def prorratear_gasto(self, gasto: Dinero) -> None:
        """RN-06: un gasto imputado al lote se reparte entre sus cajas iniciales."""
        if self.cajas_iniciales <= 0:
            return
        por_caja = Dinero(gasto.monto / Decimal(self.cajas_iniciales), gasto.moneda)
        self.costo_indirecto_unitario = self.costo_indirecto_unitario + por_caja


@dataclass(frozen=True, slots=True)
class Asignacion:
    lote_id: uuid.UUID
    cajas: int
    costo_unitario: Dinero

    @property
    def costo_total(self) -> Dinero:
        return self.costo_unitario * self.cajas


def asignar_fifo(
    lotes: list[Lote],
    producto_id: uuid.UUID,
    cajas_requeridas: int,
    *,
    lotes_preferidos: list[uuid.UUID] | None = None,
    permitir_faltante: bool = True,
) -> tuple[list[Asignacion], int]:
    """RN-05: consume lotes por FIFO sobre fecha.

    `lotes_preferidos` atiende el caso "esas mismas cajas": esos lotes se
    consumen primero, respetando FIFO entre ellos.

    Devuelve (asignaciones, cajas_sin_cubrir). Si permitir_faltante es False
    y no alcanza el inventario, levanta InventarioInsuficiente.
    """
    if cajas_requeridas <= 0:
        raise ValueError("cajas_requeridas debe ser mayor que cero")

    preferidos = set(lotes_preferidos or [])
    candidatos = [
        lote for lote in lotes if lote.producto_id == producto_id and lote.cajas_disponibles > 0
    ]
    candidatos.sort(key=lambda lote: (lote.id not in preferidos, lote.fecha, str(lote.id)))

    asignaciones: list[Asignacion] = []
    restantes = cajas_requeridas
    for lote in candidatos:
        if restantes == 0:
            break
        toma = min(lote.cajas_disponibles, restantes)
        lote.consumir(toma)
        asignaciones.append(
            Asignacion(lote_id=lote.id, cajas=toma, costo_unitario=lote.costo_total_unitario)
        )
        restantes -= toma

    if restantes > 0 and not permitir_faltante:
        raise InventarioInsuficiente(
            f"Faltan {restantes} cajas de inventario para completar la venta.",
            sugerencia="Registra primero la compra correspondiente.",
        )
    return asignaciones, restantes


def calcular_importe(
    *,
    cajas: int,
    precio_unitario: Dinero,
    unidad_precio: UnidadPrecio,
    kg_por_caja: Decimal | None = None,
) -> Dinero:
    """RN-07: el precio puede venir por caja o por kilo."""
    if cajas <= 0:
        raise ValueError("cajas debe ser mayor que cero")
    if unidad_precio is UnidadPrecio.CAJA:
        return precio_unitario * cajas
    if kg_por_caja is None or kg_por_caja <= 0:
        raise ValueError("El precio por kilo requiere kg_por_caja")
    return Dinero(precio_unitario.monto * kg_por_caja * cajas, precio_unitario.moneda)


def costo_de_venta(asignaciones: list[Asignacion]) -> Dinero:
    total = Dinero.cero()
    for asignacion in asignaciones:
        total = total + asignacion.costo_total
    return total


def utilidad(
    *,
    ingreso: Dinero,
    asignaciones: list[Asignacion],
    gastos_directos: Dinero | None = None,
) -> Dinero:
    """RN-06: utilidad = ingreso - costo de mercancia - gastos directos."""
    resultado = ingreso - costo_de_venta(asignaciones)
    if gastos_directos is not None:
        resultado = resultado - gastos_directos
    return resultado


def margen_porcentual(ingreso: Dinero, utilidad_bruta: Dinero) -> Decimal:
    if ingreso.monto == 0:
        return Decimal("0.00")
    return (utilidad_bruta.monto / ingreso.monto * Decimal("100")).quantize(Decimal("0.01"))
