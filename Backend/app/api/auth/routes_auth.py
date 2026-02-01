from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import Union
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.core.logger import logger, log_request, log_success, log_error
from app.schemas.user import (
    UserSignup,
    OTPVerify,
    UserLogin,
    GoogleSignup,
    GoogleLogin,
    LinkGoogle,
    SetRole,
    SetPassword,
    ChangePassword,
    ForgotPassword,
    TokenResponse,
    LinkingRequiredResponse,
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
    Email + Password Signup - Creates account without role (onboarding required).
    
    Requirements:
    - Email must end with @flame.edu.in
    - Password must be at least 8 characters
    
    Process:
    1. Creates user account with auth_provider='password', role=NULL
    2. Sends 6-digit OTP to email
    3. User must verify email before login
    4. After login, user must set role via /auth/set-role endpoint
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


@router.post("/google-signup", response_model=TokenResponse)
async def google_signup(
    google_data: GoogleSignup,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Google Signup - First-time registration with Google OAuth.
    
    Creates new account with auth_provider='google'.
    User must complete onboarding (set role) after signup.
    
    Returns JWT with onboarding_required=True.
    """
    try:
        log_request("/auth/google-signup", "POST")
        result = await controllers_auth.signup_with_google(db, google_data)
        
        # Set HTTP-only cookie with JWT token
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        log_success("/auth/google-signup", f"Google signup: {google_data.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/google-signup", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during Google signup. Please try again."
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
    Email + Password Login.
    
    Works for users with auth_provider='password' or 'google+password'.
    Google-only users must use Google login.
    
    Returns JWT token in HTTP-only cookie and CSRF token in response.
    """
    try:
        log_request("/auth/login", "POST")
        result = await controllers_auth.login_with_password(db, credentials)
        
        # Set HTTP-only cookie with JWT token
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=not settings.DEBUG,
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


@router.post("/google-login", response_model=Union[TokenResponse, LinkingRequiredResponse])
async def google_login(
    google_data: GoogleLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Google OAuth Login for existing users.
    
    Behavior:
    - Google user with role → Normal login
    - Google user without role → Onboarding required
    - Password-only user → Linking required (secure flow)
    - No user → Redirect to signup
    
    Returns JWT token OR linking_required response.
    """
    try:
        log_request("/auth/google-login", "POST")
        result = await controllers_auth.login_with_google(db, google_data)
        
        # Only set cookie if login successful (not linking required)
        if "access_token" in result:
            response.set_cookie(
                key="access_token",
                value=result["access_token"],
                httponly=True,
                secure=not settings.DEBUG,
                samesite="lax",
                max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            log_success("/auth/google-login", f"User Google login: {google_data.email}")
        else:
            log_success("/auth/google-login", f"Linking required: {google_data.email}")
        
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


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    forgot_data: ForgotPassword,
    db: Session = Depends(get_db)
):
    """
    Initiate password reset process.
    
    Only works for users with passwords (auth_provider='password' or 'google+password').
    Google-only users cannot reset passwords.
    
    Sends password reset OTP to email if account exists and has password.
    """
    try:
        log_request("/auth/forgot-password", "POST")
        result = await controllers_auth.forgot_password(db, forgot_data)
        log_success("/auth/forgot-password", f"Password reset requested: {forgot_data.email}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/forgot-password", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


# ============ Protected Endpoints (Require Authentication) ============

@router.post("/set-role", response_model=TokenResponse)
async def set_role(
    role_data: SetRole,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Set user role during onboarding (one-time operation).
    
    Works for users who haven't set their role yet (both Google and email+password signups).
    After setting role, returns new JWT with role populated.
    
    Requires: JWT authentication
    """
    try:
        log_request("/auth/set-role", "POST")
        result = await controllers_auth.set_user_role(db, current_user["user_id"], role_data)
        
        # Update cookie with new token
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        log_success("/auth/set-role", f"Role set: {current_user['sub']} -> {role_data.role}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/set-role", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.post("/link-google", response_model=MessageResponse)
async def link_google(
    link_data: LinkGoogle,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Securely link Google account to existing password-based account.
    
    Requires password verification for security.
    Upgrades auth_provider from 'password' to 'google+password'.
    
    Requires: JWT authentication
    """
    try:
        log_request("/auth/link-google", "POST")
        result = await controllers_auth.link_google_to_account(db, current_user["user_id"], link_data)
        log_success("/auth/link-google", f"Google linked: {current_user['sub']}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/link-google", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.post("/set-password", response_model=MessageResponse)
async def set_password(
    password_data: SetPassword,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Set password for Google-only users.
    
    Enables email + password login for Google users.
    Upgrades auth_provider from 'google' to 'google+password'.
    
    Requires: JWT authentication
    """
    try:
        log_request("/auth/set-password", "POST")
        result = await controllers_auth.set_user_password(db, current_user["user_id"], password_data)
        log_success("/auth/set-password", f"Password set: {current_user['sub']}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/set-password", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Change password for users with existing passwords.
    
    Works for auth_provider='password' and 'google+password'.
    Requires current password verification.
    
    Requires: JWT authentication
    """
    try:
        log_request("/auth/change-password", "POST")
        result = await controllers_auth.change_user_password(db, current_user["user_id"], password_data)
        log_success("/auth/change-password", f"Password changed: {current_user['sub']}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error("POST /auth/change-password", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again."
        )
