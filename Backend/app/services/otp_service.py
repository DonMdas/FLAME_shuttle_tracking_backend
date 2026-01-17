import random
import string
from datetime import datetime, timedelta, timezone


# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def is_otp_valid(otp_created_at: datetime, validity_minutes: int = 10) -> bool:
    """
    Check if OTP is still valid (within validity period).
    
    Args:
        otp_created_at: DateTime when OTP was created
        validity_minutes: OTP validity period in minutes (default: 10)
    
    Returns:
        bool: True if OTP is still valid, False otherwise
    """
    if not otp_created_at:
        return False
    
    # Ensure both datetimes are timezone-aware for comparison
    now = datetime.now(IST)
    
    # If otp_created_at is naive (no timezone), make it IST-aware
    if otp_created_at.tzinfo is None:
        otp_created_at = otp_created_at.replace(tzinfo=IST)
    
    expiry_time = otp_created_at + timedelta(minutes=validity_minutes)
    
    return now <= expiry_time


def get_otp_expiry_time(otp_created_at: datetime, validity_minutes: int = 10) -> datetime:
    """
    Get the expiry time for an OTP.
    
    Args:
        otp_created_at: DateTime when OTP was created
        validity_minutes: OTP validity period in minutes (default: 10)
    
    Returns:
        datetime: Expiry time of the OTP
    """
    return otp_created_at + timedelta(minutes=validity_minutes)
