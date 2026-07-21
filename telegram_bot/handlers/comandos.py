"""Comandos del bot. Cada uno consulta la API interna, nunca la BD directo."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from backend.infrastructure.ai.resolver import resolver
from backend.interfaces.i18n import es
from telegram_bot.api_client import ErrorAPI, api
from telegram_bot.formatters.tarjetas import tarjeta_saldo_cajas
from telegram_bot.keyboards.confirmacion import teclado_confirmacion
from telegram_bot.pipeline import tarjeta_de_borrador
from telegram_bot.presentacion import Catalogos

router = Router(name="comandos")

_MAX_PENDIENTES = 5


@router.message(CommandStart())
async def inicio(mensaje: Message) -> None:
    await mensaje.answer(es.BIENVENIDA)


@router.message(Command("ayuda"))
async def ayuda(mensaje: Message) -> None:
    await mensaje.answer(es.AYUDA)


async def _buscar_contraparte(nombre: str, catalogos: Catalogos) -> str | None:
    resolucion = resolver(nombre, catalogos.catalogo_contrapartes())
    if resolucion.es_automatica and resolucion.elegido is not None:
        return str(resolucion.elegido.id)
    return None


@router.message(Command("cajas"))
async def cajas(mensaje: Message) -> None:
    try:
        tablero = await api().tablero_cajas()
    except ErrorAPI as exc:
        await mensaje.answer(exc.texto)
        return
    filas = [{"nombre": fila["nombre"], "saldo": fila["total"]} for fila in tablero]
    await mensaje.answer(tarjeta_saldo_cajas(filas))


@router.message(Command("saldo"))
async def saldo(mensaje: Message, command: CommandObject) -> None:
    nombre = (command.args or "").strip()
    if not nombre:
        await mensaje.answer(es.DAME_NOMBRE.format(ejemplo="/saldo Los Pinos"))
        return
    catalogos = Catalogos(await api().catalogos())
    contraparte_id = await _buscar_contraparte(nombre, catalogos)
    if contraparte_id is None:
        await mensaje.answer(es.NO_CONTRAPARTE.format(nombre=nombre))
        return
    try:
        datos = await api().saldo_cajas(contraparte_id)
    except ErrorAPI as exc:
        await mensaje.answer(exc.texto)
        return
    por_tipo = datos.get("por_tipo_caja") or {}
    if not por_tipo:
        await mensaje.answer(f"{datos['nombre']}: sin cajas pendientes.")
        return
    lineas = [f"CAJAS - {datos['nombre']}", ""]
    for tipo_id, saldo_tipo in por_tipo.items():
        nombre_tipo = catalogos.tipos_caja.get(str(tipo_id), "caja")
        signo = "te debe" if saldo_tipo > 0 else "le debes"
        lineas.append(f"  {nombre_tipo}: {abs(saldo_tipo)} ({signo})")
    lineas += ["", f"Neto: {datos['total']}"]
    await mensaje.answer("\n".join(lineas))


async def _saldo_dinero(mensaje: Message, nombre: str, *, por_cobrar: bool) -> None:
    ejemplo = "/medeben Frutas del Valle" if por_cobrar else "/debo Los Pinos"
    if not nombre:
        await mensaje.answer(es.DAME_NOMBRE.format(ejemplo=ejemplo))
        return
    catalogos = Catalogos(await api().catalogos())
    contraparte_id = await _buscar_contraparte(nombre, catalogos)
    if contraparte_id is None:
        await mensaje.answer(es.NO_CONTRAPARTE.format(nombre=nombre))
        return
    try:
        if por_cobrar:
            datos = await api().cuentas_por_cobrar(contraparte_id)
        else:
            datos = await api().cuentas_por_pagar(contraparte_id)
    except ErrorAPI as exc:
        await mensaje.answer(exc.texto)
        return
    await mensaje.answer(
        es.SALDO_DINERO.format(
            nombre=datos["nombre"],
            facturado=datos["facturado"],
            pagado=datos["pagado"],
            pendiente=datos["pendiente"],
        )
    )


@router.message(Command("medeben"))
async def medeben(mensaje: Message, command: CommandObject) -> None:
    await _saldo_dinero(mensaje, (command.args or "").strip(), por_cobrar=True)


@router.message(Command("debo"))
async def debo(mensaje: Message, command: CommandObject) -> None:
    await _saldo_dinero(mensaje, (command.args or "").strip(), por_cobrar=False)


@router.message(Command("pendientes"))
async def pendientes(mensaje: Message) -> None:
    try:
        borradores = await api().borradores_pendientes()
    except ErrorAPI as exc:
        await mensaje.answer(exc.texto)
        return
    if not borradores:
        await mensaje.answer(es.SIN_PENDIENTES)
        return
    catalogos = Catalogos(await api().catalogos())
    for borrador in borradores[:_MAX_PENDIENTES]:
        await mensaje.answer(
            tarjeta_de_borrador(borrador, catalogos),
            reply_markup=teclado_confirmacion(borrador["id"]),
        )
