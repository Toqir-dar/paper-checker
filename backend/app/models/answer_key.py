from pydantic import BaseModel, Field


class McqAnswer(BaseModel):
    question_id: str
    question_text: str = ""
    correct_option: str
    points: float = 1.0


class RubricCriterion(BaseModel):
    description: str
    max_points: float


class TextAnswer(BaseModel):
    question_id: str
    question_text: str = ""
    reference_answer: str
    rubric: list[RubricCriterion]


class AnswerKey(BaseModel):
    # Accepts "_id" on the way in (raw MongoDB documents), but always
    # serializes as "id" on the way out — API clients shouldn't have to know
    # Mongo's field naming convention.
    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    title: str
    mcq_answers: list[McqAnswer] = Field(default_factory=list)
    text_answers: list[TextAnswer] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
