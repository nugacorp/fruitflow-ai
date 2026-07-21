"""Reglas de cajas retornables (RN-03, RN-04).

Principio: la caja tiene dueno. Cuando el proveedor me entrega fruta en SUS
cajas, YO quedo debiendo. Cuando entrego al cliente, EL cliente me debe.
El saldo se lee siempre desde mi perspectiva:

    saldo > 0  ->  la contraparte me debe cajas
    saldo < 0  ->  yo le debo cajas a la contraparte
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from backend.domain.common.tipos import SaldoCajasNegativo, ahora, nuevo_id


class TipoMovimientoCaja(StrEnum):
    ENTREGA_LLENA = "entrega_llena"
    RECEPCION_LLENA = "recepcion_llena"
    DEVOLUCION_RECIBIDA = "devolucion_recibida"
    DEVOLUCION_ENTREGADA = "devolucion_entregada"
    AJUSTE = "ajuste"
    MERMA = "merma"


SIGNOS: dict[TipoMovimientoCaja, int] = {
    TipoMovimientoCaja.ENTREGA_LLENA: +1,
    TipoMovimientoCaja.RECEPCION_LLENA: -1,
    TipoMovimientoCaja.DEVOLUCION_RECIBIDA: -1,
    TipoMovimientoCaja.DEVOLUCION_ENTREGADA: +1,
    TipoMovimientoCaja.MERMA: -1,
    TipoMovimientoCaja.AJUSTE: +1,
}

DESCRIPCION: dict[TipoMovimientoCaja, str] = {
    TipoMovimientoCaja.ENTREGA_LLENA: "cajas entregadas al cliente",
    TipoMovimientoCaja.RECEPCION_LLENA: "cajas recibidas del proveedor",
    TipoMovimientoCaja.DEVOLUCION_RECIBIDA: "vacias que me regresaron",
    TipoMovimientoCaja.DEVOLUCION_ENTREGADA: "vacias que regrese",
    TipoMovimientoCaja.MERMA: "cajas perdidas o rotas",
    TipoMovimientoCaja.AJUSTE: "ajuste de conciliacion",
}


def signo_de(tipo: TipoMovimientoCaja, *, signo_explicito: int | None = None) -> int:
    """El ajuste admite signo explicito; el resto es determinista."""
    if tipo is TipoMovimientoCaja.AJUSTE:
        if signo_explicito not in (-1, 1):
            raise ValueError("Un ajuste requiere signo explicito (-1 o 1)")
        return signo_explicito
    return SIGNOS[tipo]


@dataclass(frozen=True, slots=True)
class MovimientoCaja:
    contraparte_id: uuid.UUID
    tipo_caja_id: uuid.UUID
    tipo: TipoMovimientoCaja
    cantidad: int
    fecha: date
    signo: int = 0
    referencia_tipo: str | None = None
    referencia_id: uuid.UUID | None = None
    nota: str | None = None
    id: uuid.UUID = field(default_factory=nuevo_id)

    def __post_init__(self) -> None:
        if self.cantidad <= 0:
            raise ValueError("La cantidad de cajas debe ser mayor que cero")
        if self.signo == 0:
            object.__setattr__(self, "signo", signo_de(self.tipo))
        if self.signo not in (-1, 1):
            raise ValueError("El signo debe ser -1 o 1")

    @property
    def efecto(self) -> int:
        """Impacto sobre el saldo de la contraparte."""
        return self.cantidad * self.signo


@dataclass(frozen=True, slots=True)
class SaldoCajas:
    contraparte_id: uuid.UUID
    tipo_caja_id: uuid.UUID
    saldo: int

    @property
    def me_deben(self) -> int:
        return max(self.saldo, 0)

    @property
    def le_debo(self) -> int:
        return max(-self.saldo, 0)

    def descripcion(self, nombre: str) -> str:
        if self.saldo > 0:
            return f"{nombre} te debe {self.saldo} cajas"
        if self.saldo < 0:
            return f"Le debes {-self.saldo} cajas a {nombre}"
        return f"Estas a mano con {nombre}"


def calcular_saldo(movimientos: list[MovimientoCaja]) -> int:
    return sum(m.efecto for m in movimientos)


def aplicar(
    saldo_actual: int,
    movimiento: MovimientoCaja,
    *,
    permitir_negativo: bool = True,
) -> tuple[int, bool]:
    """Aplica un movimiento al saldo.

    Devuelve (saldo_nuevo, requiere_revision).

    DECISION-1 (default): se permite el saldo negativo del lado del cliente
    porque en la practica devuelven cajas de embarques no registrados; se
    marca requiere_revision y el bot lo advierte. Si permitir_negativo=False
    se levanta SaldoCajasNegativo.
    """
    saldo_nuevo = saldo_actual + movimiento.efecto
    cruzo_a_negativo = saldo_actual >= 0 > saldo_nuevo
    requiere_revision = cruzo_a_negativo and movimiento.tipo in (
        TipoMovimientoCaja.DEVOLUCION_RECIBIDA,
        TipoMovimientoCaja.MERMA,
    )
    if requiere_revision and not permitir_negativo:
        raise SaldoCajasNegativo(
            f"El saldo quedaria en {saldo_nuevo} cajas.",
            sugerencia="Verifica si la devolucion corresponde a un embarque anterior.",
        )
    return saldo_nuevo, requiere_revision


def movimientos_de_venta(
    *,
    cliente_id: uuid.UUID,
    venta_id: uuid.UUID,
    fecha: date,
    cajas_por_tipo: dict[uuid.UUID, int],
    cajas_retornables: bool = True,
) -> list[MovimientoCaja]:
    """RN-03: toda venta confirmada genera cajas por cobrar al cliente."""
    if not cajas_retornables:
        return []
    return [
        MovimientoCaja(
            contraparte_id=cliente_id,
            tipo_caja_id=tipo_caja_id,
            tipo=TipoMovimientoCaja.ENTREGA_LLENA,
            cantidad=cantidad,
            fecha=fecha,
            referencia_tipo="venta",
            referencia_id=venta_id,
        )
        for tipo_caja_id, cantidad in cajas_por_tipo.items()
        if cantidad > 0
    ]


def movimientos_de_compra(
    *,
    proveedor_id: uuid.UUID,
    compra_id: uuid.UUID,
    fecha: date,
    cajas_por_tipo: dict[uuid.UUID, int],
    cajas_retornables: bool = True,
) -> list[MovimientoCaja]:
    """RN-03: toda compra confirmada genera cajas que YO debo al proveedor."""
    if not cajas_retornables:
        return []
    return [
        MovimientoCaja(
            contraparte_id=proveedor_id,
            tipo_caja_id=tipo_caja_id,
            tipo=TipoMovimientoCaja.RECEPCION_LLENA,
            cantidad=cantidad,
            fecha=fecha,
            referencia_tipo="compra",
            referencia_id=compra_id,
        )
        for tipo_caja_id, cantidad in cajas_por_tipo.items()
        if cantidad > 0
    ]


def movimientos_inversos(movimientos: list[MovimientoCaja]) -> list[MovimientoCaja]:
    """RN-08: anular nunca borra; genera el contra-asiento."""
    return [
        MovimientoCaja(
            contraparte_id=m.contraparte_id,
            tipo_caja_id=m.tipo_caja_id,
            tipo=TipoMovimientoCaja.AJUSTE,
            cantidad=m.cantidad,
            fecha=ahora().date(),
            signo=-m.signo,
            referencia_tipo=m.referencia_tipo,
            referencia_id=m.referencia_id,
            nota=f"Reverso de {m.tipo.value} ({m.id})",
        )
        for m in movimientos
    ]
