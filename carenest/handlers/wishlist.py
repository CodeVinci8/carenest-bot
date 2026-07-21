from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections.abc import Sequence
from typing import Literal

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from carenest.config import AppConfig
from carenest.database import WishlistDatabase
from carenest.filters import AllowedUserFilter
from carenest.texts import ADD_WISH_BUTTON, WISHLIST_BUTTON

MAX_WISHLIST_ITEM_LENGTH = 200
MAX_WISHLIST_MESSAGE_LENGTH = 3500
MAX_LEGACY_DISPLAY_LENGTH = 500
DeletionResult = Literal["ready", "deleted", "missing", "stale"]
logger = logging.getLogger(__name__)


class WishlistStates(StatesGroup):
    waiting_for_item = State()


class WishlistCallback(CallbackData, prefix="wish"):
    action: str
    item_id: int
    fingerprint: str


def wishlist_fingerprint(name: str) -> str:
    return hashlib.blake2s(name.encode("utf-8"), digest_size=6).hexdigest()


def normalize_wishlist_item(text: str) -> str:
    return text.strip()


def display_wishlist_item(name: str) -> str:
    if len(name) <= MAX_LEGACY_DISPLAY_LENGTH:
        return name
    return name[: MAX_LEGACY_DISPLAY_LENGTH - 1] + "…"


def verify_callback_item(
    database: WishlistDatabase,
    item_id: int,
    fingerprint: str,
) -> tuple[DeletionResult, str | None]:
    item = database.get_item(item_id)
    if item is None:
        return "missing", None
    name = item[1]
    if wishlist_fingerprint(name) != fingerprint:
        return "stale", None
    return "ready", name


def delete_callback_item(
    database: WishlistDatabase,
    item_id: int,
    fingerprint: str,
) -> DeletionResult:
    result, name = verify_callback_item(database, item_id, fingerprint)
    if result != "ready" or name is None:
        return result
    return "deleted" if database.delete_item(item_id, name) else "missing"


def split_wishlist(items: Sequence[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    chunks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_length = 0
    for item_id, name in items:
        line_length = len(f"#{item_id} — {display_wishlist_item(name)}\n")
        if current and current_length + line_length > MAX_WISHLIST_MESSAGE_LENGTH:
            chunks.append(current)
            current = []
            current_length = 0
        current.append((item_id, name))
        current_length += line_length
    if current:
        chunks.append(current)
    return chunks


def get_wishlist_keyboard(items: Sequence[tuple[int, str]]):
    builder = InlineKeyboardBuilder()
    for item_id, name in items:
        builder.button(
            text=f"Удалить #{item_id}",
            callback_data=WishlistCallback(
                action="ask",
                item_id=item_id,
                fingerprint=wishlist_fingerprint(name),
            ),
        )
    builder.adjust(2)
    return builder.as_markup()


def get_confirmation_keyboard(item_id: int, fingerprint: str):
    return InlineKeyboardBuilder(
        markup=[
            [
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=WishlistCallback(
                        action="confirm",
                        item_id=item_id,
                        fingerprint=fingerprint,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=WishlistCallback(
                        action="cancel",
                        item_id=item_id,
                        fingerprint=fingerprint,
                    ).pack(),
                ),
            ]
        ]
    ).as_markup()


async def cancel_wishlist_input(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление желания отменено.")


async def _answer_callback(
    callback: CallbackQuery,
    text: str,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramAPIError as error:
        logger.warning("Не удалось подтвердить действие со списком желаний: %s", error)


async def _replace_callback_message(callback: CallbackQuery, text: str) -> None:
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(text)
    except TelegramAPIError as error:
        logger.info("Сообщение списка желаний уже недоступно: %s", error)


def build_wishlist_router(config: AppConfig, database: WishlistDatabase) -> Router:
    router = Router(name="wishlist")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def add_item_start(message: Message, state: FSMContext) -> None:
        await state.set_state(WishlistStates.waiting_for_item)
        await message.answer(
            "Напишите желание одним сообщением. Допустимо до "
            f"{MAX_WISHLIST_ITEM_LENGTH} символов. Для отмены используйте /cancel."
        )

    async def save_item(message: Message, state: FSMContext) -> None:
        item_name = normalize_wishlist_item(message.text or "")
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
        await message.answer("Пожалуйста, отправьте желание обычным текстом или нажмите /cancel.")

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
        chunks = split_wishlist(items)
        for chunk_index, chunk in enumerate(chunks):
            title = "Список желаний 📝" if chunk_index == 0 else "Продолжение списка 📝"
            lines = [f"#{item_id} — {display_wishlist_item(name)}" for item_id, name in chunk]
            await message.answer(
                title + "\n\n" + "\n".join(lines),
                reply_markup=get_wishlist_keyboard(chunk),
            )

    async def process_wishlist_callback(
        callback: CallbackQuery,
        callback_data: WishlistCallback,
    ) -> None:
        action = callback_data.action
        item_id = callback_data.item_id
        fingerprint = callback_data.fingerprint
        if action == "cancel":
            await _answer_callback(callback, "Удаление отменено.")
            await _replace_callback_message(callback, "Удаление желания отменено.")
            return
        if action not in {"ask", "confirm"} or item_id <= 0:
            await _answer_callback(callback, "Некорректная кнопка.", show_alert=True)
            return

        try:
            if action == "ask":
                result, name = verify_callback_item(database, item_id, fingerprint)
            else:
                result = delete_callback_item(database, item_id, fingerprint)
                name = None
        except sqlite3.Error as error:
            logger.error("Ошибка базы данных при удалении желания: %s", error)
            await _answer_callback(callback, "Не удалось изменить список.", show_alert=True)
            return

        if result == "missing":
            await _answer_callback(
                callback, "Это желание уже удалено или не найдено.", show_alert=True
            )
            await _replace_callback_message(callback, "Желание уже удалено или не найдено.")
            return
        if result == "stale":
            await _answer_callback(
                callback, "Кнопка устарела. Откройте список снова.", show_alert=True
            )
            return
        if action == "ask" and name is not None:
            await _answer_callback(callback, "Подтвердите удаление.")
            if isinstance(callback.message, Message):
                try:
                    await callback.message.answer(
                        f"Удалить желание #{item_id}: «{display_wishlist_item(name)}»?",
                        reply_markup=get_confirmation_keyboard(item_id, fingerprint),
                    )
                except TelegramAPIError as error:
                    logger.warning("Не удалось показать подтверждение удаления: %s", error)
            return

        await _answer_callback(callback, "Желание удалено.")
        await _replace_callback_message(callback, f"Желание #{item_id} удалено.")

    async def malformed_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback, "Некорректная или устаревшая кнопка.", show_alert=True)

    async def cancel_without_input(message: Message) -> None:
        await message.answer("Сейчас нет активного ввода желания.")

    router.message.register(add_item_start, Command("wish"), allowed)
    router.message.register(add_item_start, F.text == ADD_WISH_BUTTON, allowed)
    router.message.register(show_wishlist, Command("wishlist"), allowed)
    router.message.register(show_wishlist, F.text == WISHLIST_BUTTON, allowed)
    router.message.register(
        cancel_wishlist_input,
        WishlistStates.waiting_for_item,
        Command("cancel"),
        allowed,
    )
    router.message.register(
        save_item,
        WishlistStates.waiting_for_item,
        F.text,
        ~F.text.startswith("/"),
        allowed,
    )
    router.message.register(wrong_item_content, WishlistStates.waiting_for_item, allowed)
    router.message.register(cancel_without_input, Command("cancel"), allowed)
    router.callback_query.register(
        process_wishlist_callback,
        WishlistCallback.filter(),
        allowed,
    )
    router.callback_query.register(malformed_callback, F.data.startswith("wish:"), allowed)
    return router
