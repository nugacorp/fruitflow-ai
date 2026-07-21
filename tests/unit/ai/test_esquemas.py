"""Golden tests: frases reales del negocio -> estructura esperada.

No llaman a la API. Validan el contrato Pydantic sobre respuestas grabadas.
"""

from decimal import Decimal

import pytest

from backend.infrastructure.ai.esquemas import ExtraccionIA


def extraer(payload: dict) -> ExtraccionIA:
    return ExtraccionIA.model_validate(payload)


def test_caso_1_compra_completa():
    """'Compramos 220 cajas de frambuesa a Rancho Los Pinos en Zamora a 385'"""
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "compra",
                    "fecha": "2026-07-21",
                    "contraparte_texto": "Rancho Los Pinos",
                    "origen_texto": "Zamora",
                    "referencia_operacion_anterior": False,
                    "lineas": [
                        {
                            "producto_texto": "frambuesa",
                            "cajas": 220,
                            "precio_unitario": "385.00",
                            "unidad_precio": "caja",
                        }
                    ],
                }
            ],
            "preguntas": [],
            "confianza": 0.95,
        }
    )
    op = r.operaciones[0]
    assert op.tipo == "compra"
    assert op.lineas[0].precio_unitario == Decimal("385.00")
    assert r.esta_completa


def test_caso_2_venta_con_referencia_anterior():
    """'Vendimos esas mismas cajas a Exportadora ABC en Tijuana en 455'"""
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "venta",
                    "contraparte_texto": "Exportadora ABC",
                    "destino_texto": "Tijuana",
                    "referencia_operacion_anterior": True,
                    "lineas": [
                        {
                            "producto_texto": "frambuesa",
                            "cajas": 220,
                            "precio_unitario": "455.00",
                            "unidad_precio": "caja",
                        }
                    ],
                }
            ],
            "preguntas": [],
            "confianza": 0.9,
        }
    )
    assert r.operaciones[0].referencia_operacion_anterior is True


def test_caso_5_memo_regreso_80_cajas():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "devolucion_cajas",
                    "contraparte_texto": "Memo",
                    "referencia_operacion_anterior": False,
                    "lineas": [{"producto_texto": None, "cajas": 80}],
                }
            ],
            "preguntas": [],
            "confianza": 0.88,
        }
    )
    assert r.operaciones[0].contraparte_texto == "Memo"
    assert r.operaciones[0].lineas[0].cajas == 80


def test_dos_operaciones_en_una_frase():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "compra",
                    "contraparte_texto": "Pinos",
                    "referencia_operacion_anterior": False,
                    "lineas": [
                        {
                            "producto_texto": "frambuesa",
                            "cajas": 100,
                            "precio_unitario": "380.00",
                            "unidad_precio": "caja",
                        }
                    ],
                },
                {
                    "tipo": "venta",
                    "contraparte_texto": "ABC",
                    "referencia_operacion_anterior": True,
                    "lineas": [
                        {
                            "producto_texto": "frambuesa",
                            "cajas": 60,
                            "precio_unitario": "450.00",
                            "unidad_precio": "caja",
                        }
                    ],
                },
            ],
            "preguntas": [],
            "confianza": 0.85,
        }
    )
    assert [op.tipo for op in r.operaciones] == ["compra", "venta"]


def test_precio_por_kilo_sin_peso_pide_el_dato():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "compra",
                    "contraparte_texto": "Los Reyes",
                    "referencia_operacion_anterior": False,
                    "lineas": [
                        {
                            "producto_texto": "zarzamora",
                            "cajas": 120,
                            "precio_unitario": "42.00",
                            "unidad_precio": "kg",
                        }
                    ],
                }
            ],
            "preguntas": [],
            "confianza": 0.8,
        }
    )
    assert "kilos por caja" in r.todas_las_faltantes()
    assert not r.esta_completa


def test_gasto_de_flete():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "gasto",
                    "contraparte_texto": "transportista",
                    "referencia_operacion_anterior": False,
                    "lineas": [],
                    "monto": "8000.00",
                    "categoria_gasto": "flete",
                }
            ],
            "preguntas": [],
            "confianza": 0.92,
        }
    )
    assert r.operaciones[0].monto == Decimal("8000.00")
    assert r.esta_completa


def test_montos_con_simbolo_y_comas_se_limpian():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "pago",
                    "contraparte_texto": "Chuy",
                    "referencia_operacion_anterior": False,
                    "lineas": [],
                    "monto": "$50,000.00",
                }
            ],
            "preguntas": [],
            "confianza": 0.9,
        }
    )
    assert r.operaciones[0].monto == Decimal("50000.00")


def test_mensaje_sin_operacion():
    r = extraer({"operaciones": [], "preguntas": [], "confianza": 0.1})
    assert not r.esta_completa
    assert r.operaciones == []


def test_cajas_negativas_son_rechazadas():
    with pytest.raises(ValueError):
        extraer(
            {
                "operaciones": [
                    {
                        "tipo": "compra",
                        "contraparte_texto": "X",
                        "referencia_operacion_anterior": False,
                        "lineas": [{"producto_texto": "fresa", "cajas": -5}],
                    }
                ],
                "preguntas": [],
                "confianza": 0.5,
            }
        )


def test_faltantes_no_se_repiten():
    r = extraer(
        {
            "operaciones": [
                {
                    "tipo": "compra",
                    "contraparte_texto": None,
                    "referencia_operacion_anterior": False,
                    "lineas": [
                        {"producto_texto": None, "cajas": None},
                        {"producto_texto": None, "cajas": None},
                    ],
                }
            ],
            "preguntas": [],
            "confianza": 0.3,
        }
    )
    faltantes = r.todas_las_faltantes()
    assert len(faltantes) == len(set(faltantes))
