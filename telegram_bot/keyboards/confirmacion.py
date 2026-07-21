"""Teclados inline. Los callback_data llevan el id del borrador.

Telegram limita callback_data a 64 bytes: nunca van dos UUIDs juntos;
los candidatos viajan por indice contra payload['candidatos'].
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from backend.interfaces.i18n import es
from telegram_bot.presentacion import CAMPOS_EDITABLES


def teclado_confirmacion(borrador_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=es.BOTON_GUARDAR, callback_data=f"ok:{borrador_id}"),
                InlineKeyboardButton(text=es.BOTON_EDITAR, callback_data=f"ed:{borrador_id}"),
                InlineKeyboardButton(text=es.BOTON_CANCELAR, callback_data=f"no:{borrador_id}"),
            ]
        ]
    )


def teclado_advertencia(borrador_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=es.BOTON_SI, callback_data=f"ok:{borrador_id}"),
                InlineKeyboardButton(text=es.BOTON_CORREGIR, callback_data=f"ed:{borrador_id}"),
            ]
        ]
    )


def teclado_candidatos(borrador_id: str, candidatos: list[str]) -> InlineKeyboardMarkup:
    """Cuando el alias es ambiguo, el usuario elige por indice (RN-09)."""
    filas = [
        [InlineKeyboardButton(text=nombre, callback_data=f"cp:{borrador_id}:{indice}")]
        for indice, nombre in enumerate(candidatos[:4])
    ]
    filas.append([InlineKeyboardButton(text=es.BOTON_ES_NUEVO, callback_data=f"cn:{borrador_id}")])
    return InlineKeyboardMarkup(inline_keyboard=filas)


def teclado_campos(borrador_id: str, intencion: str) -> InlineKeyboardMarkup:
    """Un boton por campo editable, mas volver a la tarjeta."""
    filas = [
        [InlineKeyboardButton(text=etiqueta, callback_data=f"cf:{borrador_id}:{campo}")]
        for campo, etiqueta in CAMPOS_EDITABLES.get(intencion, [])
    ]
    filas.append([InlineKeyboardButton(text=es.BOTON_VOLVER, callback_data=f"cv:{borrador_id}")])
    return InlineKeyboardMarkup(inline_keyboard=filas)
