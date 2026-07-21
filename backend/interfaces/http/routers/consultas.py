"""Consultas de lectura: saldos, cuentas y resumen del periodo."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter

from backend.application.use_cases.consultas.resumen import resumen_periodo
from backend.application.use_cases.consultas.saldos import (
    cuentas_por_cobrar,
    cuentas_por_pagar,
    saldo_cajas,
    tablero_cajas,
)
from backend.interfaces.http.dependencias import LlaveInterna, Uow

router = APIRouter(prefix="/v1", tags=["consultas"], dependencies=[LlaveInterna])


@router.get("/catalogos")
async def consultar_catalogos(uow: Uow) -> dict[str, Any]:
    """Catalogos (id, nombre) para que el bot resuelva texto libre (RN-09)."""
    contrapartes = await uow.contrapartes.listar()
    productos = await uow.catalogos.productos()
    tipos_caja = await uow.catalogos.tipos_caja()
    return {
        "contrapartes": [
            {"id": str(c.id), "nombre": c.nombre, "tipo": c.tipo.value} for c in contrapartes
        ],
        "productos": [{"id": str(pid), "nombre": nombre} for pid, nombre in productos],
        "tipos_caja": [{"id": str(tid), "nombre": nombre} for tid, nombre in tipos_caja],
    }


@router.get("/saldos/cajas")
async def consultar_tablero_cajas(uow: Uow) -> list[dict[str, Any]]:
    """Tablero global: contrapartes con saldo de cajas distinto de cero."""
    return [
        {
            "contraparte_id": str(s.contraparte_id),
            "nombre": s.nombre,
            "por_tipo_caja": {str(k): v for k, v in s.por_tipo_caja.items()},
            "total": s.total,
        }
        for s in await tablero_cajas(uow)
    ]


@router.get("/saldos/cajas/{contraparte_id}")
async def consultar_saldo_cajas(contraparte_id: uuid.UUID, uow: Uow) -> dict[str, Any]:
    saldo = await saldo_cajas(uow, contraparte_id)
    return {
        "contraparte_id": str(saldo.contraparte_id),
        "nombre": saldo.nombre,
        "por_tipo_caja": {str(k): v for k, v in saldo.por_tipo_caja.items()},
        "total": saldo.total,
    }


@router.get("/saldos/cxc/{cliente_id}")
async def consultar_cxc(cliente_id: uuid.UUID, uow: Uow) -> dict[str, Any]:
    saldo = await cuentas_por_cobrar(uow, cliente_id)
    return {
        "contraparte_id": str(saldo.contraparte_id),
        "nombre": saldo.nombre,
        "facturado": str(saldo.facturado.monto),
        "pagado": str(saldo.pagado.monto),
        "pendiente": str(saldo.pendiente.monto),
    }


@router.get("/saldos/cxp/{proveedor_id}")
async def consultar_cxp(proveedor_id: uuid.UUID, uow: Uow) -> dict[str, Any]:
    saldo = await cuentas_por_pagar(uow, proveedor_id)
    return {
        "contraparte_id": str(saldo.contraparte_id),
        "nombre": saldo.nombre,
        "facturado": str(saldo.facturado.monto),
        "pagado": str(saldo.pagado.monto),
        "pendiente": str(saldo.pendiente.monto),
    }


@router.get("/resumen")
async def consultar_resumen(desde: date, hasta: date, uow: Uow) -> dict[str, Any]:
    resumen = await resumen_periodo(uow, desde, hasta)
    return {
        "desde": resumen.desde.isoformat(),
        "hasta": resumen.hasta.isoformat(),
        "compras": {
            "cantidad": resumen.compras_cantidad,
            "total": str(resumen.compras_total.monto),
            "cajas": resumen.compras_cajas,
        },
        "ventas": {
            "cantidad": resumen.ventas_cantidad,
            "total": str(resumen.ventas_total.monto),
            "cajas": resumen.ventas_cajas,
        },
        "costo_ventas": str(resumen.costo_ventas.monto),
        "gastos_total": str(resumen.gastos_total.monto),
        "utilidad_bruta": str(resumen.utilidad_bruta.monto),
        "utilidad_neta": str(resumen.utilidad_neta.monto),
        "margen": str(resumen.margen),
    }
