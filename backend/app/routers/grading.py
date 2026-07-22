from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.grading import grade_submission
from app.grading.llm_client import AllProvidersExhaustedError
from app.models.grade_result import GradeResult
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository

router = APIRouter(prefix="/grading", tags=["grading"])


@router.post(
    "/{submission_id}",
    response_model=GradeResult,
    dependencies=[Depends(require_api_key)],
)
async def grade(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> GradeResult:
    submission = await SubmissionRepository(db).get(submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    answer_key = await AnswerKeyRepository(db).get(submission.answer_key_id)
    if answer_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")

    try:
        result = await grade_submission(submission, answer_key)
    except AllProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All configured LLM providers are currently rate-limited or unavailable. Try again shortly.",
        ) from exc

    return await ResultRepository(db).upsert(result)
