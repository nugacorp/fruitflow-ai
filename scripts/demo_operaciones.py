"""Registra una compra y una venta de prueba usando los casos de uso reales.

Uso: DATABASE_URL=<url> python scripts/demo_operaciones.py
Idempotente a nivel practico: si ya existe la compra con folio 1, no hace nada.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from backend.application.dto.comandos import ComandoRegistrarCompra, ComandoRegistrarVenta
from backend.application.use_cases.registrar_operaciones import registrar_compra, registrar_venta
from backend.domain.common.tipos import Dinero
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta
from backend.infrastructure.db import models
from backend.infrastructure.db.session import fabrica_de_sesiones
from backend.infrastructure.db.uow import UnitOfWorkSQLAlchemy


async def principal() -> None:
    async with fabrica_de_sesiones()() as sesion:
        if await sesion.scalar(select(models.Compra).limit(1)) is not None:
            print("Ya hay operaciones registradas; no hago nada.")
            return
        proveedor_id = await sesion.scalar(
            select(models.Contraparte.id).where(models.Contraparte.nombre == "Rancho Los Pinos")
        )
        cliente_id = await sesion.scalar(
            select(models.Contraparte.id).where(
                models.Contraparte.nombre == "Exportadora del Norte"
            )
        )
        producto_id = await sesion.scalar(
            select(models.Producto.id).where(models.Producto.variedad == "Adelita")
        )
        tipo_caja_id = await sesion.scalar(
            select(models.TipoCaja.id).where(models.TipoCaja.nombre == "Caja plastica 8 lb")
        )
    if not all((proveedor_id, cliente_id, producto_id, tipo_caja_id)):
        raise SystemExit("Faltan datos demo: corre primero scripts/seed_dev.py")

    hoy = date.today()
    async with fabrica_de_sesiones()() as sesion:
        resultado = await registrar_compra(
            UnitOfWorkSQLAlchemy(sesion),
            ComandoRegistrarCompra(
                proveedor_id=proveedor_id,
                fecha=hoy,
                items=[
                    ItemCompra(
                        producto_id=producto_id,
                        cajas=220,
                        precio_unitario=Dinero(Decimal("385.00")),
                        tipo_caja_id=tipo_caja_id,
                    )
                ],
                nota="Operacion de demostracion",
            ),
        )
        print(f"Compra registrada: folio {resultado.folio}")

    async with fabrica_de_sesiones()() as sesion:
        resultado = await registrar_venta(
            UnitOfWorkSQLAlchemy(sesion),
            ComandoRegistrarVenta(
                cliente_id=cliente_id,
                fecha=hoy,
                items=[
                    ItemVenta(
                        producto_id=producto_id,
                        cajas=180,
                        precio_unitario=Dinero(Decimal("455.00")),
                        tipo_caja_id=tipo_caja_id,
                    )
                ],
                nota="Operacion de demostracion",
            ),
        )
        print(f"Venta registrada: folio {resultado.folio}")


if __name__ == "__main__":
    asyncio.run(principal())
