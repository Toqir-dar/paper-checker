from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.grade_result import GradeResult
from app.models.submission import Submission


class Batch(BaseModel):
    """A group of papers uploaded and graded together against one answer key.

    Deliberately thin — the submissions themselves carry a batch_id back to
    this record, so a Batch is just an anchor for "these papers belong to one
    run" plus a timestamp. Everything else (rows, scores, CSV) is derived by
    joining submissions + their grade results at read time.
    """

    id: str | None = Field(default=None, validation_alias="_id", serialization_alias="id")
    answer_key_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}


class BatchRow(BaseModel):
    """One paper's submission paired with its grade — result is None until
    that paper has been graded, so a still-in-progress batch renders sensibly."""

    submission: Submission
    result: GradeResult | None = None


class BatchDetail(BaseModel):
    """Everything the batch results page / CSV export needs in one response."""

    batch: Batch
    rows: list[BatchRow]
