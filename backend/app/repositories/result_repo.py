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
