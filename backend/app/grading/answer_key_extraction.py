import logging

from app.grading.document_images import file_to_page_images
from app.grading.vision_client import VisionClient
from app.models.answer_key import AnswerKey

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "You are an assistant that reads scanned exam answer keys or textbook pages and "
    "converts them into structured grading data. Read every page of the provided "
    "document carefully before answering."
)

_EXTRACTION_PROMPT = """Extract a structured answer key from this document.

For every multiple-choice question you find, record its question_text (the
question as written, verbatim or near-verbatim) and its correct option.
For every free-text / short-answer question you find, record its question_text,
the reference answer given (or, if the document doesn't spell one out
explicitly, write the best reference answer based on the document's content),
and break it down into 2-4 rubric criteria that a grader could check
independently, each worth some number of points (criteria points should sum to
a reasonable total per question, e.g. 4-10 points).

question_text matters beyond record-keeping: it is later shown to a separate
model matching a student's answer sheet to these questions, so it needs enough
of the actual question wording to distinguish this question from the others —
not just a label like "Question 9".

Assign question IDs sequentially as q1, q2, q3... in the order questions appear,
across both MCQ and free-text questions combined.

Respond as JSON only, in exactly this shape:
{
  "title": "a short descriptive title for this document",
  "mcq_answers": [
    {"question_id": "q1", "question_text": "...", "correct_option": "B", "points": 1}
  ],
  "text_answers": [
    {
      "question_id": "q2",
      "question_text": "...",
      "reference_answer": "...",
      "rubric": [
        {"description": "...", "max_points": 3},
        {"description": "...", "max_points": 3}
      ]
    }
  ]
}

If there are no MCQ questions, return an empty mcq_answers list. If there are no
free-text questions, return an empty text_answers list. Do not include any text
outside the JSON object."""


async def extract_answer_key_from_file(
    file_bytes: bytes,
    content_type: str,
    vision_client: VisionClient,
) -> AnswerKey:
    """Parse an uploaded answer-key PDF/image into a structured AnswerKey."""
    images, mime_type = file_to_page_images(file_bytes, content_type)

    result, model = await vision_client.generate_json_from_images(
        images,
        mime_type=mime_type,
        prompt=_EXTRACTION_PROMPT,
        system_instruction=_SYSTEM_INSTRUCTION,
    )
    logger.info("Answer key extracted by %s", model)

    return AnswerKey.model_validate(result)
