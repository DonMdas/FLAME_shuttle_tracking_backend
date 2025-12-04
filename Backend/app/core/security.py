from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import secrets
from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logger import logger, log_auth_attempt

# JWT Bearer token scheme (for backwards compatibility)
security = HTTPBearer(auto_error=False)

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


def generate_csrf_token() -> str:
    """Generate a secure CSRF token"""
    return secrets.token_urlsafe(32)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        result = bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        return result
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, csrf_token: Optional[str] = None) -> str:
    """Create a JWT access token with optional CSRF token"""
    to_encode = data.copy()
    
    # Use UTC for JWT expiration
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # JWT expects Unix timestamp
    to_encode.update({"exp": expire})
    
    # Add CSRF token to JWT if provided (for cookie-based auth)
    if csrf_token:
        to_encode.update({"csrf": csrf_token})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token verification failed: Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        logger.warning(f"Token verification failed: Invalid claims - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning(f"Token verification failed: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user.
    Supports both cookie-based (preferred) and bearer token authentication.
    Returns user info with role (super_admin or admin).
    """
    token = None
    
    # Try cookie first (preferred method)
    if access_token:
        token = access_token
        logger.debug(f"Authentication via cookie for {request.method} {request.url.path}")
    # Fallback to bearer token for backwards compatibility
    elif credentials:
        token = credentials.credentials
        logger.debug(f"Authentication via Bearer token for {request.method} {request.url.path}")
    
    if not token:
        logger.warning(f"No authentication credentials provided for {request.method} {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    
    # Verify CSRF token for cookie-based auth on state-changing operations
    if access_token and request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        jwt_csrf = payload.get("csrf")
        header_csrf = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")
        
        # Only enforce CSRF if JWT has a csrf token (cookie-based auth)
        if jwt_csrf:
            # Skip CSRF validation in DEBUG mode for Swagger UI testing
            if settings.DEBUG:
                if not header_csrf:
                    logger.debug(f"CSRF check skipped (DEBUG mode) for {request.method} {request.url.path}")
            else:
                # Production: enforce CSRF
                if not header_csrf:
                    logger.warning(f"CSRF token missing for {request.method} {request.url.path}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CSRF token is required. Please include X-CSRF-Token header."
                    )
                if jwt_csrf != header_csrf:
                    logger.warning(f"CSRF token mismatch for user {payload.get('sub')} - {request.method} {request.url.path}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CSRF token is invalid or has expired. Please logout and login again."
                    )
    
    username: str = payload.get("sub")
    role: str = payload.get("role", "admin")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"username": username, "role": role, "csrf_token": payload.get("csrf")}


async def get_current_user_no_csrf(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user WITHOUT CSRF validation.
    Use this for low-risk operations like logout or GET requests.
    """
    token = None
    
    # Try cookie first (preferred method)
    if access_token:
        token = access_token
        logger.debug(f"Authentication via cookie for {request.method} {request.url.path}")
    # Fallback to bearer token for backwards compatibility
    elif credentials:
        token = credentials.credentials
        logger.debug(f"Authentication via Bearer token for {request.method} {request.url.path}")
    
    if not token:
        logger.warning(f"No authentication credentials provided for {request.method} {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    username: str = payload.get("sub")
    role: str = payload.get("role", "admin")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"username": username, "role": role, "csrf_token": payload.get("csrf")}


async def get_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to ensure user is Super Admin.
    Use this for Super Admin-only endpoints.
    """
    if current_user.get("role") != "super_admin":
        logger.warning(f"Access denied: User '{current_user.get('username')}' (role: {current_user.get('role')}) attempted to access Super Admin endpoint")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required. This operation is restricted to Super Admin users only."
        )
    return current_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user (Super Admin from .env or normal admin from DB).
    Returns user dict with role if authenticated, None otherwise.
    """
    try:
        # Check if it's the Super Admin (from .env)
        if username == settings.ADMIN_USERNAME:
            if password == settings.ADMIN_PASSWORD:
                log_auth_attempt(username, success=True)
                logger.info(f"Super Admin '{username}' authenticated successfully")
                return {"username": username, "role": "super_admin"}
            else:
                log_auth_attempt(username, success=False, reason="Invalid password for Super Admin")
                return None
        
        # Check database for normal admins
        from app.db import crud
        db_admin = crud.get_admin_by_username(db, username)
        
        if not db_admin:
            log_auth_attempt(username, success=False, reason="Username not found in database")
            return None
        
        if not db_admin.is_active:
            log_auth_attempt(username, success=False, reason="Account is disabled")
            logger.warning(f"Login attempt for disabled account: {username}")
            return None
        
        if verify_password(password, db_admin.hashed_password):
            log_auth_attempt(username, success=True)
            logger.info(f"Admin '{username}' authenticated successfully")
            return {"username": username, "role": "admin"}
        else:
            log_auth_attempt(username, success=False, reason="Invalid password")
            return None
            
    except Exception as e:
        logger.error(f"Authentication error for user '{username}': {type(e).__name__} - {str(e)}", exc_info=True)
        return None


def authenticate_admin(username: str, password: str) -> Optional[dict]:
    """
    Legacy function - authenticate only Super Admin from .env.
    Kept for backward compatibility.
    """
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return {"username": username, "role": "super_admin"}
    return None
