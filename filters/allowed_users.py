from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import ALLOWED_IDS


class AllowedUserFilter(BaseFilter):

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ALLOWED_IDS