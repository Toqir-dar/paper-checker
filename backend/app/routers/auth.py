import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.config import settings
from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceededError
from app.core.sessions import create_session, revoke_session, rotate_session
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_database

router = APIRouter(prefix="/auth", tags=["auth"])
auth_rate_limiter = InMemoryRateLimiter()


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    email: str
    csrf_token: str


def _set_session_cookie(response: Response, access_token: str, refresh_token: str) -> str:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=60 * 15,
        path="/",
    )
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=60 * 60 * 24 * 30,
        path="/auth",
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=60 * 15,
        path="/",
    )
    return csrf_token


def _normalise_email(email: str) -> str:
    return email.strip().lower()


async def _claim_legacy_data(db: AsyncIOMotorDatabase, user_id: str, user: dict) -> None:
    """Attach pre-authentication records to the first account once."""
    first_user = await db["users"].find_one(sort=[("_id", 1)])
    if first_user is None or first_user["_id"] != user["_id"]:
        return
    legacy_filter = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]}
    for collection in ("answer_keys", "submissions", "batches", "grade_results", "subjects"):
        await db[collection].update_many(legacy_filter, {"$set": {"user_id": user_id}})


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _check_auth_rate_limit(request: Request, email: str, limit: int, window_seconds: int) -> None:
    try:
        await auth_rate_limiter.check(
            [f"ip:{_client_ip(request)}", f"email:{email}"],
            limit,
            window_seconds,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    credentials: Credentials,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AuthResponse:
    email = _normalise_email(credentials.email)
    await _check_auth_rate_limit(
        request, email, settings.auth_signup_limit, settings.auth_signup_window_seconds
    )
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    users = db["users"]
    if await users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    result = await users.insert_one({"email": email, "password_hash": hash_password(credentials.password)})
    user_id = str(result.inserted_id)
    await _claim_legacy_data(db, user_id, {"_id": result.inserted_id})
    session_id, refresh_token = await create_session(db, user_id, email)
    csrf_token = _set_session_cookie(response, create_access_token(user_id, session_id), refresh_token)
    return AuthResponse(email=email, csrf_token=csrf_token)


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: Credentials,
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AuthResponse:
    email = _normalise_email(credentials.email)
    await _check_auth_rate_limit(
        request, email, settings.auth_login_limit, settings.auth_login_window_seconds
    )
    user = await db["users"].find_one({"email": email})
    if user is None or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    user_id = str(user["_id"])
    await _claim_legacy_data(db, user_id, user)
    session_id, refresh_token = await create_session(db, user_id, email)
    csrf_token = _set_session_cookie(response, create_access_token(user_id, session_id), refresh_token)
    return AuthResponse(email=email, csrf_token=csrf_token)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=settings.auth_refresh_cookie_name),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AuthResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    rotated = await rotate_session(db, refresh_token)
    if rotated is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    new_session_id, new_refresh_token, user_id, email = rotated
    csrf_token = _set_session_cookie(response, create_access_token(user_id, new_session_id), new_refresh_token)
    return AuthResponse(email=email, csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=settings.auth_refresh_cookie_name),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> None:
    await revoke_session(db, refresh_token)
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    response.delete_cookie(key=settings.auth_csrf_cookie_name, path="/")
    response.delete_cookie(key=settings.auth_refresh_cookie_name, path="/auth")
