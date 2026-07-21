"""Pagos, gastos con prorrateo, anulacion (RN-08) y consultas."""

from datetime import date
from decimal import Decimal

import pytest

from backend.application.dto.comandos import (
    ComandoAnularOperacion,
    ComandoRegistrarCompra,
    ComandoRegistrarGasto,
    ComandoRegistrarPago,
    ComandoRegistrarVenta,
)
from backend.application.use_cases.anular_operacion import anular_operacion
from backend.application.use_cases.consultas.resumen import resumen_dia
from backend.application.use_cases.consultas.saldos import (
    cuentas_por_cobrar,
    saldo_cajas,
)
from backend.application.use_cases.registrar_finanzas import registrar_gasto, registrar_pago
from backend.application.use_cases.registrar_operaciones import (
    registrar_compra,
    registrar_venta,
)
from backend.domain.common.tipos import (
    Dinero,
    ErrorDominio,
    EstadoOperacion,
    OperacionYaAnulada,
)
from backend.domain.finanzas.modelo import DireccionPago
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta
from tests.integration.use_cases.conftest import CAJA_RETORNABLE, PRODUCTO_FRAMBUESA

HOY = date(2026, 7, 20)


async def comprar(uow, proveedor, cajas=220, precio="385.00"):
    return await registrar_compra(
        uow,
        ComandoRegistrarCompra(
            proveedor_id=proveedor.id,
            fecha=HOY,
            items=[
                ItemCompra(
                    producto_id=PRODUCTO_FRAMBUESA,
                    cajas=cajas,
                    precio_unitario=Dinero.de(precio),
                    tipo_caja_id=CAJA_RETORNABLE,
                )
            ],
        ),
    )


async def vender(uow, cliente, cajas=220, precio="455.00"):
    return await registrar_venta(
        uow,
        ComandoRegistrarVenta(
            cliente_id=cliente.id,
            fecha=HOY,
            items=[
                ItemVenta(
                    producto_id=PRODUCTO_FRAMBUESA,
                    cajas=cajas,
                    precio_unitario=Dinero.de(precio),
                    tipo_caja_id=CAJA_RETORNABLE,
                )
            ],
        ),
    )


async def test_pago_se_registra_y_audita(uow, cliente):
    resultado = await registrar_pago(
        uow,
        ComandoRegistrarPago(
            contraparte_id=cliente.id,
            direccion=DireccionPago.COBRO,
            monto=Dinero.de("50000.00"),
            fecha=HOY,
        ),
    )
    assert len(uow.pagos.datos) == 1
    assert uow.auditoria[-1].tipo_evento == "pago_registrado"
    assert resultado.folio is None


async def test_gasto_imputado_a_lote_prorratea(uow, proveedor):
    """RN-06: flete de 8,000 sobre 220 cajas sube el costo a 421.36."""
    await comprar(uow, proveedor)
    lote = next(iter(uow.lotes.datos.values()))

    await registrar_gasto(
        uow,
        ComandoRegistrarGasto(
            categoria="flete",
            monto=Dinero.de("8000.00"),
            fecha=HOY,
            imputable_tipo="lote",
            imputable_id=lote.id,
        ),
    )
    assert lote.costo_total_unitario.monto == Decimal("421.36")


async def test_anular_venta_libera_inventario_y_cajas(uow, proveedor, cliente):
    """RN-08: contra-asientos, nunca DELETE."""
    await comprar(uow, proveedor)
    venta = await vender(uow, cliente)

    await anular_operacion(uow, ComandoAnularOperacion(tipo="venta", folio=venta.folio))

    assert uow.ventas.datos[venta.id].estado is EstadoOperacion.ANULADO
    lotes = await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA)
    assert lotes[0].cajas_disponibles == 220
    # el contra-asiento deja al cliente sin deuda de cajas, sin borrar nada
    assert await uow.movimientos_caja.saldo(cliente.id, CAJA_RETORNABLE) == 0
    assert len(uow.movimientos_caja.datos) == 3  # compra, venta y reverso
    assert uow.auditoria[-1].tipo_evento == "venta_anulada"


async def test_anular_venta_dos_veces_falla(uow, proveedor, cliente):
    await comprar(uow, proveedor)
    venta = await vender(uow, cliente)
    await anular_operacion(uow, ComandoAnularOperacion(tipo="venta", folio=venta.folio))
    with pytest.raises(OperacionYaAnulada):
        await anular_operacion(uow, ComandoAnularOperacion(tipo="venta", folio=venta.folio))


async def test_anular_compra_intacta_retira_el_inventario(uow, proveedor):
    compra = await comprar(uow, proveedor)
    await anular_operacion(uow, ComandoAnularOperacion(tipo="compra", folio=compra.folio))

    assert uow.compras.datos[compra.id].estado is EstadoOperacion.ANULADO
    assert await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA) == []
    assert await uow.movimientos_caja.saldo(proveedor.id, CAJA_RETORNABLE) == 0


async def test_anular_compra_con_cajas_vendidas_bloquea(uow, proveedor, cliente):
    compra = await comprar(uow, proveedor)
    await vender(uow, cliente, cajas=50)
    with pytest.raises(ErrorDominio, match="ya se vendieron"):
        await anular_operacion(uow, ComandoAnularOperacion(tipo="compra", folio=compra.folio))


async def test_saldo_cajas_y_cuentas_por_cobrar(uow, proveedor, cliente):
    await comprar(uow, proveedor)
    await vender(uow, cliente)
    await registrar_pago(
        uow,
        ComandoRegistrarPago(
            contraparte_id=cliente.id,
            direccion=DireccionPago.COBRO,
            monto=Dinero.de("60000.00"),
            fecha=HOY,
        ),
    )

    saldo = await saldo_cajas(uow, cliente.id)
    assert saldo.por_tipo_caja[CAJA_RETORNABLE] == 220

    cxc = await cuentas_por_cobrar(uow, cliente.id)
    assert cxc.facturado.monto == Decimal("100100.00")
    assert cxc.pendiente.monto == Decimal("40100.00")


async def test_resumen_del_dia_cuadra(uow, proveedor, cliente):
    await comprar(uow, proveedor)
    await vender(uow, cliente)
    await registrar_gasto(
        uow, ComandoRegistrarGasto(categoria="flete", monto=Dinero.de("8000.00"), fecha=HOY)
    )

    resumen = await resumen_dia(uow, HOY)
    assert resumen.compras_total.monto == Decimal("84700.00")
    assert resumen.ventas_total.monto == Decimal("100100.00")
    assert resumen.utilidad_bruta.monto == Decimal("15400.00")
    assert resumen.utilidad_neta.monto == Decimal("7400.00")
    assert resumen.margen == Decimal("15.38")


async def test_resumen_ignora_operaciones_anuladas(uow, proveedor, cliente):
    await comprar(uow, proveedor)
    venta = await vender(uow, cliente)
    await anular_operacion(uow, ComandoAnularOperacion(tipo="venta", folio=venta.folio))

    resumen = await resumen_dia(uow, HOY)
    assert resumen.ventas_cantidad == 0
    assert resumen.ventas_total.monto == Decimal("0.00")
