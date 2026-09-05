from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_database

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


def _normalise_email(email: str) -> str:
    return email.strip().lower()


async def _claim_legacy_data(db: AsyncIOMotorDatabase, user_id: str, user: dict) -> None:
    """Attach pre-authentication records to the first account once."""
    first_user = await db["users"].find_one(sort=[("_id", 1)])
    if first_user is None or first_user["_id"] != user["_id"]:
        return
    legacy_filter = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]}
    for collection in ("answer_keys", "submissions", "batches", "grade_results"):
        await db[collection].update_many(legacy_filter, {"$set": {"user_id": user_id}})


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(credentials: Credentials, db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthResponse:
    email = _normalise_email(credentials.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    users = db["users"]
    if await users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    result = await users.insert_one({"email": email, "password_hash": hash_password(credentials.password)})
    user_id = str(result.inserted_id)
    await _claim_legacy_data(db, user_id, {"_id": result.inserted_id})
    return AuthResponse(access_token=create_access_token(user_id), email=email)


@router.post("/login", response_model=AuthResponse)
async def login(credentials: Credentials, db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthResponse:
    email = _normalise_email(credentials.email)
    user = await db["users"].find_one({"email": email})
    if user is None or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    user_id = str(user["_id"])
    await _claim_legacy_data(db, user_id, user)
    return AuthResponse(access_token=create_access_token(user_id), email=email)
