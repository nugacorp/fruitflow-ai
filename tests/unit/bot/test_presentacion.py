"""Presentacion del bot: vista de tarjetas y edicion campo por campo."""

from datetime import date, timedelta

import pytest

from backend.domain.common.tipos import nuevo_id
from telegram_bot.presentacion import Catalogos, aplicar_edicion, vista_operacion

PROVEEDOR = nuevo_id()
PRODUCTO = nuevo_id()
CAJA = nuevo_id()


@pytest.fixture
def catalogos():
    return Catalogos(
        {
            "contrapartes": [
                {"id": str(PROVEEDOR), "nombre": "Rancho Los Pinos", "tipo": "proveedor"},
            ],
            "productos": [{"id": str(PRODUCTO), "nombre": "Frambuesa Adelita"}],
            "tipos_caja": [{"id": str(CAJA), "nombre": "Caja plastica 8 lb"}],
        }
    )


@pytest.fixture
def payload_compra():
    return {
        "proveedor_id": str(PROVEEDOR),
        "fecha": "2026-07-20",
        "items": [{"producto_id": str(PRODUCTO), "cajas": 220, "precio_unitario": "385.00"}],
    }


def test_vista_muestra_nombres_no_uuids(catalogos, payload_compra):
    vista = vista_operacion("compra", payload_compra, catalogos)
    assert vista["contraparte"] == "Rancho Los Pinos"
    assert vista["lineas"][0]["producto"] == "Frambuesa Adelita"
    assert vista["lineas"][0]["importe"] == "84700.00"


def test_vista_traduce_faltantes(catalogos):
    vista = vista_operacion(
        "compra", {"fecha": "2026-07-20"}, catalogos, faltantes=["proveedor_id"]
    )
    assert vista["faltantes"] == ["proveedor"]


def test_editar_cajas_reescribe_items(catalogos, payload_compra):
    cambios = aplicar_edicion("compra", payload_compra, "cajas", "180", catalogos)
    assert cambios["items"][0]["cajas"] == 180
    assert cambios["items"][0]["precio_unitario"] == "385.00"


def test_editar_precio_normaliza_monto(catalogos, payload_compra):
    cambios = aplicar_edicion("compra", payload_compra, "precio", "$1,250.50", catalogos)
    assert cambios["items"][0]["precio_unitario"] == "1250.50"


def test_editar_contraparte_resuelve_alias(catalogos, payload_compra):
    cambios = aplicar_edicion("compra", payload_compra, "contraparte", "los pinos", catalogos)
    assert cambios == {"proveedor_id": str(PROVEEDOR)}


def test_editar_contraparte_desconocida_avisa(catalogos, payload_compra):
    with pytest.raises(ValueError, match="No encontre"):
        aplicar_edicion("compra", payload_compra, "contraparte", "Rancho Fantasma", catalogos)


def test_editar_fecha_acepta_relativas_y_ddmm(catalogos, payload_compra):
    assert aplicar_edicion("compra", payload_compra, "fecha", "hoy", catalogos) == {
        "fecha": date.today().isoformat()
    }
    assert aplicar_edicion("compra", payload_compra, "fecha", "ayer", catalogos) == {
        "fecha": (date.today() - timedelta(days=1)).isoformat()
    }
    assert aplicar_edicion("compra", payload_compra, "fecha", "15/07/2026", catalogos) == {
        "fecha": "2026-07-15"
    }


def test_editar_direccion_de_pago(catalogos):
    assert aplicar_edicion("pago", {}, "direccion", "cobro", catalogos) == {"direccion": "cobro"}
    assert aplicar_edicion("pago", {}, "direccion", "pago", catalogos) == {"direccion": "pago"}
    with pytest.raises(ValueError):
        aplicar_edicion("pago", {}, "direccion", "quien sabe", catalogos)


def test_editar_valores_invalidos(catalogos, payload_compra):
    with pytest.raises(ValueError):
        aplicar_edicion("compra", payload_compra, "cajas", "muchas", catalogos)
    with pytest.raises(ValueError):
        aplicar_edicion("compra", payload_compra, "cajas", "-3", catalogos)
    with pytest.raises(ValueError):
        aplicar_edicion("compra", payload_compra, "fecha", "el otro dia", catalogos)
