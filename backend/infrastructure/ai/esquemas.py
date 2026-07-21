"""Modelos Pydantic que validan la salida de la IA antes de tocar el dominio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Intencion(StrEnum):
    COMPRA = "compra"
    VENTA = "venta"
    DEVOLUCION_CAJAS = "devolucion_cajas"
    PAGO = "pago"
    GASTO = "gasto"
    CONSULTA = "consulta"
    CORRECCION = "correccion"
    OTRO = "otro"


def _a_decimal(valor: str | None) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor).replace(",", "").replace("$", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"Monto invalido: {valor!r}") from exc


class LineaExtraida(BaseModel):
    producto_texto: str | None = None
    tipo_caja_texto: str | None = None
    cajas: int | None = None
    kg_por_caja: Decimal | None = None
    precio_unitario: Decimal | None = None
    unidad_precio: str | None = None

    @field_validator("kg_por_caja", "precio_unitario", mode="before")
    @classmethod
    def _decimal(cls, v):
        return _a_decimal(v) if isinstance(v, str) else v

    @field_validator("cajas")
    @classmethod
    def _cajas_positivas(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("cajas debe ser mayor que cero")
        return v

    def campos_faltantes(self) -> list[str]:
        faltan = []
        if not self.producto_texto:
            faltan.append("producto")
        if self.cajas is None:
            faltan.append("cantidad de cajas")
        if self.precio_unitario is None:
            faltan.append("precio")
        if self.unidad_precio == "kg" and self.kg_por_caja is None:
            faltan.append("kilos por caja")
        return faltan


class OperacionExtraida(BaseModel):
    tipo: str
    fecha: date | None = None
    contraparte_texto: str | None = None
    origen_texto: str | None = None
    destino_texto: str | None = None
    transportista_texto: str | None = None
    folio_externo: str | None = None
    referencia_operacion_anterior: bool = False
    lineas: list[LineaExtraida] = Field(default_factory=list)
    monto: Decimal | None = None
    categoria_gasto: str | None = None
    nota: str | None = None

    @field_validator("monto", mode="before")
    @classmethod
    def _monto(cls, v):
        return _a_decimal(v) if isinstance(v, str) else v

    def campos_faltantes(self) -> list[str]:
        faltan: list[str] = []
        if not self.contraparte_texto:
            faltan.append("contraparte")
        if self.tipo in ("compra", "venta"):
            if not self.lineas:
                faltan.append("detalle de la operacion")
            for linea in self.lineas:
                faltan.extend(linea.campos_faltantes())
        if self.tipo in ("pago", "gasto") and self.monto is None:
            faltan.append("monto")
        if self.tipo == "devolucion_cajas" and not any(linea.cajas for linea in self.lineas):
            faltan.append("cantidad de cajas")
        return list(dict.fromkeys(faltan))


class ExtraccionIA(BaseModel):
    operaciones: list[OperacionExtraida] = Field(default_factory=list)
    preguntas: list[str] = Field(default_factory=list)
    confianza: float = 0.0

    @property
    def esta_completa(self) -> bool:
        return bool(self.operaciones) and not any(op.campos_faltantes() for op in self.operaciones)

    def todas_las_faltantes(self) -> list[str]:
        faltan: list[str] = []
        for op in self.operaciones:
            faltan.extend(op.campos_faltantes())
        return list(dict.fromkeys(faltan))
