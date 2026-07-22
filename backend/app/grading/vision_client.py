import asyncio
import base64
import json
import logging
from typing import Any

import openai

from app.config import settings

logger = logging.getLogger(__name__)

# Free OpenRouter vision models are more likely than paid frontier models to
# reject an unsupported request param (e.g. response_format) outright — a 400
# from one model in the chain should mean "try the next model", not "give up".
_RETRYABLE_STATUS_CODES = {400, 404, 429, 500, 503}

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class AllVisionProvidersExhaustedError(Exception):
    """Every configured vision API key/model combination failed or was rate-limited."""


class VisionClient:
    """Vision-capable client with fallback across OpenRouter API keys and models.

    As of setup time, this is a single-provider chain (OpenRouter) because neither
    Groq (no vision-capable model on the account) nor Gemini (0 free-tier quota
    granted) could do image/PDF input. Structured the same way as LLMClient so a
    second vision provider chain can be added later without touching callers.
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
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,
                )
            except openai.APIStatusError as exc:
                if exc.status_code in _RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "OpenRouter model %s unavailable (status %s), falling back: %s",
                        model,
                        exc.status_code,
                        exc,
                    )
                    last_error = exc
                    continue
                raise

            text = (response.choices[0].message.content or "").strip()
            try:
                return json.loads(text), f"openrouter:{model}"
            except json.JSONDecodeError as exc:
                logger.warning("OpenRouter model %s returned non-JSON output, falling back: %s", model, exc)
                last_error = exc
                continue

        raise AllVisionProvidersExhaustedError(
            "All configured vision provider/key/model combinations failed"
        ) from last_error


_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    global _client
    if _client is None:
        _client = VisionClient()
    return _client
