import asyncio
import logging
import random
from typing import Any, Protocol

import groq as groq_sdk
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.core.api_budget import request_budget
from app.grading.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

# HTTP statuses that mean "this key/model combo is unusable right now or transiently unavailable"
_RETRYABLE_STATUS_CODES = {400, 404, 408, 429, 500, 502, 503, 504}
_NON_FATAL_KEY_STATUS_CODES = {401, 403}

_MAX_RETRIES_PER_MODEL = 2
_BASE_RETRY_DELAY = 2.0


class AllProvidersExhaustedError(Exception):
    """Every configured provider/key/model combination failed or was rate-limited."""


class _ProviderChain(Protocol):
    async def call(self, prompt: str, system_instruction: str | None) -> tuple[dict[str, Any], str] | None:
        """Try every (key, model) combination for this provider.

        Returns (parsed_json, "provider:model") on success, or None if every
        combination in this provider was exhausted (caller moves to the next
        provider).
        """


class _GroqChain:
    """Falls back across every configured Groq API key/model combination with retry on 429."""

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
            for attempt in range(_MAX_RETRIES_PER_MODEL + 1):
                try:
                    await request_budget.acquire()
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0,
                    )
                except groq_sdk.APIStatusError as exc:
                    status_code = exc.status_code
                    if status_code in _NON_FATAL_KEY_STATUS_CODES:
                        logger.warning(
                            "Groq key/model %s permission issue (status %s), skipping to next: %s",
                            model,
                            status_code,
                            exc,
                        )
                        break
                    if status_code in _RETRYABLE_STATUS_CODES:
                        if status_code == 429 and attempt < _MAX_RETRIES_PER_MODEL:
                            delay = _BASE_RETRY_DELAY * (2**attempt) + random.uniform(0.1, 0.5)
                            logger.warning(
                                "Groq model %s rate-limited (429), retrying in %.1fs (attempt %d/%d)...",
                                model,
                                delay,
                                attempt + 1,
                                _MAX_RETRIES_PER_MODEL,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.warning(
                            "Groq model %s unavailable (status %s), falling back: %s",
                            model,
                            status_code,
                            exc,
                        )
                        break
                    logger.warning("Groq model %s non-retryable API status error: %s", model, exc)
                    break
                except (groq_sdk.APIConnectionError, groq_sdk.APITimeoutError) as exc:
                    if attempt < _MAX_RETRIES_PER_MODEL:
                        delay = _BASE_RETRY_DELAY * (2**attempt) + random.uniform(0.1, 0.5)
                        logger.warning(
                            "Groq model %s connection error, retrying in %.1fs: %s",
                            model,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning("Groq model %s connection failed after retries: %s", model, exc)
                    break
                except Exception as exc:
                    logger.warning("Groq model %s unexpected error, falling back: %s", model, exc)
                    break

                text = (response.choices[0].message.content or "").strip()
                try:
                    parsed = safe_parse_json(text)
                    return parsed, f"groq:{model}"
                except ValueError as exc:
                    logger.warning("Groq model %s returned unparseable JSON output, falling back: %s", model, exc)
                    break

        return None


class _GeminiChain:
    """Falls back across every configured Gemini API key/model combination with retry on 429."""

    def __init__(self, api_keys: list[str], models: list[str]) -> None:
        self._clients = [genai.Client(api_key=key) for key in api_keys]
        self._models = models

    def _combinations(self) -> list[tuple[genai.Client, str]]:
        return [(client, model) for client in self._clients for model in self._models]

    async def call(self, prompt: str, system_instruction: str | None) -> tuple[dict[str, Any], str] | None:
        for client, model in self._combinations():
            for attempt in range(_MAX_RETRIES_PER_MODEL + 1):
                try:
                    await request_budget.acquire()
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
                    if status_code in _NON_FATAL_KEY_STATUS_CODES:
                        logger.warning(
                            "Gemini key/model %s permission issue (status %s), skipping to next: %s",
                            model,
                            status_code,
                            exc,
                        )
                        break
                    if status_code in _RETRYABLE_STATUS_CODES:
                        if status_code == 429 and attempt < _MAX_RETRIES_PER_MODEL:
                            delay = _BASE_RETRY_DELAY * (2**attempt) + random.uniform(0.1, 0.5)
                            logger.warning(
                                "Gemini model %s rate-limited (429), retrying in %.1fs (attempt %d/%d)...",
                                model,
                                delay,
                                attempt + 1,
                                _MAX_RETRIES_PER_MODEL,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.warning(
                            "Gemini model %s unavailable (status %s), falling back: %s",
                            model,
                            status_code,
                            exc,
                        )
                        break
                    logger.warning("Gemini model %s API error: %s", model, exc)
                    break
                except Exception as exc:
                    logger.warning("Gemini model %s unexpected error, falling back: %s", model, exc)
                    break

                text = (response.text or "").strip()
                try:
                    parsed = safe_parse_json(text)
                    return parsed, f"gemini:{model}"
                except ValueError as exc:
                    logger.warning("Gemini model %s returned unparseable JSON output, falling back: %s", model, exc)
                    break

        return None


class LLMClient:
    """Multi-provider LLM client with automatic fallback and rate limit retries.

    Tries Groq first — fast inference and a generous free tier — falling back
    across every configured Groq API key/model combination. Only once all of
    those are exhausted does it move to Gemini, again falling back across every
    configured key/model combination there.
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

        self._semaphore = asyncio.Semaphore(2)

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
        async with self._semaphore:
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
