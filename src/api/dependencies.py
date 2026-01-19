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
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
# Allow HS256, RS256, and ES256 for maximum compatibility with Supabase
ALLOWED_ALGORITHMS = ["HS256", "RS256", "ES256"]
if JWT_ALGORITHM not in ALLOWED_ALGORITHMS:
    ALLOWED_ALGORITHMS.append(JWT_ALGORITHM)
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
            try:
                # Debug: Peek at header and payload
                unverified_header = jwt.get_unverified_header(token)
                unverified_payload = decode_jwt_payload_unsafe(token)
                logger.debug(
                    "JWT Debug (Unverified)", 
                    header=unverified_header,
                    iss=unverified_payload.get("iss"),
                    sub=unverified_payload.get("sub")
                )

                # Try verification
                algorithms = ALLOWED_ALGORITHMS
                
                # If HS256 is used, the secret is a string, not a PEM
                if unverified_header.get("alg") == "HS256":
                    algorithms = ["HS256"]
                
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=algorithms,
                    options={"verify_aud": False},
                )
            except JWTError as e:
                # Fallback: If verification fails but we are in DEBUG, allow unverified for now
                # to let the user work, but log a loud warning.
                if DEBUG_MODE:
                    logger.warning("JWT verification FAILED, but allowing in DEBUG mode", error=str(e))
                    payload = unverified_payload
                else:
                    logger.warning(
                        "JWT verification failed",
                        error=str(e),
                        token_alg=unverified_header.get("alg"),
                        allowed_algorithms=ALLOWED_ALGORITHMS,
                    )
                    raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")
            except Exception as e:
                logger.error("Unexpected error during JWT verification", error=str(e))
                if DEBUG_MODE:
                    payload = unverified_payload
                else:
                    raise HTTPException(status_code=401, detail="Internal authentication error")
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
            if user:
                logger.info("Found user by email, ID mismatch with JWT sub", db_id=str(user.id), jwt_sub=user_id)
            
            if not user:
                # Auto-create user if not found
                logger.info("User not found, creating new account", email=email, id=user_id)
                from src.models.user import UserCreate, AuthProvider
                
                user_create = UserCreate(
                    email=email,
                    full_name=payload.get("user_metadata", {}).get("full_name"),
                    auth_provider=AuthProvider.OAUTH,
                )
                user = await user_repo.create(user_create, user_id=UUID(user_id))
                logger.info("Created new user from Supabase auth", user_id=str(user.id))

        from src.models.user import UserTier
        logger.info("Authentication successful", user_id=str(user.id), email=user.email)
        return CurrentUser(
            id=user.id,
            email=user.email,
            tier=UserTier(user.tier) if hasattr(user, 'tier') else UserTier.FREE,
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
