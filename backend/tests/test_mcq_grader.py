from app.grading.mcq_grader import grade_mcq_responses
from app.models.answer_key import McqAnswer
from app.models.submission import McqResponse


def _key() -> list[McqAnswer]:
    return [
        McqAnswer(question_id="q1", question_text="Capital of France?", correct_option="B", points=2.0),
        McqAnswer(question_id="q2", question_text="2 + 2?", correct_option="C", points=1.0),
    ]


def test_correct_answer_earns_full_points():
    grades = grade_mcq_responses([McqResponse(question_id="q1", selected_option="B")], _key())
    assert len(grades) == 1
    assert grades[0].points_awarded == 2.0
    assert grades[0].points_possible == 2.0
    assert grades[0].graded_by == "mcq"
    assert grades[0].feedback == "Correct"
    # MCQ grades never carry a rubric breakdown.
    assert grades[0].criteria == []


def test_incorrect_answer_earns_zero():
    grades = grade_mcq_responses([McqResponse(question_id="q1", selected_option="A")], _key())
    assert grades[0].points_awarded == 0.0
    assert grades[0].points_possible == 2.0
    assert "expected B" in grades[0].feedback


def test_option_match_is_case_and_whitespace_insensitive():
    grades = grade_mcq_responses([McqResponse(question_id="q2", selected_option=" c ")], _key())
    assert grades[0].points_awarded == 1.0


def test_response_for_unknown_question_is_dropped():
    grades = grade_mcq_responses(
        [McqResponse(question_id="does-not-exist", selected_option="A")], _key()
    )
    assert grades == []
