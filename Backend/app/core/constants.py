"""
Application Constants and Enums
"""
from enum import Enum


class RouteType(str, Enum):
    """
    Allowed route and schedule types.
    
    These types control access based on user roles:
    - STUDENT: Routes/schedules for student shuttles (mapped to student role)
    - STAFF: Routes/schedules for staff/faculty (mapped to staff role)
    - INTERNAL: Internal/administrative routes (special access)
    """
    STUDENT = "student"
    STAFF = "staff"
    INTERNAL = "internal"
    
    @classmethod
    def values(cls):
        """Get list of all valid values"""
        return [e.value for e in cls]
    
    @classmethod
    def get_for_user_role(cls, role: str) -> str:
        """
        Get the appropriate route type for a user role.
        
        Args:
            role: User role ('student' or 'staff')
            
        Returns:
            Corresponding route type
        """
        if role == "staff":
            return cls.STAFF.value
        return cls.STUDENT.value
