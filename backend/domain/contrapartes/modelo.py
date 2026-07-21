"""Contraparte como entidad de dominio pura (proveedor, cliente, etc.)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from backend.domain.common.tipos import TipoContraparte, nuevo_id


@dataclass(frozen=True, slots=True)
class Contraparte:
    """Con quien opero. El dominio solo necesita saber si sus cajas son
    retornables y de que tipo es, para decidir asientos de cajas y credito."""

    nombre: str
    tipo: TipoContraparte
    cajas_retornables: bool = True
    dias_credito: int = 0
    estado: str = "activo"
    id: uuid.UUID = field(default_factory=nuevo_id)

    @property
    def es_proveedor(self) -> bool:
        return self.tipo in (TipoContraparte.PROVEEDOR, TipoContraparte.AMBOS)

    @property
    def es_cliente(self) -> bool:
        return self.tipo in (TipoContraparte.CLIENTE, TipoContraparte.AMBOS)
