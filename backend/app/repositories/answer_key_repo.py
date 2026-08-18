from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.answer_key import AnswerKey

COLLECTION = "answer_keys"


class AnswerKeyRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db[COLLECTION]

    async def create(self, answer_key: AnswerKey) -> AnswerKey:
        doc = answer_key.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(doc)
        answer_key.id = str(result.inserted_id)
        return answer_key

    async def get(self, answer_key_id: str) -> AnswerKey | None:
        doc = await self._collection.find_one({"_id": ObjectId(answer_key_id)})
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        return AnswerKey.model_validate(doc)

    async def list(self) -> list[AnswerKey]:
        cursor = self._collection.find()
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(AnswerKey.model_validate(doc))
        return results

    async def delete(self, answer_key_id: str) -> bool:
        result = await self._collection.delete_one({"_id": ObjectId(answer_key_id)})
        return result.deleted_count > 0

    async def update(self, answer_key_id: str, answer_key: AnswerKey) -> AnswerKey | None:
        doc = answer_key.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.replace_one({"_id": ObjectId(answer_key_id)}, doc)
        if result.matched_count == 0:
            return None
        answer_key.id = answer_key_id
        return answer_key
