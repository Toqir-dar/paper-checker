import logging

from app.grading.llm_client import LLMClient
from app.grading.similarity import cosine_similarity
from app.models.answer_key import RubricCriterion, TextAnswer
from app.models.grade_result import CriterionGrade, QuestionGrade
from app.models.submission import TextResponse

logger = logging.getLogger(__name__)

# When the LLM's rubric score and the local embedding similarity disagree by more
# than this (both as fractions of the total), flag the question for a human look.
# The two measure different things — embeddings reward paraphrase, the rubric rewards
# content — so some gap is normal; only a wide one is worth surfacing.
_DISAGREEMENT_THRESHOLD = 0.5

_RUBRIC_SYSTEM_INSTRUCTION = (
    "You are a strict but fair grader scoring a student's short-answer response "
    "against an explicit rubric. Award points criterion by criterion: for each "
    "criterion, decide how fully the student's answer satisfies it and award between "
    "0 and that criterion's max points. Judge only on what the student actually wrote "
    "against the reference answer — never award points for correct-sounding content "
    "that is not present, and give no credit for a criterion the answer does not "
    "address. Be consistent and deterministic."
)

_FALLBACK_FEEDBACK = (
    "Scored by semantic similarity to the reference answer (rubric grader unavailable)."
)


def _build_rubric_prompt(
    questions: list[tuple[TextAnswer, TextResponse]],
) -> str:
    question_blocks = []
    for answer, response in questions:
        rubric_lines = "\n".join(
            f"{i}. {criterion.description} (max {criterion.max_points} pts)"
            for i, criterion in enumerate(answer.rubric)
        )
        question_blocks.append(
            f"Question ID: {answer.question_id}\n"
            f"Reference answer:\n{answer.reference_answer}\n\n"
            f"Rubric — score each criterion by its index:\n{rubric_lines}\n\n"
            f"Student answer:\n{response.answer_text}"
        )

    return (
        "Grade every question below independently. For every rubric criterion, award "
        "between 0 and its maximum points. Judge only what the student wrote.\n\n"
        + "\n\n---\n\n".join(question_blocks)
        + "\n\nRespond as JSON only, no prose:\n"
        '{"questions": [{"question_id": "q1", "criteria": '
        '[{"index": 0, "awarded_points": <number>}], '
        '"feedback": "<one concise sentence>"}]}'
    )


def _coerce_number(value: object) -> float | None:
    # bool is an int subclass — reject it so `true`/`false` isn't read as 1/0 points.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _score_from_criteria(
    rubric: list[RubricCriterion], parsed: dict
) -> tuple[list[CriterionGrade], float] | None:
    """Turn the model's JSON into clamped per-criterion grades.

    Returns (criteria, total_awarded), or None if the payload is unusable (missing or
    empty "criteria") so the caller can fall back to similarity for this response.
    Each criterion is clamped to [0, max_points], so the total can never exceed the
    rubric's possible points.
    """
    raw = parsed.get("criteria")
    if not isinstance(raw, list) or not raw:
        return None

    awarded_by_index: dict[int, float] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        points = _coerce_number(item.get("awarded_points"))
        if isinstance(index, int) and not isinstance(index, bool) and points is not None:
            awarded_by_index[index] = points

    criteria: list[CriterionGrade] = []
    for i, criterion in enumerate(rubric):
        awarded = awarded_by_index.get(i, 0.0)
        awarded = max(0.0, min(criterion.max_points, awarded))
        criteria.append(
            CriterionGrade(
                description=criterion.description,
                max_points=criterion.max_points,
                awarded_points=round(awarded, 2),
            )
        )

    total = round(sum(c.awarded_points for c in criteria), 2)
    return criteria, total


def _disagreement_warning(question_id: str, rubric_fraction: float, similarity: float) -> str | None:
    if abs(rubric_fraction - similarity) <= _DISAGREEMENT_THRESHOLD:
        return None
    return (
        f"{question_id}: rubric score ({round(rubric_fraction * 100)}%) and semantic "
        f"similarity ({round(similarity * 100)}%) diverge — verify this one."
    )


async def grade_text_responses(
    responses: list[TextResponse],
    answer_key: list[TextAnswer],
    client: LLMClient,
) -> tuple[list[QuestionGrade], list[str]]:
    """Grade short-answer responses against their rubric.

    Each rubric criterion is scored by the LLM (0..max_points) and the awarded points
    are the clamped sum — so a fluent-but-wrong answer no longer earns marks it didn't
    support. Local embedding similarity is kept for two jobs: (1) a fallback scorer when
    every LLM provider is exhausted, so a provider outage doesn't fail the whole paper,
    and (2) a cross-check that flags large rubric-vs-similarity disagreements for review.

    Returns (grades, warnings).
    """
    key_by_question = {answer.question_id: answer for answer in answer_key}
    grades: list[QuestionGrade] = []
    warnings: list[str] = []
    answers_by_question = {answer.question_id: answer for answer in answer_key}
    valid_responses = [
        (answers_by_question[response.question_id], response)
        for response in responses
        if response.question_id in answers_by_question
    ]
    similarities = {
        response.question_id: await cosine_similarity(answer.reference_answer, response.answer_text)
        for answer, response in valid_responses
    }
    rubric_questions = [(answer, response) for answer, response in valid_responses if answer.rubric]
    rubric_scores: dict[str, tuple[list[CriterionGrade], float, str, str]] = {}
    llm_warning: str | None = None

    if rubric_questions:
        prompt = _build_rubric_prompt(rubric_questions)
        try:
            parsed, model = await client.generate_json(
                prompt, system_instruction=_RUBRIC_SYSTEM_INSTRUCTION
            )
        except Exception as exc:
            logger.warning("LLM rubric grader failed, falling back to similarity: %s", exc)
            llm_warning = (
                "LLM rubric grader was unavailable — written answers were scored by "
                "semantic similarity only. Review these scores carefully."
            )
        else:
            raw_questions = parsed.get("questions")
            if not isinstance(raw_questions, list) and len(rubric_questions) == 1:
                raw_questions = [{"question_id": rubric_questions[0][0].question_id, **parsed}]

            answers_by_id = {answer.question_id: answer for answer, _ in rubric_questions}
            if isinstance(raw_questions, list):
                for item in raw_questions:
                    if not isinstance(item, dict):
                        continue
                    question_id = item.get("question_id")
                    answer = answers_by_id.get(question_id)
                    if answer is None:
                        continue
                    scored = _score_from_criteria(answer.rubric, item)
                    if scored is not None:
                        criteria, points_awarded = scored
                        rubric_scores[question_id] = (
                            criteria,
                            points_awarded,
                            str(item.get("feedback", "")).strip(),
                            model,
                        )

        if llm_warning:
            warnings.append(llm_warning)

    for response in responses:
        answer = key_by_question.get(response.question_id)
        if answer is None:
            continue

        points_possible = round(sum(c.max_points for c in answer.rubric), 2)
        similarity = similarities[response.question_id]

        criteria: list[CriterionGrade] = []
        rubric_score = rubric_scores.get(response.question_id)
        if rubric_score is not None:
            criteria, points_awarded, feedback, model = rubric_score
            graded_by = f"rubric:{model}"
            if points_possible > 0:
                warning = _disagreement_warning(
                    response.question_id, points_awarded / points_possible, similarity
                )
                if warning:
                    warnings.append(warning)
        else:
            points_awarded = round(similarity * points_possible, 2)
            graded_by = "cosine_similarity"
            feedback = _FALLBACK_FEEDBACK

        grades.append(
            QuestionGrade(
                question_id=response.question_id,
                question_text=answer.question_text,
                detected_label=response.detected_label,
                points_awarded=points_awarded,
                points_possible=points_possible,
                feedback=feedback,
                graded_by=graded_by,
                criteria=criteria,
            )
        )

    return grades, warnings
