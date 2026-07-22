from pydantic import BaseModel, Field


class QuestionGrade(BaseModel):
    question_id: str
    points_awarded: float
    points_possible: float
    feedback: str = ""
    graded_by: str  # "mcq" | "llm:<model>"


class GradeResult(BaseModel):
    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    submission_id: str
    answer_key_id: str
    question_grades: list[QuestionGrade] = Field(default_factory=list)
    total_points_awarded: float = 0.0
    total_points_possible: float = 0.0

    model_config = {"populate_by_name": True}
