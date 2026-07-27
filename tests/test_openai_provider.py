from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest

from carenest.compliments import (
    ComplimentProviderError,
    OpenAICompatibleComplimentProvider,
    _normalize_openai_base_url,
)


class _FakeCompletions:
    def __init__(self, *, result=None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._result


def _install_fake(provider: OpenAICompatibleComplimentProvider, fake: _FakeCompletions) -> None:
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))


def _make_provider() -> OpenAICompatibleComplimentProvider:
    return OpenAICompatibleComplimentProvider(
        api_key="test-key",
        base_url="https://aiprimetech.io",
        model="gpt-5.6-luna",
    )


def _completion(content: str | None):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("https://aiprimetech.io", "https://aiprimetech.io/v1"),
        ("https://aiprimetech.io/", "https://aiprimetech.io/v1"),
        ("https://aiprimetech.io/v1", "https://aiprimetech.io/v1"),
        ("https://aiprimetech.io/v1/", "https://aiprimetech.io/v1"),
    ],
)
def test_base_url_is_normalized_to_v1(configured: str, expected: str) -> None:
    assert _normalize_openai_base_url(configured) == expected


@pytest.mark.asyncio
async def test_successful_generation_parses_choice_content() -> None:
    provider = _make_provider()
    fake = _FakeCompletions(result=_completion("  Тёплый  комплимент.  "))
    _install_fake(provider, fake)

    text = await provider.generate(("Любит спокойный юмор.",))

    assert text == "Тёплый комплимент."
    # Exactly one request per generate() call.
    assert len(fake.calls) == 1
    # The model is a Codex-group model, never a Claude model.
    assert fake.calls[0]["model"] == "gpt-5.6-luna"


@pytest.mark.asyncio
async def test_allowed_profile_reaches_request_and_forbidden_does_not() -> None:
    provider = _make_provider()
    fake = _FakeCompletions(result=_completion("Комплимент."))
    _install_fake(provider, fake)

    # safe_context + the approved depersonalised profile are the only inputs.
    await provider.generate(
        ("Ценит внимательность.",),
        ("Любит настольные игры.", "Тёплый, спокойный тон."),
    )

    messages = fake.calls[0]["messages"]
    user_message = messages[-1]["content"]
    # Both the safe context and every approved profile trait reach the request.
    assert "Ценит внимательность." in user_message
    assert "Любит настольные игры." in user_message
    assert "Тёплый, спокойный тон." in user_message
    # Forbidden private data is never added by the provider: no name, ids, dates,
    # secrets, urls or media filenames.
    for forbidden in ("test-key", "@", "id=", "http", ".jpg", ".png", "2020-", "Настя"):
        assert forbidden not in user_message


@pytest.mark.asyncio
async def test_empty_context_uses_neutral_placeholder() -> None:
    provider = _make_provider()
    fake = _FakeCompletions(result=_completion("Комплимент."))
    _install_fake(provider, fake)

    await provider.generate(())

    assert "Без личных деталей." in fake.calls[0]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_empty_response_raises_empty_category() -> None:
    provider = _make_provider()
    _install_fake(provider, _FakeCompletions(result=_completion("   ")))

    with pytest.raises(ComplimentProviderError) as exc:
        await provider.generate(())
    assert exc.value.category == "empty"


@pytest.mark.asyncio
async def test_none_content_raises_empty_category() -> None:
    provider = _make_provider()
    _install_fake(provider, _FakeCompletions(result=_completion(None)))

    with pytest.raises(ComplimentProviderError) as exc:
        await provider.generate(())
    assert exc.value.category == "empty"


@pytest.mark.asyncio
async def test_malformed_response_raises_malformed_category() -> None:
    provider = _make_provider()
    _install_fake(provider, _FakeCompletions(result=SimpleNamespace(choices=[])))

    with pytest.raises(ComplimentProviderError) as exc:
        await provider.generate(())
    assert exc.value.category == "malformed"


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://aiprimetech.io/v1/chat/completions")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            openai.AuthenticationError(
                "bad", response=httpx.Response(401, request=_request()), body=None
            ),
            "authentication",
        ),
        (
            openai.RateLimitError(
                "rl", response=httpx.Response(429, request=_request()), body=None
            ),
            "rate_limit",
        ),
        (openai.APITimeoutError(_request()), "timeout"),
        (openai.APIConnectionError(message="conn", request=_request()), "provider"),
        (
            openai.APIStatusError(
                "srv", response=httpx.Response(500, request=_request()), body=None
            ),
            "provider",
        ),
        (openai.OpenAIError("generic"), "provider"),
    ],
)
async def test_provider_errors_map_to_categories(error: Exception, expected: str) -> None:
    provider = _make_provider()
    _install_fake(provider, _FakeCompletions(error=error))

    with pytest.raises(ComplimentProviderError) as exc:
        await provider.generate(("safe",))
    assert exc.value.category == expected
