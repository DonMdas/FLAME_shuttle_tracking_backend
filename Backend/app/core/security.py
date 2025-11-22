from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from core.config import settings

# JWT Bearer token scheme
security = HTTPBearer()

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = get_ist_now() + expires_delta
    else:
        expire = get_ist_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get the current authenticated user.
    Returns user info with role (super_admin or admin).
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    username: str = payload.get("sub")
    role: str = payload.get("role", "admin")
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"username": username, "role": role}


async def get_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to ensure user is Super Admin.
    Use this for Super Admin-only endpoints.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user (Super Admin from .env or normal admin from DB).
    Returns user dict with role if authenticated, None otherwise.
    """
    # Check if it's the Super Admin (from .env)
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return {"username": username, "role": "super_admin"}
    
    # Check database for normal admins
    from db import crud
    db_admin = crud.get_admin_by_username(db, username)
    
    if db_admin and db_admin.is_active and verify_password(password, db_admin.hashed_password):
        return {"username": username, "role": "admin"}
    
    return None


def authenticate_admin(username: str, password: str) -> Optional[dict]:
    """
    Legacy function - authenticate only Super Admin from .env.
    Kept for backward compatibility.
    """
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return {"username": username, "role": "super_admin"}
    return None
