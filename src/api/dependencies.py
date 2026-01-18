"""
API Dependencies

FastAPI dependencies for authentication and authorization.
"""

import os
from typing import Annotated
from uuid import UUID
import base64
import json

import structlog
from fastapi import Depends, HTTPException, Header
from jose import JWTError, jwt
from pydantic import BaseModel

from src.storage.database import get_database
from src.storage.repositories.user_repo import UserRepository
from src.models.user import User

logger = structlog.get_logger(__name__)

# Supabase JWT configuration
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"


class CurrentUser(BaseModel):
    """Current authenticated user."""
    id: UUID
    email: str
    tier: str
    full_name: str | None = None


def decode_jwt_payload_unsafe(token: str) -> dict:
    """Decode JWT payload without verification (for dev only!)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        # Add padding if needed
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return {}


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """
    Extract and validate user from Supabase JWT token.
    
    The token is passed in the Authorization header as: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]  # Remove "Bearer "

    try:
        payload = None
        
        # If JWT secret is configured, verify properly
        if SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                options={"verify_aud": False},
            )
        else:
            # Dev mode: decode without verification (WARNING: Not for production!)
            logger.warning("SUPABASE_JWT_SECRET not set - decoding token without verification (DEV ONLY)")
            payload = decode_jwt_payload_unsafe(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token format")

        # Extract user info from Supabase JWT
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload",
            )

        # Get user from database or create if new
        db = await get_database()
        user_repo = UserRepository(db)

        user = await user_repo.get_by_id(UUID(user_id))
        
        if not user:
            # Check if user exists by email (might have different ID)
            user = await user_repo.get_by_email(email)
            
            if not user:
                # Auto-create user on first login from Supabase
                from src.models.user import UserCreate, AuthProvider
                
                user_create = UserCreate(
                    email=email,
                    full_name=payload.get("user_metadata", {}).get("full_name"),
                    auth_provider=AuthProvider.OAUTH,
                )
                user = await user_repo.create(user_create)
                logger.info("Created new user from Supabase auth", user_id=str(user.id))

        return CurrentUser(
            id=user.id,
            email=user.email,
            tier=user.tier.value,
            full_name=user.full_name,
        )

    except JWTError as e:
        logger.warning("JWT verification failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )
    except Exception as e:
        logger.error("Authentication error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Authentication error",
        )
