import re

from app.grading.llm_client import get_llm_client
from app.grading.mcq_grader import grade_mcq_responses
from app.grading.text_grader import grade_text_responses
from app.models.answer_key import AnswerKey
from app.models.grade_result import GradeResult, QuestionGrade
from app.models.submission import Submission

_ID_NUMBER = re.compile(r"(\d+)")


def _question_number(question_id: str) -> int | None:
    match = _ID_NUMBER.search(question_id)
    return int(match.group(1)) if match else None


def _detect_numbering_warnings(question_grades: list[QuestionGrade], answer_key: AnswerKey) -> list[str]:
    """Flag cases where the extracted question numbering looks unreliable, so a
    teacher double-checks the score instead of trusting a confidently-labeled
    but possibly misrouted grade. Both checks are heuristics — false positives
    are expected and fine, this is a "verify" flag, not a hard failure."""
    warnings: list[str] = []

    for grade in question_grades:
        detected_number = _question_number(grade.detected_label) if grade.detected_label else None
        matched_number = _question_number(grade.question_id)
        if detected_number is not None and matched_number is not None and detected_number != matched_number:
            warnings.append(
                f"{grade.question_id}: page shows question number '{grade.detected_label}' but this "
                f"answer was matched to {grade.question_id} by content — verify before finalizing."
            )

    all_ids = [a.question_id for a in answer_key.mcq_answers] + [a.question_id for a in answer_key.text_answers]
    numbered_ids = sorted(
        (qid for qid in all_ids if _question_number(qid) is not None),
        key=lambda qid: _question_number(qid) or 0,
    )
    present_ids = {g.question_id for g in question_grades}
    present_numbers = [n for qid in numbered_ids if (qid in present_ids) and (n := _question_number(qid)) is not None]
    if present_numbers:
        max_present = max(present_numbers)
        missing_before_max = [
            qid
            for qid in numbered_ids
            if qid not in present_ids and (_question_number(qid) or 0) < max_present
        ]
        if missing_before_max:
            warnings.append(
                "Some question numbers in this submission don't match the answer key "
                f"(missing {', '.join(missing_before_max)} despite later questions being present) — "
                "verify before finalizing scores."
            )

    return warnings


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
        warnings=_detect_numbering_warnings(question_grades, answer_key),
    )
