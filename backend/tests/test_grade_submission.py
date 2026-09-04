import pytest

from app import grading
from app.grading import text_grader
from app.models.answer_key import AnswerKey, DiagramAnswer, McqAnswer, RubricCriterion, TextAnswer
from app.models.submission import DiagramResponse, McqResponse, Submission, TextResponse


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


async def test_grade_submission_grades_diagram_from_the_recorded_page(monkeypatch):
    class _FakeVisionClient:
        async def generate_json_from_images(self, images, *, mime_type, prompt, system_instruction=None):
            assert images == [b"page-2"]
            assert mime_type == "image/png"
            return {
                "criteria": [
                    {"index": 0, "awarded_points": 5},
                    {"index": 1, "awarded_points": 1},
                ],
                "feedback": "The structure is correct but one label is missing.",
            }, "vision-test"

    monkeypatch.setattr(grading, "get_vision_client", lambda: _FakeVisionClient())
    answer_key = AnswerKey(
        id="k1",
        title="Diagram quiz",
        diagram_answers=[
            DiagramAnswer(
                question_id="q1",
                question_text="Draw a cell.",
                reference_description="A labeled cell",
                rubric=[
                    RubricCriterion(description="Correct structure", max_points=3),
                    RubricCriterion(description="Correct labels", max_points=2),
                ],
            )
        ],
    )
    submission = Submission(
        id="s1",
        answer_key_id="k1",
        student_name="Ada",
        diagram_responses=[DiagramResponse(question_id="q1", page_number=2)],
        source_images=["cGFnZS0x", "cGFnZS0y"],
    )

    result = await grading.grade_submission(submission, answer_key)

    assert result.total_points_possible == 5.0
    assert result.total_points_awarded == 4.0
    assert result.question_grades[0].graded_by == "diagram:vision-test"
    assert result.question_grades[0].criteria[0].awarded_points == 3.0
    assert result.question_grades[0].criteria[1].awarded_points == 1.0
