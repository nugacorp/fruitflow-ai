"""Pagos y gastos como entidades de dominio puras (RN-10)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from backend.domain.common.tipos import Dinero, SaldoEfectivoNegativo, nuevo_id


class DireccionPago(StrEnum):
    COBRO = "cobro"  # me pagan (entra dinero)
    PAGO = "pago"  # yo pago (sale dinero)


@dataclass(frozen=True, slots=True)
class Pago:
    """Movimiento de dinero contra una contraparte."""

    contraparte_id: uuid.UUID
    direccion: DireccionPago
    monto: Dinero
    fecha: date
    metodo: str | None = None
    referencia: str | None = None
    nota: str | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)

    def __post_init__(self) -> None:
        if self.monto.es_negativo or self.monto.monto == 0:
            raise ValueError("El monto de un pago debe ser positivo")


@dataclass(frozen=True, slots=True)
class Gasto:
    """Gasto operativo. Puede imputarse a un lote/operacion para prorrateo."""

    categoria: str
    monto: Dinero
    fecha: date
    descripcion: str | None = None
    contraparte_id: uuid.UUID | None = None
    imputable_tipo: str | None = None
    imputable_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)

    def __post_init__(self) -> None:
        if self.monto.es_negativo or self.monto.monto == 0:
            raise ValueError("El monto de un gasto debe ser positivo")


def aplicar_a_efectivo(saldo_actual: Dinero, pago: Pago) -> Dinero:
    """RN-10: el efectivo si bloquea. Un pago de salida no puede dejar
    la caja chica en negativo."""
    delta = pago.monto if pago.direccion is DireccionPago.COBRO else -pago.monto
    saldo_nuevo = saldo_actual + delta
    if saldo_nuevo.es_negativo:
        raise SaldoEfectivoNegativo(
            f"El efectivo quedaria en {saldo_nuevo.formateado()}.",
            sugerencia="Registra primero un cobro o reduce el pago.",
        )
    return saldo_nuevo
