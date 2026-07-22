import logging
from typing import Any

from app.grading.document_images import file_to_page_images
from app.grading.vision_client import VisionClient
from app.models.answer_key import AnswerKey

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are an assistant that reads scanned student answer sheets — which may be "
    "handwritten — and transcribes the student's responses. Read every page of the "
    "provided document carefully before answering. For multiple-choice questions, "
    "identify which option the student marked, circled, checked, or otherwise selected."
)


def _build_prompt(answer_key: AnswerKey) -> str:
    mcq_ids = [a.question_id for a in answer_key.mcq_answers]
    text_ids = [a.question_id for a in answer_key.text_answers]

    return f"""This is a scanned student answer sheet for an exam with these questions:
- Multiple-choice question IDs: {mcq_ids}
- Free-text question IDs: {text_ids}

For each multiple-choice question ID, determine which option letter the student
selected (look for circled, checked, underlined, or otherwise marked options).
For each free-text question ID, transcribe the student's full written answer as
accurately as possible, including handwriting.

If a question's response is illegible or missing, use an empty string for that
question's answer rather than guessing.

Respond as JSON only, in exactly this shape:
{{
  "mcq_responses": [
    {{"question_id": "q1", "selected_option": "B"}}
  ],
  "text_responses": [
    {{"question_id": "q2", "answer_text": "..."}}
  ]
}}

Do not include any text outside the JSON object."""


async def extract_submission_responses(
    file_bytes: bytes,
    content_type: str,
    answer_key: AnswerKey,
    vision_client: VisionClient,
) -> dict[str, Any]:
    """Parse a scanned answer sheet into mcq_responses/text_responses keyed by
    the answer key's question IDs. Returns a plain dict (not a Submission) —
    the caller still needs to attach student_name and answer_key_id."""
    images, mime_type = file_to_page_images(file_bytes, content_type)

    result, model = await vision_client.generate_json_from_images(
        images,
        mime_type=mime_type,
        prompt=_build_prompt(answer_key),
        system_instruction=_SYSTEM_INSTRUCTION,
    )
    logger.info("Submission responses extracted by %s", model)

    return result
