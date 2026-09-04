"""Authentication and Authorization Dependencies for Route Protection."""

import logging
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from app.core.auth_database import auth_db_manager
from app.core.security import decode_token
from app.schemas.auth import UserResponse

logger = logging.getLogger(__name__)

# Native FastAPI OAuth2 scheme pointing to login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=True,
)


async def validate_token_and_get_user(token: str) -> UserResponse:
    """Validates token authenticity, blacklist revocation, and active user profile."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Check if token was blacklisted (logged out)
    token_jti = payload.get("jti")
    if token_jti:
        is_revoked = await auth_db_manager.is_token_blacklisted(token_jti)
        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Extract email subject
    email: Optional[str] = payload.get("sub")
    if not email:
        raise credentials_exception

    # 3. Retrieve user from auth_db
    user_dict = await auth_db_manager.get_user_by_email(email)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with token does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse(
        id=str(user_dict["id"]),
        email=user_dict["email"],
        full_name=user_dict.get("full_name"),
        is_active=user_dict.get("is_active", True),
        is_superuser=user_dict.get("is_superuser", False),
        role=user_dict.get("role", "user"),
        created_at=user_dict.get("created_at"),
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> UserResponse:
    """Decodes JWT Bearer token, checks token revocation, and fetches user profile."""
    return await validate_token_and_get_user(token)


async def get_report_user(
    request: Request,
    token: Optional[str] = Query(None, description="JWT token for report access via query param"),
) -> UserResponse:
    """Authenticates HTML report viewer via either Authorization header or ?token= query parameter."""
    auth_header = request.headers.get("Authorization")
    raw_token = None
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
    elif token:
        raw_token = token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view research report. Provide Bearer token or ?token= query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await validate_token_and_get_user(raw_token)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return user


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Ensures the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return current_user


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""
    async def role_checker(
        current_user: UserResponse = Depends(get_current_active_user),
    ) -> UserResponse:
        if current_user.is_superuser:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {allowed_roles}",
            )
        return current_user

    return role_checker
