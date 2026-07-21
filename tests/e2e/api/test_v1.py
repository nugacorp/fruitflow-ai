"""API /v1 de punta a punta: auth, registro, consultas y borradores.

Usa la UnidadDeTrabajo en memoria via dependency_overrides; el contrato
HTTP es el mismo que tendra la version con PostgreSQL.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.domain.common.tipos import TipoContraparte, nuevo_id
from backend.domain.contrapartes.modelo import Contraparte
from backend.interfaces.http.dependencias import obtener_uow
from backend.interfaces.http.main import app
from tests.fakes import UnidadDeTrabajoMem

LLAVE = {"X-Internal-Key": "cambiame"}
HOY = date(2026, 7, 20).isoformat()
PRODUCTO = nuevo_id()
CAJA = nuevo_id()


@pytest.fixture
def uow():
    return UnidadDeTrabajoMem()


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


@pytest.fixture
def cliente(uow):
    contraparte = Contraparte(nombre="Frutas del Valle", tipo=TipoContraparte.CLIENTE)
    uow.contrapartes.datos[contraparte.id] = contraparte
    return contraparte


def cuerpo_compra(proveedor, cajas=220, precio="385.00"):
    return {
        "proveedor_id": str(proveedor.id),
        "fecha": HOY,
        "items": [
            {
                "producto_id": str(PRODUCTO),
                "cajas": cajas,
                "precio_unitario": precio,
                "tipo_caja_id": str(CAJA),
            }
        ],
    }


def cuerpo_venta(cliente, cajas=220, precio="455.00"):
    return {
        "cliente_id": str(cliente.id),
        "fecha": HOY,
        "items": [
            {
                "producto_id": str(PRODUCTO),
                "cajas": cajas,
                "precio_unitario": precio,
                "tipo_caja_id": str(CAJA),
            }
        ],
    }


def test_sin_llave_devuelve_401(cliente_api):
    assert cliente_api.get("/v1/borradores/pendientes").status_code == 401
    assert cliente_api.post("/v1/compras", json={}).status_code == 401


def test_compra_y_venta_devuelven_folio(cliente_api, proveedor, cliente):
    r = cliente_api.post("/v1/compras", json=cuerpo_compra(proveedor), headers=LLAVE)
    assert r.status_code == 201, r.text
    assert r.json()["folio"] == 1

    r = cliente_api.post("/v1/ventas", json=cuerpo_venta(cliente), headers=LLAVE)
    assert r.status_code == 201
    datos = r.json()
    assert datos["folio"] == 1
    assert datos["requiere_revision"] is False


def test_venta_sin_inventario_trae_advertencia(cliente_api, cliente):
    r = cliente_api.post("/v1/ventas", json=cuerpo_venta(cliente, cajas=50), headers=LLAVE)
    assert r.status_code == 201
    datos = r.json()
    assert datos["requiere_revision"] is True
    assert datos["advertencias"][0]["codigo"] == "inventario_insuficiente"


def test_error_de_dominio_es_422_no_500(cliente_api, uow):
    """El proveedor no existe: ErrorDominio -> 422 con codigo."""
    fantasma = {
        "proveedor_id": str(nuevo_id()),
        "fecha": HOY,
        "items": [{"producto_id": str(PRODUCTO), "cajas": 1, "precio_unitario": "10"}],
    }
    r = cliente_api.post("/v1/compras", json=fantasma, headers=LLAVE)
    assert r.status_code == 422
    assert r.json()["codigo"] == "OPE-002"


def test_anulacion_por_folio(cliente_api, proveedor):
    cliente_api.post("/v1/compras", json=cuerpo_compra(proveedor), headers=LLAVE)
    r = cliente_api.post("/v1/anulaciones", json={"tipo": "compra", "folio": 1}, headers=LLAVE)
    assert r.status_code == 200
    r = cliente_api.post("/v1/anulaciones", json={"tipo": "compra", "folio": 1}, headers=LLAVE)
    assert r.status_code == 422
    assert r.json()["codigo"] == "OPE-003"


def test_consultas_de_saldos_y_resumen(cliente_api, proveedor, cliente):
    cliente_api.post("/v1/compras", json=cuerpo_compra(proveedor), headers=LLAVE)
    cliente_api.post("/v1/ventas", json=cuerpo_venta(cliente), headers=LLAVE)
    cliente_api.post(
        "/v1/pagos",
        json={
            "contraparte_id": str(cliente.id),
            "direccion": "cobro",
            "monto": "60000.00",
            "fecha": HOY,
        },
        headers=LLAVE,
    )

    r = cliente_api.get(f"/v1/saldos/cajas/{cliente.id}", headers=LLAVE)
    assert r.json()["total"] == 220

    r = cliente_api.get(f"/v1/saldos/cxc/{cliente.id}", headers=LLAVE)
    assert r.json()["pendiente"] == "40100.00"

    r = cliente_api.get(f"/v1/saldos/cxp/{proveedor.id}", headers=LLAVE)
    assert r.json()["pendiente"] == "84700.00"

    r = cliente_api.get("/v1/resumen", params={"desde": HOY, "hasta": HOY}, headers=LLAVE)
    datos = r.json()
    assert datos["utilidad_bruta"] == "15400.00"
    assert datos["margen"] == "15.38"


def test_ciclo_de_borrador_por_api(cliente_api, proveedor):
    r = cliente_api.post(
        "/v1/borradores",
        json={"intencion": "compra", "payload": cuerpo_compra(proveedor)},
        headers=LLAVE,
    )
    assert r.status_code == 201
    borrador_id = r.json()["id"]
    assert r.json()["estado"] == "pendiente"

    r = cliente_api.get("/v1/borradores/pendientes", headers=LLAVE)
    assert len(r.json()) == 1

    r = cliente_api.post(f"/v1/borradores/{borrador_id}/confirmar", headers=LLAVE)
    assert r.status_code == 200
    assert r.json()["folio"] == 1

    # confirmar dos veces: BOR-002, y no duplica la compra
    r = cliente_api.post(f"/v1/borradores/{borrador_id}/confirmar", headers=LLAVE)
    assert r.status_code == 422
    assert r.json()["codigo"] == "BOR-002"


def test_editar_y_cancelar_borrador(cliente_api, proveedor):
    r = cliente_api.post(
        "/v1/borradores",
        json={
            "intencion": "compra",
            "payload": {"fecha": HOY},
            "faltantes": ["proveedor_id", "items"],
        },
        headers=LLAVE,
    )
    borrador_id = r.json()["id"]

    r = cliente_api.post(f"/v1/borradores/{borrador_id}/confirmar", headers=LLAVE)
    assert r.status_code == 422  # faltan datos

    cuerpo = cuerpo_compra(proveedor)
    r = cliente_api.patch(
        f"/v1/borradores/{borrador_id}",
        json={"cambios": {"proveedor_id": cuerpo["proveedor_id"], "items": cuerpo["items"]}},
        headers=LLAVE,
    )
    assert r.json()["faltantes"] == []

    r = cliente_api.post(f"/v1/borradores/{borrador_id}/cancelar", headers=LLAVE)
    assert r.json()["estado"] == "cancelado"
