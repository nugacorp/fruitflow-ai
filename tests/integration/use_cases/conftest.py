"""Fixtures compartidas: una unidad de trabajo en memoria con catalogo base."""

from __future__ import annotations

import pytest

from backend.domain.common.tipos import TipoContraparte, nuevo_id
from backend.domain.contrapartes.modelo import Contraparte
from tests.fakes import UnidadDeTrabajoMem

PRODUCTO_FRAMBUESA = nuevo_id()
CAJA_RETORNABLE = nuevo_id()


@pytest.fixture
def uow() -> UnidadDeTrabajoMem:
    return UnidadDeTrabajoMem()


@pytest.fixture
def proveedor(uow) -> Contraparte:
    contraparte = Contraparte(nombre="Rancho Los Pinos", tipo=TipoContraparte.PROVEEDOR)
    uow.contrapartes.datos[contraparte.id] = contraparte
    return contraparte


@pytest.fixture
def cliente(uow) -> Contraparte:
    contraparte = Contraparte(nombre="Frutas del Valle", tipo=TipoContraparte.CLIENTE)
    uow.contrapartes.datos[contraparte.id] = contraparte
    return contraparte
