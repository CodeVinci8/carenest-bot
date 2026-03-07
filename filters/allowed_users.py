from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import ALLOWED_IDS


class AllowedUserFilter(BaseFilter):

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id in ALLOWED_IDS