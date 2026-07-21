from datetime import date

import pytest

from carenest.handlers.relationship import day_word, relationship_days


@pytest.mark.parametrize(
    ("days", "expected"),
    [(1, "день"), (2, "дня"), (5, "дней"), (11, "дней"), (21, "день"), (24, "дня")],
)
def test_day_word_forms(days: int, expected: str) -> None:
    assert day_word(days) == expected


def test_relationship_days_uses_given_date() -> None:
    assert relationship_days(date(2024, 1, 1), date(2024, 1, 11)) == 10
