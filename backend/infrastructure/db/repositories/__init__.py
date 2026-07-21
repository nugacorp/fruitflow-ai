"""Adaptadores SQLAlchemy de los puertos (FASE 4)."""

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

__all__ = [
    "RepoBorradoresSQL",
    "RepoCatalogosSQL",
    "RepoComprasSQL",
    "RepoContrapartesSQL",
    "RepoGastosSQL",
    "RepoLotesSQL",
    "RepoMovimientosCajaSQL",
    "RepoPagosSQL",
    "RepoVentasSQL",
]
