from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.models.batch import Batch, BatchDetail, BatchRow
from app.reporting import build_submissions_csv
from app.repositories.answer_key_repo import AnswerKeyRepository
from app.repositories.batch_repo import BatchRepository
from app.repositories.result_repo import ResultRepository
from app.repositories.submission_repo import SubmissionRepository

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=Batch, dependencies=[Depends(require_api_key)])
async def create_batch(
    batch: Batch,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Batch:
    """Create the batch shell a frontend-driven batch upload attaches its
    per-paper submissions to. One call up front, then the caller uploads and
    grades each file individually against this batch_id."""
    answer_key = await AnswerKeyRepository(db).get(batch.answer_key_id)
    if answer_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")
    return await BatchRepository(db).create(batch)


@router.get("", response_model=list[Batch])
async def list_batches(
    answer_key_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[Batch]:
    return await BatchRepository(db).list_by_answer_key(answer_key_id)


async def _load_batch_detail(batch_id: str, db: AsyncIOMotorDatabase) -> BatchDetail:
    batch = await BatchRepository(db).get(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    submissions = await SubmissionRepository(db).list_by_batch(batch_id)
    result_repo = ResultRepository(db)
    rows = [
        BatchRow(submission=submission, result=await result_repo.get_by_submission(submission.id))
        for submission in submissions
    ]
    return BatchDetail(batch=batch, rows=rows)


@router.get("/{batch_id}", response_model=BatchDetail)
async def get_batch(
    batch_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> BatchDetail:
    """Batch info plus every submission filed under it, paired with its grade
    result (None if not graded yet) — everything the results table needs in
    one call."""
    return await _load_batch_detail(batch_id, db)


@router.get("/{batch_id}/csv")
async def download_batch_csv(
    batch_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> StreamingResponse:
    detail = await _load_batch_detail(batch_id, db)
    csv_text = build_submissions_csv(detail.rows)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_id}.csv"'},
    )


@router.delete(
    "/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
async def delete_batch(
    batch_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    """Deleting a batch also removes every submission filed under it and their
    grade results — same cascade rule as deleting an answer key."""
    deleted = await BatchRepository(db).delete(batch_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    submission_repo = SubmissionRepository(db)
    submissions = await submission_repo.list_by_batch(batch_id)
    submission_ids = [s.id for s in submissions if s.id]

    await ResultRepository(db).delete_by_submission_ids(submission_ids)
    await submission_repo.delete_by_batch(batch_id)
