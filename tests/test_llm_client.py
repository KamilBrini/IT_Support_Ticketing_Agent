"""Tests for the provider-agnostic LLM client (src/llm/client.py).

No test here makes a real network call - that's covered by live
verification against each provider's actual endpoint instead. These check
the configuration/validation logic only.
"""

from __future__ import annotations

import pytest

from src.llm.client import LLMClient, LLMConfigError


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    with pytest.raises(LLMConfigError, match="not configured"):
        LLMClient()


def test_nvidia_nim_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "nvidia_nim")
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "some-model")
    with pytest.raises(LLMConfigError, match="NVIDIA_NIM_API_KEY"):
        LLMClient()


def test_nvidia_nim_requires_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "nvidia_nim")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "fake-key-for-test")
    monkeypatch.delenv("NVIDIA_NIM_MODEL", raising=False)
    with pytest.raises(LLMConfigError, match="NVIDIA_NIM_MODEL"):
        LLMClient()


def test_opencode_zen_does_not_require_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """opencode.ai/zen is a free, keyless router - the client must build
    successfully with no OPENCODE_ZEN_API_KEY set at all."""
    monkeypatch.setenv("LLM_PROVIDER", "opencode_zen")
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENCODE_ZEN_MODEL", "big-pickle")
    client = LLMClient()
    assert client.provider == "opencode_zen"
    assert client.model == "big-pickle"


def test_opencode_zen_still_requires_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "opencode_zen")
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_ZEN_MODEL", raising=False)
    with pytest.raises(LLMConfigError, match="OPENCODE_ZEN_MODEL"):
        LLMClient()


def test_client_has_a_bounded_timeout_shorter_than_the_frontend_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow/hung provider call must fail before the frontend's own 60s
    request timeout gives up - otherwise the user sees a false "could not
    connect to the backend" error while the backend is still waiting on an
    LLM call with no bound (the SDK default is 600s), and the try/except
    fallback in generate_grounded_answer never triggers because nothing
    ever raises."""
    monkeypatch.setenv("LLM_PROVIDER", "nvidia_nim")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "some-model")
    client = LLMClient()
    assert client._client.timeout == 45.0
    assert client._client.timeout < 60
