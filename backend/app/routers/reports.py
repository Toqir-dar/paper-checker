from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.models.grade_result import GradeResult
from app.repositories.result_repo import ResultRepository

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{submission_id}", response_model=GradeResult)
async def get_report(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GradeResult:
    result = await ResultRepository(db).get_by_submission(submission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No grade result for this submission")
    return result
