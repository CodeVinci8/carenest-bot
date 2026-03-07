from aiogram import Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from handlers.keyboards import get_main_keyboard
from handlers.quiz import get_quiz_keyboard
from quiz_data import QUESTIONS
from filters.allowed_users import AllowedUserFilter

router = Router()


@router.message(Command("start"), AllowedUserFilter())
async def start_handler(message: Message):
    await message.answer(
        "с 8 марта, любимая! 🌷\n"
        "я написал этого бота специально для тебя,\n"
        "чтобы частичка моей заботы всегда была в твоем телефоне.\n"
        "он умеет поднимать настроение, хранить твои желания и считать наши дни.\n"
        "а чтобы получить подарок — пройди мой праздничный квиз! жми -> /quiz 🎁",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("quiz"), AllowedUserFilter())
async def quiz_handler(message: Message):
    question_index = 0
    question = QUESTIONS[question_index]

    photo = FSInputFile(f"photos/{question['photo']}")

    await message.answer_photo(
        photo=photo,
        caption=question["question"],
        reply_markup=get_quiz_keyboard(question_index)
    )