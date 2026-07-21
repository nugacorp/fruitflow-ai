"""Puente entre el payload del borrador (UUIDs, contrato JSON) y lo que ve
el usuario: tarjetas con nombres y campos editables con etiquetas."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.infrastructure.ai.resolver import resolver

# Clave de payload de la contraparte segun la intencion.
CLAVE_CONTRAPARTE = {
    "compra": "proveedor_id",
    "venta": "cliente_id",
    "devolucion_cajas": "contraparte_id",
    "pago": "contraparte_id",
    "gasto": "contraparte_id",
}

# Campos editables por intencion: (clave corta para callback, etiqueta).
CAMPOS_EDITABLES: dict[str, list[tuple[str, str]]] = {
    "compra": [
        ("contraparte", "Proveedor"),
        ("fecha", "Fecha"),
        ("cajas", "Cajas"),
        ("precio", "Precio"),
        ("nota", "Nota"),
    ],
    "venta": [
        ("contraparte", "Cliente"),
        ("fecha", "Fecha"),
        ("cajas", "Cajas"),
        ("precio", "Precio"),
        ("nota", "Nota"),
    ],
    "devolucion_cajas": [
        ("contraparte", "Contraparte"),
        ("fecha", "Fecha"),
        ("cantidad", "Cantidad"),
    ],
    "pago": [
        ("contraparte", "Contraparte"),
        ("fecha", "Fecha"),
        ("monto", "Monto"),
        ("direccion", "Cobro o pago"),
    ],
    "gasto": [
        ("categoria", "Categoria"),
        ("fecha", "Fecha"),
        ("monto", "Monto"),
        ("descripcion", "Concepto"),
    ],
}

# Etiqueta en espanol de cada clave de payload que puede faltar.
ETIQUETAS_FALTANTES = {
    "proveedor_id": "proveedor",
    "cliente_id": "cliente",
    "contraparte_id": "contraparte",
    "fecha": "fecha",
    "items": "detalle (producto, cajas, precio)",
    "tipo_caja_id": "tipo de caja",
    "cantidad": "cantidad de cajas",
    "monto": "monto",
    "direccion": "si es cobro o pago",
    "categoria": "categoria del gasto",
}


class Catalogos:
    """Catalogos (id -> nombre) que el bot usa para mostrar y resolver."""

    def __init__(self, crudo: dict[str, Any]) -> None:
        self.contrapartes = {c["id"]: c["nombre"] for c in crudo.get("contrapartes", [])}
        self.tipos_contraparte = {c["id"]: c["tipo"] for c in crudo.get("contrapartes", [])}
        self.productos = {p["id"]: p["nombre"] for p in crudo.get("productos", [])}
        self.tipos_caja = {t["id"]: t["nombre"] for t in crudo.get("tipos_caja", [])}

    def catalogo_contrapartes(self) -> list[tuple[Any, str]]:
        return [(cid, nombre) for cid, nombre in self.contrapartes.items()]

    def catalogo_productos(self) -> list[tuple[Any, str]]:
        return [(pid, nombre) for pid, nombre in self.productos.items()]

    def catalogo_tipos_caja(self) -> list[tuple[Any, str]]:
        return [(tid, nombre) for tid, nombre in self.tipos_caja.items()]


def vista_operacion(
    intencion: str,
    payload: dict[str, Any],
    catalogos: Catalogos,
    *,
    faltantes: list[str] | None = None,
    advertencias: list[str] | None = None,
) -> dict[str, Any]:
    """Arma el dict que consume tarjeta_operacion, con nombres en vez de UUIDs."""
    contraparte_id = payload.get(CLAVE_CONTRAPARTE.get(intencion, "contraparte_id"))
    vista: dict[str, Any] = {
        "tipo": intencion,
        "contraparte": catalogos.contrapartes.get(str(contraparte_id)) if contraparte_id else None,
        "fecha": payload.get("fecha", "?"),
        "lineas": [],
        "faltantes": [ETIQUETAS_FALTANTES.get(c, c) for c in (faltantes or [])],
        "advertencias": list(advertencias or []),
    }

    for item in payload.get("items", []):
        precio = item.get("precio_unitario")
        cajas = item.get("cajas")
        importe = None
        if precio is not None and cajas and item.get("unidad_precio", "caja") == "caja":
            try:
                importe = str(Decimal(str(precio)) * int(cajas))
            except (InvalidOperation, ValueError):
                importe = None
        vista["lineas"].append(
            {
                "cajas": cajas if cajas is not None else "?",
                "producto": catalogos.productos.get(str(item.get("producto_id")), "?"),
                "precio_unitario": precio,
                "unidad_precio": item.get("unidad_precio", "caja"),
                "importe": importe,
            }
        )

    if intencion == "devolucion_cajas":
        vista["cantidad"] = payload.get("cantidad")
        tipo_caja_id = payload.get("tipo_caja_id")
        vista["tipo_caja"] = catalogos.tipos_caja.get(str(tipo_caja_id)) if tipo_caja_id else None
    if intencion in ("pago", "gasto"):
        vista["monto"] = payload.get("monto")
    if intencion == "pago":
        vista["direccion"] = payload.get("direccion")
    if intencion == "gasto":
        vista["categoria"] = payload.get("categoria")
        vista["descripcion"] = payload.get("descripcion")

    if payload.get("nota"):
        vista["descripcion"] = vista.get("descripcion") or payload["nota"]
    return vista


def _parsear_fecha(texto: str) -> str:
    limpio = texto.strip().lower()
    hoy = date.today()
    if limpio in ("hoy", "hoi"):
        return hoy.isoformat()
    if limpio == "ayer":
        return (hoy - timedelta(days=1)).isoformat()
    if limpio == "antier":
        return (hoy - timedelta(days=2)).isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", limpio):
        return date.fromisoformat(limpio).isoformat()
    dmy = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", limpio)
    if dmy:
        dia, mes, anio = int(dmy.group(1)), int(dmy.group(2)), dmy.group(3)
        anio_num = hoy.year if anio is None else (int(anio) + 2000 if len(anio) == 2 else int(anio))
        return date(anio_num, mes, dia).isoformat()
    raise ValueError(f"No entendi la fecha {texto!r}. Usa AAAA-MM-DD, DD/MM o 'hoy'.")


def _parsear_monto(texto: str) -> str:
    limpio = texto.strip().replace("$", "").replace(",", "")
    try:
        return str(Decimal(limpio))
    except InvalidOperation as exc:
        raise ValueError(f"No entendi el monto {texto!r}. Ejemplo: 385.00") from exc


def _parsear_entero(texto: str) -> int:
    try:
        valor = int(texto.strip())
    except ValueError as exc:
        raise ValueError(f"No entendi la cantidad {texto!r}. Manda un numero entero.") from exc
    if valor <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    return valor


def aplicar_edicion(
    intencion: str,
    payload: dict[str, Any],
    campo: str,
    texto: str,
    catalogos: Catalogos,
) -> dict[str, Any]:
    """Convierte la respuesta del usuario en cambios para PATCH del borrador.

    Levanta ValueError con mensaje apto para el usuario si el valor no sirve.
    """
    if campo == "fecha":
        return {"fecha": _parsear_fecha(texto)}

    if campo == "contraparte":
        resolucion = resolver(texto.strip(), catalogos.catalogo_contrapartes())
        if not resolucion.es_automatica:
            opciones = ", ".join(c.nombre for c in resolucion.candidatos[:4])
            pista = f" Parecidos: {opciones}." if opciones else ""
            raise ValueError(f"No encontre a {texto.strip()!r}.{pista}")
        assert resolucion.elegido is not None
        return {CLAVE_CONTRAPARTE[intencion]: str(resolucion.elegido.id)}

    if campo in ("cajas", "precio"):
        items = [dict(item) for item in payload.get("items", [])] or [{}]
        if campo == "cajas":
            items[0]["cajas"] = _parsear_entero(texto)
        else:
            items[0]["precio_unitario"] = _parsear_monto(texto)
        return {"items": items}

    if campo == "cantidad":
        return {"cantidad": _parsear_entero(texto)}

    if campo == "monto":
        return {"monto": _parsear_monto(texto)}

    if campo == "direccion":
        limpio = texto.strip().lower()
        if limpio.startswith("cobr") or limpio in ("me pagan", "entrada"):
            return {"direccion": "cobro"}
        if limpio.startswith("pag") or limpio in ("yo pago", "salida"):
            return {"direccion": "pago"}
        raise ValueError("Dime 'cobro' (me pagan) o 'pago' (yo pago).")

    if campo in ("nota", "categoria", "descripcion"):
        return {campo: texto.strip()}

    raise ValueError(f"No se puede editar el campo {campo!r}.")
