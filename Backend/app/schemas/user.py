from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserSignup(BaseModel):
    """Schema for user signup request"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: str = Field(..., description="User role: student or staff")
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Ensure email is from @flame.edu.in domain"""
        if not v.endswith('@flame.edu.in'):
            raise ValueError('Email must be from @flame.edu.in domain')
        return v.lower()
    
    @validator('role')
    def validate_role(cls, v):
        """Ensure role is either student or staff"""
        if v.lower() not in ['student', 'staff']:
            raise ValueError('Role must be either "student" or "staff"')
        return v.lower()


class OTPVerify(BaseModel):
    """Schema for OTP verification request"""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")


class UserLogin(BaseModel):
    """Schema for email + password login"""
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    """Schema for Google OAuth login"""
    google_token: str = Field(..., description="Google OAuth ID token")
    google_id: str = Field(..., description="Google user ID")
    email: EmailStr


class UserResponse(BaseModel):
    """Schema for user response (public info)"""
    id: int
    email: str
    role: str
    is_verified: bool
    is_active: bool
    google_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for admin updating user role"""
    role: str
    
    @validator('role')
    def validate_role(cls, v):
        """Ensure role is either student or staff"""
        if v.lower() not in ['student', 'staff']:
            raise ValueError('Role must be either "student" or "staff"')
        return v.lower()


class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str
    token_type: str = "bearer"
    csrf_token: Optional[str] = None
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
