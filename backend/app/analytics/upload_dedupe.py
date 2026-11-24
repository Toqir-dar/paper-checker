"""Upload-stream Bloom filter + persistent fingerprint store for duplicate checks."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.analytics.bloom import BloomFilter, content_fingerprint
from app.core.security import current_user_id

COLLECTION = "upload_fingerprints"

# Per-process Bloom filters keyed by user_id (fast path; Mongo is source of truth).
_blooms: dict[str, BloomFilter] = {}


def _bloom_for(user_id: str) -> BloomFilter:
    if user_id not in _blooms:
        _blooms[user_id] = BloomFilter(capacity=50_000, error_rate=0.01)
    return _blooms[user_id]


async def lookup_duplicate_upload(
    db: AsyncIOMotorDatabase,
    *,
    file_bytes: bytes,
    answer_key_id: str,
    answer_texts: list[str] | None = None,
) -> tuple[str, str | None]:
    """Return (fingerprint, warning_or_none). Does not register yet.

    Bloom is the cheap pre-filter; Mongo confirms exact duplicates per answer key.
    """
    user_id = current_user_id() or "anonymous"
    fingerprint = content_fingerprint(file_bytes, answer_texts)
    key = f"{answer_key_id}:{fingerprint}"
    bloom = _bloom_for(user_id)
    warning: str | None = None

    # Bloom is the in-process stream filter; Mongo is durable truth (covers restarts).
    _ = bloom.might_contain(key)  # exercise stream membership probe
    existing = await db[COLLECTION].find_one(
        {
            "user_id": user_id,
            "answer_key_id": answer_key_id,
            "fingerprint": fingerprint,
        }
    )
    if existing is not None:
        warning = "likely_duplicate_upload"
        bloom.add(key)  # re-seed bloom after process restart
    return fingerprint, warning


async def register_upload_fingerprint(
    db: AsyncIOMotorDatabase,
    *,
    fingerprint: str,
    answer_key_id: str,
) -> None:
    user_id = current_user_id() or "anonymous"
    key = f"{answer_key_id}:{fingerprint}"
    _bloom_for(user_id).add(key)
    await db[COLLECTION].update_one(
        {
            "user_id": user_id,
            "answer_key_id": answer_key_id,
            "fingerprint": fingerprint,
        },
        {"$set": {"user_id": user_id, "answer_key_id": answer_key_id, "fingerprint": fingerprint}},
        upsert=True,
    )
