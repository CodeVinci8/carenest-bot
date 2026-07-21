from __future__ import annotations

import logging
import sqlite3

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from carenest.config import AppConfig
from carenest.database import WishlistDatabase
from carenest.filters import AllowedUserFilter
from carenest.texts import ADD_WISH_BUTTON, WISHLIST_BUTTON

MAX_WISHLIST_ITEM_LENGTH = 200
logger = logging.getLogger(__name__)


class WishlistStates(StatesGroup):
    waiting_for_item = State()


def build_wishlist_router(config: AppConfig, database: WishlistDatabase) -> Router:
    router = Router(name="wishlist")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def add_item_start(message: Message, state: FSMContext) -> None:
        await state.set_state(WishlistStates.waiting_for_item)
        await message.answer(
            f"Напишите желание одним сообщением. Допустимо до {MAX_WISHLIST_ITEM_LENGTH} символов."
        )

    async def save_item(message: Message, state: FSMContext) -> None:
        item_name = (message.text or "").strip()
        if not item_name:
            await message.answer("Желание не может быть пустым. Напишите его текстом.")
            return
        if len(item_name) > MAX_WISHLIST_ITEM_LENGTH:
            await message.answer(
                f"Слишком длинный текст. Сократите его до {MAX_WISHLIST_ITEM_LENGTH} символов."
            )
            return
        try:
            database.add_item(item_name)
        except sqlite3.Error as error:
            logger.error("Не удалось сохранить желание в базе данных: %s", error)
            await message.answer("Не удалось сохранить желание. Попробуйте немного позже.")
            return
        await state.clear()
        await message.answer("Желание сохранено. ✨")

    async def wrong_item_content(message: Message) -> None:
        await message.answer("Пожалуйста, отправьте желание обычным текстом.")

    async def show_wishlist(message: Message) -> None:
        try:
            items = database.get_items()
        except sqlite3.Error as error:
            logger.error("Не удалось прочитать список желаний: %s", error)
            await message.answer("Не удалось открыть список. Попробуйте немного позже.")
            return
        if not items:
            await message.answer("Список желаний пока пуст.")
            return
        lines = [f"{index}. {name}" for index, (_, name) in enumerate(items, start=1)]
        await message.answer("Список желаний 📝\n\n" + "\n".join(lines))

    router.message.register(add_item_start, Command("wish"), allowed)
    router.message.register(add_item_start, F.text == ADD_WISH_BUTTON, allowed)
    router.message.register(save_item, WishlistStates.waiting_for_item, F.text, allowed)
    router.message.register(wrong_item_content, WishlistStates.waiting_for_item, allowed)
    router.message.register(show_wishlist, Command("wishlist"), allowed)
    router.message.register(show_wishlist, F.text == WISHLIST_BUTTON, allowed)
    return router
