import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


_REFRESH_TTL = timedelta(days=30)


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(db: AsyncIOMotorDatabase, user_id: str, email: str) -> tuple[str, str]:
    session_id = secrets.token_urlsafe(24)
    refresh_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    await db["auth_sessions"].insert_one(
        {
            "_id": session_id,
            "user_id": user_id,
            "email": email,
            "refresh_token_hash": _hash_refresh_token(refresh_token),
            "created_at": now,
            "expires_at": now + _REFRESH_TTL,
            "revoked_at": None,
        }
    )
    return session_id, refresh_token


async def get_active_session(db: AsyncIOMotorDatabase, session_id: str) -> dict | None:
    session = await db["auth_sessions"].find_one(
        {
            "_id": session_id,
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    return session


async def rotate_session(db: AsyncIOMotorDatabase, refresh_token: str) -> tuple[str, str, str, str] | None:
    session = await db["auth_sessions"].find_one(
        {
            "refresh_token_hash": _hash_refresh_token(refresh_token),
            "revoked_at": None,
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    if session is None:
        return None

    await db["auth_sessions"].update_one(
        {"_id": session["_id"], "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )
    new_session_id, new_refresh_token = await create_session(
        db, str(session["user_id"]), session["email"]
    )
    return new_session_id, new_refresh_token, session["user_id"], session["email"]


async def revoke_session(db: AsyncIOMotorDatabase, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    await db["auth_sessions"].update_one(
        {"refresh_token_hash": _hash_refresh_token(refresh_token), "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )
