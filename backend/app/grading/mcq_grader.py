from app.models.answer_key import McqAnswer
from app.models.grade_result import QuestionGrade
from app.models.submission import McqResponse


def grade_mcq_responses(
    responses: list[McqResponse],
    answer_key: list[McqAnswer],
) -> list[QuestionGrade]:
    """Score multiple-choice responses by direct comparison — no LLM call needed."""
    key_by_question = {answer.question_id: answer for answer in answer_key}
    grades = []

    for response in responses:
        answer = key_by_question.get(response.question_id)
        if answer is None:
            continue
        is_correct = response.selected_option.strip().lower() == answer.correct_option.strip().lower()
        grades.append(
            QuestionGrade(
                question_id=response.question_id,
                points_awarded=answer.points if is_correct else 0.0,
                points_possible=answer.points,
                feedback="Correct" if is_correct else f"Incorrect — expected {answer.correct_option}",
                graded_by="mcq",
            )
        )

    return grades
