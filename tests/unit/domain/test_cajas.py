"""Casos borde de la mecanica de cajas retornables."""

from datetime import date

import pytest

from backend.domain.cajas.politica import (
    MovimientoCaja,
    SaldoCajas,
    TipoMovimientoCaja,
    aplicar,
    calcular_saldo,
    movimientos_de_compra,
    movimientos_de_venta,
    movimientos_inversos,
)
from backend.domain.common.tipos import SaldoCajasNegativo, nuevo_id

HOY = date(2026, 7, 21)


@pytest.fixture
def ids():
    return {"cliente": nuevo_id(), "proveedor": nuevo_id(), "caja": nuevo_id()}


def _mov(ids, tipo, cantidad, **kw):
    return MovimientoCaja(
        contraparte_id=ids["cliente"],
        tipo_caja_id=ids["caja"],
        tipo=tipo,
        cantidad=cantidad,
        fecha=HOY,
        **kw,
    )


def test_venta_deja_al_cliente_debiendo(ids):
    movs = movimientos_de_venta(
        cliente_id=ids["cliente"],
        venta_id=nuevo_id(),
        fecha=HOY,
        cajas_por_tipo={ids["caja"]: 220},
    )
    assert calcular_saldo(movs) == 220


def test_compra_me_deja_debiendo_al_proveedor(ids):
    movs = movimientos_de_compra(
        proveedor_id=ids["proveedor"],
        compra_id=nuevo_id(),
        fecha=HOY,
        cajas_por_tipo={ids["caja"]: 220},
    )
    assert calcular_saldo(movs) == -220


def test_contraparte_sin_cajas_retornables_no_genera_movimientos(ids):
    movs = movimientos_de_venta(
        cliente_id=ids["cliente"],
        venta_id=nuevo_id(),
        fecha=HOY,
        cajas_por_tipo={ids["caja"]: 220},
        cajas_retornables=False,
    )
    assert movs == []


def test_caso_de_uso_5_memo_regreso_80_cajas(ids):
    """220 entregadas, 80 devueltas -> quedan debiendo 140."""
    entrega = _mov(ids, TipoMovimientoCaja.ENTREGA_LLENA, 220)
    devolucion = _mov(ids, TipoMovimientoCaja.DEVOLUCION_RECIBIDA, 80)
    assert calcular_saldo([entrega, devolucion]) == 140


def test_devolucion_mayor_al_saldo_marca_revision(ids):
    """RN-04: se registra pero se advierte."""
    saldo, revisar = aplicar(50, _mov(ids, TipoMovimientoCaja.DEVOLUCION_RECIBIDA, 80))
    assert saldo == -30
    assert revisar is True


def test_devolucion_mayor_al_saldo_bloquea_si_se_configura(ids):
    with pytest.raises(SaldoCajasNegativo):
        aplicar(
            50,
            _mov(ids, TipoMovimientoCaja.DEVOLUCION_RECIBIDA, 80),
            permitir_negativo=False,
        )


def test_devolucion_exacta_no_marca_revision(ids):
    saldo, revisar = aplicar(80, _mov(ids, TipoMovimientoCaja.DEVOLUCION_RECIBIDA, 80))
    assert saldo == 0
    assert revisar is False


def test_saldo_ya_negativo_no_vuelve_a_alertar(ids):
    saldo, revisar = aplicar(-10, _mov(ids, TipoMovimientoCaja.DEVOLUCION_RECIBIDA, 5))
    assert saldo == -15
    assert revisar is False


def test_merma_reduce_lo_que_me_deben(ids):
    saldo, _ = aplicar(140, _mov(ids, TipoMovimientoCaja.MERMA, 12))
    assert saldo == 128


def test_ajuste_requiere_signo_explicito(ids):
    with pytest.raises(ValueError):
        MovimientoCaja(
            contraparte_id=ids["cliente"],
            tipo_caja_id=ids["caja"],
            tipo=TipoMovimientoCaja.AJUSTE,
            cantidad=5,
            fecha=HOY,
            signo=0,
        )


def test_anulacion_genera_contra_asiento(ids):
    original = movimientos_de_venta(
        cliente_id=ids["cliente"],
        venta_id=nuevo_id(),
        fecha=HOY,
        cajas_por_tipo={ids["caja"]: 220},
    )
    reversos = movimientos_inversos(original)
    assert calcular_saldo(original + reversos) == 0
    assert all(r.nota and "Reverso" in r.nota for r in reversos)


def test_cantidad_cero_es_invalida(ids):
    with pytest.raises(ValueError):
        _mov(ids, TipoMovimientoCaja.ENTREGA_LLENA, 0)


@pytest.mark.parametrize(
    ("saldo", "esperado"),
    [(140, "te debe 140"), (-30, "Le debes 30"), (0, "a mano")],
)
def test_lectura_humana_del_saldo(ids, saldo, esperado):
    s = SaldoCajas(ids["cliente"], ids["caja"], saldo)
    assert esperado in s.descripcion("Exportadora ABC")
