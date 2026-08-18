from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.grade_result import GradeResult

COLLECTION = "grade_results"


class ResultRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def upsert(self, result: GradeResult) -> GradeResult:
        doc = result.model_dump(by_alias=True, exclude={"id"})
        existing = await self._collection.find_one({"submission_id": result.submission_id})
        if existing is not None:
            await self._collection.replace_one({"_id": existing["_id"]}, doc)
            result.id = str(existing["_id"])
        else:
            inserted = await self._collection.insert_one(doc)
            result.id = str(inserted.inserted_id)
        return result

    async def get_by_submission(self, submission_id: str) -> GradeResult | None:
        doc = await self._collection.find_one({"submission_id": submission_id})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return GradeResult.model_validate(doc)

    async def get(self, result_id: str) -> GradeResult | None:
        doc = await self._collection.find_one({"_id": ObjectId(result_id)})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return GradeResult.model_validate(doc)

    async def delete_by_submission(self, submission_id: str) -> bool:
        result = await self._collection.delete_one({"submission_id": submission_id})
        return result.deleted_count > 0

    async def delete_by_answer_key(self, answer_key_id: str) -> int:
        """Cascade delete when the parent answer key is removed."""
        result = await self._collection.delete_many({"answer_key_id": answer_key_id})
        return result.deleted_count

    async def delete_by_submission_ids(self, submission_ids: list[str]) -> int:
        """Cascade delete when a parent batch (and its submissions) is removed."""
        if not submission_ids:
            return 0
        result = await self._collection.delete_many({"submission_id": {"$in": submission_ids}})
        return result.deleted_count
