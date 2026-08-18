from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.batch import Batch

COLLECTION = "batches"


class BatchRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def create(self, batch: Batch) -> Batch:
        doc = batch.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        batch.id = str(result.inserted_id)
        return batch

    async def get(self, batch_id: str) -> Batch | None:
        doc = await self._collection.find_one({"_id": ObjectId(batch_id)})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return Batch.model_validate(doc)

    async def list_by_answer_key(self, answer_key_id: str) -> list[Batch]:
        cursor = self._collection.find({"answer_key_id": answer_key_id}).sort("created_at", -1)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(Batch.model_validate(doc))
        return results

    async def delete(self, batch_id: str) -> bool:
        result = await self._collection.delete_one({"_id": ObjectId(batch_id)})
        return result.deleted_count > 0

    async def delete_by_answer_key(self, answer_key_id: str) -> int:
        """Cascade delete when the parent answer key is removed."""
        result = await self._collection.delete_many({"answer_key_id": answer_key_id})
        return result.deleted_count
