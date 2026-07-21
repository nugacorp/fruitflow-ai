"""Puerto de Unit of Work: agrupa repositorios y eventos en una transaccion."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from backend.application.ports.repositorios import (
    RepositorioBorradores,
    RepositorioCatalogos,
    RepositorioCompras,
    RepositorioContrapartes,
    RepositorioGastos,
    RepositorioLotes,
    RepositorioMovimientosCaja,
    RepositorioPagos,
    RepositorioVentas,
)
from backend.domain.common.tipos import EventoDominio


class UnidadDeTrabajo(Protocol):
    """Una transaccion por caso de uso. Si algo falla, no se guarda nada."""

    contrapartes: RepositorioContrapartes
    compras: RepositorioCompras
    ventas: RepositorioVentas
    lotes: RepositorioLotes
    movimientos_caja: RepositorioMovimientosCaja
    pagos: RepositorioPagos
    gastos: RepositorioGastos
    borradores: RepositorioBorradores
    catalogos: RepositorioCatalogos

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    def registrar(self, *eventos: EventoDominio) -> None:
        """Encola eventos de auditoria; se persisten en el commit."""
        ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
