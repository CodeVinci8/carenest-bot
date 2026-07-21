from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from carenest.config import AppConfig, QuizQuestion
from carenest.filters import AllowedUserFilter

logger = logging.getLogger(__name__)


class QuizCallback(CallbackData, prefix="quiz"):
    question: int
    answer: int


def get_quiz_keyboard(question: QuizQuestion, question_index: int):
    builder = InlineKeyboardBuilder()
    for answer_index, option_text in enumerate(question.options):
        builder.button(
            text=option_text,
            callback_data=QuizCallback(question=question_index, answer=answer_index),
        )
    builder.adjust(1)
    return builder.as_markup()


async def send_quiz_question(message: Message, config: AppConfig, question_index: int) -> None:
    question = config.questions[question_index]
    keyboard = get_quiz_keyboard(question, question_index)
    photo_path = config.paths.quiz_media / question.photo if question.photo else None
    if photo_path is not None and photo_path.is_file():
        try:
            await message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=question.question,
                reply_markup=keyboard,
            )
            return
        except (OSError, TelegramAPIError) as error:
            logger.warning("Не удалось отправить фотографию вопроса: %s", error)
    try:
        await message.answer(question.question, reply_markup=keyboard)
    except TelegramAPIError as error:
        logger.error("Не удалось отправить текст вопроса: %s", error)


async def _answer_callback(
    callback: CallbackQuery,
    text: str,
    *,
    show_alert: bool = False,
) -> bool:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramAPIError as error:
        logger.warning("Не удалось подтвердить нажатие кнопки квиза: %s", error)
        return False
    return True


async def _delete_quiz_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        logger.info("Предыдущее сообщение квиза уже недоступно.")
    except TelegramAPIError as error:
        logger.warning("Не удалось удалить предыдущее сообщение квиза: %s", error)


def build_quiz_router(config: AppConfig) -> Router:
    router = Router(name="quiz")
    allowed = AllowedUserFilter(config.allowed_ids)

    @router.message(Command("quiz"), allowed)
    async def quiz_handler(message: Message) -> None:
        if not config.questions:
            await message.answer("В квизе пока нет вопросов. Добавьте их в конфигурацию.")
            return
        await send_quiz_question(message, config, 0)

    @router.callback_query(QuizCallback.filter(), allowed)
    async def process_quiz_answer(
        callback: CallbackQuery,
        callback_data: QuizCallback,
    ) -> None:
        question_index = callback_data.question
        answer_index = callback_data.answer
        if not 0 <= question_index < len(config.questions):
            await _answer_callback(callback, "Этот вопрос больше недоступен.", show_alert=True)
            return

        question = config.questions[question_index]
        if not 0 <= answer_index < len(question.options):
            await _answer_callback(callback, "Такого варианта ответа нет.", show_alert=True)
            return
        if answer_index != question.correct:
            await _answer_callback(callback, "Пока неверно. Попробуйте ещё раз.", show_alert=True)
            return

        if not await _answer_callback(callback, "Верно! ❤️"):
            return
        if not isinstance(callback.message, Message):
            return

        await _delete_quiz_message(callback.message)
        next_index = question_index + 1
        if next_index < len(config.questions):
            await send_quiz_question(callback.message, config, next_index)
        else:
            await callback.message.answer(config.rendered_final_message())

    return router
