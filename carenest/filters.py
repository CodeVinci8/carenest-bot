from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message


class AllowedUserFilter(BaseFilter):
    def __init__(self, allowed_ids: frozenset[int]):
        self.allowed_ids = allowed_ids

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id in self.allowed_ids
