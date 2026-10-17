"""
app/api/v1/endpoints/auth.py
----------------------------
API endpoints for user registration, authentication, JWT token issuance,
and authenticated profile inspection.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Creates a new application user account with bcrypt password hashing.",
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # 1. Check for duplicate email
    existing_user = await db.execute(select(User).where(User.email == user_in.email.lower()))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    # 2. Hash password and persist user
    user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT access token (JSON payload)",
    description="Validates email and password credentials, returning a signed JWT Bearer access token.",
)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    # 1. Fetch user by email
    res = await db.execute(select(User).where(User.email == credentials.email.lower()))
    user = res.scalar_one_or_none()

    # 2. Validate password
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    # 4. Generate token
    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=expires_minutes),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_minutes * 60,
    )


@router.post(
    "/login/oauth",
    response_model=Token,
    summary="OAuth2-compatible token login endpoint (form-data)",
    description="Compliant with OAuth2 password specification for OpenAPI documentation and clients.",
)
async def login_oauth(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    res = await db.execute(select(User).where(User.email == form_data.username.lower()))
    user = res.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=expires_minutes),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
    description="Returns the profile information of the currently authenticated bearer token owner.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
