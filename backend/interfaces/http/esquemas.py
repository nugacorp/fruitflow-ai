"""Modelos Pydantic de la API /v1. Espejo del contrato de payload de los
casos de uso (ver backend/application/use_cases/borradores.py)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.application.dto.comandos import ResultadoOperacion
from backend.domain.operaciones.borrador import Borrador


class LineaEntrada(BaseModel):
    producto_id: uuid.UUID
    cajas: int = Field(gt=0)
    precio_unitario: str
    unidad_precio: str = "caja"
    kg_por_caja: str | None = None
    tipo_caja_id: uuid.UUID | None = None
    lotes_preferidos: list[uuid.UUID] | None = None


class CompraEntrada(BaseModel):
    proveedor_id: uuid.UUID
    fecha: date
    items: list[LineaEntrada] = Field(min_length=1)
    origen_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    folio_externo: str | None = None
    nota: str | None = None


class VentaEntrada(BaseModel):
    cliente_id: uuid.UUID
    fecha: date
    items: list[LineaEntrada] = Field(min_length=1)
    destino_id: uuid.UUID | None = None
    transportista_id: uuid.UUID | None = None
    nota: str | None = None


class DevolucionEntrada(BaseModel):
    contraparte_id: uuid.UUID
    tipo_caja_id: uuid.UUID
    cantidad: int = Field(gt=0)
    fecha: date
    recibida: bool = True
    nota: str | None = None


class PagoEntrada(BaseModel):
    contraparte_id: uuid.UUID
    direccion: str  # "cobro" | "pago"
    monto: str
    fecha: date
    metodo: str | None = None
    referencia: str | None = None
    nota: str | None = None


class GastoEntrada(BaseModel):
    categoria: str
    monto: str
    fecha: date
    descripcion: str | None = None
    contraparte_id: uuid.UUID | None = None
    imputable_tipo: str | None = None
    imputable_id: uuid.UUID | None = None


class AnulacionEntrada(BaseModel):
    tipo: str  # "compra" | "venta"
    folio: int
    motivo: str | None = None


class BorradorEntrada(BaseModel):
    intencion: str
    payload: dict[str, Any]
    faltantes: list[str] = Field(default_factory=list)
    preguntas: list[str] = Field(default_factory=list)
    confianza: float | None = None
    mensaje_id: uuid.UUID | None = None


class BorradorEdicion(BaseModel):
    cambios: dict[str, Any]


class AdvertenciaSalida(BaseModel):
    codigo: str
    datos: dict[str, Any]


class ResultadoSalida(BaseModel):
    id: uuid.UUID
    folio: int | None
    advertencias: list[AdvertenciaSalida]
    requiere_revision: bool

    @classmethod
    def de(cls, resultado: ResultadoOperacion) -> ResultadoSalida:
        return cls(
            id=resultado.id,
            folio=resultado.folio,
            advertencias=[
                AdvertenciaSalida(
                    codigo=a.codigo,
                    datos={k: _json_seguro(v) for k, v in a.datos.items()},
                )
                for a in resultado.advertencias
            ],
            requiere_revision=resultado.requiere_revision,
        )


class BorradorSalida(BaseModel):
    id: uuid.UUID
    intencion: str
    estado: str
    payload: dict[str, Any]
    faltantes: list[str]
    preguntas: list[str]
    confianza: float | None
    expira_en: datetime
    resultado_tipo: str | None
    resultado_id: uuid.UUID | None

    @classmethod
    def de(cls, borrador: Borrador) -> BorradorSalida:
        return cls(
            id=borrador.id,
            intencion=borrador.intencion,
            estado=borrador.estado.value,
            payload=borrador.payload,
            faltantes=borrador.faltantes,
            preguntas=borrador.preguntas,
            confianza=borrador.confianza,
            expira_en=borrador.expira_en,
            resultado_tipo=borrador.resultado_tipo,
            resultado_id=borrador.resultado_id,
        )


def _json_seguro(valor: Any) -> Any:
    return str(valor) if isinstance(valor, uuid.UUID) else valor
