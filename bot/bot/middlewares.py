from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from redis.asyncio import Redis

# Telegram keeps undelivered updates for 24 hours, so older ids can't come back.
UPDATE_ID_TTL_SECONDS = 24 * 60 * 60


class DeduplicateUpdatesMiddleware(BaseMiddleware):
    """Processes each update_id once across all bot replicas.

    The key is released if handling fails, so Telegram's retry can process it again.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        key = f"tg:update:{event.update_id}"
        if not await self._redis.set(key, 1, nx=True, ex=UPDATE_ID_TTL_SECONDS):
            return None
        try:
            return await handler(event, data)
        except Exception:
            await self._redis.delete(key)
            raise
