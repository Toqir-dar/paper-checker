from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import require_api_key
from app.db import get_database
from app.models.subject import Subject
from app.repositories.subject_repo import SubjectRepository

router = APIRouter(
    prefix="/subjects",
    tags=["subjects"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Subject, status_code=status.HTTP_201_CREATED)
async def create_subject(subject: Subject, db: AsyncIOMotorDatabase = Depends(get_database)) -> Subject:
    if not subject.name.strip():
        raise HTTPException(status_code=400, detail="Subject name is required")
    return await SubjectRepository(db).create(subject)


@router.get("", response_model=list[Subject])
async def list_subjects(db: AsyncIOMotorDatabase = Depends(get_database)) -> list[Subject]:
    return await SubjectRepository(db).list()