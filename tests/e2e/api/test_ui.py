"""Superficies de UI: catalogos, tablero de cajas, borrador por id y panel web."""

import base64
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.domain.common.tipos import TipoContraparte, nuevo_id
from backend.domain.contrapartes.modelo import Contraparte
from backend.interfaces.http.dependencias import obtener_uow
from backend.interfaces.http.main import app
from tests.fakes import UnidadDeTrabajoMem

LLAVE = {"X-Internal-Key": "cambiame"}
BASIC = {"Authorization": "Basic " + base64.b64encode(b"admin:cambiame").decode()}
HOY = date(2026, 7, 20).isoformat()
PRODUCTO = nuevo_id()
CAJA = nuevo_id()


@pytest.fixture
def uow():
    uow = UnidadDeTrabajoMem()
    uow.catalogos.productos_datos[PRODUCTO] = "Frambuesa Adelita"
    uow.catalogos.tipos_caja_datos[CAJA] = "Caja plastica 8 lb"
    return uow


@pytest.fixture
def cliente_api(uow):
    app.dependency_overrides[obtener_uow] = lambda: uow
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def proveedor(uow):
    contraparte = Contraparte(nombre="Rancho Los Pinos", tipo=TipoContraparte.PROVEEDOR)
    uow.contrapartes.datos[contraparte.id] = contraparte
    return contraparte


def cuerpo_compra(proveedor):
    return {
        "proveedor_id": str(proveedor.id),
        "fecha": HOY,
        "items": [
            {
                "producto_id": str(PRODUCTO),
                "cajas": 220,
                "precio_unitario": "385.00",
                "tipo_caja_id": str(CAJA),
            }
        ],
    }


def test_catalogos(cliente_api, proveedor):
    r = cliente_api.get("/v1/catalogos", headers=LLAVE)
    assert r.status_code == 200
    datos = r.json()
    assert datos["contrapartes"][0]["nombre"] == "Rancho Los Pinos"
    assert datos["contrapartes"][0]["tipo"] == "proveedor"
    assert datos["productos"][0]["nombre"] == "Frambuesa Adelita"
    assert datos["tipos_caja"][0]["nombre"] == "Caja plastica 8 lb"


def test_tablero_de_cajas_global(cliente_api, proveedor):
    cliente_api.post("/v1/compras", json=cuerpo_compra(proveedor), headers=LLAVE)
    r = cliente_api.get("/v1/saldos/cajas", headers=LLAVE)
    assert r.status_code == 200
    filas = r.json()
    assert len(filas) == 1
    assert filas[0]["nombre"] == "Rancho Los Pinos"
    assert filas[0]["total"] == -220  # RN-03: yo le debo las cajas al proveedor


def test_borrador_por_id_incluye_payload(cliente_api, proveedor):
    payload = cuerpo_compra(proveedor)
    r = cliente_api.post(
        "/v1/borradores", json={"intencion": "compra", "payload": payload}, headers=LLAVE
    )
    borrador_id = r.json()["id"]

    r = cliente_api.get(f"/v1/borradores/{borrador_id}", headers=LLAVE)
    assert r.status_code == 200
    assert r.json()["payload"]["proveedor_id"] == payload["proveedor_id"]

    r = cliente_api.get(f"/v1/borradores/{nuevo_id()}", headers=LLAVE)
    assert r.status_code == 404


def test_panel_exige_credenciales(cliente_api):
    assert cliente_api.get("/panel").status_code == 401
    assert cliente_api.get("/panel/datos").status_code == 401
    mala = {"Authorization": "Basic " + base64.b64encode(b"admin:incorrecta").decode()}
    assert cliente_api.get("/panel/datos", headers=mala).status_code == 401


def test_panel_pagina_html(cliente_api):
    r = cliente_api.get("/panel", headers=BASIC)
    assert r.status_code == 200
    assert "FruitFlow" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_panel_datos(cliente_api, proveedor):
    cliente_api.post("/v1/compras", json=cuerpo_compra(proveedor), headers=LLAVE)
    cliente_api.post(
        "/v1/borradores",
        json={"intencion": "venta", "payload": {"fecha": HOY}, "faltantes": ["cliente_id"]},
        headers=LLAVE,
    )

    r = cliente_api.get("/panel/datos", params={"desde": HOY, "hasta": HOY}, headers=BASIC)
    assert r.status_code == 200
    datos = r.json()
    assert datos["resumen"]["compras_total"] == "84700.00"
    assert datos["cajas"][0]["por_tipo"] == {"Caja plastica 8 lb": -220}
    assert datos["cxp"][0]["pendiente"] == "84700.00"
    assert datos["cxc"] == []
    assert datos["borradores"][0]["intencion"] == "venta"
