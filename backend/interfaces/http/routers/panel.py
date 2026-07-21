"""Panel web de consulta (solo lectura) para el administrador.

Es la unica superficie con navegador: se protege con HTTP Basic
(usuario `admin`, contrasena = INTERNAL_API_KEY) porque un navegador no
puede mandar la cabecera X-Internal-Key de la API interna.
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from backend.application.use_cases.consultas.resumen import resumen_periodo
from backend.application.use_cases.consultas.saldos import (
    cuentas_por_cobrar,
    cuentas_por_pagar,
    tablero_cajas,
)
from backend.config import get_settings
from backend.interfaces.http.dependencias import Uow

_RUTA_HTML = Path(__file__).resolve().parents[1] / "static" / "panel.html"

_seguridad = HTTPBasic()


def _verificar_acceso(
    credenciales: Annotated[HTTPBasicCredentials, Depends(_seguridad)],
) -> None:
    esperada = get_settings().internal_api_key
    usuario_ok = secrets.compare_digest(credenciales.username.encode(), b"admin")
    llave_ok = secrets.compare_digest(credenciales.password.encode(), esperada.encode())
    if not (usuario_ok and llave_ok):
        raise HTTPException(
            status_code=401,
            detail="Credenciales invalidas",
            headers={"WWW-Authenticate": "Basic"},
        )


router = APIRouter(prefix="/panel", tags=["panel"], dependencies=[Depends(_verificar_acceso)])


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def pagina() -> HTMLResponse:
    return HTMLResponse(_RUTA_HTML.read_text(encoding="utf-8"))


@router.get("/datos")
async def datos(uow: Uow, desde: date | None = None, hasta: date | None = None) -> dict[str, Any]:
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=6)

    resumen = await resumen_periodo(uow, desde, hasta)

    tipos_caja = dict(await uow.catalogos.tipos_caja())
    cajas = [
        {
            "nombre": s.nombre,
            "total": s.total,
            "por_tipo": {
                tipos_caja.get(tipo, "caja"): saldo for tipo, saldo in s.por_tipo_caja.items()
            },
        }
        for s in await tablero_cajas(uow)
    ]

    cxc: list[dict[str, Any]] = []
    cxp: list[dict[str, Any]] = []
    for contraparte in await uow.contrapartes.listar():
        if contraparte.es_cliente:
            saldo = await cuentas_por_cobrar(uow, contraparte.id)
            if saldo.pendiente.monto != 0:
                cxc.append({"nombre": saldo.nombre, "pendiente": str(saldo.pendiente.monto)})
        if contraparte.es_proveedor:
            saldo = await cuentas_por_pagar(uow, contraparte.id)
            if saldo.pendiente.monto != 0:
                cxp.append({"nombre": saldo.nombre, "pendiente": str(saldo.pendiente.monto)})

    borradores = [
        {
            "intencion": b.intencion,
            "faltantes": b.faltantes,
            "confianza": b.confianza,
            "expira_en": b.expira_en.isoformat(),
        }
        for b in await uow.borradores.pendientes()
    ]

    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "resumen": {
            "compras_total": str(resumen.compras_total.monto),
            "compras_cajas": resumen.compras_cajas,
            "ventas_total": str(resumen.ventas_total.monto),
            "ventas_cajas": resumen.ventas_cajas,
            "gastos_total": str(resumen.gastos_total.monto),
            "utilidad_neta": str(resumen.utilidad_neta.monto),
            "margen": str(resumen.margen),
        },
        "cajas": cajas,
        "cxc": cxc,
        "cxp": cxp,
        "borradores": borradores,
    }
