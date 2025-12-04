from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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

class ScheduleBase(BaseModel):
    """Base schedule schema"""
    vehicle_id: int
    start_time: datetime
    route_id: str  # Must match a route_id from ROUTE_DEFINITIONS in route_config.py
    is_active: bool = True


class ScheduleCreate(ScheduleBase):
    """Schema for creating a schedule (admin only)"""
    pass


class ScheduleUpdate(BaseModel):
    """Schema for updating a schedule (admin only)"""
    vehicle_id: Optional[int] = None
    start_time: Optional[datetime] = None
    route_id: Optional[str] = None  # Must match a route_id from ROUTE_DEFINITIONS
    is_active: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    """Schedule response with metadata"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ScheduleWithVehicle(ScheduleResponse):
    """Schedule response with vehicle details (for client view)"""
    vehicle: VehiclePublic
    
    class Config:
        from_attributes = True


# ============ GPS Location Data ============

class DeviceAttributes(BaseModel):
    """Device sensor and operational attributes"""
    power: Optional[float] = None
    ignition: bool
    charge: bool
    batteryLevel: int
    ac: Optional[bool] = None
    door: Optional[bool] = None
    panic: Optional[bool] = None
    alarm: Optional[bool] = None
    motion: bool
    totalDistance: float
    todayDistance: float


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
