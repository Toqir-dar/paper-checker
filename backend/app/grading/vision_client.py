import asyncio
import base64
import logging
import random
from typing import Any

import openai

from app.config import settings
from app.grading.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

# HTTP statuses that mean "this key/model combo is unusable right now or transiently unavailable"
_RETRYABLE_STATUS_CODES = {400, 404, 408, 429, 500, 502, 503, 504}
_NON_FATAL_KEY_STATUS_CODES = {401, 403}

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_MAX_RETRIES_PER_MODEL = 2
_BASE_RETRY_DELAY = 2.0


class AllVisionProvidersExhaustedError(Exception):
    """Every configured vision API key/model combination failed or was rate-limited."""


class VisionClient:
    """Vision-capable client with fallback across OpenRouter API keys and models.

    Includes retry with exponential backoff for rate limits (429), safe JSON extraction,
    graceful handling of invalid keys/models, and concurrency control.
    """

    def __init__(self) -> None:
        api_keys = settings.openrouter_api_keys
        models = settings.openrouter_vision_models
        if not api_keys:
            raise ValueError("No OpenRouter API keys configured — set OPENROUTER_API_KEYS in .env")
        if not models:
            raise ValueError("No OpenRouter vision models configured — set OPENROUTER_VISION_MODELS in .env")
        self._clients = [
            openai.OpenAI(api_key=key, base_url=_OPENROUTER_BASE_URL) for key in api_keys
        ]
        self._models = models
        # Global semaphore to throttle concurrent vision requests and avoid free-tier burst limits
        self._semaphore = asyncio.Semaphore(1)

    def _combinations(self) -> list[tuple[openai.OpenAI, str]]:
        return [(client, model) for client in self._clients for model in self._models]

    async def generate_json_from_images(
        self,
        images: list[bytes],
        *,
        mime_type: str,
        prompt: str,
        system_instruction: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Send one or more page images plus a text prompt, parse the response as
        JSON, falling back across (api_key, model) combinations on failure.

        Returns (parsed_json, "openrouter:model" that served the request).
        """
        async with self._semaphore:
            return await self._generate_json_from_images_internal(
                images,
                mime_type=mime_type,
                prompt=prompt,
                system_instruction=system_instruction,
            )

    async def _generate_json_from_images_internal(
        self,
        images: list[bytes],
        *,
        mime_type: str,
        prompt: str,
        system_instruction: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_bytes in images:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": content})

        last_error: Exception | None = None

        for client, model in self._combinations():
            for attempt in range(_MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0,
                    )
                except openai.APIStatusError as exc:
                    status_code = exc.status_code
                    if status_code in _NON_FATAL_KEY_STATUS_CODES:
                        logger.warning(
                            "OpenRouter key/model %s permission issue (status %s), skipping to next: %s",
                            model,
                            status_code,
                            exc,
                        )
                        last_error = exc
                        break  # skip this combination immediately
                    if status_code in _RETRYABLE_STATUS_CODES:
                        last_error = exc
                        if status_code == 429 and attempt < _MAX_RETRIES_PER_MODEL:
                            delay = _BASE_RETRY_DELAY * (2**attempt) + random.uniform(0.1, 0.5)
                            logger.warning(
                                "OpenRouter model %s rate-limited (429), retrying in %.1fs (attempt %d/%d)...",
                                model,
                                delay,
                                attempt + 1,
                                _MAX_RETRIES_PER_MODEL,
                            )
                            await asyncio.sleep(delay)
                            continue
                        logger.warning(
                            "OpenRouter model %s unavailable (status %s), falling back: %s",
                            model,
                            status_code,
                            exc,
                        )
                        break
                    last_error = exc
                    logger.warning("OpenRouter model %s non-retryable API status error: %s", model, exc)
                    break
                except (openai.APIConnectionError, openai.APITimeoutError) as exc:
                    last_error = exc
                    if attempt < _MAX_RETRIES_PER_MODEL:
                        delay = _BASE_RETRY_DELAY * (2**attempt) + random.uniform(0.1, 0.5)
                        logger.warning(
                            "OpenRouter model %s connection/timeout error, retrying in %.1fs: %s",
                            model,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning("OpenRouter model %s connection failed after retries: %s", model, exc)
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning("OpenRouter model %s unexpected error, falling back: %s", model, exc)
                    break

                if not response.choices:
                    error = getattr(response, "error", None)
                    logger.warning(
                        "OpenRouter model %s returned no choices (error=%s), falling back",
                        model,
                        error,
                    )
                    last_error = RuntimeError(f"OpenRouter model {model} returned no choices: {error}")
                    break

                text = (response.choices[0].message.content or "").strip()
                try:
                    parsed = safe_parse_json(text)
                    return parsed, f"openrouter:{model}"
                except ValueError as exc:
                    logger.warning(
                        "OpenRouter model %s returned unparseable JSON output, falling back: %s",
                        model,
                        exc,
                    )
                    last_error = exc
                    break

        raise AllVisionProvidersExhaustedError(
            "All configured vision provider/key/model combinations failed or were rate-limited"
        ) from last_error


_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    global _client
    if _client is None:
        _client = VisionClient()
    return _client
