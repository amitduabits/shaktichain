"""
Authentication module for V2G Marketplace API.

Provides JWT-based authentication with bcrypt password hashing.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_database
from core.logging import (
    get_logger,
    LoggerFactory,
    set_user_context,
)
from core.metrics import (
    record_user_registration,
    record_user_login,
)

# JWT configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "v2g-marketplace-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Security scheme
security = HTTPBearer()

# Router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Logger
logger = LoggerFactory.get_auth_logger()


# === Schemas ===

class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = JWT_EXPIRY_HOURS * 3600


class UserResponse(BaseModel):
    """Schema for user response (without password)."""
    id: str
    email: str
    role: str
    created_at: str


# === Helper Functions ===

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, email: str, role: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("token_expired", message="JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("token_invalid", message="Invalid JWT token", error=str(e))
        return None


# === Dependencies ===

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user.

    Raises HTTPException if token is invalid or expired.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = get_database()
    user = db.get_user_by_id(payload["sub"])

    if user is None:
        logger.warning("user_not_found", user_id=payload["sub"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set user context for logging
    set_user_context(user["id"], user["email"])

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[dict]:
    """
    Dependency to optionally get the current user.

    Returns None if no token is provided or token is invalid.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        return None

    db = get_database()
    user = db.get_user_by_id(payload["sub"])

    if user:
        set_user_context(user["id"], user["email"])

    return user


# === Endpoints ===

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """
    Register a new user account.

    Returns a JWT token on successful registration.
    """
    db = get_database()

    # Check if email already exists
    existing_user = db.get_user_by_email(user_data.email)
    if existing_user:
        logger.info(
            "registration_failed",
            reason="email_exists",
            email=user_data.email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user with hashed password
    password_hash = hash_password(user_data.password)
    user_id = db.create_user({
        "email": user_data.email,
        "password_hash": password_hash,
        "role": "user",
    })

    # Record metrics
    record_user_registration()

    # Log successful registration
    logger.info(
        "user_registered",
        user_id=user_id,
        email=user_data.email,
    )

    # Generate token
    token = create_access_token(user_id, user_data.email, "user")

    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """
    Login with email and password.

    Returns a JWT token on successful authentication.
    """
    db = get_database()

    # Find user by email
    user = db.get_user_by_email(user_data.email)
    if user is None:
        # Record failed login
        record_user_login(success=False)
        logger.warning(
            "login_failed",
            reason="user_not_found",
            email=user_data.email,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(user_data.password, user["password_hash"]):
        # Record failed login
        record_user_login(success=False)
        logger.warning(
            "login_failed",
            reason="invalid_password",
            email=user_data.email,
            user_id=user["id"],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Record successful login
    record_user_login(success=True)

    # Log successful login
    logger.info(
        "user_logged_in",
        user_id=user["id"],
        email=user["email"],
    )

    # Generate token
    token = create_access_token(user["id"], user["email"], user["role"])

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's information.
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        created_at=current_user["created_at"],
    )
