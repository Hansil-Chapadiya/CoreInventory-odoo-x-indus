"""
Authentication endpoints: register, login, refresh, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User
from app.schemas.schemas import UserCreate, UserOut, LoginRequest, TokenResponse

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    existing = await db.execute(
        select(User).where((User.email == payload.email) | (User.username == payload.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already exists")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=payload.password,  # TODO: hash with bcrypt in production
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT tokens."""
    result = await db.execute(
        select(User).where(User.username == payload.username, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # TODO: verify hashed password with bcrypt
    if user.hashed_password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # TODO: generate real JWT tokens
    return TokenResponse(
        access_token=f"access-{user.id}",
        refresh_token=f"refresh-{user.id}",
    )


@router.get("/me", response_model=UserOut)
async def get_me(db: AsyncSession = Depends(get_db)):
    """Get current user profile. (TODO: extract user from JWT)"""
    raise HTTPException(status_code=501, detail="Implement JWT auth dependency")
