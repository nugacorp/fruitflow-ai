"""Tipos base del dominio. Python puro: sin dependencias de infraestructura."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Self

CENTAVOS = Decimal("0.01")
KILOS = Decimal("0.001")


def nuevo_id() -> uuid.UUID:
    """UUID v7 (ordenable por tiempo). Cae a uuid4 si la libreria no esta."""
    try:
        from uuid6 import uuid7

        return uuid7()
    except ImportError:  # pragma: no cover
        return uuid.uuid4()


def ahora() -> datetime:
    return datetime.now(UTC)


class ErrorDominio(Exception):
    """Error de negocio esperado. Nunca debe producir un 500."""

    codigo = "DOM-000"

    def __init__(self, detalle: str, sugerencia: str | None = None) -> None:
        super().__init__(detalle)
        self.detalle = detalle
        self.sugerencia = sugerencia

    def a_dict(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "codigo": self.codigo,
            "detalle": self.detalle,
            "sugerencia": self.sugerencia,
        }


class SaldoCajasNegativo(ErrorDominio):
    codigo = "CAJ-001"


class InventarioInsuficiente(ErrorDominio):
    codigo = "OPE-001"


class DatosIncompletos(ErrorDominio):
    codigo = "OPE-002"


class OperacionYaAnulada(ErrorDominio):
    codigo = "OPE-003"


class SaldoEfectivoNegativo(ErrorDominio):
    codigo = "FIN-001"


class BorradorExpirado(ErrorDominio):
    codigo = "BOR-001"


class BorradorYaProcesado(ErrorDominio):
    codigo = "BOR-002"


@dataclass(frozen=True, slots=True, order=True)
class Dinero:
    """Monto monetario. Siempre Decimal, nunca float."""

    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self) -> None:
        if not isinstance(self.monto, Decimal):
            raise TypeError("Dinero.monto debe ser Decimal; float esta prohibido")
        object.__setattr__(self, "monto", self.monto.quantize(CENTAVOS, ROUND_HALF_UP))

    @classmethod
    def de(cls, valor: str | int | Decimal, moneda: str = "MXN") -> Self:
        return cls(Decimal(str(valor)), moneda)

    @classmethod
    def cero(cls, moneda: str = "MXN") -> Self:
        return cls(Decimal("0"), moneda)

    def _verificar(self, otro: Dinero) -> None:
        if self.moneda != otro.moneda:
            raise ErrorDominio(f"No se pueden operar {self.moneda} con {otro.moneda}")

    def __add__(self, otro: Dinero) -> Dinero:
        self._verificar(otro)
        return Dinero(self.monto + otro.monto, self.moneda)

    def __sub__(self, otro: Dinero) -> Dinero:
        self._verificar(otro)
        return Dinero(self.monto - otro.monto, self.moneda)

    def __mul__(self, factor: int | Decimal) -> Dinero:
        return Dinero(self.monto * Decimal(str(factor)), self.moneda)

    def __neg__(self) -> Dinero:
        return Dinero(-self.monto, self.moneda)

    @property
    def es_negativo(self) -> bool:
        return self.monto < 0

    def formateado(self) -> str:
        return f"${self.monto:,.2f}"

    def __str__(self) -> str:
        return f"{self.monto} {self.moneda}"


@dataclass(frozen=True, slots=True)
class Peso:
    """Peso en kilogramos con tres decimales."""

    kg: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kg, Decimal):
            raise TypeError("Peso.kg debe ser Decimal")
        object.__setattr__(self, "kg", self.kg.quantize(KILOS, ROUND_HALF_UP))

    @classmethod
    def de(cls, valor: str | int | Decimal) -> Self:
        return cls(Decimal(str(valor)))


class UnidadPrecio(StrEnum):
    CAJA = "caja"
    KG = "kg"


class EstadoOperacion(StrEnum):
    BORRADOR = "borrador"
    CONFIRMADO = "confirmado"
    ANULADO = "anulado"


class TipoContraparte(StrEnum):
    PROVEEDOR = "proveedor"
    CLIENTE = "cliente"
    AMBOS = "ambos"
    TRANSPORTISTA = "transportista"


@dataclass(frozen=True, slots=True)
class EventoDominio:
    """Evento que se persiste en eventos_auditoria. Nunca se borra."""

    agregado_tipo: str
    agregado_id: uuid.UUID
    tipo_evento: str
    datos_despues: dict[str, Any]
    datos_antes: dict[str, Any] | None = None
    actor_usuario_id: uuid.UUID | None = None
    origen: str = "telegram"
    id: uuid.UUID = field(default_factory=nuevo_id)
    ocurrido_en: datetime = field(default_factory=ahora)
