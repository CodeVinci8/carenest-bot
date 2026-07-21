from __future__ import annotations

import logging
import secrets

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from carenest.config import AppConfig, QuizQuestion
from carenest.filters import AllowedUserFilter

logger = logging.getLogger(__name__)


class QuizStates(StatesGroup):
    in_progress = State()


class QuizCallback(CallbackData, prefix="quiz"):
    question: int
    answer: int
    session: str


def format_quiz_question(question: QuizQuestion, question_index: int, total: int) -> str:
    return f"Вопрос {question_index + 1} из {total}\n\n{question.question}"


def validate_quiz_answer(
    questions: tuple[QuizQuestion, ...],
    question_index: int,
    answer_index: int,
) -> str | None:
    if not 0 <= question_index < len(questions):
        return "Этот вопрос больше недоступен."
    if not 0 <= answer_index < len(questions[question_index].options):
        return "Такого варианта ответа нет."
    return None


def is_current_quiz_callback(
    state_name: str | None,
    state_data: dict,
    callback_data: QuizCallback,
) -> bool:
    return (
        state_name == QuizStates.in_progress.state
        and state_data.get("quiz_session") == callback_data.session
        and state_data.get("quiz_index") == callback_data.question
    )


def get_quiz_keyboard(question: QuizQuestion, question_index: int, session: str):
    builder = InlineKeyboardBuilder()
    for answer_index, option_text in enumerate(question.options):
        builder.button(
            text=option_text,
            callback_data=QuizCallback(
                question=question_index,
                answer=answer_index,
                session=session,
            ),
        )
    builder.adjust(1)
    return builder.as_markup()


async def send_quiz_question(
    message: Message,
    config: AppConfig,
    question_index: int,
    session: str,
) -> bool:
    question = config.questions[question_index]
    keyboard = get_quiz_keyboard(question, question_index, session)
    text = format_quiz_question(question, question_index, len(config.questions))
    photo_path = config.paths.quiz_media / question.photo if question.photo else None
    if photo_path is not None and photo_path.is_file():
        try:
            await message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=text,
                reply_markup=keyboard,
            )
            return True
        except (OSError, TelegramAPIError) as error:
            logger.warning("Не удалось отправить фотографию вопроса: %s", error)
    try:
        await message.answer(text, reply_markup=keyboard)
    except TelegramAPIError as error:
        logger.error("Не удалось отправить текст вопроса: %s", error)
        return False
    return True


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
    async def quiz_handler(message: Message, state: FSMContext) -> None:
        if not config.questions:
            await state.clear()
            await message.answer("В квизе пока нет вопросов. Добавьте их в конфигурацию.")
            return
        session = secrets.token_hex(4)
        await state.set_state(QuizStates.in_progress)
        await state.set_data({"quiz_session": session, "quiz_index": 0})
        await send_quiz_question(message, config, 0, session)

    @router.callback_query(QuizCallback.filter(), allowed)
    async def process_quiz_answer(
        callback: CallbackQuery,
        callback_data: QuizCallback,
        state: FSMContext,
    ) -> None:
        question_index = callback_data.question
        answer_index = callback_data.answer
        validation_error = validate_quiz_answer(config.questions, question_index, answer_index)
        if validation_error:
            await _answer_callback(callback, validation_error, show_alert=True)
            return

        state_data = await state.get_data()
        if not is_current_quiz_callback(
            await state.get_state(),
            state_data,
            callback_data,
        ):
            await _answer_callback(
                callback,
                "Эта кнопка устарела. Запустите квиз командой /quiz.",
                show_alert=True,
            )
            return

        question = config.questions[question_index]
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
            await state.update_data(quiz_index=next_index)
            await send_quiz_question(
                callback.message,
                config,
                next_index,
                callback_data.session,
            )
        else:
            await state.clear()
            try:
                await callback.message.answer(config.rendered_final_message())
            except TelegramAPIError as error:
                logger.error("Не удалось отправить результат квиза: %s", error)

    @router.callback_query(F.data.startswith("quiz:"), allowed)
    async def malformed_quiz_callback(callback: CallbackQuery) -> None:
        await _answer_callback(
            callback,
            "Некорректная или устаревшая кнопка квиза.",
            show_alert=True,
        )

    return router
