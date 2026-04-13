"""
JWT + API Key authentication system for SignalDACH.

Uses PyJWT for token management and hashlib+secrets for password hashing.
Supports role-based access control (admin, analyst, viewer).
"""

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    APIKeyHeader,
)
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Enums & Models
# ---------------------------------------------------------------------------
class UserRole(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


class TokenPayload(BaseModel):
    sub: str  # user_id
    role: str
    jti: str
    type: str  # "access" or "refresh"
    exp: int
    iat: int


# ---------------------------------------------------------------------------
# Password policy (NIST 800-63B inspired)
# ---------------------------------------------------------------------------

class PasswordError(Exception):
    pass


def validate_password(password: str) -> None:
    """NIST 800-63B password policy. Raises PasswordError if invalid."""
    if len(password) < 12:
        raise PasswordError("Password must be at least 12 characters")
    if len(password) > 128:
        raise PasswordError("Password must be at most 128 characters")
    if not re.search(r'[A-Z]', password):
        raise PasswordError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        raise PasswordError("Password must contain at least one lowercase letter")
    if not re.search(r'[0-9]', password):
        raise PasswordError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:,.<>?]', password):
        raise PasswordError("Password must contain at least one special character")


# ---------------------------------------------------------------------------
# Account lockout
# ---------------------------------------------------------------------------

_failed_attempts: dict[str, list[float]] = {}
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_WINDOW = 900  # 15 minutes


def check_lockout(email: str) -> bool:
    """Returns True if account is locked out."""
    attempts = _failed_attempts.get(email, [])
    now = time.time()
    recent = [t for t in attempts if now - t < _LOCKOUT_WINDOW]
    _failed_attempts[email] = recent
    return len(recent) >= _LOCKOUT_THRESHOLD


def record_failed_attempt(email: str) -> None:
    if email not in _failed_attempts:
        _failed_attempts[email] = []
    _failed_attempts[email].append(time.time())


def clear_failed_attempts(email: str) -> None:
    _failed_attempts.pop(email, None)


# ---------------------------------------------------------------------------
# Password hashing  (hashlib + secrets, no external deps)
# ---------------------------------------------------------------------------
_HASH_ITERATIONS = 260_000
_HASH_ALGO = "sha256"


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO,
        password.encode(),
        salt.encode(),
        _HASH_ITERATIONS,
    )
    return f"{salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt, stored_dk = password_hash.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGO,
        password.encode(),
        salt.encode(),
        _HASH_ITERATIONS,
    )
    return hmac.compare_digest(dk.hex(), stored_dk)


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------
def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, key_hash)."""
    raw_key = f"sd_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------
def create_user(email: str, password: str, role: str = "viewer") -> dict:
    """Create a new user in the database. Returns the user dict."""
    validate_password(password)
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        try:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (user_id, email, pw_hash, role, now, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )
        except Exception as e:
            # Catch PostgreSQL IntegrityError (psycopg/psycopg2) and other DB drivers
            if "IntegrityError" in type(e).__name__ or "UniqueViolation" in type(e).__name__:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email already exists",
                )
            raise

    return {
        "id": user_id,
        "email": email,
        "role": role,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate by email+password. Returns user dict or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()

    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_user_by_id(user_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": str(uuid.uuid4()),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(minutes=settings.refresh_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Token verification & blacklisting
# ---------------------------------------------------------------------------
def verify_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Returns the payload dict."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Expected {expected_type} token",
        )

    # Check blacklist
    jti = payload.get("jti")
    if jti and _is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )

    return payload


def blacklist_token(jti: str, expires_at: Optional[str] = None) -> None:
    bl_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO token_blacklist (id, token_jti, expires_at) VALUES (?, ?, ?)",
            (bl_id, jti, expires_at),
        )


def _is_token_blacklisted(jti: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM token_blacklist WHERE token_jti = ?", (jti,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def _resolve_user_from_bearer(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[dict]:
    """Resolve user from Bearer token. Returns None when auth is disabled or no token."""
    if credentials is None:
        return None
    payload = verify_token(credentials.credentials, expected_type="access")
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def _resolve_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[dict]:
    """Resolve user from X-API-Key header."""
    if api_key is None:
        return None
    key_hash = _hash_api_key(api_key)
    with get_db() as conn:
        row = conn.execute(
            """SELECT ak.user_id, ak.permissions, u.role, u.is_active
               FROM api_keys ak
               JOIN users u ON u.id = ak.user_id
               WHERE ak.key_hash = ? AND ak.is_active = 1""",
            (key_hash,),
        ).fetchone()

    if row is None or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # Update last_used_at
    with get_db() as conn:
        conn.execute(
            "UPDATE api_keys SET last_used_at = datetime('now') WHERE key_hash = ?",
            (key_hash,),
        )

    user = get_user_by_id(row["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user(
    bearer_user: Optional[dict] = Depends(_resolve_user_from_bearer),
    api_key_user: Optional[dict] = Depends(_resolve_user_from_api_key),
) -> Optional[dict]:
    """
    Resolve the current user from either Bearer token or API key.
    When AUTH_ENABLED is False, returns None (all endpoints open).
    When AUTH_ENABLED is True, raises 401 if no valid credentials.
    """
    user = bearer_user or api_key_user

    if not settings.auth_enabled:
        return user  # Allow unauthenticated access

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: str):
    """Dependency factory: require the current user to have one of the given roles."""

    async def _check(user: Optional[dict] = Depends(get_current_user)):
        if not settings.auth_enabled:
            return user
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' not permitted. Required: {', '.join(roles)}",
            )
        return user

    return _check
