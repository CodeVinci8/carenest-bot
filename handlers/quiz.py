from aiogram import Router
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from filters.allowed_users import AllowedUserFilter
from quiz_data import QUESTIONS

router = Router()


class QuizCallback(CallbackData, prefix="quiz"):
    question_index: int
    answer_index: int


def get_quiz_keyboard(question_index: int):
    builder = InlineKeyboardBuilder()

    options = QUESTIONS[question_index]["options"]

    for answer_index, option_text in enumerate(options):
        builder.button(
            text=option_text,
            callback_data=QuizCallback(
                question_index=question_index,
                answer_index=answer_index
            )
        )

    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(QuizCallback.filter(), AllowedUserFilter())
async def process_quiz_answer(
    callback_query: CallbackQuery,
    callback_data: QuizCallback
):
    question_index = callback_data.question_index
    answer_index = callback_data.answer_index

    correct_index = QUESTIONS[question_index]["correct"]

    if answer_index != correct_index:
        await callback_query.answer(
            "неправильно 💔 попробуй ещё раз",
            show_alert=True
        )
        return

    await callback_query.answer("правильно ❤️")

    next_index = question_index + 1

    if next_index < len(QUESTIONS):
        next_question = QUESTIONS[next_index]
        photo = FSInputFile(f"photos/{next_question['photo']}")

        try:
            await callback_query.message.delete()
        except TelegramBadRequest:
            pass

        try:
            await callback_query.message.answer_photo(
                photo=photo,
                caption=next_question["question"],
                reply_markup=get_quiz_keyboard(next_index)
            )
        except TelegramNetworkError:
            await callback_query.message.answer(
                "сеть немного шалит 💔 попробуй нажать ещё раз"
            )
    else:
        try:
            await callback_query.message.delete()
        except TelegramBadRequest:
            pass

        await callback_query.message.answer(
            "УРА - квиз пройден! ❤️\n\n"
            "Ты ответила правильно на все вопросы.\n"
            "твой настоящий подарок уже ждёт.\n\n"
            "напиши Никите кодовое слово:\n"
            "эрнест 🌸\n\n"
            "и он всё пришлёт !"
        )