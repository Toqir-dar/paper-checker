from app.grading.llm_client import AllProvidersExhaustedError, LLMClient
from app.grading.similarity import cosine_similarity
from app.models.answer_key import RubricCriterion, TextAnswer
from app.models.grade_result import CriterionGrade, QuestionGrade
from app.models.submission import TextResponse

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
    reference_answer: str, student_answer: str, rubric: list[RubricCriterion]
) -> str:
    rubric_lines = "\n".join(
        f"{i}. {c.description} (max {c.max_points} pts)" for i, c in enumerate(rubric)
    )
    return (
        f"Reference answer:\n{reference_answer}\n\n"
        f"Rubric — score each criterion by its index:\n{rubric_lines}\n\n"
        f"Student answer:\n{student_answer}\n\n"
        "For every criterion above, award points between 0 and its max. "
        "Respond as JSON only, no prose:\n"
        '{"criteria": [{"index": 0, "awarded_points": <number>}, ...], '
        '"feedback": "<one concise sentence on what was right and what was missing>"}'
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
    llm_available = True

    for response in responses:
        answer = key_by_question.get(response.question_id)
        if answer is None:
            continue

        points_possible = round(sum(c.max_points for c in answer.rubric), 2)
        # Local, cheap, always available — used for the fallback score and the cross-check.
        similarity = await cosine_similarity(answer.reference_answer, response.answer_text)

        criteria: list[CriterionGrade] = []
        feedback = ""
        graded_by = ""
        points_awarded: float | None = None

        if llm_available and answer.rubric:
            prompt = _build_rubric_prompt(answer.reference_answer, response.answer_text, answer.rubric)
            try:
                parsed, model = await client.generate_json(
                    prompt, system_instruction=_RUBRIC_SYSTEM_INSTRUCTION
                )
            except AllProvidersExhaustedError:
                # Every provider/key/model is exhausted. Stop trying for the rest of this
                # paper and note it once, rather than hammering dead providers per answer.
                llm_available = False
                warnings.append(
                    "LLM rubric grader was unavailable — written answers were scored by "
                    "semantic similarity only. Review these scores carefully."
                )
            else:
                scored = _score_from_criteria(answer.rubric, parsed)
                if scored is not None:
                    criteria, points_awarded = scored
                    feedback = str(parsed.get("feedback", "")).strip()
                    graded_by = f"rubric:{model}"
                    if points_possible > 0:
                        warning = _disagreement_warning(
                            response.question_id, points_awarded / points_possible, similarity
                        )
                        if warning:
                            warnings.append(warning)

        if points_awarded is None:
            # Fallback: LLM exhausted, no rubric on this question, or an unusable payload.
            points_awarded = round(similarity * points_possible, 2)
            graded_by = "cosine_similarity"
            feedback = _FALLBACK_FEEDBACK
            criteria = []

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
