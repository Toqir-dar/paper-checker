import asyncio
import logging
import random
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.core.api_budget import request_budget
from app.grading.json_utils import safe_parse_json

logger = logging.getLogger(__name__)

# HTTP statuses that mean "this key/model combo is unusable right now or transiently unavailable"
_RETRYABLE_STATUS_CODES = {400, 404, 408, 429, 500, 502, 503, 504}
_NON_FATAL_KEY_STATUS_CODES = {401, 403}

_MAX_RETRIES_PER_MODEL = 2
_BASE_RETRY_DELAY = 2.0


class AllVisionProvidersExhaustedError(Exception):
    """Every configured vision API key/model combination failed or was rate-limited."""


class VisionClient:
    """Vision-capable Gemini client with fallback across keys and models.

    Includes retry with exponential backoff for rate limits (429), safe JSON extraction,
    graceful handling of invalid keys/models, and concurrency control.
    """

    def __init__(self) -> None:
        api_keys = settings.gemini_api_keys
        models = settings.gemini_models
        if not api_keys:
            raise ValueError("No Gemini API keys configured — set GEMINI_API_KEYS in .env")
        if not models:
            raise ValueError("No Gemini models configured — set GEMINI_MODELS in .env")
        self._clients = [genai.Client(api_key=key) for key in api_keys]
        self._models = models
        # Global semaphore to throttle concurrent vision requests and avoid free-tier burst limits
        self._semaphore = asyncio.Semaphore(1)

    def _combinations(self) -> list[tuple[genai.Client, str]]:
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

        Returns (parsed_json, "gemini:model" that served the request).
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
        parts = [types.Part.from_text(text=prompt)]
        parts.extend(types.Part.from_bytes(data=image_bytes, mime_type=mime_type) for image_bytes in images)
        contents = [types.Content(role="user", parts=parts)]

        last_error: Exception | None = None

        for client, model in self._combinations():
            for attempt in range(_MAX_RETRIES_PER_MODEL + 1):
                try:
                    await request_budget.acquire()
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=0,
                        ),
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
                        last_error = exc
                        break  # skip this combination immediately
                    if status_code in _RETRYABLE_STATUS_CODES:
                        last_error = exc
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
                    last_error = exc
                    logger.warning("Gemini model %s non-retryable API status error: %s", model, exc)
                    break
                except Exception as exc:
                    last_error = exc
                    logger.warning("Gemini model %s unexpected error, falling back: %s", model, exc)
                    break

                text = (response.text or "").strip()
                try:
                    parsed = safe_parse_json(text)
                    return parsed, f"gemini:{model}"
                except ValueError as exc:
                    logger.warning(
                        "Gemini model %s returned unparseable JSON output, falling back: %s",
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
