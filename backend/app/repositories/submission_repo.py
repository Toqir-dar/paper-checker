from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.submission import Submission

COLLECTION = "submissions"


class SubmissionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def create(self, submission: Submission) -> Submission:
        doc = submission.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        submission.id = str(result.inserted_id)
        return submission

    async def get(self, submission_id: str) -> Submission | None:
        doc = await self._collection.find_one({"_id": ObjectId(submission_id)})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return Submission.model_validate(doc)

    async def list_by_answer_key(self, answer_key_id: str) -> list[Submission]:
        cursor = self._collection.find({"answer_key_id": answer_key_id})
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(Submission.model_validate(doc))
        return results

    async def list_all(self) -> list[Submission]:
        cursor = self._collection.find()
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(Submission.model_validate(doc))
        return results

    async def list_by_batch(self, batch_id: str) -> list[Submission]:
        cursor = self._collection.find({"batch_id": batch_id})
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(Submission.model_validate(doc))
        return results

    async def delete(self, submission_id: str) -> bool:
        result = await self._collection.delete_one({"_id": ObjectId(submission_id)})
        return result.deleted_count > 0

    async def delete_by_answer_key(self, answer_key_id: str) -> int:
        """Cascade delete when the parent answer key is removed."""
        result = await self._collection.delete_many({"answer_key_id": answer_key_id})
        return result.deleted_count

    async def delete_by_batch(self, batch_id: str) -> int:
        """Cascade delete when the parent batch is removed."""
        result = await self._collection.delete_many({"batch_id": batch_id})
        return result.deleted_count
