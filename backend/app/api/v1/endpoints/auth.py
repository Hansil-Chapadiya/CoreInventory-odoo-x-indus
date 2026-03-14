"""
Authentication endpoints: register, login, refresh, logout, me,
forgot-password (OTP), reset-password.
"""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.models.auth import User, UserRole, UserSession, OTPVerification
from app.schemas.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenRefreshResponse,
    TokenResponse,
    UserCreate,
    UserOut,
)
from app.services.email_service import send_otp_email, send_welcome_email

router = APIRouter()


# ─────────────────────────────────────────
# POST /auth/register
# ─────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    Password is bcrypt-hashed before storage.
    """
    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole(payload.role),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    asyncio.create_task(send_welcome_email(user.email, user.full_name))
    return user


# ─────────────────────────────────────────
# POST /auth/login
# ─────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with username + password.
    Returns access token (30 min) and refresh token (7 days).
    Session is persisted in user_sessions for audit and revocation.
    """
    result = await db.execute(
        select(User).where(
            User.username == payload.username,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token  = create_access_token(str(user.id), user.username, user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    session = UserSession(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.flush()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ─────────────────────────────────────────
# POST /auth/refresh
# ─────────────────────────────────────────

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    Refresh token must exist in user_sessions and be active.
    """
    bad_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token_data = decode_token(payload.refresh_token)
    except JWTError:
        raise bad_token

    if token_data.get("type") != "refresh":
        raise bad_token

    user_id = token_data.get("sub")
    if not user_id:
        raise bad_token

    session_result = await db.execute(
        select(UserSession).where(
            UserSession.refresh_token == payload.refresh_token,
            UserSession.is_active.is_(True),
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise bad_token

    user_result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise bad_token

    new_access_token = create_access_token(str(user.id), user.username, user.role.value)
    session.access_token = new_access_token
    await db.flush()

    return TokenRefreshResponse(access_token=new_access_token)


# ─────────────────────────────────────────
# POST /auth/logout
# ─────────────────────────────────────────

@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invalidate the session. Requires a valid access token in Authorization header.
    """
    session_result = await db.execute(
        select(UserSession).where(
            UserSession.refresh_token == payload.refresh_token,
            UserSession.user_id == current_user.id,
            UserSession.is_active.is_(True),
        )
    )
    session = session_result.scalar_one_or_none()
    if session:
        session.is_active = False
        await db.flush()


# ─────────────────────────────────────────
# GET /auth/me
# ─────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


# ─────────────────────────────────────────
# POST /auth/forgot-password
# ─────────────────────────────────────────

@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a 6-digit OTP to the user's email for password reset.
    Always returns 200 to prevent email enumeration.
    """
    _safe_response = MessageResponse(
        message="If that email is registered, an OTP has been sent."
    )

    result = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return _safe_response

    # Invalidate any existing unused OTPs for this user
    await db.execute(
        update(OTPVerification)
        .where(
            OTPVerification.user_id == user.id,
            OTPVerification.purpose == "forgot_password",
            OTPVerification.is_used.is_(False),
        )
        .values(is_used=True)
    )

    # Generate a 6-digit OTP
    otp_code = str(secrets.randbelow(1_000_000)).zfill(6)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    otp = OTPVerification(
        user_id=user.id,
        otp_code=otp_code,
        purpose="forgot_password",
        expires_at=expires_at,
    )
    db.add(otp)
    await db.flush()

    asyncio.create_task(send_otp_email(user.email, user.full_name, otp_code))

    return _safe_response


# ─────────────────────────────────────────
# POST /auth/reset-password
# ─────────────────────────────────────────

@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the OTP and set a new password.
    Deactivates all existing sessions (forces re-login).
    """
    invalid_otp = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired OTP",
    )

    user_result = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise invalid_otp

    now = datetime.now(timezone.utc)
    otp_result = await db.execute(
        select(OTPVerification)
        .where(
            OTPVerification.user_id == user.id,
            OTPVerification.purpose == "forgot_password",
            OTPVerification.is_used.is_(False),
            OTPVerification.expires_at > now,
        )
        .order_by(OTPVerification.created_at.desc())
        .limit(1)
    )
    otp = otp_result.scalar_one_or_none()

    if not otp or otp.otp_code != payload.otp_code:
        raise invalid_otp

    # Mark OTP as used
    otp.is_used = True

    # Update password
    user.hashed_password = hash_password(payload.new_password)

    # Force re-login: deactivate all sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
        .values(is_active=False)
    )

    await db.flush()
    return MessageResponse(message="Password reset successfully. Please log in again.")

