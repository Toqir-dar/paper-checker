import base64
import logging

from app.grading.vision_client import VisionClient
from app.models.answer_key import DiagramAnswer
from app.models.grade_result import CriterionGrade, QuestionGrade
from app.models.submission import Submission

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are a strict but fair grader evaluating a student's hand-drawn diagram "
    "against an explicit rubric. Judge only visible evidence in the image. Do not "
    "award points for artistic quality unless the rubric explicitly requires it."
)


def _prompt(answer: DiagramAnswer) -> str:
    rubric = "\n".join(
        f"{i}. {criterion.description} (max {criterion.max_points} pts)"
        for i, criterion in enumerate(answer.rubric)
    )
    return (
        f"Question: {answer.question_text}\n"
        f"Reference diagram description: {answer.reference_description}\n"
        f"Rubric:\n{rubric}\n\n"
        "Score every criterion independently from 0 to its maximum. If a label or "
        "feature is unclear, do not guess and mention the uncertainty in feedback.\n"
        'Respond as JSON only: {"criteria": [{"index": 0, "awarded_points": 0}], '
        '"feedback": "one concise sentence"}'
    )


def _parse_criteria(answer: DiagramAnswer, parsed: dict) -> tuple[list[CriterionGrade], float] | None:
    raw = parsed.get("criteria")
    if not isinstance(raw, list):
        return None
    by_index = {
        item.get("index"): item.get("awarded_points")
        for item in raw
        if isinstance(item, dict) and isinstance(item.get("index"), int)
        and isinstance(item.get("awarded_points"), (int, float))
    }
    criteria = [
        CriterionGrade(
            description=criterion.description,
            max_points=criterion.max_points,
            awarded_points=round(max(0.0, min(criterion.max_points, float(by_index.get(i, 0)))), 2),
        )
        for i, criterion in enumerate(answer.rubric)
    ]
    return criteria, round(sum(item.awarded_points for item in criteria), 2)


async def grade_diagram_responses(
    submission: Submission,
    answer_key: list[DiagramAnswer],
    client: VisionClient,
) -> tuple[list[QuestionGrade], list[str]]:
    images = [base64.b64decode(image) for image in submission.source_images]
    answers = {answer.question_id: answer for answer in answer_key}
    grades: list[QuestionGrade] = []
    warnings: list[str] = []

    for response in submission.diagram_responses:
        answer = answers.get(response.question_id)
        if answer is None:
            continue
        if response.page_number is None or not 1 <= response.page_number <= len(images):
            warnings.append(f"{response.question_id}: diagram image was not found — verify manually.")
            grades.append(QuestionGrade(
                question_id=answer.question_id,
                question_text=answer.question_text,
                detected_label=response.detected_label,
                points_awarded=0,
                points_possible=sum(c.max_points for c in answer.rubric),
                feedback="Diagram image was not available for grading.",
                graded_by="diagram_unavailable",
            ))
            continue

        try:
            parsed, model = await client.generate_json_from_images(
                [images[response.page_number - 1]],
                mime_type=submission.source_image_mime_type,
                prompt=_prompt(answer),
                system_instruction=_SYSTEM_INSTRUCTION,
            )
        except Exception as exc:
            logger.warning("Diagram grading failed for %s: %s", response.question_id, exc)
            warnings.append(f"{response.question_id}: diagram grader unavailable — verify manually.")
            continue

        scored = _parse_criteria(answer, parsed)
        if scored is None:
            warnings.append(f"{response.question_id}: diagram grader returned invalid scoring data.")
            continue
        criteria, points = scored
        grades.append(QuestionGrade(
            question_id=answer.question_id,
            question_text=answer.question_text,
            detected_label=response.detected_label,
            points_awarded=points,
            points_possible=sum(c.max_points for c in answer.rubric),
            feedback=str(parsed.get("feedback", "")).strip(),
            graded_by=f"diagram:{model}",
            criteria=criteria,
        ))

    return grades, warnings