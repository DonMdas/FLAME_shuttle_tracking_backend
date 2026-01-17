from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Dict, Any
from datetime import timedelta

from app.db import crud
from app.core.security import verify_password, get_password_hash, create_access_token, generate_csrf_token
from app.core.config import settings
from app.core.logger import logger
from app.services.email_service import email_service
from app.services.otp_service import generate_otp, is_otp_valid
from app.schemas.user import UserSignup, OTPVerify, UserLogin, GoogleLogin, UserResponse


async def signup_user(db: Session, signup_data: UserSignup) -> Dict[str, Any]:
    """
    Handle user signup: create user account and send OTP verification email.
    
    Args:
        db: Database session
        signup_data: User signup data (email, password, role)
    
    Returns:
        Dict with message and user info
    """
    # Check if user already exists
    existing_user = crud.get_user_by_email(db, signup_data.email)
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists"
            )
        else:
            # User exists but not verified, resend OTP
            otp = generate_otp()
            crud.update_user_otp(db, existing_user.id, otp)
            
            # Send OTP email
            email_sent = email_service.send_otp_email(signup_data.email, otp)
            
            if email_sent:
                logger.info(f"OTP resent to existing unverified user: {signup_data.email}")
                return {
                    "message": "Account exists but not verified. New OTP sent to your email.",
                    "email": signup_data.email,
                    "requires_verification": True
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP email. Please try again."
                )
    
    # Hash password
    hashed_password = get_password_hash(signup_data.password)
    
    # Create new user
    new_user = crud.create_user(
        db=db,
        email=signup_data.email,
        hashed_password=hashed_password,
        role=signup_data.role
    )
    
    # Generate and store OTP
    otp = generate_otp()
    crud.update_user_otp(db, new_user.id, otp)
    
    # Send OTP email
    email_sent = email_service.send_otp_email(signup_data.email, otp)
    
    if not email_sent:
        # If email fails, we don't delete the user, they can request resend
        logger.warning(f"Failed to send OTP email during signup for: {signup_data.email}")
    
    logger.info(f"New user signed up: {signup_data.email} (role: {signup_data.role})")
    
    return {
        "message": "Signup successful! Please check your email for the OTP to verify your account.",
        "email": new_user.email,
        "requires_verification": True
    }


async def verify_otp(db: Session, verify_data: OTPVerify) -> Dict[str, Any]:
    """
    Verify user's email using OTP.
    
    Args:
        db: Database session
        verify_data: Email and OTP
    
    Returns:
        Dict with success message and user info
    """
    # Get user by email
    user = crud.get_user_by_email(db, verify_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified. You can login now."
        )
    
    # Check if OTP exists
    if not user.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found. Please request a new one."
        )
    
    # Verify OTP validity (10 minutes)
    if not is_otp_valid(user.otp_created_at, validity_minutes=10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one."
        )
    
    # Check if OTP matches
    if user.otp != verify_data.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please try again."
        )
    
    # Mark user as verified
    crud.verify_user(db, user.id)
    
    logger.info(f"User email verified: {user.email}")
    
    return {
        "message": "Email verified successfully! You can now login.",
        "email": user.email
    }


async def resend_otp(db: Session, email: str) -> Dict[str, Any]:
    """
    Resend OTP to user's email.
    
    Args:
        db: Database session
        email: User's email
    
    Returns:
        Dict with success message
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate new OTP
    otp = generate_otp()
    crud.update_user_otp(db, user.id, otp)
    
    # Send OTP email
    email_sent = email_service.send_otp_email(email, otp)
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email. Please try again."
        )
    
    logger.info(f"OTP resent to: {email}")
    
    return {
        "message": "OTP sent successfully to your email"
    }


async def login_with_password(db: Session, login_data: UserLogin) -> Dict[str, Any]:
    """
    Handle user login with email and password.
    
    Args:
        db: Database session
        login_data: Email and password
    
    Returns:
        Dict with access token and user info
    """
    # Get user by email
    user = crud.get_user_by_email(db, login_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first."
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact administrator."
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    
    # Create JWT token with user info
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role,
            "user_type": "user"  # To distinguish from admin tokens
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"User logged in: {user.email} (role: {user.role})")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(user)
    }


async def login_with_google(db: Session, google_data: GoogleLogin) -> Dict[str, Any]:
    """
    Handle user login with Google OAuth.
    User must have signed up first - Google login doesn't auto-create accounts.
    
    Args:
        db: Database session
        google_data: Google OAuth token and user info
    
    Returns:
        Dict with access token and user info
    """
    # Check if user exists by Google ID
    user = crud.get_user_by_google_id(db, google_data.google_id)
    
    if not user:
        # Check if user exists by email but hasn't linked Google
        user = crud.get_user_by_email(db, google_data.email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this Google account. Please sign up first."
            )
        
        # Link Google ID to existing account
        user.google_id = google_data.google_id
        db.commit()
        db.refresh(user)
        logger.info(f"Google account linked: {user.email}")
    
    # Check if user is verified (should be if using Google)
    if not user.is_verified:
        # Auto-verify Google users
        crud.verify_user(db, user.id)
        logger.info(f"User auto-verified via Google: {user.email}")
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact administrator."
        )
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    
    # Create JWT token with user info
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role,
            "user_type": "user"
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"User logged in via Google: {user.email} (role: {user.role})")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(user)
    }
