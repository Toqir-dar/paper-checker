from pydantic import BaseModel, Field


class QuestionGrade(BaseModel):
    question_id: str
    question_text: str = ""
    detected_label: str = ""
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
    # Flags for a teacher to double check before trusting the score(s) as-is —
    # e.g. a submission's question numbering doesn't line up with the answer
    # key, which most often means a misread handwritten number, not a skipped
    # question.
    warnings: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
