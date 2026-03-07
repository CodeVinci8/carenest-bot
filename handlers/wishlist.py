from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from filters.allowed_users import AllowedUserFilter
from database import add_item, get_items

router = Router()


class WishlistStates(StatesGroup):
    waiting_for_item = State()


@router.message(F.text.lower() == "добавить хотелку 🎁", AllowedUserFilter())
async def add_wishlist_item_start(message: Message, state: FSMContext):
    await message.answer("что ты хочешь добавить в список?")
    await state.set_state(WishlistStates.waiting_for_item)


@router.message(WishlistStates.waiting_for_item, F.text, AllowedUserFilter())
async def save_wishlist_item(message: Message, state: FSMContext):
    item_name = message.text.strip()

    if not item_name:
        await message.answer("напиши что-нибудь текстом ✍️")
        return

    add_item(item_name)
    await message.answer("сохранено! ✨")
    await state.clear()


@router.message(WishlistStates.waiting_for_item, AllowedUserFilter())
async def wrong_wishlist_content(message: Message, state: FSMContext):
    await message.answer("эй, я жду текст, а не стикер! 😌")


@router.message(F.text.lower() == "мой wishlist 📝", AllowedUserFilter())
async def show_wishlist(message: Message):
    items = get_items()

    if not items:
        await message.answer("твой список пока пуст")
        return

    lines = []
    for index, (_, name) in enumerate(items, start=1):
        lines.append(f"{index}. {name}")

    text = "твой wishlist 📝\n\n" + "\n".join(lines)
    await message.answer(text)