import pytest

from app import grading
from app.grading import text_grader
from app.models.answer_key import AnswerKey, McqAnswer, RubricCriterion, TextAnswer
from app.models.submission import McqResponse, Submission, TextResponse


class _FakeClient:
    async def generate_json(self, prompt: str, *, system_instruction: str | None = None):
        return {"criteria": [{"index": 0, "awarded_points": 3.0}], "feedback": "solid"}, "test-model"


@pytest.fixture(autouse=True)
def _patched(monkeypatch):
    async def _sim(_a: str, _b: str) -> float:
        return 0.6

    monkeypatch.setattr(text_grader, "cosine_similarity", _sim)
    monkeypatch.setattr(grading, "get_llm_client", lambda: _FakeClient())


async def test_grade_submission_merges_mcq_and_text_totals_and_warnings():
    answer_key = AnswerKey(
        id="k1",
        title="Quiz",
        mcq_answers=[McqAnswer(question_id="q1", correct_option="A", points=1.0)],
        text_answers=[
            TextAnswer(
                question_id="q2",
                reference_answer="ref",
                rubric=[RubricCriterion(description="key idea", max_points=3.0)],
            )
        ],
    )
    submission = Submission(
        id="s1",
        answer_key_id="k1",
        student_name="Ada",
        mcq_responses=[McqResponse(question_id="q1", selected_option="A")],
        text_responses=[TextResponse(question_id="q2", answer_text="an answer")],
    )

    result = await grading.grade_submission(submission, answer_key)

    assert result.total_points_possible == 4.0  # 1 (mcq) + 3 (text)
    assert result.total_points_awarded == 4.0  # mcq correct (1) + text full marks (3)
    assert len(result.question_grades) == 2

    text_grade = next(g for g in result.question_grades if g.question_id == "q2")
    assert text_grade.graded_by == "rubric:test-model"
    assert len(text_grade.criteria) == 1
    assert text_grade.criteria[0].awarded_points == 3.0

    # 3/3 = 100% vs similarity 60% → gap 0.4, under threshold; labels line up → no warnings.
    assert result.warnings == []
