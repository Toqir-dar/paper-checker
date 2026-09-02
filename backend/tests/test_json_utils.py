import pytest

from app.grading.json_utils import safe_parse_json


def test_safe_parse_json_direct():
    payload = '{"title": "Exam 1", "score": 95}'
    result = safe_parse_json(payload)
    assert result == {"title": "Exam 1", "score": 95}


def test_safe_parse_json_markdown_block():
    payload = """Here is the result:
```json
{
  "roll_number": "12345",
  "mcq_responses": [{"question_id": "q1", "selected_option": "A"}]
}
```
Hope this helps!"""
    result = safe_parse_json(payload)
    assert result["roll_number"] == "12345"
    assert len(result["mcq_responses"]) == 1


def test_safe_parse_json_markdown_generic_block():
    payload = """```
{
  "status": "ok"
}
```"""
    result = safe_parse_json(payload)
    assert result == {"status": "ok"}


def test_safe_parse_json_with_outermost_json():
    payload = """The model generated the following json object:
{"criteria": [{"index": 0, "awarded_points": 2.0}], "feedback": "Good"}
End of explanation."""
    result = safe_parse_json(payload)
    assert result["feedback"] == "Good"
    assert result["criteria"][0]["awarded_points"] == 2.0


def test_safe_parse_json_empty_raises():
    with pytest.raises(ValueError, match="Empty response"):
        safe_parse_json("")


def test_safe_parse_json_malformed_raises():
    with pytest.raises(ValueError, match="Could not parse valid JSON"):
        safe_parse_json("This is purely plain text with no json at all.")

