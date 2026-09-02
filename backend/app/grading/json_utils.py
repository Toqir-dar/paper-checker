import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def safe_parse_json(text: str) -> dict[str, Any]:
    """Parse JSON from an LLM or vision model response text safely.

    Handles:
    - Direct JSON strings
    - JSON enclosed within markdown code fences (```json ... ``` or ``` ... ```)
    - Responses containing explanatory text before/after the JSON object
    - Common escaping or whitespace formatting quirks
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Empty response text received from model")

    # 1. Try direct json.loads
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"data": parsed}
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from markdown code block ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if code_block_match:
        block_content = code_block_match.group(1).strip()
        try:
            parsed = json.loads(block_content)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"data": parsed}
        except json.JSONDecodeError:
            pass

    # 3. Find outermost JSON object {...}
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. Find outermost JSON array [...]
    start_arr = cleaned.find("[")
    end_arr = cleaned.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        candidate_arr = cleaned[start_arr : end_arr + 1]
        try:
            parsed = json.loads(candidate_arr)
            if isinstance(parsed, list):
                return {"data": parsed}
        except json.JSONDecodeError:
            pass

    snippet = cleaned[:200] + ("..." if len(cleaned) > 200 else "")
    raise ValueError(f"Could not parse valid JSON from model output: {snippet}")

