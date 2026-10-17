"""
app/api/deps.py
---------------
Reusable FastAPI dependencies for database sessions, JWT authentication,
role-based authorization, and resource ownership verification.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/oauth",
    auto_error=True,
)

optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/oauth",
    auto_error=False,
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """
    Decodes the Bearer access token, validates claims and expiration,
    and returns the active User model from the database.
    """
    payload = decode_access_token(token)
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing user identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(optional_oauth2),
) -> Optional[User]:
    """
    Optional authentication dependency for endpoints that support both
    guest operations and authenticated user scoping.
    """
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await db.get(User, user_id)
        if user and user.is_active:
            return user
        return None
    except HTTPException:
        return None
    except Exception as exc:
        logger.debug("Optional authentication failed to parse token: %s", exc)
        return None


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the current authenticated user has administrative privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )
    return current_user


def enforce_resume_ownership(
    resume: Resume,
    current_user: Optional[User],
) -> None:
    """
    Verifies that the accessing user owns the target resume.
    If the resume is tagged with a user_id, access is denied (HTTP 403 Forbidden)
    to any different non-superuser user.
    """
    # If the resume has an assigned owner:
    if resume.user_id:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this resume.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.id != resume.user_id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to access or modify this resume.",
            )
