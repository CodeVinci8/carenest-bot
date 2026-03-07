from aiogram import Router
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

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


@router.callback_query(QuizCallback.filter())
async def process_quiz_answer(
    callback_query: CallbackQuery,
    callback_data: QuizCallback
):
    question_index = callback_data.question_index
    answer_index = callback_data.answer_index

    correct_index = QUESTIONS[question_index]["correct"]

    if answer_index != correct_index:
        await callback_query.answer(
            "Неправильный ответ 💔 Попробуй ещё раз",
            show_alert=True
        )
        return
    await callback_query.answer("Правильно! ❤️")

    next_index = question_index + 1

    await callback_query.message.delete()

    if next_index < len(QUESTIONS):
        next_question = QUESTIONS[next_index]
        photo = FSInputFile(f"photos/{next_question['photo']}")

        await callback_query.message.answer_photo(
                photo=photo,
                caption=next_question["question"],
                reply_markup=get_quiz_keyboard(next_index)
        )
    else:
        heart_gif = FSInputFile("photos/heart.gif")

        await callback_query.message.answer_animation(
            animation=heart_gif,
            caption=(
                "УРА - квиз пройден! ❤️\n\n"
                "Ты ответила правильно на все вопросы.\n"
                "Твой подарок уже ждёт тебя 🎁"
            )
        )

        await callback_query.message.answer(
            "Спасибо за прохождение квиза! 💌\n"
            "Напиши мне, чтобы забрать свой подарок."
        )