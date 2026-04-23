from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message


class AdminOnly(BaseMiddleware):
    def __init__(self, allowed_user_ids: list[int]):
        self.allowed = set(allowed_user_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user is not None:
            if event.from_user.id not in self.allowed:
                return None
        return await handler(event, data)
