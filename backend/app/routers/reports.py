from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from app.db import get_database
from app.models.grade_result import GradeResult
from app.repositories.result_repo import ResultRepository

router = APIRouter(prefix="/reports", tags=["reports"])


class ConfirmPayload(BaseModel):
    """Point overrides a teacher made while reviewing, keyed by question_id.
    Questions not present here keep whatever score the model/grader gave."""

    overrides: dict[str, float] = Field(default_factory=dict)


@router.get("/{submission_id}", response_model=GradeResult)
async def get_report(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GradeResult:
    result = await ResultRepository(db).get_by_submission(submission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grade result for this submission")
    return result


@router.patch(
    "/{submission_id}/confirm",
    response_model=GradeResult,
    dependencies=[Depends(require_api_key)],
)
async def confirm_report(
    submission_id: str,
    payload: ConfirmPayload,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GradeResult:
    """A teacher's sign-off after reviewing a graded paper: bakes in any point
    overrides they made during review and marks the report reviewed."""
    repo = ResultRepository(db)
    result = await repo.get_by_submission(submission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grade result for this submission")

    for grade in result.question_grades:
        if grade.question_id not in payload.overrides:
            continue
        grade.points_awarded = round(min(grade.points_possible, max(0.0, payload.overrides[grade.question_id])), 2)

    result.total_points_awarded = round(sum(g.points_awarded for g in result.question_grades), 2)
    result.reviewed_at = datetime.now(timezone.utc)

    return await repo.upsert(result)
