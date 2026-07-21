"""Costeo FIFO, precios por kilo y utilidad."""

from datetime import date
from decimal import Decimal

import pytest

from backend.domain.common.tipos import Dinero, InventarioInsuficiente, UnidadPrecio, nuevo_id
from backend.domain.operaciones.costeo import (
    Lote,
    asignar_fifo,
    calcular_importe,
    costo_de_venta,
    margen_porcentual,
    utilidad,
)

PRODUCTO = nuevo_id()


def lote(cajas, costo, dia, producto=PRODUCTO):
    return Lote(
        producto_id=producto,
        cajas_iniciales=cajas,
        cajas_disponibles=cajas,
        costo_unitario=Dinero.de(costo),
        fecha=date(2026, 7, dia),
    )


def test_caso_de_uso_1_y_2_compra_y_venta_completa():
    """220 cajas a 385 vendidas a 455 -> utilidad de 15,400."""
    lotes = [lote(220, "385.00", 20)]
    asignaciones, faltante = asignar_fifo(lotes, PRODUCTO, 220)
    ingreso = calcular_importe(
        cajas=220, precio_unitario=Dinero.de("455.00"), unidad_precio=UnidadPrecio.CAJA
    )
    assert faltante == 0
    assert ingreso.monto == Decimal("100100.00")
    assert costo_de_venta(asignaciones).monto == Decimal("84700.00")
    assert utilidad(ingreso=ingreso, asignaciones=asignaciones).monto == Decimal("15400.00")


def test_fifo_consume_el_lote_mas_antiguo_primero():
    lotes = [lote(100, "400.00", 22), lote(100, "380.00", 20)]
    asignaciones, _ = asignar_fifo(lotes, PRODUCTO, 150)
    assert asignaciones[0].costo_unitario.monto == Decimal("380.00")
    assert asignaciones[0].cajas == 100
    assert asignaciones[1].cajas == 50
    assert lotes[0].cajas_disponibles == 50


def test_una_venta_puede_venir_de_varias_compras():
    lotes = [lote(80, "380.00", 20), lote(80, "400.00", 21), lote(80, "410.00", 22)]
    asignaciones, faltante = asignar_fifo(lotes, PRODUCTO, 200)
    assert len(asignaciones) == 3
    assert faltante == 0
    assert sum(a.cajas for a in asignaciones) == 200


def test_una_compra_puede_repartirse_en_varias_ventas():
    lotes = [lote(220, "385.00", 20)]
    primera, _ = asignar_fifo(lotes, PRODUCTO, 120)
    segunda, faltante = asignar_fifo(lotes, PRODUCTO, 100)
    assert sum(a.cajas for a in primera) == 120
    assert sum(a.cajas for a in segunda) == 100
    assert faltante == 0
    assert lotes[0].cajas_disponibles == 0


def test_lote_preferido_rompe_el_fifo():
    """Caso 'esas mismas cajas': el usuario senala la compra."""
    antiguo = lote(100, "380.00", 20)
    senalado = lote(100, "400.00", 22)
    asignaciones, _ = asignar_fifo(
        [antiguo, senalado], PRODUCTO, 60, lotes_preferidos=[senalado.id]
    )
    assert asignaciones[0].lote_id == senalado.id
    assert antiguo.cajas_disponibles == 100


def test_inventario_insuficiente_reporta_faltante():
    asignaciones, faltante = asignar_fifo([lote(50, "385.00", 20)], PRODUCTO, 220)
    assert faltante == 170
    assert sum(a.cajas for a in asignaciones) == 50


def test_inventario_insuficiente_puede_bloquear():
    with pytest.raises(InventarioInsuficiente):
        asignar_fifo([lote(50, "385.00", 20)], PRODUCTO, 220, permitir_faltante=False)


def test_no_toma_lotes_de_otro_producto():
    otro = nuevo_id()
    asignaciones, faltante = asignar_fifo([lote(100, "385.00", 20, producto=otro)], PRODUCTO, 10)
    assert asignaciones == []
    assert faltante == 10


def test_precio_por_kilo():
    """120 cajas de 1.5 kg a 42 el kilo = 7,560."""
    importe = calcular_importe(
        cajas=120,
        precio_unitario=Dinero.de("42.00"),
        unidad_precio=UnidadPrecio.KG,
        kg_por_caja=Decimal("1.5"),
    )
    assert importe.monto == Decimal("7560.00")


def test_precio_por_kilo_sin_peso_falla():
    with pytest.raises(ValueError):
        calcular_importe(
            cajas=120, precio_unitario=Dinero.de("42.00"), unidad_precio=UnidadPrecio.KG
        )


def test_gasto_prorrateado_reduce_la_utilidad():
    """Flete de 8,000 sobre 220 cajas."""
    el_lote = lote(220, "385.00", 20)
    el_lote.prorratear_gasto(Dinero.de("8000.00"))
    assert el_lote.costo_total_unitario.monto == Decimal("421.36")
    asignaciones, _ = asignar_fifo([el_lote], PRODUCTO, 220)
    ingreso = Dinero.de("100100.00")
    assert utilidad(ingreso=ingreso, asignaciones=asignaciones).monto == Decimal("7400.80")


def test_liberar_devuelve_inventario_al_anular():
    el_lote = lote(220, "385.00", 20)
    asignar_fifo([el_lote], PRODUCTO, 220)
    assert el_lote.cajas_disponibles == 0
    el_lote.liberar(220)
    assert el_lote.cajas_disponibles == 220


def test_liberar_no_excede_el_inicial():
    el_lote = lote(100, "385.00", 20)
    el_lote.liberar(500)
    assert el_lote.cajas_disponibles == 100


def test_margen_porcentual():
    assert margen_porcentual(Dinero.de("100100.00"), Dinero.de("15400.00")) == Decimal("15.38")
    assert margen_porcentual(Dinero.cero(), Dinero.cero()) == Decimal("0.00")
