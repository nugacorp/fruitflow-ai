"""Repositorios SQLAlchemy contra PostgreSQL real (FASE 4).

Requiere una base disponible en TEST_DATABASE_URL, por ejemplo:

    TEST_DATABASE_URL=postgresql+asyncpg://fruitflow:cambiame@localhost:5432/fruitflow_test

Sin esa variable las pruebas se saltan (en CI se provee con testcontainers
o un servicio de Postgres).
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.application.dto.comandos import ComandoRegistrarCompra, ComandoRegistrarVenta
from backend.application.use_cases.registrar_operaciones import registrar_compra, registrar_venta
from backend.domain.common.tipos import Dinero, TipoContraparte, nuevo_id
from backend.domain.contrapartes.modelo import Contraparte
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta
from backend.infrastructure.db import models
from backend.infrastructure.db.models import Base
from backend.infrastructure.db.uow import UnitOfWorkSQLAlchemy

URL = os.environ.get("TEST_DATABASE_URL")
PRODUCTO = nuevo_id()
CAJA = nuevo_id()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL no esta definida"),
]


@pytest.fixture
async def fabrica():
    from backend.config import get_settings

    motor = create_async_engine(URL)
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    empresa_id = uuid.UUID(get_settings().empresa_id)
    async with fabrica() as sesion:
        sesion.add(models.Empresa(id=empresa_id, nombre="Prueba"))
        sesion.add(models.Producto(id=PRODUCTO, empresa_id=empresa_id, nombre="Frambuesa"))
        sesion.add(
            models.TipoCaja(id=CAJA, empresa_id=empresa_id, nombre="Caja 8lb", retornable=True)
        )
        await sesion.commit()
    yield fabrica
    await motor.dispose()


async def test_ciclo_compra_venta_y_saldos(fabrica):
    proveedor = Contraparte(nombre="Rancho Los Pinos", tipo=TipoContraparte.PROVEEDOR)
    cliente = Contraparte(nombre="Frutas del Valle", tipo=TipoContraparte.CLIENTE)

    async with fabrica() as sesion:
        uow = UnitOfWorkSQLAlchemy(sesion)
        async with uow:
            await uow.contrapartes.agregar(proveedor)
            await uow.contrapartes.agregar(cliente)

    async with fabrica() as sesion:
        uow = UnitOfWorkSQLAlchemy(sesion)
        resultado = await registrar_compra(
            uow,
            ComandoRegistrarCompra(
                proveedor_id=proveedor.id,
                fecha=date(2026, 7, 20),
                items=[
                    ItemCompra(
                        producto_id=PRODUCTO,
                        cajas=220,
                        precio_unitario=Dinero(Decimal("385.00")),
                        tipo_caja_id=CAJA,
                    )
                ],
            ),
        )
        assert resultado.folio == 1

    async with fabrica() as sesion:
        uow = UnitOfWorkSQLAlchemy(sesion)
        resultado = await registrar_venta(
            uow,
            ComandoRegistrarVenta(
                cliente_id=cliente.id,
                fecha=date(2026, 7, 20),
                items=[
                    ItemVenta(
                        producto_id=PRODUCTO,
                        cajas=220,
                        precio_unitario=Dinero(Decimal("455.00")),
                        tipo_caja_id=CAJA,
                    )
                ],
            ),
        )
        assert resultado.folio == 1
        assert resultado.advertencias == []

    async with fabrica() as sesion:
        uow = UnitOfWorkSQLAlchemy(sesion)
        # RN-03: el proveedor me presto cajas (le debo) y el cliente me debe.
        assert await uow.movimientos_caja.saldo(proveedor.id, CAJA) == -220
        assert await uow.movimientos_caja.saldo(cliente.id, CAJA) == 220
        # El lote quedo consumido por FIFO.
        assert await uow.lotes.disponibles_de(PRODUCTO) == []
        # La compra reconstruida trae lineas y lotes.
        compra = await uow.compras.buscar_por_folio(1)
        assert compra is not None
        assert compra.total == Dinero(Decimal("84700.00"))
        assert compra.lotes[0].cajas_disponibles == 0
        # La venta reconstruida trae asignaciones con costo FIFO.
        venta = await uow.ventas.buscar_por_folio(1)
        assert venta is not None
        assert venta.costo_total == Dinero(Decimal("84700.00"))
        assert venta.utilidad == Dinero(Decimal("15400.00"))
        # La auditoria quedo persistida (RN: nada se modifica sin evento).
        eventos = list(await sesion.scalars(select(models.EventoAuditoria)))
        assert {e.tipo_evento for e in eventos} >= {"compra_confirmada", "venta_confirmada"}
