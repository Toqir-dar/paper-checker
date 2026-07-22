import asyncio
import json
import logging
from typing import Any, Protocol

import groq as groq_sdk
from google import genai
from google.genai import errors as genai_errors

from app.config import settings

logger = logging.getLogger(__name__)

# HTTP statuses that mean "this key/model combo is unusable right now" — worth
# falling back on, as opposed to a genuine request error we should surface.
# 404 is included because both Groq and Gemini retire/rename free models often
# enough that a stale model ID in GROQ_MODELS/GEMINI_MODELS shouldn't take down
# the whole chain — just skip it and try the next configured model.
_RETRYABLE_STATUS_CODES = {404, 429, 500, 503}


class AllProvidersExhaustedError(Exception):
    """Every configured provider/key/model combination failed or was rate-limited."""


class _ProviderChain(Protocol):
    async def call(self, prompt: str, system_instruction: str | None) -> tuple[dict[str, Any], str] | None:
        """Try every (key, model) combination for this provider.

        Returns (parsed_json, "provider:model") on success, or None if every
        combination in this provider was exhausted (caller moves to the next
        provider). Raises only for genuinely non-retryable errors.
        """


class _GroqChain:
    """Falls back across every configured Groq API key/model combination."""

    def __init__(self, api_keys: list[str], models: list[str]) -> None:
        self._clients = [groq_sdk.Groq(api_key=key) for key in api_keys]
        self._models = models

    def _combinations(self) -> list[tuple[groq_sdk.Groq, str]]:
        return [(client, model) for client in self._clients for model in self._models]

    async def call(self, prompt: str, system_instruction: str | None) -> tuple[dict[str, Any], str] | None:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        for client, model in self._combinations():
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,
                )
            except groq_sdk.APIStatusError as exc:
                if exc.status_code in _RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "Groq model %s unavailable (status %s), falling back: %s", model, exc.status_code, exc
                    )
                    continue
                raise

            text = (response.choices[0].message.content or "").strip()
            try:
                return json.loads(text), f"groq:{model}"
            except json.JSONDecodeError as exc:
                logger.warning("Groq model %s returned non-JSON output, falling back: %s", model, exc)
                continue

        return None


class _GeminiChain:
    """Falls back across every configured Gemini API key/model combination."""

    def __init__(self, api_keys: list[str], models: list[str]) -> None:
        self._clients = [genai.Client(api_key=key) for key in api_keys]
        self._models = models

    def _combinations(self) -> list[tuple[genai.Client, str]]:
        return [(client, model) for client in self._clients for model in self._models]

    async def call(self, prompt: str, system_instruction: str | None) -> tuple[dict[str, Any], str] | None:
        for client, model in self._combinations():
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config={
                        "system_instruction": system_instruction,
                        "response_mime_type": "application/json",
                        "temperature": 0,
                    },
                )
            except genai_errors.APIError as exc:
                status_code = getattr(exc, "code", None)
                if status_code in _RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "Gemini model %s unavailable (status %s), falling back: %s", model, status_code, exc
                    )
                    continue
                raise

            text = (response.text or "").strip()
            try:
                return json.loads(text), f"gemini:{model}"
            except json.JSONDecodeError as exc:
                logger.warning("Gemini model %s returned non-JSON output, falling back: %s", model, exc)
                continue

        return None


class LLMClient:
    """Multi-provider LLM client with automatic fallback.

    Tries Groq first — fast inference and a generous free tier — falling back
    across every configured Groq API key/model combination. Only once all of
    those are exhausted does it move to Gemini, again falling back across every
    configured key/model combination there. This lets two independent free
    tiers act as one higher-capacity pool instead of the grading pipeline
    failing when a single provider's quota is hit.
    """

    def __init__(self) -> None:
        self._chains: list[_ProviderChain] = []

        if settings.groq_api_keys and settings.groq_models:
            self._chains.append(_GroqChain(settings.groq_api_keys, settings.groq_models))
        if settings.gemini_api_keys and settings.gemini_models:
            self._chains.append(_GeminiChain(settings.gemini_api_keys, settings.gemini_models))

        if not self._chains:
            raise ValueError(
                "No LLM providers configured — set GROQ_API_KEYS/GROQ_MODELS and/or "
                "GEMINI_API_KEYS/GEMINI_MODELS in .env"
            )

    async def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Send a prompt and parse the response as JSON, falling back across
        providers (Groq, then Gemini) and every configured key/model within each.

        Returns (parsed_json, "provider:model" that served the request).
        """
        for chain in self._chains:
            result = await chain.call(prompt, system_instruction)
            if result is not None:
                return result

        raise AllProvidersExhaustedError("All configured provider/key/model combinations failed")


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
