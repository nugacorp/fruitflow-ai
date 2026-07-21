"""Ciclo de vida del borrador (RN-01): crear, editar, confirmar, cancelar,
expirar.

El payload del borrador ya trae entidades resueltas a UUID (RN-09 ocurrio
antes). Contrato por intencion:

    compra:  proveedor_id, fecha, items[{producto_id, cajas, precio_unitario,
             unidad_precio?, kg_por_caja?, tipo_caja_id?}], origen_id?,
             transportista_id?, folio_externo?, nota?
    venta:   cliente_id, fecha, items[... lotes_preferidos?], destino_id?,
             transportista_id?, nota?
    devolucion_cajas: contraparte_id, tipo_caja_id, cantidad, fecha,
             recibida?, nota?
    pago:    contraparte_id, direccion, monto, fecha, metodo?, referencia?,
             nota?
    gasto:   categoria, monto, fecha, descripcion?, contraparte_id?,
             imputable_tipo?, imputable_id?

Montos como str decimal, fechas ISO, UUIDs como str: el payload viaja en JSON.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.application.dto.comandos import (
    ComandoRegistrarCompra,
    ComandoRegistrarDevolucionCajas,
    ComandoRegistrarGasto,
    ComandoRegistrarPago,
    ComandoRegistrarVenta,
    ResultadoOperacion,
)
from backend.application.ports.unidad_de_trabajo import UnidadDeTrabajo
from backend.application.use_cases.registrar_finanzas import ejecutar_gasto, ejecutar_pago
from backend.application.use_cases.registrar_operaciones import (
    ejecutar_compra,
    ejecutar_devolucion_cajas,
    ejecutar_venta,
)
from backend.domain.common.tipos import (
    BorradorExpirado,
    DatosIncompletos,
    Dinero,
    UnidadPrecio,
    ahora,
)
from backend.domain.finanzas.modelo import DireccionPago
from backend.domain.operaciones.borrador import Borrador
from backend.domain.operaciones.compra import ItemCompra
from backend.domain.operaciones.venta import ItemVenta


async def crear_borrador(
    uow: UnidadDeTrabajo,
    *,
    intencion: str,
    payload: dict[str, Any],
    faltantes: list[str] | None = None,
    preguntas: list[str] | None = None,
    confianza: float | None = None,
    mensaje_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Borrador:
    """RN-01: toda extraccion crea un borrador; nada se ejecuta solo."""
    if intencion not in _EJECUTORES:
        raise DatosIncompletos(f"No se pueden registrar operaciones de tipo {intencion!r}.")
    async with uow:
        borrador = Borrador(
            intencion=intencion,
            payload=payload,
            faltantes=list(faltantes or []),
            preguntas=list(preguntas or []),
            confianza=confianza,
            mensaje_id=mensaje_id,
        )
        await uow.borradores.agregar(borrador)
        uow.registrar(borrador.evento("borrador_creado", actor_id))
    return borrador


async def editar_borrador(
    uow: UnidadDeTrabajo,
    borrador_id: uuid.UUID,
    cambios: dict[str, Any],
    *,
    actor_id: uuid.UUID | None = None,
) -> Borrador:
    async with uow:
        borrador = await _obtener_pendiente(uow, borrador_id)
        borrador.editar(cambios)
        await uow.borradores.guardar(borrador)
        uow.registrar(borrador.evento("borrador_editado", actor_id))
    return borrador


async def cancelar_borrador(
    uow: UnidadDeTrabajo,
    borrador_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> Borrador:
    async with uow:
        borrador = await _obtener_pendiente(uow, borrador_id)
        borrador.cancelar()
        await uow.borradores.guardar(borrador)
        uow.registrar(borrador.evento("borrador_cancelado", actor_id))
    return borrador


async def confirmar_borrador(
    uow: UnidadDeTrabajo,
    borrador_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    permitir_saldo_negativo: bool = True,
) -> ResultadoOperacion:
    """Callback GUARDAR: ejecuta la operacion y marca el borrador confirmado
    en la misma transaccion. Si la operacion falla, el borrador sigue
    pendiente y editable."""
    async with uow:
        borrador = await _obtener_pendiente(uow, borrador_id)
        if borrador.esta_vencido():
            raise BorradorExpirado(
                "Ese borrador ya expiro.",
                sugerencia="Mandame la operacion de nuevo.",
            )
        if not borrador.esta_completo:
            raise DatosIncompletos("Faltan datos para confirmar: " + ", ".join(borrador.faltantes))

        ejecutor = _EJECUTORES[borrador.intencion]
        resultado = await ejecutor(uow, borrador.payload, actor_id, permitir_saldo_negativo)
        borrador.confirmar(borrador.intencion, resultado.id)
        await uow.borradores.guardar(borrador)
        uow.registrar(borrador.evento("borrador_confirmado", actor_id))
    return resultado


async def expirar_borradores(uow: UnidadDeTrabajo, momento: datetime | None = None) -> int:
    """Tarea programada: los pendientes vencidos pasan a expirado (RN-01)."""
    momento = momento or ahora()
    async with uow:
        vencidos = await uow.borradores.vencidos(momento)
        for borrador in vencidos:
            borrador.expirar()
            await uow.borradores.guardar(borrador)
            uow.registrar(borrador.evento("borrador_expirado"))
    return len(vencidos)


async def registrar_desde_payload(
    uow: UnidadDeTrabajo,
    *,
    intencion: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None = None,
    permitir_saldo_negativo: bool = True,
) -> ResultadoOperacion:
    """Registro directo (API) sin borrador de por medio, mismo contrato de
    payload. La confirmacion del usuario ya ocurrio en el cliente."""
    ejecutor = _EJECUTORES.get(intencion)
    if ejecutor is None:
        raise DatosIncompletos(f"No se pueden registrar operaciones de tipo {intencion!r}.")
    async with uow:
        return await ejecutor(uow, payload, actor_id, permitir_saldo_negativo)


async def _obtener_pendiente(uow: UnidadDeTrabajo, borrador_id: uuid.UUID) -> Borrador:
    borrador = await uow.borradores.obtener(borrador_id)
    if borrador is None:
        raise DatosIncompletos("No encontre ese borrador.")
    # Validar ANTES de ejecutar nada: un borrador ya procesado no debe
    # disparar la operacion por segunda vez.
    borrador.exigir_pendiente()
    return borrador


# --- conversion payload (JSON) -> comandos tipados ---


def _uuid(valor: Any) -> uuid.UUID:
    return valor if isinstance(valor, uuid.UUID) else uuid.UUID(str(valor))


def _uuid_opcional(valor: Any) -> uuid.UUID | None:
    return None if valor is None else _uuid(valor)


def _fecha(valor: Any) -> date:
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def _dinero(valor: Any) -> Dinero:
    return valor if isinstance(valor, Dinero) else Dinero.de(str(valor))


def _decimal_opcional(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def _requerir(payload: dict[str, Any], *campos: str) -> None:
    ausentes = [campo for campo in campos if payload.get(campo) is None]
    if ausentes:
        raise DatosIncompletos("Faltan datos: " + ", ".join(ausentes))


def _item_compra(datos: dict[str, Any]) -> ItemCompra:
    _requerir(datos, "producto_id", "cajas", "precio_unitario")
    return ItemCompra(
        producto_id=_uuid(datos["producto_id"]),
        cajas=int(datos["cajas"]),
        precio_unitario=_dinero(datos["precio_unitario"]),
        unidad_precio=UnidadPrecio(datos.get("unidad_precio", "caja")),
        kg_por_caja=_decimal_opcional(datos.get("kg_por_caja")),
        tipo_caja_id=_uuid_opcional(datos.get("tipo_caja_id")),
    )


def _item_venta(datos: dict[str, Any]) -> ItemVenta:
    _requerir(datos, "producto_id", "cajas", "precio_unitario")
    preferidos = datos.get("lotes_preferidos")
    return ItemVenta(
        producto_id=_uuid(datos["producto_id"]),
        cajas=int(datos["cajas"]),
        precio_unitario=_dinero(datos["precio_unitario"]),
        unidad_precio=UnidadPrecio(datos.get("unidad_precio", "caja")),
        kg_por_caja=_decimal_opcional(datos.get("kg_por_caja")),
        tipo_caja_id=_uuid_opcional(datos.get("tipo_caja_id")),
        lotes_preferidos=[_uuid(x) for x in preferidos] if preferidos else None,
    )


async def _ejecutar_compra(
    uow: UnidadDeTrabajo,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    _permitir: bool,
) -> ResultadoOperacion:
    _requerir(payload, "proveedor_id", "fecha", "items")
    cmd = ComandoRegistrarCompra(
        proveedor_id=_uuid(payload["proveedor_id"]),
        fecha=_fecha(payload["fecha"]),
        items=[_item_compra(d) for d in payload["items"]],
        origen_id=_uuid_opcional(payload.get("origen_id")),
        transportista_id=_uuid_opcional(payload.get("transportista_id")),
        folio_externo=payload.get("folio_externo"),
        nota=payload.get("nota"),
        actor_id=actor_id,
    )
    return await ejecutar_compra(uow, cmd)


async def _ejecutar_venta(
    uow: UnidadDeTrabajo,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    _permitir: bool,
) -> ResultadoOperacion:
    _requerir(payload, "cliente_id", "fecha", "items")
    cmd = ComandoRegistrarVenta(
        cliente_id=_uuid(payload["cliente_id"]),
        fecha=_fecha(payload["fecha"]),
        items=[_item_venta(d) for d in payload["items"]],
        destino_id=_uuid_opcional(payload.get("destino_id")),
        transportista_id=_uuid_opcional(payload.get("transportista_id")),
        nota=payload.get("nota"),
        actor_id=actor_id,
    )
    return await ejecutar_venta(uow, cmd)


async def _ejecutar_devolucion(
    uow: UnidadDeTrabajo,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    permitir: bool,
) -> ResultadoOperacion:
    _requerir(payload, "contraparte_id", "tipo_caja_id", "cantidad", "fecha")
    cmd = ComandoRegistrarDevolucionCajas(
        contraparte_id=_uuid(payload["contraparte_id"]),
        tipo_caja_id=_uuid(payload["tipo_caja_id"]),
        cantidad=int(payload["cantidad"]),
        fecha=_fecha(payload["fecha"]),
        recibida=bool(payload.get("recibida", True)),
        nota=payload.get("nota"),
        actor_id=actor_id,
    )
    return await ejecutar_devolucion_cajas(uow, cmd, permitir_saldo_negativo=permitir)


async def _ejecutar_pago(
    uow: UnidadDeTrabajo,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    _permitir: bool,
) -> ResultadoOperacion:
    _requerir(payload, "contraparte_id", "direccion", "monto", "fecha")
    cmd = ComandoRegistrarPago(
        contraparte_id=_uuid(payload["contraparte_id"]),
        direccion=DireccionPago(payload["direccion"]),
        monto=_dinero(payload["monto"]),
        fecha=_fecha(payload["fecha"]),
        metodo=payload.get("metodo"),
        referencia=payload.get("referencia"),
        nota=payload.get("nota"),
        actor_id=actor_id,
    )
    return await ejecutar_pago(uow, cmd)


async def _ejecutar_gasto(
    uow: UnidadDeTrabajo,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    _permitir: bool,
) -> ResultadoOperacion:
    _requerir(payload, "categoria", "monto", "fecha")
    cmd = ComandoRegistrarGasto(
        categoria=payload["categoria"],
        monto=_dinero(payload["monto"]),
        fecha=_fecha(payload["fecha"]),
        descripcion=payload.get("descripcion"),
        contraparte_id=_uuid_opcional(payload.get("contraparte_id")),
        imputable_tipo=payload.get("imputable_tipo"),
        imputable_id=_uuid_opcional(payload.get("imputable_id")),
        actor_id=actor_id,
    )
    return await ejecutar_gasto(uow, cmd)


_EJECUTORES = {
    "compra": _ejecutar_compra,
    "venta": _ejecutar_venta,
    "devolucion_cajas": _ejecutar_devolucion,
    "pago": _ejecutar_pago,
    "gasto": _ejecutar_gasto,
}
