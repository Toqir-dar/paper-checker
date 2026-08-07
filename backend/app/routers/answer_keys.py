from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.grading.answer_key_extraction import extract_answer_key_from_file
from app.grading.vision_client import AllVisionProvidersExhaustedError, get_vision_client
from app.models.answer_key import AnswerKey
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository

router = APIRouter(prefix="/answer-keys", tags=["answer-keys"])

_SUPPORTED_UPLOAD_TYPES_HINT = "Unsupported file type — upload a PDF or image."


@router.post("", response_model=AnswerKey, dependencies=[Depends(require_api_key)])
async def create_answer_key(
    answer_key: AnswerKey,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AnswerKey:
    return await AnswerKeyRepository(db).create(answer_key)


@router.post("/upload", response_model=AnswerKey, dependencies=[Depends(require_api_key)])
async def upload_answer_key(
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AnswerKey:
    """Upload a scanned/PDF answer key or textbook page; a vision model extracts
    the MCQ answers and free-text reference answers + rubric automatically."""
    content_type = file.content_type or ""
    if content_type != "application/pdf" and not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_SUPPORTED_UPLOAD_TYPES_HINT)

    file_bytes = await file.read()

    try:
        answer_key = await extract_answer_key_from_file(file_bytes, content_type, get_vision_client())
    except AllVisionProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vision extraction is currently rate-limited across all configured providers. Try again shortly.",
        ) from exc

    return await AnswerKeyRepository(db).create(answer_key)


@router.get("", response_model=list[AnswerKey])
async def list_answer_keys(db: AsyncIOMotorDatabase = Depends(get_database)) -> list[AnswerKey]:
    return await AnswerKeyRepository(db).list()


@router.get("/{answer_key_id}", response_model=AnswerKey)
async def get_answer_key(
    answer_key_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AnswerKey:
    answer_key = await AnswerKeyRepository(db).get(answer_key_id)
    if answer_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")
    return answer_key


@router.delete(
    "/{answer_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_answer_key(
    answer_key_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    """Deleting a key also removes every submission filed against it and
    their grade results — an orphaned submission can't be graded or reviewed."""
    deleted = await AnswerKeyRepository(db).delete(answer_key_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")
    await ResultRepository(db).delete_by_answer_key(answer_key_id)
    await SubmissionRepository(db).delete_by_answer_key(answer_key_id)
