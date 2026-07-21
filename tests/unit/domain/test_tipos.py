from decimal import Decimal

import pytest

from backend.domain.common.tipos import Dinero, ErrorDominio, Peso


def test_dinero_rechaza_float():
    with pytest.raises(TypeError):
        Dinero(385.5)  # type: ignore[arg-type]


def test_dinero_redondea_a_centavos():
    assert Dinero.de("385.555").monto == Decimal("385.56")
    assert Dinero.de("385.554").monto == Decimal("385.55")


def test_aritmetica_exacta():
    total = Dinero.de("385.00") * 220
    assert total.monto == Decimal("84700.00")
    assert total.formateado() == "$84,700.00"


def test_no_mezcla_monedas():
    with pytest.raises(ErrorDominio):
        Dinero.de("100", "MXN") + Dinero.de("100", "USD")


def test_peso_tres_decimales():
    assert Peso.de("1.5").kg == Decimal("1.500")
    assert Peso.de("0.12345").kg == Decimal("0.123")
