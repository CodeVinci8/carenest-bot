from aiogram import Router
from aiogram.types import Message,FSInputFile
from aiogram.filters import Command
from keyboards import get_main_keyboard

from quiz_data import QUESTIONS
from handlers.quiz import get_quiz_keyboard
from config import ALLOWED_IDS
from filters.allowed_users import AllowedUserFilter


router = Router()


@router.message(Command('start'), AllowedUserFilter())
async def start_handler(message: Message):

    await message.answer(
        "Привет! Я CareBot, всё работает.\n"
        "Нажми /quiz, чтобы начать квиз!)",
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

