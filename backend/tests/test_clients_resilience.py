from unittest.mock import MagicMock, patch
import pytest

from app.grading.llm_client import LLMClient, _GroqChain, _GeminiChain, AllProvidersExhaustedError
from app.grading.vision_client import VisionClient, AllVisionProvidersExhaustedError


@pytest.mark.asyncio
async def test_groq_chain_retry_on_429(monkeypatch):
    monkeypatch.setattr("app.grading.llm_client._BASE_RETRY_DELAY", 0.01)
    monkeypatch.setattr("app.grading.llm_client._MAX_RETRIES_PER_MODEL", 2)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"result": "success"}'
    mock_response.choices = [mock_choice]

    import groq
    # First call throws 429, second call succeeds
    error_429 = groq.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    mock_client.chat.completions.create.side_effect = [error_429, mock_response]

    chain = _GroqChain(api_keys=["fake-key"], models=["model-1"])
    chain._clients = [mock_client]

    result = await chain.call("prompt", None)
    assert result is not None
    parsed, model = result
    assert parsed == {"result": "success"}
    assert model == "groq:model-1"
    assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_groq_chain_fallback_on_invalid_key_401(monkeypatch):
    import groq
    mock_client1 = MagicMock()
    error_401 = groq.AuthenticationError(
        message="Invalid API Key",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )
    mock_client1.chat.completions.create.side_effect = error_401

    mock_client2 = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"key": 2}'
    mock_response.choices = [mock_choice]
    mock_client2.chat.completions.create.return_value = mock_response

    chain = _GroqChain(api_keys=["bad-key", "good-key"], models=["model-1"])
    chain._clients = [mock_client1, mock_client2]

    result = await chain.call("prompt", None)
    assert result is not None
    parsed, model = result
    assert parsed == {"key": 2}


@pytest.mark.asyncio
async def test_vision_client_retry_on_429(monkeypatch):
    monkeypatch.setattr("app.grading.vision_client._BASE_RETRY_DELAY", 0.01)
    monkeypatch.setattr("app.grading.vision_client._MAX_RETRIES_PER_MODEL", 2)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '```json\n{"roll_number": "100"}\n```'

    from google.genai import errors as genai_errors
    error_429 = genai_errors.APIError(code=429, response=MagicMock())
    mock_client.models.generate_content.side_effect = [error_429, mock_response]

    client = VisionClient.__new__(VisionClient)
    client._clients = [mock_client]
    client._models = ["vision-model-1"]
    import asyncio
    client._semaphore = asyncio.Semaphore(1)

    parsed, model = await client.generate_json_from_images(
        [b"fake-image"], mime_type="image/png", prompt="extract"
    )
    assert parsed == {"roll_number": "100"}
    assert model == "gemini:vision-model-1"
    assert mock_client.models.generate_content.call_count == 2

