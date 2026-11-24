from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.analytics.recommender import (
    collaborative_recommendations,
    content_recommendations,
    evaluate_recommendations,
    merge_recommendations,
)
from app.analytics.upload_dedupe import lookup_duplicate_upload, register_upload_fingerprint
from app.config import settings
from app.core.security import require_api_key
from app.core.upload_security import read_validated_upload
from app.db import get_database
from app.grading.similarity import embed_texts
from app.grading.submission_extraction import extract_submission_responses
from app.grading.vision_client import AllVisionProvidersExhaustedError, get_vision_client
from app.models.batch import BatchRow
from app.models.batch_analytics import RecommendationOut, RecommenderEvalOut
from app.models.submission import Submission
from app.reporting import build_submissions_csv
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.batch_analytics_repo import BatchAnalyticsRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository


class RecommendationsResponse(BaseModel):
    submission_id: str
    recommendations: list[RecommendationOut] = Field(default_factory=list)
    eval: RecommenderEvalOut | None = None



router = APIRouter(
    prefix="/submissions",
    tags=["submissions"],
    dependencies=[Depends(require_api_key)],
)

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
    # Optional so the batch-upload flow — which never asks a teacher to type
    # a name per paper — can rely on the roll number the vision model reads
    # off the page instead. Still required in spirit for the one-by-one
    # upload form, which always sends it.
    student_name: str | None = Form(None),
    batch_id: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Submission:
    """Upload a scanned/PDF student answer sheet; a vision model transcribes the
    MCQ selections, free-text answers, and roll number, matched to the answer
    key's questions."""
    content_type = file.content_type or ""
    if content_type != "application/pdf" and not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_SUPPORTED_UPLOAD_TYPES_HINT)

    answer_key = await AnswerKeyRepository(db).get(answer_key_id)
    if answer_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")

    file_bytes = await read_validated_upload(file, content_type, settings.max_upload_bytes)
    fingerprint, duplicate_warning = await lookup_duplicate_upload(
        db, file_bytes=file_bytes, answer_key_id=answer_key_id
    )

    try:
        extracted = await extract_submission_responses(
            file_bytes, content_type, answer_key, get_vision_client()
        )
    except AllVisionProvidersExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vision extraction is currently rate-limited across all configured providers. Try again shortly.",
        ) from exc

    roll_number = str(extracted.get("roll_number") or "").strip()
    resolved_name = (student_name or "").strip() or (f"Roll {roll_number}" if roll_number else "Unknown student")

    submission = Submission(
        answer_key_id=answer_key_id,
        student_name=resolved_name,
        roll_number=roll_number,
        batch_id=batch_id,
        mcq_responses=extracted.get("mcq_responses", []),
        text_responses=extracted.get("text_responses", []),
    )
    created = await SubmissionRepository(db).create(submission)
    await register_upload_fingerprint(db, fingerprint=fingerprint, answer_key_id=answer_key_id)

    if duplicate_warning:
        payload = created.model_dump(by_alias=True)
        return JSONResponse(
            content=payload,
            headers={"X-Duplicate-Warning": duplicate_warning},
        )
    return created


@router.get("/csv")
async def download_submissions_csv(
    answer_key_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> StreamingResponse:
    """CSV export for every submission filed against this answer key —
    covers papers added one-by-one or typed in directly, not just ones
    grouped into a batch (which get their own /batches/{id}/csv). Declared
    ahead of GET /{submission_id} so "csv" isn't swallowed as a submission id.
    """
    submissions = await SubmissionRepository(db).list_by_answer_key(answer_key_id)
    result_repo = ResultRepository(db)
    rows = [
        BatchRow(submission=submission, result=await result_repo.get_by_submission(submission.id))
        for submission in submissions
    ]
    csv_text = build_submissions_csv(rows)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="submissions-{answer_key_id}.csv"'},
    )


@router.get("/{submission_id}", response_model=Submission)
async def get_submission(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Submission:
    submission = await SubmissionRepository(db).get(submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.get(
    "/{submission_id}/recommendations",
    response_model=RecommendationsResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_recommendations(
    submission_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> RecommendationsResponse:
    """Review-topic recommendations from content + collaborative filtering on miss patterns."""
    submission = await SubmissionRepository(db).get(submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Prefer stored batch analytics if this paper is in a batch that was analyzed.
    if submission.batch_id:
        stored = await BatchAnalyticsRepository(db).get_by_batch(submission.batch_id)
        if stored and submission_id in stored.recommendations:
            return RecommendationsResponse(
                submission_id=submission_id,
                recommendations=stored.recommendations[submission_id],
                eval=stored.recommender_eval,
            )

    peers = await SubmissionRepository(db).list_by_answer_key(submission.answer_key_id)
    result_repo = ResultRepository(db)
    miss_matrix: dict[str, set[str]] = {}
    for peer in peers:
        if not peer.id:
            continue
        result = await result_repo.get_by_submission(peer.id)
        if result is None:
            continue
        miss_matrix[peer.id] = {
            g.question_id for g in result.question_grades if g.points_awarded < g.points_possible
        }

    target_misses = miss_matrix.get(submission_id, set())
    question_ids = sorted({qid for misses in miss_matrix.values() for qid in misses} | target_misses)
    q_embeddings: dict[str, list[float]] = {}
    if question_ids:
        vectors = await embed_texts(question_ids)
        q_embeddings = dict(zip(question_ids, vectors))

    content = content_recommendations(list(target_misses), q_embeddings)
    collab = collaborative_recommendations(submission_id, miss_matrix)
    merged = merge_recommendations(content, collab)
    eval_result = evaluate_recommendations(miss_matrix)
    return RecommendationsResponse(
        submission_id=submission_id,
        recommendations=[
            RecommendationOut(question_id=r.question_id, reason=r.reason, score=r.score)
            for r in merged
        ],
        eval=RecommenderEvalOut(
            rmse=eval_result.rmse,
            precision_at_k=eval_result.precision_at_k,
            k=eval_result.k,
            held_out=eval_result.held_out,
        ),
    )


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
