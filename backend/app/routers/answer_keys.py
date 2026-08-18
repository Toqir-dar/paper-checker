from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.grading.answer_key_extraction import extract_answer_key_from_docx_text, extract_answer_key_from_file
from app.grading.docx_text import extract_text_from_docx
from app.grading.llm_client import AllProvidersExhaustedError, get_llm_client
from app.grading.vision_client import AllVisionProvidersExhaustedError, get_vision_client
from app.models.answer_key import AnswerKey
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.batch_repo import BatchRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository

router = APIRouter(prefix="/answer-keys", tags=["answer-keys"])

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_SUPPORTED_UPLOAD_TYPES_HINT = "Unsupported file type — upload a PDF, image, or Word (.docx) document."


def _resolve_upload_content_type(file: UploadFile) -> str:
    """Determine which extraction path a file should take.

    Some browsers/OSes send a generic or missing content-type for .docx
    uploads (e.g. application/octet-stream), so fall back to the filename
    extension for that one case rather than rejecting a valid upload.
    """
    content_type = file.content_type or ""
    if content_type == _DOCX_CONTENT_TYPE or content_type == "application/pdf" or content_type.startswith("image/"):
        return content_type
    if (file.filename or "").lower().endswith(".docx"):
        return _DOCX_CONTENT_TYPE
    return content_type


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
    """Upload a scanned/PDF/Word answer key or textbook page. PDFs and images go
    through a vision model; .docx files are read as plain text and go through a
    text-only model instead, since there's no scan to read off of."""
    content_type = _resolve_upload_content_type(file)
    is_supported = content_type in (_DOCX_CONTENT_TYPE, "application/pdf") or content_type.startswith("image/")
    if not is_supported:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_SUPPORTED_UPLOAD_TYPES_HINT)

    file_bytes = await file.read()

    try:
        if content_type == _DOCX_CONTENT_TYPE:
            text = extract_text_from_docx(file_bytes)
            if not text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This Word document doesn't contain any readable text.",
                )
            answer_key = await extract_answer_key_from_docx_text(text, get_llm_client())
        else:
            answer_key = await extract_answer_key_from_file(file_bytes, content_type, get_vision_client())
    except AllVisionProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vision extraction is currently rate-limited across all configured providers. Try again shortly.",
        ) from exc
    except AllProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text extraction is currently rate-limited across all configured providers. Try again shortly.",
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


@router.put(
    "/{answer_key_id}",
    response_model=AnswerKey,
    dependencies=[Depends(require_api_key)],
)
async def update_answer_key(
    answer_key_id: str,
    answer_key: AnswerKey,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AnswerKey:
    updated = await AnswerKeyRepository(db).update(answer_key_id, answer_key)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")
    return updated


@router.delete(
    "/{answer_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_answer_key(
    answer_key_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    """Deleting a key also removes every submission filed against it, their
    grade results, and any batches grouping them — an orphaned submission
    can't be graded or reviewed, and an orphaned batch has nothing to show."""
    deleted = await AnswerKeyRepository(db).delete(answer_key_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")
    await ResultRepository(db).delete_by_answer_key(answer_key_id)
    await SubmissionRepository(db).delete_by_answer_key(answer_key_id)
    await BatchRepository(db).delete_by_answer_key(answer_key_id)
