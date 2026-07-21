"""Formato de las tarjetas de confirmacion que ve el usuario."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

ICONO = {
    "compra": "COMPRA",
    "venta": "VENTA",
    "devolucion_cajas": "CAJAS",
    "pago": "PAGO",
    "gasto": "GASTO",
}


def _money(valor: Decimal | None) -> str:
    return f"${valor:,.2f}" if valor is not None else "-"


def tarjeta_operacion(op: dict[str, Any]) -> str:
    """Construye el mensaje de confirmacion. Siempre muestra el efecto en cajas."""
    tipo = op.get("tipo", "otro")
    lineas: list[str] = [f"{ICONO.get(tipo, tipo.upper())} detectada", ""]

    etiqueta = "Proveedor" if tipo == "compra" else "Cliente"
    lineas.append(f"{etiqueta}: {op.get('contraparte') or '?'}")
    if op.get("origen"):
        lineas.append(f"Origen:    {op['origen']}")
    if op.get("destino"):
        lineas.append(f"Destino:   {op['destino']}")
    lineas.append(f"Fecha:     {op.get('fecha', '?')}")
    lineas.append("")

    total = Decimal("0")
    for linea in op.get("lineas", []):
        cajas = linea.get("cajas")
        precio = linea.get("precio_unitario")
        importe = linea.get("importe")
        if importe is not None:
            total += Decimal(str(importe))
        unidad = "kg" if linea.get("unidad_precio") == "kg" else "c/u"
        lineas.append(
            f"  - {cajas} cajas · {linea.get('producto', '?')} · "
            f"{_money(Decimal(str(precio)) if precio is not None else None)} {unidad}"
        )
        if importe is not None:
            lineas.append(f"    Importe: {_money(Decimal(str(importe)))}")

    if op.get("cantidad") is not None:
        lineas.append(f"Cajas:     {op['cantidad']} ({op.get('tipo_caja') or 'tipo por definir'})")
    if op.get("categoria"):
        lineas.append(f"Categoria: {op['categoria']}")
    if op.get("descripcion"):
        lineas.append(f"Concepto:  {op['descripcion']}")
    if op.get("direccion"):
        lineas.append(f"Direccion: {op['direccion']}")
    if op.get("monto") is not None:
        lineas.append(f"Monto:     {_money(Decimal(str(op['monto'])))}")

    if total:
        lineas += ["", f"TOTAL: {_money(total)}"]

    if op.get("utilidad_estimada") is not None:
        lineas.append(f"Utilidad estimada: {_money(Decimal(str(op['utilidad_estimada'])))}")

    if op.get("efecto_cajas"):
        lineas += ["", op["efecto_cajas"]]

    if op.get("faltantes"):
        lineas += ["", "Falta: " + ", ".join(op["faltantes"])]

    if op.get("advertencias"):
        lineas += [""] + [f"! {a}" for a in op["advertencias"]]

    return "\n".join(lineas)


def tarjeta_saldo_cajas(filas: list[dict[str, Any]]) -> str:
    if not filas:
        return "No hay cajas pendientes. Todo cuadrado."
    lineas = ["CAJAS PENDIENTES", ""]
    total = 0
    for fila in filas:
        saldo = int(fila["saldo"])
        total += saldo
        signo = "te debe" if saldo > 0 else "le debes"
        lineas.append(f"  {fila['nombre']}: {abs(saldo)} ({signo})")
    lineas += ["", f"Neto: {total}"]
    return "\n".join(lineas)


def resumen_diario(datos: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"RESUMEN DEL DIA - {datos['fecha']}",
            "",
            f"Compras: {datos['compras_cajas']} cajas · {_money(datos['compras_monto'])}",
            f"Ventas:  {datos['ventas_cajas']} cajas · {_money(datos['ventas_monto'])}",
            f"Gastos:  {_money(datos['gastos_monto'])}",
            "",
            f"Utilidad bruta: {_money(datos['utilidad'])}",
            "",
            f"Cajas pendientes de recoger: {datos['cajas_pendientes']}",
        ]
    )
