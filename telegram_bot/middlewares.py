"""Whitelist estricta: solo los telegram_user_id autorizados pueden operar."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from backend.config import get_settings
from backend.interfaces.i18n import es

log = logging.getLogger("fruitflow.bot.auth")


class AutorizacionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        evento: TelegramObject,
        datos: dict[str, Any],
    ) -> Any:
        usuario = getattr(evento, "from_user", None)
        permitidos = get_settings().usuarios_permitidos

        if usuario is None or (permitidos and usuario.id not in permitidos):
            log.warning("Acceso denegado a telegram_user_id=%s", getattr(usuario, "id", None))
            if isinstance(evento, Message):
                await evento.answer(es.NO_AUTORIZADO)
            elif isinstance(evento, CallbackQuery):
                await evento.answer(es.NO_AUTORIZADO, show_alert=True)
            return None

        datos["telegram_user_id"] = usuario.id
        return await handler(evento, datos)
