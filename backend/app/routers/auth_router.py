"""
Authentication router for SignalDACH.

Endpoints for registration, login, token refresh, logout,
user info, and API key management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from app.auth import (
    authenticate_user,
    blacklist_token,
    check_lockout,
    clear_failed_attempts,
    create_access_token,
    create_refresh_token,
    create_user,
    generate_api_key,
    get_current_user,
    PasswordError,
    record_failed_attempt,
    require_role,
    validate_password,
    verify_token,
)
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "viewer"

    @property
    def validated_email(self) -> str:
        if len(self.email) > 254:
            raise ValueError("Email must be at most 254 characters")
        return self.email


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreateRequest(BaseModel):
    name: str
    permissions: str = "{}"


class ApiKeyResponse(BaseModel):
    id: str
    key: str  # Only returned at creation time
    name: str
    created_at: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    current_user: Optional[dict] = Depends(require_role("admin")),
):
    """Register a new user. Admin-only when auth is enabled."""
    if body.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be admin, analyst, or viewer.",
        )
    try:
        validate_password(body.password)
    except PasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    user = create_user(email=body.email, password=body.password, role=body.role)
    logger.info("User registered: %s (role=%s)", user["email"], user["role"])
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate and return JWT tokens."""
    # Check account lockout before attempting authentication
    if check_lockout(body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed login attempts. Try again later.",
        )

    user = authenticate_user(body.email, body.password)
    if user is None:
        record_failed_attempt(body.email)
        try:
            from app.audit import log_auth
            log_auth("failed_login", email=body.email)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Successful login — clear any failed attempts
    clear_failed_attempts(body.email)

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"], user["role"])

    logger.info("User logged in: %s", user["email"])
    try:
        from app.audit import log_auth
        log_auth("login", user_id=user["id"], email=user["email"])
    except Exception:
        pass
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """Exchange a refresh token for new access + refresh tokens."""
    payload = verify_token(body.refresh_token, expected_type="refresh")

    # Blacklist the old refresh token (rotation)
    blacklist_token(
        jti=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
    )

    access_token = create_access_token(payload["sub"], payload["role"])
    refresh_token = create_refresh_token(payload["sub"], payload["role"])

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Blacklist the current access token so it cannot be reused."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        try:
            payload = verify_token(token, expected_type="access")
            blacklist_token(
                jti=payload["jti"],
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
            )
            logger.info("Token blacklisted for user %s", payload.get("sub"))
        except HTTPException:
            pass  # Token already invalid/expired — nothing to blacklist
    try:
        from app.audit import log_auth
        uid = current_user["id"] if current_user else None
        log_auth("logout", user_id=uid)
    except Exception:
        pass
    return MessageResponse(message="Logged out successfully. Token has been revoked.")


@router.get("/me", response_model=UserResponse)
async def me(current_user: Optional[dict] = Depends(get_current_user)):
    """Return current user info."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return UserResponse(**current_user)


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Create a new API key for the current user."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    raw_key, key_hash = generate_api_key()
    key_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO api_keys (id, user_id, key_hash, name, permissions, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (key_id, current_user["id"], key_hash, body.name, body.permissions, now),
        )

    logger.info("API key created: %s for user %s", body.name, current_user["email"])
    return ApiKeyResponse(id=key_id, key=raw_key, name=body.name, created_at=now)


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Revoke (deactivate) an API key."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    with get_db() as conn:
        # Ensure the key belongs to the current user (or user is admin)
        row = conn.execute(
            "SELECT user_id FROM api_keys WHERE id = ? AND is_active = 1", (key_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        if row["user_id"] != current_user["id"] and current_user["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your API key")

        conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))

    logger.info("API key revoked: %s", key_id)
    return MessageResponse(message="API key revoked")
