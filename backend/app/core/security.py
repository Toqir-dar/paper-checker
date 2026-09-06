import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from contextvars import ContextVar

from fastapi import Header, HTTPException, status

from app.config import settings


_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
_DEVELOPMENT_TOKEN_SECRET = secrets.token_urlsafe(32)
_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: str | None):
    return _current_user_id.set(user_id)


def reset_current_user_id(token) -> None:
    _current_user_id.reset(token)


def current_user_id() -> str | None:
    return _current_user_id.get()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_text, digest_text = stored_hash.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
    except (ValueError, UnicodeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300_000)
    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + _TOKEN_TTL_SECONDS}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_token_secret().encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def get_user_id_from_token(token: str) -> str | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_token_secret().encode(), encoded.encode(), hashlib.sha256).digest()
        provided = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, provided):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < time.time():
            return None
        return str(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError, binascii.Error):
        return None


def _token_secret() -> str:
    if settings.auth_secret:
        return settings.auth_secret
    if settings.app_environment.strip().lower() in {"production", "prod"}:
        raise RuntimeError("AUTH_SECRET must be configured in production")
    return _DEVELOPMENT_TOKEN_SECRET


async def require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Require a valid login token, or the configured service API key."""
    bearer_token = authorization.removeprefix("Bearer ") if authorization else None
    if bearer_token and get_user_id_from_token(bearer_token):
        return
    if settings.api_key and x_api_key == settings.api_key:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
