from dataclasses import replace
from pathlib import Path

import pytest

from carenest.config import QuizQuestion, inspect_configuration
from carenest.handlers.quiz import (
    QuizCallback,
    QuizStates,
    format_quiz_question,
    is_current_quiz_callback,
    send_quiz_question,
    validate_quiz_answer,
)


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.photo_calls = 0

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def answer_photo(self, **kwargs) -> None:
        self.photo_calls += 1


def test_quiz_progress_text() -> None:
    question = QuizQuestion(question="Тест?", options=("Да", "Нет"), correct=0)

    assert format_quiz_question(question, 1, 5) == "Вопрос 2 из 5\n\nТест?"


@pytest.mark.asyncio
async def test_text_only_quiz_question_does_not_try_to_send_photo(
    tmp_path: Path,
    clean_environment: None,
) -> None:
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    assert result.config is not None
    question = QuizQuestion(question="Текстовый вопрос?", options=("Да", "Нет"), correct=0)
    config = replace(result.config, questions=(question,))
    message = FakeMessage()

    sent = await send_quiz_question(message, config, 0, "session1")

    assert sent is True
    assert message.photo_calls == 0
    assert message.answers == ["Вопрос 1 из 1\n\nТекстовый вопрос?"]


@pytest.mark.parametrize(
    ("question_index", "answer_index", "expected"),
    [
        (-1, 0, "Этот вопрос больше недоступен."),
        (2, 0, "Этот вопрос больше недоступен."),
        (0, -1, "Такого варианта ответа нет."),
        (0, 4, "Такого варианта ответа нет."),
    ],
)
def test_invalid_quiz_callback_indexes(
    question_index: int,
    answer_index: int,
    expected: str,
) -> None:
    questions = (QuizQuestion(question="Тест?", options=("Да", "Нет"), correct=0),)

    assert validate_quiz_answer(questions, question_index, answer_index) == expected


def test_quiz_session_is_part_of_callback_data() -> None:
    first = QuizCallback(question=0, answer=0, session="old").pack()
    restarted = QuizCallback(question=0, answer=0, session="new").pack()

    assert first != restarted
    assert first.startswith("quiz:")


def test_restarted_quiz_rejects_old_session() -> None:
    old_callback = QuizCallback(question=0, answer=0, session="old")
    new_callback = QuizCallback(question=0, answer=0, session="new")
    current_state = {"quiz_session": "new", "quiz_index": 0}

    assert not is_current_quiz_callback(
        QuizStates.in_progress.state,
        current_state,
        old_callback,
    )
    assert is_current_quiz_callback(
        QuizStates.in_progress.state,
        current_state,
        new_callback,
    )
