"""Agregado Venta. Puro: asigna lotes por FIFO y calcula costo y utilidad."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from backend.domain.common.tipos import (
    Dinero,
    EstadoOperacion,
    EventoDominio,
    UnidadPrecio,
    nuevo_id,
)
from backend.domain.operaciones.costeo import (
    Asignacion,
    Lote,
    asignar_fifo,
    calcular_importe,
    costo_de_venta,
)


@dataclass(frozen=True, slots=True)
class ItemVenta:
    producto_id: uuid.UUID
    cajas: int
    precio_unitario: Dinero
    unidad_precio: UnidadPrecio = UnidadPrecio.CAJA
    kg_por_caja: Decimal | None = None
    tipo_caja_id: uuid.UUID | None = None
    lotes_preferidos: list[uuid.UUID] | None = None


@dataclass(frozen=True, slots=True)
class LineaVenta:
    producto_id: uuid.UUID
    cajas: int
    precio_unitario: Dinero
    unidad_precio: UnidadPrecio
    importe: Dinero
    costo: Dinero
    asignaciones: list[Asignacion]
    cajas_faltantes: int = 0
    tipo_caja_id: uuid.UUID | None = None
    kg_por_caja: Decimal | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)


@dataclass(slots=True)
class Venta:
    cliente_id: uuid.UUID
    fecha: date
    lineas: list[LineaVenta]
    moneda: str = "MXN"
    destino_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    nota: str | None = None
    requiere_revision: bool = False
    estado: EstadoOperacion = EstadoOperacion.CONFIRMADO
    folio: int | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)

    @property
    def total(self) -> Dinero:
        total = Dinero.cero(self.moneda)
        for linea in self.lineas:
            total = total + linea.importe
        return total

    @property
    def costo_total(self) -> Dinero:
        total = Dinero.cero(self.moneda)
        for linea in self.lineas:
            total = total + linea.costo
        return total

    @property
    def utilidad(self) -> Dinero:
        return self.total - self.costo_total

    @property
    def cajas_por_tipo(self) -> dict[uuid.UUID, int]:
        acumulado: dict[uuid.UUID, int] = {}
        for linea in self.lineas:
            if linea.tipo_caja_id is None:
                continue
            acumulado[linea.tipo_caja_id] = acumulado.get(linea.tipo_caja_id, 0) + linea.cajas
        return acumulado

    def evento_creacion(self, actor_id: uuid.UUID | None = None) -> EventoDominio:
        return EventoDominio(
            agregado_tipo="venta",
            agregado_id=self.id,
            tipo_evento="venta_confirmada",
            datos_despues={
                "cliente_id": str(self.cliente_id),
                "total": str(self.total.monto),
                "costo_total": str(self.costo_total.monto),
                "requiere_revision": self.requiere_revision,
            },
            actor_usuario_id=actor_id,
        )


def armar_venta(
    *,
    cliente_id: uuid.UUID,
    fecha: date,
    items: list[ItemVenta],
    lotes_disponibles: list[Lote],
    moneda: str = "MXN",
    destino_id: uuid.UUID | None = None,
    transportista_id: uuid.UUID | None = None,
    nota: str | None = None,
) -> Venta:
    """RN-05/RN-06: consume inventario por FIFO y calcula el costo.

    Muta `lotes_disponibles` (reduce cajas_disponibles). El caso de uso es
    responsable de persistir esos lotes despues. Si falta inventario no
    bloquea: marca la venta para revision (RN-05/DECISION-1).
    """
    if not items:
        raise ValueError("Una venta requiere al menos una linea")

    lineas: list[LineaVenta] = []
    requiere_revision = False
    for item in items:
        asignaciones, faltante = asignar_fifo(
            lotes_disponibles,
            item.producto_id,
            item.cajas,
            lotes_preferidos=item.lotes_preferidos,
            permitir_faltante=True,
        )
        if faltante > 0:
            requiere_revision = True
        importe = calcular_importe(
            cajas=item.cajas,
            precio_unitario=item.precio_unitario,
            unidad_precio=item.unidad_precio,
            kg_por_caja=item.kg_por_caja,
        )
        lineas.append(
            LineaVenta(
                producto_id=item.producto_id,
                cajas=item.cajas,
                precio_unitario=item.precio_unitario,
                unidad_precio=item.unidad_precio,
                importe=importe,
                costo=costo_de_venta(asignaciones),
                asignaciones=asignaciones,
                cajas_faltantes=faltante,
                tipo_caja_id=item.tipo_caja_id,
                kg_por_caja=item.kg_por_caja,
            )
        )

    return Venta(
        cliente_id=cliente_id,
        fecha=fecha,
        lineas=lineas,
        moneda=moneda,
        destino_id=destino_id,
        transportista_id=transportista_id,
        nota=nota,
        requiere_revision=requiere_revision,
    )
