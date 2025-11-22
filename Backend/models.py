from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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


class DeviceInfo(BaseModel):
    """Complete device information"""
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


class DeviceInfoResponse(BaseModel):
    """API response wrapper"""
    successful: bool
    message: str
    object: list[DeviceInfo]
