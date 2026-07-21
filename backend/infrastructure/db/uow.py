"""Unidad de trabajo SQLAlchemy: cumple el puerto UnidadDeTrabajo."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.application.unit_of_work import UnitOfWork
from backend.config import get_settings
from backend.infrastructure.db.repositories.sqlalchemy_repos import (
    RepoBorradoresSQL,
    RepoCatalogosSQL,
    RepoComprasSQL,
    RepoContrapartesSQL,
    RepoGastosSQL,
    RepoLotesSQL,
    RepoMovimientosCajaSQL,
    RepoPagosSQL,
    RepoVentasSQL,
)


class UnitOfWorkSQLAlchemy(UnitOfWork):
    """Una transaccion por caso de uso; los eventos van a eventos_auditoria."""

    contrapartes: RepositorioContrapartes
    compras: RepositorioCompras
    ventas: RepositorioVentas
    lotes: RepositorioLotes
    movimientos_caja: RepositorioMovimientosCaja
    pagos: RepositorioPagos
    gastos: RepositorioGastos
    borradores: RepositorioBorradores
    catalogos: RepositorioCatalogos

    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion)
        empresa_id = uuid.UUID(get_settings().empresa_id)
        self.contrapartes = RepoContrapartesSQL(sesion, empresa_id)
        self.compras = RepoComprasSQL(sesion, empresa_id)
        self.ventas = RepoVentasSQL(sesion, empresa_id)
        self.lotes = RepoLotesSQL(sesion, empresa_id)
        self.movimientos_caja = RepoMovimientosCajaSQL(sesion, empresa_id)
        self.pagos = RepoPagosSQL(sesion, empresa_id)
        self.gastos = RepoGastosSQL(sesion, empresa_id)
        self.borradores = RepoBorradoresSQL(sesion, empresa_id)
        self.catalogos = RepoCatalogosSQL(sesion, empresa_id)
