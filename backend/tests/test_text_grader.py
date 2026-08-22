import pytest

from app.grading import text_grader
from app.grading.llm_client import AllProvidersExhaustedError
from app.grading.text_grader import grade_text_responses
from app.models.answer_key import RubricCriterion, TextAnswer
from app.models.submission import TextResponse


class _FakeClient:
    """Stands in for LLMClient — returns a queued payload or raises."""

    def __init__(self, payload: dict | None = None, *, raises: Exception | None = None, model: str = "test-model"):
        self._payload = payload
        self._raises = raises
        self._model = model
        self.calls = 0

    async def generate_json(self, prompt: str, *, system_instruction: str | None = None):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._payload, self._model


def _answer() -> TextAnswer:
    return TextAnswer(
        question_id="q1",
        question_text="Explain photosynthesis.",
        reference_answer="Plants convert light, water and CO2 into glucose and oxygen.",
        rubric=[
            RubricCriterion(description="Mentions light energy", max_points=2.0),
            RubricCriterion(description="Mentions CO2 and water inputs", max_points=2.0),
            RubricCriterion(description="Mentions glucose/oxygen outputs", max_points=1.0),
        ],
    )


def _responses() -> list[TextResponse]:
    return [TextResponse(question_id="q1", answer_text="Plants make food from sunlight.")]


@pytest.fixture(autouse=True)
def _fixed_similarity(monkeypatch):
    """Pin the embedding similarity so tests are fast, offline, and deterministic."""

    async def _fake(_a: str, _b: str) -> float:
        return 0.5

    monkeypatch.setattr(text_grader, "cosine_similarity", _fake)


async def test_rubric_scoring_sums_per_criterion_awards():
    client = _FakeClient(
        {
            "criteria": [
                {"index": 0, "awarded_points": 2.0},
                {"index": 1, "awarded_points": 1.0},
                {"index": 2, "awarded_points": 1.0},
            ],
            "feedback": "Good, but light-dependent detail was thin.",
        }
    )
    grades, warnings = await grade_text_responses(_responses(), [_answer()], client)

    assert len(grades) == 1
    grade = grades[0]
    assert grade.points_possible == 5.0
    assert grade.points_awarded == 4.0
    assert grade.graded_by == "rubric:test-model"
    assert [c.awarded_points for c in grade.criteria] == [2.0, 1.0, 1.0]
    assert grade.feedback == "Good, but light-dependent detail was thin."
    # 4/5 = 0.8 vs similarity 0.5 → gap 0.3, under threshold, so no divergence warning.
    assert warnings == []


async def test_awards_are_clamped_and_missing_index_defaults_to_zero():
    client = _FakeClient(
        {
            "criteria": [
                {"index": 0, "awarded_points": 99.0},  # over max → clamp to 2.0
                {"index": 1, "awarded_points": -5.0},  # below 0 → clamp to 0.0
                # index 2 omitted → 0.0
            ]
        }
    )
    grades, _ = await grade_text_responses(_responses(), [_answer()], client)

    grade = grades[0]
    assert [c.awarded_points for c in grade.criteria] == [2.0, 0.0, 0.0]
    assert grade.points_awarded == 2.0


async def test_all_providers_exhausted_falls_back_to_similarity():
    client = _FakeClient(raises=AllProvidersExhaustedError())
    grades, warnings = await grade_text_responses(_responses(), [_answer()], client)

    grade = grades[0]
    assert grade.graded_by == "cosine_similarity"
    assert grade.points_awarded == 2.5  # similarity 0.5 × 5.0 possible
    assert grade.criteria == []
    assert any("unavailable" in w for w in warnings)


async def test_unusable_payload_falls_back_for_that_response_only():
    client = _FakeClient({"feedback": "no criteria field here"})
    grades, warnings = await grade_text_responses(_responses(), [_answer()], client)

    assert grades[0].graded_by == "cosine_similarity"
    assert grades[0].points_awarded == 2.5
    # The LLM answered (badly) but is up, so no "unavailable" warning is raised.
    assert not any("unavailable" in w for w in warnings)


async def test_large_rubric_vs_similarity_disagreement_emits_warning(monkeypatch):
    async def _low(_a: str, _b: str) -> float:
        return 0.1

    monkeypatch.setattr(text_grader, "cosine_similarity", _low)
    client = _FakeClient(
        {
            "criteria": [
                {"index": 0, "awarded_points": 2.0},
                {"index": 1, "awarded_points": 2.0},
                {"index": 2, "awarded_points": 1.0},
            ]
        }
    )
    grades, warnings = await grade_text_responses(_responses(), [_answer()], client)

    assert grades[0].points_awarded == 5.0  # rubric says 100%
    assert any("diverge" in w for w in warnings)  # vs similarity 10% → gap 0.9 > 0.5


async def test_exhaustion_warning_is_emitted_only_once_across_responses():
    answers = [
        _answer(),
        TextAnswer(
            question_id="q2",
            reference_answer="ref",
            rubric=[RubricCriterion(description="c", max_points=1.0)],
        ),
    ]
    responses = [
        TextResponse(question_id="q1", answer_text="a"),
        TextResponse(question_id="q2", answer_text="b"),
    ]
    client = _FakeClient(raises=AllProvidersExhaustedError())
    grades, warnings = await grade_text_responses(responses, answers, client)

    assert len(grades) == 2
    assert all(g.graded_by == "cosine_similarity" for g in grades)
    assert sum("unavailable" in w for w in warnings) == 1
    # Once exhausted, we stop calling the LLM for the remaining responses.
    assert client.calls == 1
