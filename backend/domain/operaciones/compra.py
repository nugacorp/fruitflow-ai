"""Agregado Compra. Puro: arma lineas, calcula importes y genera lotes."""

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
from backend.domain.operaciones.costeo import Lote, calcular_importe


@dataclass(frozen=True, slots=True)
class ItemCompra:
    """Entrada ya resuelta: la IA extrajo texto, la BD resolvio los ids."""

    producto_id: uuid.UUID
    cajas: int
    precio_unitario: Dinero
    unidad_precio: UnidadPrecio = UnidadPrecio.CAJA
    kg_por_caja: Decimal | None = None
    tipo_caja_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class LineaCompra:
    producto_id: uuid.UUID
    cajas: int
    precio_unitario: Dinero
    unidad_precio: UnidadPrecio
    importe: Dinero
    tipo_caja_id: uuid.UUID | None = None
    kg_por_caja: Decimal | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)


@dataclass(slots=True)
class Compra:
    proveedor_id: uuid.UUID
    fecha: date
    lineas: list[LineaCompra]
    lotes: list[Lote]
    moneda: str = "MXN"
    origen_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    folio_externo: str | None = None
    nota: str | None = None
    estado: EstadoOperacion = EstadoOperacion.CONFIRMADO
    folio: int | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)

    @property
    def subtotal(self) -> Dinero:
        total = Dinero.cero(self.moneda)
        for linea in self.lineas:
            total = total + linea.importe
        return total

    @property
    def total(self) -> Dinero:
        return self.subtotal

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
            agregado_tipo="compra",
            agregado_id=self.id,
            tipo_evento="compra_confirmada",
            datos_despues={
                "proveedor_id": str(self.proveedor_id),
                "total": str(self.total.monto),
                "cajas": sum(linea.cajas for linea in self.lineas),
            },
            actor_usuario_id=actor_id,
        )


def armar_compra(
    *,
    proveedor_id: uuid.UUID,
    fecha: date,
    items: list[ItemCompra],
    moneda: str = "MXN",
    origen_id: uuid.UUID | None = None,
    transportista_id: uuid.UUID | None = None,
    folio_externo: str | None = None,
    nota: str | None = None,
) -> Compra:
    """RN-05/RN-07: cada linea calcula su importe y crea un lote de inventario.

    El costo unitario del lote se guarda por caja aunque el precio venga por
    kilo, para que el costeo FIFO siempre razone en cajas.
    """
    if not items:
        raise ValueError("Una compra requiere al menos una linea")

    lineas: list[LineaCompra] = []
    lotes: list[Lote] = []
    for item in items:
        importe = calcular_importe(
            cajas=item.cajas,
            precio_unitario=item.precio_unitario,
            unidad_precio=item.unidad_precio,
            kg_por_caja=item.kg_por_caja,
        )
        linea = LineaCompra(
            producto_id=item.producto_id,
            cajas=item.cajas,
            precio_unitario=item.precio_unitario,
            unidad_precio=item.unidad_precio,
            importe=importe,
            tipo_caja_id=item.tipo_caja_id,
            kg_por_caja=item.kg_por_caja,
        )
        costo_unitario_caja = Dinero(importe.monto / item.cajas, moneda)
        lotes.append(
            Lote(
                producto_id=item.producto_id,
                cajas_iniciales=item.cajas,
                cajas_disponibles=item.cajas,
                costo_unitario=costo_unitario_caja,
                fecha=fecha,
                compra_linea_id=linea.id,
            )
        )
        lineas.append(linea)

    return Compra(
        proveedor_id=proveedor_id,
        fecha=fecha,
        lineas=lineas,
        lotes=lotes,
        moneda=moneda,
        origen_id=origen_id,
        transportista_id=transportista_id,
        folio_externo=folio_externo,
        nota=nota,
    )
