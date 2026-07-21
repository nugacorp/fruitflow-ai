"""Agregado Borrador (RN-01): nada se guarda sin confirmacion explicita.

Toda extraccion de la IA crea un borrador con TTL de 24 horas. El usuario
lo confirma, lo edita o lo cancela; si nadie lo toca, expira. Un borrador
nunca se ejecuta solo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from backend.domain.common.tipos import (
    BorradorYaProcesado,
    EventoDominio,
    ahora,
    nuevo_id,
)

TTL_HORAS = 24


class EstadoBorrador(StrEnum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"
    EXPIRADO = "expirado"


@dataclass(slots=True)
class Borrador:
    intencion: str
    payload: dict[str, Any]
    faltantes: list[str] = field(default_factory=list)
    preguntas: list[str] = field(default_factory=list)
    confianza: float | None = None
    estado: EstadoBorrador = EstadoBorrador.PENDIENTE
    resultado_tipo: str | None = None
    resultado_id: uuid.UUID | None = None
    mensaje_id: uuid.UUID | None = None
    creado_en: datetime = field(default_factory=ahora)
    expira_en: datetime = field(default_factory=lambda: ahora() + timedelta(hours=TTL_HORAS))
    id: uuid.UUID = field(default_factory=nuevo_id)

    @property
    def esta_pendiente(self) -> bool:
        return self.estado is EstadoBorrador.PENDIENTE

    @property
    def esta_completo(self) -> bool:
        return not self.faltantes

    def esta_vencido(self, momento: datetime | None = None) -> bool:
        return (momento or ahora()) >= self.expira_en

    def exigir_pendiente(self) -> None:
        if not self.esta_pendiente:
            raise BorradorYaProcesado(
                f"Este borrador ya esta {self.estado.value}.",
                sugerencia="Manda la operacion de nuevo si quieres registrarla.",
            )

    def editar(self, cambios: dict[str, Any]) -> None:
        """Funde los cambios al payload y descuenta los faltantes cubiertos."""
        self.exigir_pendiente()
        self.payload.update(cambios)
        self.faltantes = [campo for campo in self.faltantes if campo not in cambios]

    def confirmar(self, resultado_tipo: str, resultado_id: uuid.UUID) -> None:
        self.exigir_pendiente()
        self.estado = EstadoBorrador.CONFIRMADO
        self.resultado_tipo = resultado_tipo
        self.resultado_id = resultado_id

    def cancelar(self) -> None:
        self.exigir_pendiente()
        self.estado = EstadoBorrador.CANCELADO

    def expirar(self) -> None:
        self.exigir_pendiente()
        self.estado = EstadoBorrador.EXPIRADO

    def evento(self, tipo_evento: str, actor_id: uuid.UUID | None = None) -> EventoDominio:
        return EventoDominio(
            agregado_tipo="borrador",
            agregado_id=self.id,
            tipo_evento=tipo_evento,
            datos_despues={
                "intencion": self.intencion,
                "estado": self.estado.value,
                "resultado_tipo": self.resultado_tipo,
                "resultado_id": str(self.resultado_id) if self.resultado_id else None,
            },
            actor_usuario_id=actor_id,
        )
