import asyncio
import logging
from collections.abc import Awaitable, Callable

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonWebApp, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis

from bot.api_client import CatalogApi
from bot.config import Settings
from bot.handlers import admin, common
from bot.middlewares import DeduplicateUpdatesMiddleware

log = logging.getLogger(__name__)


async def call_with_flood_retry(call: Callable[[], Awaitable[object]], attempts: int = 3) -> None:
    """All replicas configure the webhook on start; Telegram may throttle the parallel calls."""
    for attempt in range(1, attempts + 1):
        try:
            await call()
            return
        except TelegramRetryAfter as exc:
            if attempt == attempts:
                raise
            await asyncio.sleep(exc.retry_after)


async def on_startup(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    http_session = aiohttp.ClientSession()
    dispatcher["http_session"] = http_session
    dispatcher["api"] = CatalogApi(
        settings.api_base_url, settings.internal_api_token.get_secret_value(), http_session
    )

    await call_with_flood_retry(
        lambda: bot.set_webhook(
            settings.webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    )
    await call_with_flood_retry(
        lambda: bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Каталог", web_app=WebAppInfo(url=settings.webapp_url))
        )
    )
    # The Mini App menu button hides the command list, so "/" suggestions are the way back to /start.
    await call_with_flood_retry(
        lambda: bot.set_my_commands([BotCommand(command="start", description="Каталог товаров")])
    )
    admin_commands = [
        BotCommand(command="start", description="Каталог товаров"),
        BotCommand(command="create", description="Создать товар"),
        BotCommand(command="cancel", description="Отменить создание товара"),
    ]
    for admin_id in settings.admin_id_set:
        await call_with_flood_retry(
            lambda admin_id=admin_id: bot.set_my_commands(
                admin_commands, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        )
    log.info("Webhook is set to %s", settings.webhook_url)


async def on_shutdown(dispatcher: Dispatcher) -> None:
    await dispatcher["http_session"].close()


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()

    session = None
    if settings.telegram_api_base:
        session = AiohttpSession(api=TelegramAPIServer.from_base(settings.telegram_api_base))
    bot = Bot(
        settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    redis = Redis.from_url(settings.redis_url)
    dispatcher = Dispatcher(storage=RedisStorage(redis), settings=settings)
    dispatcher.update.outer_middleware(DeduplicateUpdatesMiddleware(redis))
    dispatcher.include_routers(
        common.start_router,
        admin.create_admin_router(settings.admin_id_set),
        common.fallback_router,
    )
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value(),
        handle_in_background=False,
    ).register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)
    app.router.add_get("/health", health)

    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
