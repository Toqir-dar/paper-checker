from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.grading.submission_extraction import extract_submission_responses
from app.grading.vision_client import AllVisionProvidersExhaustedError, get_vision_client
from app.models.submission import Submission
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository

router = APIRouter(prefix="/submissions", tags=["submissions"])

_SUPPORTED_UPLOAD_TYPES_HINT = "Unsupported file type — upload a PDF or image."


@router.post("", response_model=Submission, dependencies=[Depends(require_api_key)])
async def create_submission(
    submission: Submission,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Submission:
    return await SubmissionRepository(db).create(submission)


@router.post("/upload", response_model=Submission, dependencies=[Depends(require_api_key)])
async def upload_submission(
    answer_key_id: str = Form(...),
    student_name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Submission:
    """Upload a scanned/PDF student answer sheet; a vision model transcribes the
    MCQ selections and free-text answers, matched to the answer key's questions."""
    content_type = file.content_type or ""
    if content_type != "application/pdf" and not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_SUPPORTED_UPLOAD_TYPES_HINT)

    answer_key = await AnswerKeyRepository(db).get(answer_key_id)
    if answer_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")

    file_bytes = await file.read()

    try:
        extracted = await extract_submission_responses(
            file_bytes, content_type, answer_key, get_vision_client()
        )
    except AllVisionProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vision extraction is currently rate-limited across all configured providers. Try again shortly.",
        ) from exc

    submission = Submission(
        answer_key_id=answer_key_id,
        student_name=student_name,
        mcq_responses=extracted.get("mcq_responses", []),
        text_responses=extracted.get("text_responses", []),
    )
    return await SubmissionRepository(db).create(submission)


@router.get("/{submission_id}", response_model=Submission)
async def get_submission(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Submission:
    submission = await SubmissionRepository(db).get(submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.get("", response_model=list[Submission])
async def list_submissions_for_answer_key(
    answer_key_id: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[Submission]:
    """Filtered by answer_key_id when given; otherwise every submission
    (used by the dashboard, which would otherwise need one call per key)."""
    repo = SubmissionRepository(db)
    if answer_key_id is None:
        return await repo.list_all()
    return await repo.list_by_answer_key(answer_key_id)


@router.delete(
    "/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_submission(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    deleted = await SubmissionRepository(db).delete(submission_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    await ResultRepository(db).delete_by_submission(submission_id)
