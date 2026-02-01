from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Dict, Any, Union
from datetime import timedelta

from app.db import crud
from app.core.security import verify_password, get_password_hash, create_access_token, generate_csrf_token
from app.core.config import settings
from app.core.logger import logger
from app.services.email_service import email_service
from app.services.otp_service import generate_otp, is_otp_valid
from app.schemas.user import (
    UserSignup, OTPVerify, UserLogin, GoogleSignup, GoogleLogin, 
    LinkGoogle, SetRole, SetPassword, ChangePassword, ForgotPassword,
    UserResponse, TokenResponse, LinkingRequiredResponse
)


async def signup_user(db: Session, signup_data: UserSignup) -> Dict[str, Any]:
    """
    Handle email + password signup.
    Creates user with auth_provider='password', role=NULL (requires onboarding).
    Sends OTP for verification.
    
    Args:
        db: Database session
        signup_data: User signup data (email, password)
    
    Returns:
        Dict with message and user info
    """
    # Check if user already exists
    existing_user = crud.get_user_by_email(db, signup_data.email)
    if existing_user:
        if existing_user.is_email_verified:
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
    
    # Create new user with auth_provider='password', role=NULL (onboarding required)
    new_user = crud.create_user(
        db=db,
        email=signup_data.email,
        hashed_password=hashed_password,
        role=None,  # Role will be set via onboarding
        auth_provider="password",
        google_id=None,
        is_email_verified=False
    )
    
    # Generate and store OTP
    otp = generate_otp()
    crud.update_user_otp(db, new_user.id, otp)
    
    # Send OTP email
    email_sent = email_service.send_otp_email(signup_data.email, otp)
    
    if not email_sent:
        logger.warning(f"Failed to send OTP email during signup for: {signup_data.email}")
    
    logger.info(f"New user signed up: {signup_data.email} (onboarding required, provider: password)")
    
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
    
    if user.is_email_verified:
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
    
    if user.is_email_verified:
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
    Only works for users with auth_provider='password' or 'google+password'.
    
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
    
    # Check if user has a password (reject Google-only users)
    if user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses Google Sign-In. Please log in with Google."
        )
    
    # Check if user is email verified
    if not user.is_email_verified:
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
    
    # Check if onboarding is required (role is NULL)
    onboarding_required = user.role is None
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    
    # Create JWT token with user info
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role,
            "auth_provider": user.auth_provider,
            "onboarding_required": onboarding_required,
            "user_type": "user"  # To distinguish from admin tokens
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"User logged in: {user.email} (role: {user.role}, onboarding: {onboarding_required}, provider: {user.auth_provider})")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(user),
        "onboarding_required": onboarding_required
    }


async def signup_with_google(db: Session, google_data: GoogleSignup) -> Dict[str, Any]:
    """
    Handle first-time Google signup.
    Creates a new user with auth_provider='google', role=NULL (requires onboarding).
    
    Args:
        db: Database session
        google_data: Google OAuth token and user info
    
    Returns:
        Dict with access token and onboarding_required=True
    """
    # Check if user already exists by Google ID
    existing_google_user = crud.get_user_by_google_id(db, google_data.google_id)
    if existing_google_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This Google account is already registered. Please use login instead."
        )
    
    # Check if email already exists (password-based account)
    existing_email_user = crud.get_user_by_email(db, google_data.email)
    if existing_email_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please use the link-google endpoint to link accounts."
        )
    
    # Create new Google user with role=NULL
    new_user = crud.create_user(
        db=db,
        email=google_data.email,
        hashed_password=None,
        role=None,  # Role will be set via onboarding
        auth_provider="google",
        google_id=google_data.google_id,
        is_email_verified=True  # Google users are pre-verified
    )
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    
    # Create JWT token with onboarding_required flag
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": new_user.email,
            "user_id": new_user.id,
            "role": None,  # No role yet
            "auth_provider": new_user.auth_provider,
            "onboarding_required": True,
            "user_type": "user"
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"New Google user signed up: {new_user.email} (onboarding required)")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(new_user),
        "onboarding_required": True
    }


async def login_with_google(db: Session, google_data: GoogleLogin) -> Union[Dict[str, Any], LinkingRequiredResponse]:
    """
    Handle Google login for existing users.
    Returns different responses based on account state:
    - Google user with role -> Normal login
    - Google user without role -> Onboarding required
    - Password user -> Linking required (security check)
    - No user -> Redirect to signup
    
    Args:
        db: Database session
        google_data: Google OAuth token and user info
    
    Returns:
        Dict with access token OR linking required response
    """
    # Check if user exists by Google ID
    user = crud.get_user_by_google_id(db, google_data.google_id)
    
    if not user:
        # Check if email exists (password-based account)
        user = crud.get_user_by_email(db, google_data.email)
        
        if not user:
            # No account exists
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this Google account. Please sign up first."
            )
        
        # User exists but Google not linked - require secure linking
        if user.hashed_password is not None:
            logger.info(f"Google login attempted for password account: {user.email} - linking required")
            return LinkingRequiredResponse(
                message="An account with this email exists. Please link your Google account by providing your password.",
                linking_required=True,
                email=user.email
            ).dict()
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact administrator."
        )
    
    # Check if onboarding is required (role is NULL)
    onboarding_required = user.role is None
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    
    # Create JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "role": user.role,
            "auth_provider": user.auth_provider,
            "onboarding_required": onboarding_required,
            "user_type": "user"
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"User logged in via Google: {user.email} (role: {user.role}, onboarding: {onboarding_required})")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(user),
        "onboarding_required": onboarding_required
    }


async def link_google_to_account(db: Session, user_id: int, link_data: LinkGoogle) -> Dict[str, Any]:
    """
    Securely link Google account to existing password-based account.
    Requires password verification for security.
    
    Args:
        db: Database session
        user_id: Current user ID (from JWT)
        link_data: Google credentials and current password
    
    Returns:
        Dict with success message and updated user info
    """
    # Get current user
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if Google already linked
    if user.google_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account is already linked to this account"
        )
    
    # Check if user has password
    if user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account does not have a password. Use set-password endpoint instead."
        )
    
    # Verify password for security
    if not verify_password(link_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password. Cannot link Google account."
        )
    
    # Check if Google ID is already used by another account
    existing_google_user = crud.get_user_by_google_id(db, link_data.google_id)
    if existing_google_user and existing_google_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This Google account is already linked to another user"
        )
    
    # Link Google account
    updated_user = crud.link_google_account(db, user_id, link_data.google_id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link Google account"
        )
    
    logger.info(f"Google account linked: {updated_user.email} (provider: {updated_user.auth_provider})")
    
    return {
        "message": "Google account linked successfully. You can now log in with Google.",
        "auth_provider": updated_user.auth_provider
    }


async def set_user_role(db: Session, user_id: int, role_data: SetRole) -> Dict[str, Any]:
    """
    Set user role during onboarding (one-time operation).
    Only works if role is currently NULL.
    Works for both Google and password-based signups.
    
    Args:
        db: Database session
        user_id: User ID from JWT
        role_data: Role to set
    
    Returns:
        Dict with new access token containing role
    """
    # Get user
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if role is already set
    if user.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role is already set and cannot be changed via this endpoint"
        )
    
    # Set role
    updated_user = crud.set_user_role(db, user_id, role_data.role)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set role"
        )
    
    # Generate new JWT with role
    csrf_token = generate_csrf_token()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": updated_user.email,
            "user_id": updated_user.id,
            "role": updated_user.role,
            "auth_provider": updated_user.auth_provider,
            "onboarding_required": False,
            "user_type": "user"
        },
        expires_delta=access_token_expires,
        csrf_token=csrf_token
    )
    
    logger.info(f"User role set: {updated_user.email} -> {updated_user.role}")
    
    return {
        "message": "Role set successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": UserResponse.from_orm(updated_user)
    }


async def set_user_password(db: Session, user_id: int, password_data: SetPassword) -> Dict[str, Any]:
    """
    Set password for Google-only users (enables hybrid auth).
    Upgrades auth_provider from 'google' to 'google+password'.
    
    Args:
        db: Database session
        user_id: User ID from JWT
        password_data: New password
    
    Returns:
        Dict with success message
    """
    # Get user
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if password already exists
    if user.hashed_password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is already set. Use change-password endpoint to update it."
        )
    
    # Hash and set password
    hashed_password = get_password_hash(password_data.password)
    updated_user = crud.set_user_password(db, user_id, hashed_password)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set password"
        )
    
    logger.info(f"Password set for user: {updated_user.email} (provider: {updated_user.auth_provider})")
    
    return {
        "message": "Password set successfully. You can now log in with email and password.",
        "auth_provider": updated_user.auth_provider
    }


async def change_user_password(db: Session, user_id: int, password_data: ChangePassword) -> Dict[str, Any]:
    """
    Change password for users with existing passwords.
    Works for auth_provider='password' and 'google+password'.
    
    Args:
        db: Database session
        user_id: User ID from JWT
        password_data: Current and new passwords
    
    Returns:
        Dict with success message
    """
    # Get user
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user has a password
    if user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password is set. Use set-password endpoint first."
        )
    
    # Verify current password
    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Check new password is different
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Hash and update password
    new_hashed_password = get_password_hash(password_data.new_password)
    updated_user = crud.update_user_password(db, user_id, new_hashed_password)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
    
    logger.info(f"Password changed for user: {updated_user.email}")
    
    return {
        "message": "Password updated successfully"
    }


async def forgot_password(db: Session, forgot_data: ForgotPassword) -> Dict[str, Any]:
    """
    Initiate password reset process.
    Only works for users with auth_provider='password' or 'google+password'.
    Google-only users cannot reset password.
    
    Args:
        db: Database session
        forgot_data: Email address
    
    Returns:
        Dict with success message
    """
    # Get user
    user = crud.get_user_by_email(db, forgot_data.email)
    
    # Security: Always return success message (don't reveal if email exists)
    success_message = {
        "message": "If an account with this email exists and has a password, a reset link will be sent."
    }
    
    if not user:
        logger.info(f"Password reset requested for non-existent email: {forgot_data.email}")
        return success_message
    
    # Check if user has a password
    if user.hashed_password is None:
        logger.info(f"Password reset requested for Google-only user: {forgot_data.email}")
        # Still return success for security, but don't send email
        return success_message
    
    # Generate password reset token (OTP-based for simplicity)
    reset_token = generate_otp()
    crud.update_user_otp(db, user.id, reset_token)
    
    # Send password reset email
    email_sent = email_service.send_otp_email(
        forgot_data.email, 
        reset_token,
        subject="Password Reset Request"
    )
    
    if email_sent:
        logger.info(f"Password reset email sent to: {forgot_data.email}")
    else:
        logger.error(f"Failed to send password reset email to: {forgot_data.email}")
    
    return success_message
