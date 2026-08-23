"""Pydantic Schemas for Authentication, Authorization, and User Management."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserSignupRequest(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr = Field(..., description="User's unique email address")
    full_name: str = Field(..., min_length=2, max_length=150, description="Full name of the user")
    password: str = Field(..., min_length=6, max_length=128, description="User password (min 6 characters)")


class UserLoginRequest(BaseModel):
    """Payload for JSON-based login."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class UserResponse(BaseModel):
    """Public user profile representation."""

    id: str = Field(..., description="Unique User UUID")
    email: EmailStr = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="User's full name")
    is_active: bool = Field(default=True, description="Account active status")
    is_superuser: bool = Field(default=False, description="Superuser privilege status")
    role: str = Field(default="user", description="Assigned user role (user, admin, auditor)")
    created_at: Optional[datetime] = Field(default=None, description="Account registration timestamp")


class TokenResponse(BaseModel):
    """Response returned upon successful login."""

    access_token: str = Field(..., description="Signed JWT Bearer Access Token")
    token_type: str = Field(default="bearer", description="Token type (bearer)")
    expires_in_minutes: int = Field(default=60, description="Token validity window in minutes")
    user: UserResponse = Field(..., description="Authenticated user profile")


class ForgotPasswordRequest(BaseModel):
    """Payload to initiate a password reset request."""

    email: EmailStr = Field(..., description="Registered email address to send reset instructions")


class ResetPasswordRequest(BaseModel):
    """Payload to reset user password using a verified token."""

    token: str = Field(..., description="Password reset verification token")
    new_password: str = Field(..., min_length=6, max_length=128, description="New user password")


class MessageResponse(BaseModel):
    """Standard message response."""

    message: str = Field(..., description="Response or operation status message")
    status: str = Field(default="success", description="Status indicator")
