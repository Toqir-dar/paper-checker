from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import current_user_id
from app.models.batch_analytics import BatchAnalytics

COLLECTION = "batch_analytics"


class BatchAnalyticsRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def upsert(self, analytics: BatchAnalytics) -> BatchAnalytics:
        doc = analytics.model_dump(by_alias=True, exclude={"id"})
        doc["user_id"] = current_user_id()
        existing = await self._collection.find_one(
            {"batch_id": analytics.batch_id, "user_id": current_user_id()}
        )
        if existing is not None:
            await self._collection.replace_one({"_id": existing["_id"]}, doc)
            analytics.id = str(existing["_id"])
        else:
            inserted = await self._collection.insert_one(doc)
            analytics.id = str(inserted.inserted_id)
        return analytics

    async def get_by_batch(self, batch_id: str) -> BatchAnalytics | None:
        doc = await self._collection.find_one({"batch_id": batch_id, "user_id": current_user_id()})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return BatchAnalytics.model_validate(doc)

    async def delete_by_batch(self, batch_id: str) -> bool:
        result = await self._collection.delete_one({"batch_id": batch_id, "user_id": current_user_id()})
        return result.deleted_count > 0
