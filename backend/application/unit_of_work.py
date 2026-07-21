"""Unit of Work: una transaccion por caso de uso, eventos incluidos."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.common.tipos import EventoDominio


class UnitOfWork:
    """Agrupa cambios y eventos. Si algo falla, no se guarda nada."""

    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion
        self.eventos: list[EventoDominio] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        if tipo is not None:
            await self.rollback()
        else:
            await self.commit()

    def registrar(self, *eventos: EventoDominio) -> None:
        self.eventos.extend(eventos)

    async def commit(self) -> None:
        await self._persistir_eventos()
        await self.sesion.commit()

    async def rollback(self) -> None:
        await self.sesion.rollback()

    async def _persistir_eventos(self) -> None:
        """RN: toda modificacion queda auditada. Nunca se sobreescribe."""
        if not self.eventos:
            return
        from backend.config import get_settings
        from backend.infrastructure.db.models import EventoAuditoria

        empresa_id = get_settings().empresa_id
        for evento in self.eventos:
            self.sesion.add(
                EventoAuditoria(
                    id=evento.id,
                    empresa_id=empresa_id,
                    agregado_tipo=evento.agregado_tipo,
                    agregado_id=evento.agregado_id,
                    tipo_evento=evento.tipo_evento,
                    datos_antes=evento.datos_antes,
                    datos_despues=evento.datos_despues,
                    actor_usuario_id=evento.actor_usuario_id,
                    origen=evento.origen,
                    ocurrido_en=evento.ocurrido_en,
                )
            )
        self.eventos.clear()
