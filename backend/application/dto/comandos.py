"""Comandos de entrada a los casos de uso.

Aqui ya no hay texto libre: las entidades vienen resueltas a UUID (RN-09
ocurrio antes, contra la BD) y los montos son Decimal via Dinero.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from backend.domain.common.tipos import Dinero
from backend.domain.finanzas.modelo import DireccionPago
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta


@dataclass(frozen=True, slots=True)
class ComandoRegistrarCompra:
    proveedor_id: uuid.UUID
    fecha: date
    items: list[ItemCompra]
    origen_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    folio_externo: str | None = None
    nota: str | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComandoRegistrarVenta:
    cliente_id: uuid.UUID
    fecha: date
    items: list[ItemVenta]
    destino_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    nota: str | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComandoRegistrarDevolucionCajas:
    """Cajas vacias que regresan. `recibida=True` cuando me las regresan a mi;
    False cuando yo se las regreso al proveedor."""

    contraparte_id: uuid.UUID
    tipo_caja_id: uuid.UUID
    cantidad: int
    fecha: date
    recibida: bool = True
    nota: str | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComandoRegistrarPago:
    contraparte_id: uuid.UUID
    direccion: DireccionPago
    monto: Dinero
    fecha: date
    metodo: str | None = None
    referencia: str | None = None
    nota: str | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComandoRegistrarGasto:
    categoria: str
    monto: Dinero
    fecha: date
    descripcion: str | None = None
    contraparte_id: uuid.UUID | None = None
    imputable_tipo: str | None = None
    imputable_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComandoAnularOperacion:
    """Anula una compra o venta por folio (RN-08)."""

    tipo: str  # "compra" | "venta"
    folio: int
    motivo: str | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class Advertencia:
    """Advertencia estructurada. El texto final lo arma la interfaz con i18n."""

    codigo: str  # "saldo_cajas_negativo" | "inventario_insuficiente" | ...
    datos: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResultadoOperacion:
    """Lo que el bot necesita para responder: folio y advertencias."""

    id: uuid.UUID
    folio: int | None
    advertencias: list[Advertencia] = field(default_factory=list)

    @property
    def requiere_revision(self) -> bool:
        return bool(self.advertencias)
