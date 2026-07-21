"""Puertos (Protocols) que la infraestructura debe implementar."""

from backend.application.ports.repositorios import (
    RepositorioBorradores,
    RepositorioCompras,
    RepositorioContrapartes,
    RepositorioGastos,
    RepositorioLotes,
    RepositorioMovimientosCaja,
    RepositorioPagos,
    RepositorioVentas,
)
from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo

__all__ = [
    "RepositorioBorradores",
    "RepositorioCompras",
    "RepositorioContrapartes",
    "RepositorioGastos",
    "RepositorioLotes",
    "RepositorioMovimientosCaja",
    "RepositorioPagos",
    "RepositorioVentas",
    "UnidadDeTrabajo",
]
