from app.grading.llm_client import LLMClient
from app.grading.similarity import cosine_similarity
from app.models.answer_key import TextAnswer
from app.models.grade_result import QuestionGrade
from app.models.submission import TextResponse

_FEEDBACK_SYSTEM_INSTRUCTION = (
    "You are giving feedback on a student's short-answer response. The numeric "
    "score has already been computed separately (via semantic similarity to the "
    "reference answer) — do not invent, restate, or imply a different score. Your "
    "only job is one concise sentence of feedback on what the student got right "
    "and/or what they missed, using the rubric as a guide to what should be present."
)


def _build_feedback_prompt(reference_answer: str, student_answer: str, rubric: list) -> str:
    rubric_lines = "\n".join(f"- {c.description} ({c.max_points} pts)" for c in rubric)
    return (
        f"Reference answer:\n{reference_answer}\n\n"
        f"Rubric (what a complete answer should cover):\n{rubric_lines}\n\n"
        f"Student answer:\n{student_answer}\n\n"
        'Respond as JSON only: {"feedback": "..."}'
    )


async def grade_text_responses(
    responses: list[TextResponse],
    answer_key: list[TextAnswer],
    client: LLMClient,
) -> list[QuestionGrade]:
    key_by_question = {answer.question_id: answer for answer in answer_key}
    grades: list[QuestionGrade] = []

    for response in responses:
        answer = key_by_question.get(response.question_id)
        if answer is None:
            continue

        points_possible = round(sum(c.max_points for c in answer.rubric), 2)

        similarity = await cosine_similarity(answer.reference_answer, response.answer_text)
        points_awarded = round(similarity * points_possible, 2)

        prompt = _build_feedback_prompt(answer.reference_answer, response.answer_text, answer.rubric)
        feedback_result, model = await client.generate_json(
            prompt, system_instruction=_FEEDBACK_SYSTEM_INSTRUCTION
        )
        feedback = str(feedback_result.get("feedback", "")).strip()

        grades.append(
            QuestionGrade(
                question_id=response.question_id,
                question_text=answer.question_text,
                detected_label=response.detected_label,
                points_awarded=points_awarded,
                points_possible=points_possible,
                feedback=feedback,
                graded_by=f"cosine_similarity+{model}",
            )
        )

    return grades
