from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.core.config import settings
from app.core.logger import logger, log_request, log_success, log_error
from app.schemas.user import (
    UserSignup,
    OTPVerify,
    UserLogin,
    GoogleLogin,
    TokenResponse,
    MessageResponse
)
from app.api.auth import controllers_auth

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============ Public Authentication Endpoints (No Auth Required) ============

@router.post("/signup", response_model=MessageResponse)
async def signup(
    signup_data: UserSignup,
    db: Session = Depends(get_db)
):
    """
    User signup endpoint - creates account and sends OTP verification email.
    
    Requirements:
    - Email must end with @flame.edu.in
    - Password must be at least 8 characters
    - Role must be "student" or "staff"
    
    Process:
    1. Creates user account (unverified)
    2. Sends 6-digit OTP to email
    3. User must verify email before login
    """
    try:
        log_request("/auth/signup", "POST")
        result = await controllers_auth.signup_user(db, signup_data)
        log_success("/auth/signup", f"User signup: {signup_data.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/signup", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during signup. Please try again."
        )


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(
    verify_data: OTPVerify,
    db: Session = Depends(get_db)
):
    """
    Verify email using OTP sent during signup.
    
    OTP is valid for 10 minutes.
    After verification, user can login.
    """
    try:
        log_request("/auth/verify-otp", "POST")
        result = await controllers_auth.verify_otp(db, verify_data)
        log_success("/auth/verify-otp", f"OTP verified: {verify_data.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/verify-otp", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during verification. Please try again."
        )


class ResendOTPRequest(BaseModel):
    """Request model for resending OTP"""
    email: EmailStr


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(
    request: ResendOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Resend OTP to user's email.
    Use this if OTP expired or wasn't received.
    """
    try:
        log_request("/auth/resend-otp", "POST")
        result = await controllers_auth.resend_otp(db, request.email)
        log_success("/auth/resend-otp", f"OTP resent: {request.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/resend-otp", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login with email and password.
    
    Returns JWT token in HTTP-only cookie and CSRF token in response.
    Include CSRF token in X-CSRF-Token header for subsequent requests.
    """
    try:
        log_request("/auth/login", "POST")
        result = await controllers_auth.login_with_password(db, credentials)
        
        # Set HTTP-only cookie with JWT token
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=not settings.DEBUG,  # HTTPS only in production
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        log_success("/auth/login", f"User login: {credentials.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/login", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again."
        )


@router.post("/google-login", response_model=TokenResponse)
async def google_login(
    google_data: GoogleLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login with Google OAuth.
    
    Note: User must have signed up first. Google login does NOT auto-create accounts.
    If account doesn't exist, user must sign up first with their role (student/staff).
    
    Returns JWT token in HTTP-only cookie and CSRF token in response.
    """
    try:
        log_request("/auth/google-login", "POST")
        result = await controllers_auth.login_with_google(db, google_data)
        
        # Set HTTP-only cookie with JWT token
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=not settings.DEBUG,  # HTTPS only in production
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        log_success("/auth/google-login", f"User Google login: {google_data.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/google-login", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during Google login. Please try again."
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    """
    User logout - clears authentication cookie.
    No authentication required.
    """
    try:
        log_request("/auth/logout", "POST")
        
        # Clear the access token cookie
        response.delete_cookie(
            key="access_token",
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        
        log_success("/auth/logout", "User logout")
        return {"message": "Logged out successfully"}
    except Exception as e:
        log_error("POST /auth/logout", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout. Please try again."
        )
