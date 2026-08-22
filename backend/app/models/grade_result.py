from datetime import datetime

from pydantic import BaseModel, Field


class CriterionGrade(BaseModel):
    """How one rubric criterion was scored for a single answer. Empty for MCQ
    grades and for the similarity fallback, which have no per-criterion detail."""

    description: str
    max_points: float
    awarded_points: float


class QuestionGrade(BaseModel):
    question_id: str
    question_text: str = ""
    detected_label: str = ""
    points_awarded: float
    points_possible: float
    feedback: str = ""
    graded_by: str  # "mcq" | "rubric:<model>" | "cosine_similarity"
    criteria: list[CriterionGrade] = Field(default_factory=list)


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
    # Set once a teacher has reviewed this report and hit "Confirm this paper"
    # — None until then. Re-grading (POST /grading/{id}) overwrites the whole
    # result and clears this, since a fresh model pass needs a fresh look.
    reviewed_at: datetime | None = None

    model_config = {"populate_by_name": True}
