"""RN-10: el efectivo si bloquea; validaciones de pagos y gastos."""

from datetime import date

import pytest

from backend.domain.common.tipos import Dinero, SaldoEfectivoNegativo, nuevo_id
from backend.domain.finanzas.modelo import (
    DireccionPago,
    Gasto,
    Pago,
    aplicar_a_efectivo,
)

HOY = date(2026, 7, 20)


def pago(monto, direccion=DireccionPago.PAGO):
    return Pago(contraparte_id=nuevo_id(), direccion=direccion, monto=Dinero.de(monto), fecha=HOY)


def test_cobro_aumenta_el_efectivo():
    saldo = aplicar_a_efectivo(Dinero.de("1000.00"), pago("500.00", DireccionPago.COBRO))
    assert saldo == Dinero.de("1500.00")


def test_pago_reduce_el_efectivo():
    saldo = aplicar_a_efectivo(Dinero.de("1000.00"), pago("400.00"))
    assert saldo == Dinero.de("600.00")


def test_efectivo_no_puede_quedar_negativo():
    with pytest.raises(SaldoEfectivoNegativo):
        aplicar_a_efectivo(Dinero.de("100.00"), pago("100.01"))


def test_pago_exacto_deja_el_efectivo_en_cero():
    assert aplicar_a_efectivo(Dinero.de("100.00"), pago("100.00")) == Dinero.cero()


def test_pago_con_monto_cero_es_invalido():
    with pytest.raises(ValueError):
        pago("0")


def test_gasto_negativo_es_invalido():
    with pytest.raises(ValueError):
        Gasto(categoria="flete", monto=Dinero.de("-10.00"), fecha=HOY)
