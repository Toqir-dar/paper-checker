from app.grading.llm_client import get_llm_client
from app.grading.mcq_grader import grade_mcq_responses
from app.grading.text_grader import grade_text_responses
from app.models.answer_key import AnswerKey
from app.models.grade_result import GradeResult
from app.models.submission import Submission


async def grade_submission(submission: Submission, answer_key: AnswerKey) -> GradeResult:
    mcq_grades = grade_mcq_responses(submission.mcq_responses, answer_key.mcq_answers)

    text_grades = []
    if submission.text_responses:
        client = get_llm_client()
        text_grades = await grade_text_responses(
            submission.text_responses, answer_key.text_answers, client
        )

    question_grades = [*mcq_grades, *text_grades]
    return GradeResult(
        submission_id=submission.id,
        answer_key_id=answer_key.id,
        question_grades=question_grades,
        total_points_awarded=round(sum(g.points_awarded for g in question_grades), 2),
        total_points_possible=round(sum(g.points_possible for g in question_grades), 2),
    )
