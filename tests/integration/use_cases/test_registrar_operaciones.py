"""Casos de uso de registro: compra, venta y devolucion de cajas."""

from datetime import date
from decimal import Decimal

import pytest

from backend.application.dto.comandos import (
    ComandoRegistrarCompra,
    ComandoRegistrarDevolucionCajas,
    ComandoRegistrarVenta,
)
from backend.application.use_cases.registrar_operaciones import (
    registrar_compra,
    registrar_devolucion_cajas,
    registrar_venta,
)
from backend.domain.common.tipos import (
    DatosIncompletos,
    Dinero,
    SaldoCajasNegativo,
    nuevo_id,
)
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta
from tests.integration.use_cases.conftest import CAJA_RETORNABLE, PRODUCTO_FRAMBUESA

HOY = date(2026, 7, 20)


def item_compra(cajas=220, precio="385.00"):
    return ItemCompra(
        producto_id=PRODUCTO_FRAMBUESA,
        cajas=cajas,
        precio_unitario=Dinero.de(precio),
        tipo_caja_id=CAJA_RETORNABLE,
    )


def item_venta(cajas=220, precio="455.00"):
    return ItemVenta(
        producto_id=PRODUCTO_FRAMBUESA,
        cajas=cajas,
        precio_unitario=Dinero.de(precio),
        tipo_caja_id=CAJA_RETORNABLE,
    )


async def comprar(uow, proveedor, cajas=220, precio="385.00", fecha=HOY):
    return await registrar_compra(
        uow,
        ComandoRegistrarCompra(
            proveedor_id=proveedor.id, fecha=fecha, items=[item_compra(cajas, precio)]
        ),
    )


async def test_compra_crea_lotes_movimientos_y_auditoria(uow, proveedor):
    resultado = await comprar(uow, proveedor)

    assert resultado.folio == 1
    compra = uow.compras.datos[resultado.id]
    assert compra.total.monto == Decimal("84700.00")

    lotes = await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA)
    assert len(lotes) == 1
    assert lotes[0].cajas_disponibles == 220

    # RN-03: yo quedo debiendo las cajas al proveedor
    assert await uow.movimientos_caja.saldo(proveedor.id, CAJA_RETORNABLE) == -220
    assert uow.auditoria[-1].tipo_evento == "compra_confirmada"
    assert uow.commits == 1


async def test_compra_sin_cajas_retornables_no_genera_movimientos(uow):
    from backend.domain.common.tipos import TipoContraparte
    from backend.domain.contrapartes.modelo import Contraparte

    proveedor = Contraparte(
        nombre="Sin Retorno", tipo=TipoContraparte.PROVEEDOR, cajas_retornables=False
    )
    uow.contrapartes.datos[proveedor.id] = proveedor

    await comprar(uow, proveedor)
    assert uow.movimientos_caja.datos == []


async def test_compra_con_proveedor_desconocido_falla_sin_persistir(uow):
    from backend.domain.contrapartes.modelo import Contraparte  # noqa: F401

    class Fantasma:
        id = nuevo_id()

    with pytest.raises(DatosIncompletos):
        await comprar(uow, Fantasma())
    assert uow.compras.datos == {}
    assert uow.rollbacks == 1


async def test_venta_consume_fifo_y_calcula_utilidad(uow, proveedor, cliente):
    """El caso guia: 220 a 385, vendidas a 455 -> utilidad 15,400."""
    await comprar(uow, proveedor)
    resultado = await registrar_venta(
        uow,
        ComandoRegistrarVenta(cliente_id=cliente.id, fecha=HOY, items=[item_venta()]),
    )

    venta = uow.ventas.datos[resultado.id]
    assert venta.total.monto == Decimal("100100.00")
    assert venta.costo_total.monto == Decimal("84700.00")
    assert venta.utilidad.monto == Decimal("15400.00")
    assert resultado.advertencias == []

    # inventario consumido y cajas por cobrar al cliente (RN-03)
    assert await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA) == []
    assert await uow.movimientos_caja.saldo(cliente.id, CAJA_RETORNABLE) == 220


async def test_venta_consume_lotes_antiguos_primero(uow, proveedor, cliente):
    await comprar(uow, proveedor, cajas=100, precio="400.00", fecha=date(2026, 7, 22))
    await comprar(uow, proveedor, cajas=100, precio="380.00", fecha=date(2026, 7, 20))

    await registrar_venta(
        uow,
        ComandoRegistrarVenta(
            cliente_id=cliente.id, fecha=date(2026, 7, 23), items=[item_venta(cajas=150)]
        ),
    )
    lotes = await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA)
    assert len(lotes) == 1
    assert lotes[0].costo_unitario.monto == Decimal("400.00")
    assert lotes[0].cajas_disponibles == 50


async def test_venta_sin_inventario_advierte_no_bloquea(uow, proveedor, cliente):
    """RN-05: el faltante se reporta y la venta queda para revision."""
    await comprar(uow, proveedor, cajas=50)
    resultado = await registrar_venta(
        uow,
        ComandoRegistrarVenta(cliente_id=cliente.id, fecha=HOY, items=[item_venta(cajas=220)]),
    )

    assert resultado.requiere_revision
    assert resultado.advertencias[0].codigo == "inventario_insuficiente"
    assert resultado.advertencias[0].datos["cajas"] == 170
    assert uow.ventas.datos[resultado.id].requiere_revision


async def test_devolucion_reduce_el_saldo_del_cliente(uow, proveedor, cliente):
    await comprar(uow, proveedor)
    await registrar_venta(
        uow, ComandoRegistrarVenta(cliente_id=cliente.id, fecha=HOY, items=[item_venta()])
    )

    resultado = await registrar_devolucion_cajas(
        uow,
        ComandoRegistrarDevolucionCajas(
            contraparte_id=cliente.id,
            tipo_caja_id=CAJA_RETORNABLE,
            cantidad=120,
            fecha=HOY,
        ),
    )
    assert resultado.advertencias == []
    assert await uow.movimientos_caja.saldo(cliente.id, CAJA_RETORNABLE) == 100


async def test_devolucion_mayor_al_saldo_advierte(uow, cliente):
    """RN-04: se registra igual y se marca para revision."""
    resultado = await registrar_devolucion_cajas(
        uow,
        ComandoRegistrarDevolucionCajas(
            contraparte_id=cliente.id,
            tipo_caja_id=CAJA_RETORNABLE,
            cantidad=30,
            fecha=HOY,
        ),
    )
    assert resultado.advertencias[0].codigo == "saldo_cajas_negativo"
    assert resultado.advertencias[0].datos["saldo"] == -30
    assert await uow.movimientos_caja.saldo(cliente.id, CAJA_RETORNABLE) == -30


async def test_devolucion_puede_bloquearse_por_configuracion(uow, cliente):
    with pytest.raises(SaldoCajasNegativo):
        await registrar_devolucion_cajas(
            uow,
            ComandoRegistrarDevolucionCajas(
                contraparte_id=cliente.id,
                tipo_caja_id=CAJA_RETORNABLE,
                cantidad=30,
                fecha=HOY,
            ),
            permitir_saldo_negativo=False,
        )
    assert uow.movimientos_caja.datos == []
