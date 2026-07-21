"""Texto libre -> extraccion IA -> resolucion (RN-09) -> borrador (RN-01)
-> tarjeta de confirmacion. El bot solo habla con la API interna."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from backend.infrastructure.ai.cliente import extractor, extractor_disponible
from backend.infrastructure.ai.esquemas import LineaExtraida, OperacionExtraida
from backend.infrastructure.ai.resolver import Resolucion, resolver
from backend.interfaces.i18n import es
from telegram_bot.api_client import api
from telegram_bot.formatters.tarjetas import tarjeta_operacion
from telegram_bot.keyboards.confirmacion import teclado_candidatos, teclado_confirmacion
from telegram_bot.presentacion import CLAVE_CONTRAPARTE, Catalogos, vista_operacion


@dataclass(slots=True)
class Respuesta:
    texto: str
    teclado: InlineKeyboardMarkup | None = None


@dataclass(slots=True)
class _Armado:
    payload: dict[str, Any]
    faltantes: list[str] = field(default_factory=list)
    candidatos_contraparte: list[dict[str, str]] = field(default_factory=list)


async def procesar_texto(texto: str) -> list[Respuesta]:
    if not extractor_disponible():
        return [Respuesta(es.IA_NO_DISPONIBLE)]

    catalogos = Catalogos(await api().catalogos())
    extraccion = await extractor().extraer(
        texto,
        fecha_actual=date.today(),
        contrapartes=list(catalogos.contrapartes.values()),
        productos=list(catalogos.productos.values()),
    )
    operaciones = [op for op in extraccion.operaciones if op.tipo in CLAVE_CONTRAPARTE]
    if not operaciones:
        return [Respuesta(es.NO_ENTENDI)]

    respuestas: list[Respuesta] = []
    for operacion in operaciones:
        armado = _armar_payload(operacion, catalogos)
        borrador = await api().crear_borrador(
            intencion=operacion.tipo,
            payload=armado.payload,
            faltantes=armado.faltantes,
            preguntas=list(extraccion.preguntas),
            confianza=extraccion.confianza,
        )
        respuestas.append(_respuesta_de_borrador(borrador, catalogos))
    return respuestas


def tarjeta_de_borrador(borrador: dict[str, Any], catalogos: Catalogos) -> str:
    vista = vista_operacion(
        borrador["intencion"],
        borrador["payload"],
        catalogos,
        faltantes=borrador.get("faltantes", []),
    )
    tarjeta = tarjeta_operacion(vista)
    preguntas = borrador.get("preguntas") or []
    if preguntas:
        tarjeta += "\n\n" + "\n".join(f"? {p}" for p in preguntas)
    return tarjeta


def _respuesta_de_borrador(borrador: dict[str, Any], catalogos: Catalogos) -> Respuesta:
    candidatos = borrador["payload"].get("candidatos") or []
    if candidatos:
        teclado = teclado_candidatos(borrador["id"], [c["nombre"] for c in candidatos])
    else:
        teclado = teclado_confirmacion(borrador["id"])
    return Respuesta(tarjeta_de_borrador(borrador, catalogos), teclado)


def _armar_payload(operacion: OperacionExtraida, catalogos: Catalogos) -> _Armado:
    armado = _Armado(payload={"fecha": (operacion.fecha or date.today()).isoformat()})
    if operacion.nota:
        armado.payload["nota"] = operacion.nota

    _resolver_contraparte(operacion, catalogos, armado)

    if operacion.tipo in ("compra", "venta"):
        items = [_armar_item(linea, catalogos) for linea in operacion.lineas]
        armado.payload["items"] = items
        if not items or any("producto_id" not in item for item in items):
            armado.faltantes.append("items")

    elif operacion.tipo == "devolucion_cajas":
        cantidad = next((li.cajas for li in operacion.lineas if li.cajas), None)
        if cantidad is None:
            armado.faltantes.append("cantidad")
        else:
            armado.payload["cantidad"] = cantidad
        tipo_caja = _resolver_tipo_caja(operacion, catalogos)
        if tipo_caja is None:
            armado.faltantes.append("tipo_caja_id")
        else:
            armado.payload["tipo_caja_id"] = tipo_caja

    elif operacion.tipo == "pago":
        if operacion.monto is None:
            armado.faltantes.append("monto")
        else:
            armado.payload["monto"] = str(operacion.monto)
        _inferir_direccion(armado, catalogos)

    elif operacion.tipo == "gasto":
        if operacion.monto is None:
            armado.faltantes.append("monto")
        else:
            armado.payload["monto"] = str(operacion.monto)
        if operacion.categoria_gasto:
            armado.payload["categoria"] = operacion.categoria_gasto
        else:
            armado.faltantes.append("categoria")
        # El gasto no exige contraparte: quitar el faltante si se agrego.
        armado.faltantes = [f for f in armado.faltantes if f != "contraparte_id"]

    if armado.candidatos_contraparte:
        armado.payload["candidatos"] = armado.candidatos_contraparte
    return armado


def _resolver_contraparte(
    operacion: OperacionExtraida, catalogos: Catalogos, armado: _Armado
) -> None:
    clave = CLAVE_CONTRAPARTE[operacion.tipo]
    if not operacion.contraparte_texto:
        armado.faltantes.append(clave)
        return
    resolucion: Resolucion = resolver(
        operacion.contraparte_texto, catalogos.catalogo_contrapartes()
    )
    if resolucion.es_automatica and resolucion.elegido is not None:
        armado.payload[clave] = str(resolucion.elegido.id)
        return
    armado.faltantes.append(clave)
    armado.candidatos_contraparte = [
        {"id": str(c.id), "nombre": c.nombre} for c in resolucion.candidatos[:4]
    ]


def _armar_item(linea: LineaExtraida, catalogos: Catalogos) -> dict[str, Any]:
    item: dict[str, Any] = {}
    if linea.producto_texto:
        resolucion = resolver(linea.producto_texto, catalogos.catalogo_productos())
        if resolucion.es_automatica and resolucion.elegido is not None:
            item["producto_id"] = str(resolucion.elegido.id)
    if linea.cajas is not None:
        item["cajas"] = linea.cajas
    if linea.precio_unitario is not None:
        item["precio_unitario"] = str(linea.precio_unitario)
    if linea.unidad_precio:
        item["unidad_precio"] = linea.unidad_precio
    if linea.kg_por_caja is not None:
        item["kg_por_caja"] = str(linea.kg_por_caja)
    if linea.tipo_caja_texto:
        resolucion = resolver(linea.tipo_caja_texto, catalogos.catalogo_tipos_caja())
        if resolucion.es_automatica and resolucion.elegido is not None:
            item["tipo_caja_id"] = str(resolucion.elegido.id)
    return item


def _resolver_tipo_caja(operacion: OperacionExtraida, catalogos: Catalogos) -> str | None:
    texto = next((li.tipo_caja_texto for li in operacion.lineas if li.tipo_caja_texto), None)
    if not texto:
        # Con un solo tipo de caja en catalogo no hay ambiguedad posible.
        tipos = catalogos.catalogo_tipos_caja()
        return str(tipos[0][0]) if len(tipos) == 1 else None
    resolucion = resolver(texto, catalogos.catalogo_tipos_caja())
    if resolucion.es_automatica and resolucion.elegido is not None:
        return str(resolucion.elegido.id)
    return None


def _inferir_direccion(armado: _Armado, catalogos: Catalogos) -> None:
    contraparte_id = armado.payload.get("contraparte_id")
    tipo = catalogos.tipos_contraparte.get(str(contraparte_id)) if contraparte_id else None
    if tipo == "proveedor":
        armado.payload["direccion"] = "pago"
    elif tipo == "cliente":
        armado.payload["direccion"] = "cobro"
    else:
        armado.faltantes.append("direccion")
