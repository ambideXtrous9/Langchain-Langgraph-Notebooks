"""Security and Cryptographic Utilities (Argon2 Password Hashing & PyJWT Tokens)."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError
from pwdlib import PasswordHash
from app.core.config import settings

logger = logging.getLogger(__name__)

# Modern OWASP-recommended Argon2id password hasher via pwdlib
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    try:
        return password_hasher.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a signed JWT access token with unique jti and expiration timestamp."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    # Add standard claims
    to_encode.update({
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "token_type": "access",
    })

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_reset_token(
    email: str,
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates a short-lived cryptographic password reset token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES))

    payload = {
        "sub": email,
        "user_id": str(user_id),
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "token_type": "reset_password",
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token signature and expiration."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")
    except PyJWTError as e:
        raise ValueError(f"Token decoding error: {str(e)}")
