"""Datos de desarrollo. No usar en produccion."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from backend.config import get_settings
from backend.domain.common.tipos import nuevo_id
from backend.infrastructure.ai.resolver import normalizar
from backend.infrastructure.db.models import (
    Contraparte,
    ContraparteAlias,
    Empresa,
    Producto,
    TipoCaja,
    Ubicacion,
    Usuario,
)
from backend.infrastructure.db.session import fabrica_de_sesiones

PRODUCTOS = [
    ("Frambuesa", "Adelita", Decimal("1.500")),
    ("Zarzamora", "Tupy", Decimal("1.500")),
    ("Arandano", "Biloxi", Decimal("1.200")),
    ("Fresa", "Festival", Decimal("2.000")),
    ("Frambuesa", "Kweli", Decimal("1.500")),
]
CAJAS = [("Caja plastica 8 lb", True), ("Clamshell 12x6oz", False), ("Arpilla", True)]
UBICACIONES = [
    ("Zamora", "Zamora", "Michoacan"),
    ("Los Reyes", "Los Reyes", "Michoacan"),
    ("Jacona", "Jacona", "Michoacan"),
    ("Tijuana", "Tijuana", "Baja California"),
    ("Central de Abastos CDMX", "Ciudad de Mexico", "CDMX"),
    ("Bodega propia", "Zamora", "Michoacan"),
]
CONTRAPARTES = [
    ("Rancho Los Pinos", "proveedor", ["Los Pinos", "Pinos"]),
    ("Exportadora del Norte", "cliente", ["Memo", "Exportadora Norte"]),
    ("Los Reyes Berries", "proveedor", ["Reyes"]),
    ("Comercializadora ABC", "cliente", ["ABC"]),
    ("Agricola San Jose", "proveedor", ["San Jose", "Chuy"]),
    ("Distribuidora del Valle", "cliente", ["Valle"]),
    ("Fletes Hernandez", "transportista", ["Hernandez"]),
    ("Frutas del Bajio", "ambos", ["Bajio"]),
]


async def sembrar() -> None:
    settings = get_settings()
    empresa_id = uuid.UUID(settings.empresa_id)

    async with fabrica_de_sesiones()() as sesion:
        sesion.add(Empresa(id=empresa_id, nombre="FruitFlow Demo"))

        telegram_ids = sorted(settings.usuarios_permitidos) or [123456789]
        sesion.add(
            Usuario(
                id=nuevo_id(),
                empresa_id=empresa_id,
                telegram_user_id=telegram_ids[0],
                nombre="Administrador",
                rol="admin",
            )
        )

        for nombre, variedad, kg in PRODUCTOS:
            sesion.add(
                Producto(
                    id=nuevo_id(),
                    empresa_id=empresa_id,
                    nombre=nombre,
                    variedad=variedad,
                    kg_por_caja_default=kg,
                )
            )

        for nombre, retornable in CAJAS:
            sesion.add(
                TipoCaja(id=nuevo_id(), empresa_id=empresa_id, nombre=nombre, retornable=retornable)
            )

        ubicaciones: dict[str, uuid.UUID] = {}
        for nombre, ciudad, estado in UBICACIONES:
            uid = nuevo_id()
            ubicaciones[nombre] = uid
            sesion.add(
                Ubicacion(
                    id=uid,
                    empresa_id=empresa_id,
                    nombre=nombre,
                    ciudad=ciudad,
                    estado=estado,
                    es_propia=nombre == "Bodega propia",
                )
            )

        for nombre, tipo, alias in CONTRAPARTES:
            cid = nuevo_id()
            sesion.add(Contraparte(id=cid, empresa_id=empresa_id, nombre=nombre, tipo=tipo))
            for a in alias:
                sesion.add(
                    ContraparteAlias(
                        id=nuevo_id(),
                        contraparte_id=cid,
                        alias=a,
                        alias_norm=normalizar(a),
                        origen="usuario",
                        confirmado=True,
                    )
                )

        await sesion.commit()
    print("Datos de desarrollo sembrados.")


if __name__ == "__main__":
    asyncio.run(sembrar())
