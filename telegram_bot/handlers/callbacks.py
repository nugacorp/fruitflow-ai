"""Botones de la tarjeta de confirmacion y flujo de edicion campo por campo.

Todo pasa por la API interna: confirmar ejecuta la operacion (RN-01),
cancelar nunca borra nada (el borrador queda cancelado, RN-08).
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from backend.interfaces.i18n import es
from telegram_bot.api_client import ErrorAPI, api
from telegram_bot.keyboards.confirmacion import teclado_campos, teclado_confirmacion
from telegram_bot.pipeline import tarjeta_de_borrador
from telegram_bot.presentacion import (
    CAMPOS_EDITABLES,
    CLAVE_CONTRAPARTE,
    Catalogos,
    aplicar_edicion,
)

log = logging.getLogger("fruitflow.bot.callbacks")

router = Router(name="callbacks")


class Edicion(StatesGroup):
    esperando_valor = State()


_ETIQUETAS_CAMPO = {
    campo: etiqueta for campos in CAMPOS_EDITABLES.values() for campo, etiqueta in campos
}


def _mensaje_de(consulta: CallbackQuery) -> Message | None:
    return consulta.message if isinstance(consulta.message, Message) else None


async def _catalogos() -> Catalogos:
    return Catalogos(await api().catalogos())


@router.callback_query(F.data.startswith("ok:"))
async def confirmar(consulta: CallbackQuery) -> None:
    borrador_id = (consulta.data or "")[3:]
    mensaje = _mensaje_de(consulta)
    try:
        resultado = await api().confirmar_borrador(borrador_id)
    except ErrorAPI as exc:
        await consulta.answer(exc.texto, show_alert=True)
        return
    await consulta.answer()
    if mensaje is not None:
        await mensaje.edit_reply_markup(reply_markup=None)
        texto = es.GUARDADO.format(folio=resultado.get("folio"))
        if resultado.get("requiere_revision"):
            texto += " " + es.MARCADA_REVISION
        await mensaje.answer(texto)


@router.callback_query(F.data.startswith("no:"))
async def cancelar(consulta: CallbackQuery) -> None:
    borrador_id = (consulta.data or "")[3:]
    mensaje = _mensaje_de(consulta)
    try:
        await api().cancelar_borrador(borrador_id)
    except ErrorAPI as exc:
        await consulta.answer(exc.texto, show_alert=True)
        return
    await consulta.answer()
    if mensaje is not None:
        await mensaje.edit_reply_markup(reply_markup=None)
        await mensaje.answer(es.CANCELADO)


@router.callback_query(F.data.startswith("ed:"))
async def editar(consulta: CallbackQuery) -> None:
    borrador_id = (consulta.data or "")[3:]
    mensaje = _mensaje_de(consulta)
    try:
        borrador = await api().obtener_borrador(borrador_id)
    except ErrorAPI as exc:
        await consulta.answer(exc.texto, show_alert=True)
        return
    await consulta.answer(es.ELIGE_CAMPO)
    if mensaje is not None:
        await mensaje.edit_reply_markup(
            reply_markup=teclado_campos(borrador_id, borrador["intencion"])
        )


@router.callback_query(F.data.startswith("cv:"))
async def volver(consulta: CallbackQuery, state: FSMContext) -> None:
    borrador_id = (consulta.data or "")[3:]
    await state.clear()
    await consulta.answer()
    mensaje = _mensaje_de(consulta)
    if mensaje is not None:
        await mensaje.edit_reply_markup(reply_markup=teclado_confirmacion(borrador_id))


@router.callback_query(F.data.startswith("cf:"))
async def elegir_campo(consulta: CallbackQuery, state: FSMContext) -> None:
    partes = (consulta.data or "").split(":", 2)
    if len(partes) != 3:
        await consulta.answer()
        return
    _, borrador_id, campo = partes
    await state.set_state(Edicion.esperando_valor)
    await state.update_data(borrador_id=borrador_id, campo=campo)
    await consulta.answer()
    mensaje = _mensaje_de(consulta)
    if mensaje is not None:
        etiqueta = _ETIQUETAS_CAMPO.get(campo, campo)
        await mensaje.answer(es.MANDA_VALOR.format(campo=etiqueta))


@router.message(StateFilter(Edicion.esperando_valor), F.text)
async def capturar_valor(mensaje: Message, state: FSMContext) -> None:
    datos = await state.get_data()
    borrador_id = str(datos.get("borrador_id", ""))
    campo = str(datos.get("campo", ""))
    try:
        borrador = await api().obtener_borrador(borrador_id)
        catalogos = await _catalogos()
    except ErrorAPI as exc:
        await state.clear()
        await mensaje.answer(exc.texto)
        return

    try:
        cambios = aplicar_edicion(
            borrador["intencion"], borrador["payload"], campo, mensaje.text or "", catalogos
        )
    except ValueError as exc:
        # El valor no sirve: se avisa y se mantiene el estado para reintentar.
        await mensaje.answer(str(exc))
        return

    try:
        actualizado = await api().editar_borrador(borrador_id, cambios)
    except ErrorAPI as exc:
        await state.clear()
        await mensaje.answer(exc.texto)
        return

    await state.clear()
    await mensaje.answer(
        tarjeta_de_borrador(actualizado, catalogos),
        reply_markup=teclado_confirmacion(borrador_id),
    )


@router.callback_query(F.data.startswith("cp:"))
async def elegir_candidato(consulta: CallbackQuery) -> None:
    partes = (consulta.data or "").split(":", 2)
    if len(partes) != 3 or not partes[2].isdigit():
        await consulta.answer()
        return
    _, borrador_id, indice_texto = partes
    try:
        borrador = await api().obtener_borrador(borrador_id)
        candidatos: list[dict[str, Any]] = borrador["payload"].get("candidatos") or []
        indice = int(indice_texto)
        if indice >= len(candidatos):
            await consulta.answer()
            return
        clave = CLAVE_CONTRAPARTE[borrador["intencion"]]
        actualizado = await api().editar_borrador(
            borrador_id, {clave: candidatos[indice]["id"], "candidatos": []}
        )
        catalogos = await _catalogos()
    except ErrorAPI as exc:
        await consulta.answer(exc.texto, show_alert=True)
        return
    await consulta.answer()
    mensaje = _mensaje_de(consulta)
    if mensaje is not None:
        await mensaje.edit_text(
            tarjeta_de_borrador(actualizado, catalogos),
            reply_markup=teclado_confirmacion(borrador_id),
        )


@router.callback_query(F.data.startswith("cn:"))
async def contraparte_nueva(consulta: CallbackQuery) -> None:
    # TODO(decision): alta de contrapartes desde el chat aun sin especificar.
    await consulta.answer(es.CONTRAPARTE_NUEVA_PENDIENTE, show_alert=True)
