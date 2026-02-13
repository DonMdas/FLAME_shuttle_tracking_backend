from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from datetime import datetime, time, date
from app.core.constants import RouteType


# ============ Admin Schemas ============

class AdminCreate(BaseModel):
    """Schema for creating a new admin (Super Admin only)"""
    username: str
    password: str


class AdminResponse(BaseModel):
    """Admin response schema (without password)"""
    id: int
    username: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Admin Login ============

class AdminLogin(BaseModel):
    """Admin login request"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


# ============ Vehicle Schemas ============

class VehicleBase(BaseModel):
    """Base vehicle schema"""
    name: str
    label: Optional[str] = None
    is_active: bool = True


class VehicleCreate(VehicleBase):
    """
    Schema for creating a vehicle (DEPRECATED - vehicles are now synced from API)
    """
    device_unique_id: str
    company_name: Optional[str] = None


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle (admin can only update label and is_active)"""
    label: Optional[str] = None
    is_active: Optional[bool] = None


class VehicleAdmin(VehicleBase):
    """Full vehicle schema (admin view - includes all data)"""
    vehicle_id: int
    device_unique_id: str
    company_name: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_speed: Optional[float] = None
    last_fix_time: Optional[datetime] = None
    last_server_time: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VehicleSyncResponse(BaseModel):
    """Response from vehicle sync operation"""
    success: bool
    vehicles_synced: Optional[int] = None
    new_vehicles: Optional[int] = None
    updated_vehicles: Optional[int] = None
    timestamp: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class VehiclePublic(BaseModel):
    """Public vehicle schema (client view - no sensitive data)"""
    vehicle_id: int
    name: str
    label: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_speed: Optional[float] = None
    last_updated: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Schedule Schemas ============

class ScheduleDayBase(BaseModel):
    """Base schema for schedule day"""
    day_of_week: str
    
    @validator('day_of_week')
    def validate_day_of_week(cls, v):
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if v.lower() not in valid_days:
            raise ValueError(f'day_of_week must be one of {valid_days}')
        return v.lower()


class ScheduleDayResponse(ScheduleDayBase):
    """Schedule day response with ID"""
    id: int
    schedule_id: int
    
    class Config:
        from_attributes = True


class ScheduleBase(BaseModel):
    """Base schedule schema"""
    vehicle_id: int
    start_time: time  # Changed from datetime to time (e.g., 08:00:00)
    route_id: int  # Route ID from the routes table
    schedule_type: RouteType = RouteType.STUDENT  # Type: "student", "staff", or "internal"
    is_active: bool = True
    is_recurring: bool = False
    start_date: Optional[date] = None  # Start date for recurring or execution date for one-time
    end_date: Optional[date] = None  # End date for recurring (NULL = no end)


class ScheduleCreate(ScheduleBase):
    """Schema for creating a schedule (admin only)"""
    repeat_days: Optional[List[str]] = Field(default_factory=list)  # ['monday', 'wednesday', 'friday']
    
    @validator('repeat_days')
    def validate_repeat_days(cls, v, values):
        """Validate repeat_days based on is_recurring"""
        is_recurring = values.get('is_recurring', False)
        
        if is_recurring and not v:
            raise ValueError('repeat_days required when is_recurring=True')
        
        if not is_recurring and v:
            raise ValueError('repeat_days should be empty when is_recurring=False')
        
        if v:
            valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day in v:
                if day.lower() not in valid_days:
                    raise ValueError(f'Invalid day: {day}. Must be one of {valid_days}')
        
        return [day.lower() for day in v] if v else []


class ScheduleUpdate(BaseModel):
    """Schema for updating a schedule (admin only)"""
    vehicle_id: Optional[int] = None
    start_time: Optional[time] = None
    route_id: Optional[int] = None  # Route ID from the routes table
    schedule_type: Optional[RouteType] = None  # Type: "student", "staff", or "internal"
    is_active: Optional[bool] = None
    is_recurring: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    repeat_days: Optional[List[str]] = None  # ['monday', 'wednesday', 'friday']
    
    @validator('repeat_days')
    def validate_repeat_days(cls, v):
        """Validate repeat_days format"""
        if v is not None:
            valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day in v:
                if day.lower() not in valid_days:
                    raise ValueError(f'Invalid day: {day}. Must be one of {valid_days}')
            return [day.lower() for day in v]
        return v


class ScheduleResponse(ScheduleBase):
    """Schedule response with metadata"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    days: List[ScheduleDayResponse] = Field(default_factory=list)  # List of recurring days
    
    class Config:
        from_attributes = True


class ScheduleWithVehicle(ScheduleResponse):
    """Schedule response with vehicle details (for client view)"""
    vehicle: VehiclePublic
    
    class Config:
        from_attributes = True


class ScheduleWithVehicleAdmin(ScheduleResponse):
    """Schedule response with full vehicle details (for admin view)"""
    vehicle: VehicleAdmin
    
    class Config:
        from_attributes = True


# Rebuild models to resolve forward references
ScheduleWithVehicleAdmin.model_rebuild()
ScheduleWithVehicle.model_rebuild()


# ============ GPS Location Data ============

class DeviceAttributes(BaseModel):
    """Device sensor and operational attributes"""
    power: Optional[float] = None
    ignition: Optional[bool] = None
    charge: Optional[bool] = None
    batteryLevel: Optional[int] = None
    ac: Optional[bool] = None
    door: Optional[bool] = None
    panic: Optional[bool] = None
    alarm: Optional[str] = None  # Alarm type string: 'powerCut', 'sos', 'vibration', etc.
    motion: Optional[bool] = None
    totalDistance: Optional[float] = None
    todayDistance: Optional[float] = None


class VehicleLocation(BaseModel):
    """Simplified vehicle location response for clients"""
    vehicle_id: int
    name: str
    label: Optional[str] = None
    latitude: float
    longitude: float
    speed: float
    course: int
    timestamp: str
    valid: bool
    ignition: bool
    motion: bool


class VehicleStatus(BaseModel):
    """Vehicle operational status"""
    vehicle_id: int
    name: str
    ignition: bool
    motion: bool
    charge: bool
    batteryLevel: int
    totalDistance: float
    todayDistance: float
    timestamp: str


class VehicleInfoComplete(BaseModel):
    """Complete vehicle information from EERA API"""
    attributes: DeviceAttributes
    name: str
    companyName: str
    deviceUniqueId: str
    timestamp: str
    serverTime: str
    deviceTime: str
    fixTime: str
    lastStatusUpdate: str
    valid: bool
    latitude: float
    longitude: float
    altitude: float
    speed: float
    course: int
    address: Optional[str] = None
    accuracy: float
