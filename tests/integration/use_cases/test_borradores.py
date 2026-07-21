"""RN-01: nada se guarda sin confirmacion. Ciclo de vida del borrador."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.application.use_cases.borradores import (
    cancelar_borrador,
    confirmar_borrador,
    crear_borrador,
    editar_borrador,
    expirar_borradores,
)
from backend.domain.common.tipos import (
    BorradorExpirado,
    BorradorYaProcesado,
    DatosIncompletos,
    ahora,
)
from backend.domain.operaciones.borrador import EstadoBorrador
from tests.integration.use_cases.conftest import CAJA_RETORNABLE, PRODUCTO_FRAMBUESA

HOY = date(2026, 7, 20)


def payload_compra(proveedor, cajas=220, precio="385.00", **extra):
    return {
        "proveedor_id": str(proveedor.id),
        "fecha": HOY.isoformat(),
        "items": [
            {
                "producto_id": str(PRODUCTO_FRAMBUESA),
                "cajas": cajas,
                "precio_unitario": precio,
                "tipo_caja_id": str(CAJA_RETORNABLE),
            }
        ],
        **extra,
    }


async def test_crear_borrador_con_ttl_de_24_horas(uow, proveedor):
    borrador = await crear_borrador(
        uow, intencion="compra", payload=payload_compra(proveedor), confianza=0.9
    )
    assert borrador.estado is EstadoBorrador.PENDIENTE
    assert (borrador.expira_en - borrador.creado_en) == timedelta(hours=24)
    assert uow.auditoria[-1].tipo_evento == "borrador_creado"
    # RN-01: crear el borrador NO registra la compra
    assert uow.compras.datos == {}


async def test_intencion_desconocida_no_crea_borrador(uow):
    with pytest.raises(DatosIncompletos):
        await crear_borrador(uow, intencion="consulta", payload={})
    assert uow.borradores.datos == {}


async def test_confirmar_ejecuta_la_operacion_y_enlaza_el_resultado(uow, proveedor):
    borrador = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    resultado = await confirmar_borrador(uow, borrador.id)

    assert borrador.estado is EstadoBorrador.CONFIRMADO
    assert borrador.resultado_id == resultado.id
    compra = uow.compras.datos[resultado.id]
    assert compra.total.monto == Decimal("84700.00")
    assert resultado.folio == 1
    assert uow.auditoria[-1].tipo_evento == "borrador_confirmado"


async def test_confirmar_venta_desde_payload_consume_inventario(uow, proveedor, cliente):
    compra = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    await confirmar_borrador(uow, compra.id)

    venta = await crear_borrador(
        uow,
        intencion="venta",
        payload={
            "cliente_id": str(cliente.id),
            "fecha": HOY.isoformat(),
            "items": [
                {
                    "producto_id": str(PRODUCTO_FRAMBUESA),
                    "cajas": 220,
                    "precio_unitario": "455.00",
                    "tipo_caja_id": str(CAJA_RETORNABLE),
                }
            ],
        },
    )
    resultado = await confirmar_borrador(uow, venta.id)
    assert uow.ventas.datos[resultado.id].utilidad.monto == Decimal("15400.00")
    assert await uow.lotes.disponibles_de(PRODUCTO_FRAMBUESA) == []


async def test_confirmar_con_faltantes_no_ejecuta(uow, proveedor):
    borrador = await crear_borrador(
        uow,
        intencion="compra",
        payload=payload_compra(proveedor),
        faltantes=["precio"],
    )
    with pytest.raises(DatosIncompletos, match="precio"):
        await confirmar_borrador(uow, borrador.id)
    assert borrador.estado is EstadoBorrador.PENDIENTE
    assert uow.compras.datos == {}


async def test_editar_cubre_faltantes_y_permite_confirmar(uow, proveedor):
    payload = payload_compra(proveedor)
    payload["items"][0]["precio_unitario"] = None
    borrador = await crear_borrador(uow, intencion="compra", payload=payload, faltantes=["items"])

    await editar_borrador(uow, borrador.id, {"items": payload_compra(proveedor)["items"]})
    assert borrador.esta_completo

    resultado = await confirmar_borrador(uow, borrador.id)
    assert resultado.folio == 1


async def test_confirmar_dos_veces_falla(uow, proveedor):
    borrador = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    await confirmar_borrador(uow, borrador.id)
    with pytest.raises(BorradorYaProcesado):
        await confirmar_borrador(uow, borrador.id)
    assert len(uow.compras.datos) == 1


async def test_cancelar_no_deja_rastro_operativo(uow, proveedor):
    borrador = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    await cancelar_borrador(uow, borrador.id)
    assert borrador.estado is EstadoBorrador.CANCELADO
    assert uow.compras.datos == {}
    with pytest.raises(BorradorYaProcesado):
        await confirmar_borrador(uow, borrador.id)


async def test_borrador_vencido_no_se_confirma(uow, proveedor):
    borrador = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    borrador.expira_en = ahora() - timedelta(minutes=1)
    with pytest.raises(BorradorExpirado):
        await confirmar_borrador(uow, borrador.id)
    assert uow.compras.datos == {}


async def test_expirar_borradores_solo_toca_los_vencidos(uow, proveedor):
    vencido = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))
    vencido.expira_en = ahora() - timedelta(hours=1)
    vigente = await crear_borrador(uow, intencion="compra", payload=payload_compra(proveedor))

    expirados = await expirar_borradores(uow)
    assert expirados == 1
    assert vencido.estado is EstadoBorrador.EXPIRADO
    assert vigente.estado is EstadoBorrador.PENDIENTE


async def test_fallo_al_confirmar_deja_el_borrador_pendiente(uow, proveedor):
    """Atomicidad: si la operacion truena, el borrador sigue editable."""
    payload = payload_compra(proveedor)
    payload["proveedor_id"] = str(PRODUCTO_FRAMBUESA)  # id que no existe
    borrador = await crear_borrador(uow, intencion="compra", payload=payload)

    with pytest.raises(DatosIncompletos):
        await confirmar_borrador(uow, borrador.id)
    assert borrador.estado is EstadoBorrador.PENDIENTE
    assert uow.compras.datos == {}
    assert uow.rollbacks == 1
