from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import current_user_id
from app.models.subject import Subject

COLLECTION = "subjects"


class SubjectRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def create(self, subject: Subject) -> Subject:
        subject.name = subject.name.strip()
        existing = await self._collection.find_one({"user_id": current_user_id(), "name": subject.name})
        if existing:
            existing["_id"] = str(existing["_id"])
            return Subject.model_validate(existing)
        doc = subject.model_dump(by_alias=True, exclude={"id"})
        doc["user_id"] = current_user_id()
        result = await self._collection.insert_one(doc)
        subject.id = str(result.inserted_id)
        return subject

    async def list(self) -> list[Subject]:
        cursor = self._collection.find({"user_id": current_user_id()}).sort("name", 1)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(Subject.model_validate(doc))
        return results

    async def get(self, subject_id: str) -> Subject | None:
        doc = await self._collection.find_one({"_id": ObjectId(subject_id), "user_id": current_user_id()})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return Subject.model_validate(doc)