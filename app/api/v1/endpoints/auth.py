"""Authentication and User Management Endpoints (OAuth2, JWT, Argon2, Password Reset)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.deps import get_current_active_user, oauth2_scheme
from app.core.auth_database import auth_db_manager
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & Access"])


# ------------------------------------------------------------------------------
# 1. User Registration (Sign Up)
# ------------------------------------------------------------------------------
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with Argon2id password hashing.",
)
async def signup_endpoint(request: UserSignupRequest):
    """Registers a new user in auth_db."""
    existing_user = await auth_db_manager.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Hash password using modern Argon2id
    hashed_pwd = hash_password(request.password)

    user_dict = await auth_db_manager.create_user(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hashed_pwd,
        role="user",
    )

    logger.info(f"User signed up successfully: {request.email} (ID: {user_dict['id']})")
    return UserResponse(
        id=user_dict["id"],
        email=user_dict["email"],
        full_name=user_dict["full_name"],
        is_active=user_dict["is_active"],
        is_superuser=user_dict["is_superuser"],
        role=user_dict["role"],
        created_at=user_dict["created_at"],
    )


# ------------------------------------------------------------------------------
# 2. User Login (OAuth2 Form & JSON Support)
# ------------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT token",
    description="Authenticates user credentials and returns a signed JWT Bearer token. Compatible with OAuth2 password form and JSON requests.",
)
async def login_endpoint(
    request: Request,
):
    """Authenticates credentials from OAuth2 form data (username=email) or JSON payload."""
    email = None
    password = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            email = (body.get("email") or body.get("username") or "").strip().lower()
            password = body.get("password") or ""
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            email = (form.get("username") or form.get("email") or "").strip().lower()
            password = form.get("password") or ""
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    user_dict = await auth_db_manager.get_user_by_email(email)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Account not found; please click the 'Register' tab to create an account.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user_dict["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Please verify your password or use 'Forgot Password'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_dict.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact support.",
        )

    # Issue JWT Access Token
    token_payload = {
        "sub": user_dict["email"],
        "user_id": str(user_dict["id"]),
        "role": user_dict.get("role", "user"),
    }
    access_token = create_access_token(
        data=token_payload,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    user_response = UserResponse(
        id=str(user_dict["id"]),
        email=user_dict["email"],
        full_name=user_dict.get("full_name"),
        is_active=user_dict.get("is_active", True),
        is_superuser=user_dict.get("is_superuser", False),
        role=user_dict.get("role", "user"),
        created_at=user_dict.get("created_at"),
    )

    logger.info(f"User logged in successfully: {email}")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user_response,
    )


# ------------------------------------------------------------------------------
# 3. Get Current Authenticated User Profile
# ------------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile details of the currently authenticated user.",
)
async def get_me_endpoint(
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Returns profile of currently authenticated user."""
    return current_user


# ------------------------------------------------------------------------------
# 4. User Logout & Token Revocation
# ------------------------------------------------------------------------------
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke JWT token (Logout)",
    description="Revokes the current JWT Bearer token and adds it to the token blacklist.",
)
async def logout_endpoint(
    token: str = Depends(oauth2_scheme),
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Revokes the current user's token."""
    try:
        payload = decode_token(token)
        token_jti = payload.get("jti")
        exp_timestamp = payload.get("exp")

        if token_jti and exp_timestamp:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            await auth_db_manager.blacklist_token(
                token_jti=token_jti,
                user_id=current_user.id,
                expires_at=expires_at,
            )
    except Exception as e:
        logger.warning(f"Logout token decoding note: {e}")

    logger.info(f"User logged out successfully: {current_user.email}")
    return MessageResponse(
        message="Successfully logged out. Your token has been revoked.",
        status="success",
    )


# ------------------------------------------------------------------------------
# 5. Forgot Password (Initiate Reset Request)
# ------------------------------------------------------------------------------
@router.post(
    "/forgot-password",
    summary="Request a password reset token",
    description="Generates a cryptographically secure, 15-minute time-limited password reset token.",
)
async def forgot_password_endpoint(request: ForgotPasswordRequest):
    """Generates password reset token if user exists."""
    user_dict = await auth_db_manager.get_user_by_email(request.email)

    if not user_dict:
        # Prevent account enumeration attack
        return {
            "message": "If this email address is registered, password reset instructions have been generated.",
            "status": "success",
        }

    # Generate 15-minute reset token
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    reset_token = create_reset_token(
        email=user_dict["email"],
        user_id=str(user_dict["id"]),
        expires_delta=timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
    )

    # Store token hash in auth_db
    await auth_db_manager.store_reset_token(
        user_id=str(user_dict["id"]),
        token_str=reset_token,
        expires_at=expires_at,
    )

    logger.info(f"Password reset token issued for: {request.email}")
    return {
        "message": "Password reset token generated successfully. Use this token with /auth/reset-password.",
        "status": "success",
        "reset_token": reset_token,
        "expires_in_minutes": settings.RESET_TOKEN_EXPIRE_MINUTES,
    }


# ------------------------------------------------------------------------------
# 6. Reset Password (Update Credentials)
# ------------------------------------------------------------------------------
@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    description="Validates the reset token and updates the user's password using Argon2id.",
)
async def reset_password_endpoint(request: ResetPasswordRequest):
    """Verifies reset token and updates user password."""
    # 1. Decode token to verify signature and expiry
    try:
        payload = decode_token(request.token)
        if payload.get("token_type") != "reset_password":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type: expected password reset token.",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired reset token: {str(e)}",
        )

    # 2. Check and consume token in auth_db
    user_id = await auth_db_manager.verify_and_consume_reset_token(request.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid, expired, or has already been used.",
        )

    # 3. Hash new password and update record
    new_hashed_pwd = hash_password(request.new_password)
    updated = await auth_db_manager.update_user_password(user_id, new_hashed_pwd)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password. Please try again.",
        )

    logger.info(f"Password updated successfully for User ID: {user_id}")
    return MessageResponse(
        message="Password reset successfully. You can now log in with your new credentials.",
        status="success",
    )
