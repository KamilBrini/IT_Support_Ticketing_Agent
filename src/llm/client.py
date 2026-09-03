"""Provider-agnostic LLM client (Constitution v2.0.0 Principle IX).

Concrete provider (NVIDIA NIM / Gemini / OpenAI) is selected via the
LLM_PROVIDER environment variable — nothing outside this module knows or
cares which one is active. NVIDIA NIM and OpenAI both speak the OpenAI
chat-completions wire format, so both are served by the same `openai`
SDK client pointed at a different `base_url`; Gemini is a placeholder in
_PROVIDER_CONFIG until Checkpoint 2 adds its adapter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI


@dataclass(frozen=True)
class _ProviderConfig:
    api_key_env: str
    model_env: str
    base_url_env: str | None = None
    default_base_url: str | None = None
    # Passed as `extra_body` on every chat completion call. NVIDIA NIM's
    # Nemotron reasoning models otherwise dump their full chain-of-thought
    # into `content` (and can exhaust max_tokens before ever writing the
    # actual answer) unless explicitly told not to "think" — this is NIM's
    # documented off-switch, distinct from the older "detailed thinking off"
    # system-prompt convention used by some other Nemotron deployments.
    extra_body: dict | None = None


_PROVIDER_CONFIG: dict[str, _ProviderConfig] = {
    "nvidia_nim": _ProviderConfig(
        api_key_env="NVIDIA_NIM_API_KEY",
        model_env="NVIDIA_NIM_MODEL",
        base_url_env="NVIDIA_NIM_BASE_URL",
        default_base_url="https://integrate.api.nvidia.com/v1",
        extra_body={"chat_template_kwargs": {"thinking": False}},
    ),
    "openai": _ProviderConfig(
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
    ),
}


class LLMConfigError(RuntimeError):
    """Raised when LLM_PROVIDER or its required settings are missing/invalid."""


class LLMClient:
    """Thin wrapper: one `generate()` call, provider details stay internal."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "")).strip().lower()
        if self.provider not in _PROVIDER_CONFIG:
            supported = ", ".join(sorted(_PROVIDER_CONFIG))
            raise LLMConfigError(
                f"LLM_PROVIDER='{self.provider}' is not configured. Set it to one of: {supported}"
            )

        cfg = _PROVIDER_CONFIG[self.provider]
        api_key = os.getenv(cfg.api_key_env, "").strip()
        if not api_key:
            raise LLMConfigError(f"{cfg.api_key_env} is not set")

        self.model = os.getenv(cfg.model_env, "").strip()
        if not self.model:
            raise LLMConfigError(f"{cfg.model_env} is not set")

        base_url = os.getenv(cfg.base_url_env, cfg.default_base_url) if cfg.base_url_env else None
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._extra_body = cfg.extra_body

    def generate(self, *, system: str, user: str, max_tokens: int = 700, temperature: float = 0.2) -> str:
        """Return the model's plain-text reply for a single system+user turn."""
        kwargs: dict = {}
        if self._extra_body:
            kwargs["extra_body"] = self._extra_body

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return (completion.choices[0].message.content or "").strip()


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Build the configured client once per process.

    Deliberately lazy: importing this module (or src.agent.graph, which
    imports it) must not fail just because LLM_PROVIDER/keys aren't set —
    e.g. running pytest or the RAG-only path shouldn't require an LLM key.
    The error only surfaces when generation is actually attempted.
    """
    return LLMClient()
