from types import SimpleNamespace

import pytest

from carenest.filters import AllowedUserFilter


@pytest.mark.asyncio
async def test_unauthorized_user_is_rejected() -> None:
    access_filter = AllowedUserFilter(frozenset({10}))
    event = SimpleNamespace(from_user=SimpleNamespace(id=20))

    assert await access_filter(event) is False


@pytest.mark.asyncio
async def test_authorized_user_is_allowed() -> None:
    access_filter = AllowedUserFilter(frozenset({10}))
    event = SimpleNamespace(from_user=SimpleNamespace(id=10))

    assert await access_filter(event) is True
