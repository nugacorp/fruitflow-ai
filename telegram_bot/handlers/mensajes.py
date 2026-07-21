"""Captura de mensajes: texto, voz, foto y documento."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from backend.interfaces.i18n import es
from telegram_bot.api_client import ErrorAPI
from telegram_bot.pipeline import procesar_texto

log = logging.getLogger("fruitflow.bot.mensajes")

router = Router(name="mensajes")


@router.message(F.text, StateFilter(None))
async def texto(mensaje: Message) -> None:
    espera = await mensaje.answer(es.PROCESANDO)
    try:
        respuestas = await procesar_texto(mensaje.text or "")
    except ErrorAPI as exc:
        await espera.edit_text(exc.texto)
        return
    except Exception:
        # El bot nunca debe morir por un mensaje; el detalle queda en el log.
        log.exception("Fallo procesando texto")
        await espera.edit_text(es.ERROR_INTERNO)
        return

    primera = respuestas[0]
    await espera.edit_text(primera.texto, reply_markup=primera.teclado)
    for extra in respuestas[1:]:
        await mensaje.answer(extra.texto, reply_markup=extra.teclado)


@router.message(F.voice | F.audio)
async def voz(mensaje: Message) -> None:
    # TODO(fase-9): descargar, subir a MinIO, encolar transcripcion Whisper
    await mensaje.answer(es.MEDIO_NO_DISPONIBLE.format(medio="audios"))


@router.message(F.photo)
async def foto(mensaje: Message) -> None:
    # TODO(fase-9): descargar, deduplicar por sha256, encolar Vision/OCR
    await mensaje.answer(es.MEDIO_NO_DISPONIBLE.format(medio="fotos"))


@router.message(F.document)
async def documento(mensaje: Message) -> None:
    # TODO(fase-9): PyMuPDF; si no hay capa de texto, Tesseract
    await mensaje.answer(es.MEDIO_NO_DISPONIBLE.format(medio="documentos"))
