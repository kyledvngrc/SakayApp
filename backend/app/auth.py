"""Admin authentication: bcrypt password hashes and JWT bearer tokens.

                                                          (IMPERATIVE PARADIGM)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import settings

MAX_PASSWORD_BYTES = 72          # bcrypt ignores anything longer
MIN_PASSWORD_LENGTH = 10
_bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    if len(settings.jwt_secret) < 32 or settings.jwt_secret.startswith("change-me"):
        raise RuntimeError("Set JWT_SECRET in .env to a random string of 32+ characters")
    return settings.jwt_secret


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode())


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + timedelta(hours=settings.token_ttl_hours)}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def authenticate(email: str, password: str) -> dict | None:
    rows = db.fetch_all("SELECT id, email, password_hash, role::text AS role, display_name "
                        "FROM users WHERE lower(email) = lower(%s)", (email,))
    if not rows or not verify_password(password, rows[0]["password_hash"]):
        return None
    return rows[0]


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> int:
    """FastAPI dependency: the admin's user id, or 401/403."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise unauthorized
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return int(payload["sub"])
