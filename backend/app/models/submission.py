from pydantic import BaseModel, Field


class McqResponse(BaseModel):
    question_id: str
    selected_option: str


class TextResponse(BaseModel):
    question_id: str
    answer_text: str


class Submission(BaseModel):
    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    answer_key_id: str
    student_name: str
    mcq_responses: list[McqResponse] = Field(default_factory=list)
    text_responses: list[TextResponse] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
