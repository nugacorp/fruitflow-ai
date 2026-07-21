"""Punto de entrada del bot. Polling en desarrollo, webhook en produccion."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.config import get_settings
from telegram_bot.handlers import callbacks, comandos, mensajes
from telegram_bot.middlewares import AutorizacionMiddleware

log = logging.getLogger("fruitflow.bot")


def crear_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(AutorizacionMiddleware())
    dp.callback_query.middleware(AutorizacionMiddleware())
    dp.include_router(comandos.router)
    dp.include_router(callbacks.router)
    dp.include_router(mensajes.router)  # ultimo: captura todo lo demas
    return dp


async def principal() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el entorno")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = crear_dispatcher()

    if settings.telegram_use_webhook:
        url = f"https://{settings.domain}/webhook/telegram/{settings.telegram_webhook_secret}"
        await bot.set_webhook(url, secret_token=settings.telegram_webhook_secret)
        log.info("Webhook configurado en %s", url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Iniciando polling")
        await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(principal())
