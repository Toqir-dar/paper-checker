from pydantic import BaseModel, Field

# question_id is the extractor's best content-matched guess against the answer
# key; detected_label is whatever number/marker was literally written on the
# page next to the answer. They're kept separate so a mismatch between them
# (e.g. page says "10" but content matched q9) is visible instead of silently
# collapsed into one field.


class McqResponse(BaseModel):
    question_id: str
    selected_option: str
    detected_label: str = ""


class TextResponse(BaseModel):
    question_id: str
    answer_text: str
    detected_label: str = ""


class Submission(BaseModel):
    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    answer_key_id: str
    student_name: str
    # Read off the page by the same vision pass that transcribes the answers —
    # empty when the page has no roll number or it couldn't be made out.
    roll_number: str = ""
    # Set only for submissions created through the batch-upload flow; groups
    # them for the batch results view/CSV. None for one-off submissions.
    batch_id: str | None = None
    mcq_responses: list[McqResponse] = Field(default_factory=list)
    text_responses: list[TextResponse] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
