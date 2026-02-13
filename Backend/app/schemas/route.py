from pydantic import BaseModel, Field, validator, model_validator
from typing import List, Optional
from datetime import datetime
from app.core.constants import RouteType


class StationInfo(BaseModel):
    """Station information"""
    id: int
    name: str
    lat: float
    lon: float


class RouteStopsResponse(BaseModel):
    """Response model for route stops"""
    route_id: int
    route_name: str
    from_location: str
    to_location: str
    stops: List[StationInfo]


# ============ Station Schemas ============

class StationCreate(BaseModel):
    """Schema for creating a new station"""
    name: str = Field(..., description="Display name of the station")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")


class StationUpdate(BaseModel):
    """Schema for updating a station"""
    name: Optional[str] = Field(None, description="Display name of the station")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    is_active: Optional[bool] = Field(None, description="Active status")


class StationResponse(BaseModel):
    """Schema for station response"""
    id: int
    name: str
    latitude: float
    longitude: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Route Schemas ============

class StopData(BaseModel):
    """Schema for inline station creation"""
    name: str = Field(..., description="Station name")
    latitude: float = Field(..., description="Latitude coordinate", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude coordinate", ge=-180, le=180)


class RouteCreate(BaseModel):
    """Schema for creating a new route"""
    name: str = Field(..., description="Display name (e.g., 'Campus → FC Road')")
    from_location: str = Field(..., description="Starting location name")
    to_location: str = Field(..., description="Ending location name")
    route_type: RouteType = Field(..., description="Route type: 'student', 'staff', or 'internal'")
    
    # Option 1: Use existing station IDs
    stop_ids: Optional[List[int]] = Field(None, description="Ordered list of existing station IDs", min_length=2)
    
    # Option 2: Create stations inline
    stops: Optional[List[StopData]] = Field(None, description="Ordered list of station data to create/use", min_length=2)
    
    @model_validator(mode='after')
    def check_stops_provided(self):
        if not self.stop_ids and not self.stops:
            raise ValueError('Either stop_ids or stops must be provided')
        
        if self.stop_ids and self.stops:
            raise ValueError('Provide either stop_ids or stops, not both')
        
        return self


class RouteUpdate(BaseModel):
    """Schema for updating a route"""
    name: Optional[str] = Field(None, description="Display name")
    from_location: Optional[str] = Field(None, description="Starting location name")
    to_location: Optional[str] = Field(None, description="Ending location name")
    route_type: Optional[RouteType] = Field(None, description="Route type: 'student', 'staff', or 'internal'")
    is_active: Optional[bool] = Field(None, description="Active status")
    
    # Option 1: Use existing station IDs
    stop_ids: Optional[List[int]] = Field(None, description="Ordered list of existing station IDs")
    
    # Option 2: Update stations inline
    stops: Optional[List[StopData]] = Field(None, description="Ordered list of station data to create/use")
    
    @model_validator(mode='after')
    def check_stops_not_both(self):
        if self.stop_ids and self.stops:
            raise ValueError('Provide either stop_ids or stops, not both')
        
        return self


class RouteResponse(BaseModel):
    """Schema for route response (without stops)"""
    id: int
    name: str
    from_location: str
    to_location: str
    route_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RouteStopInfo(BaseModel):
    """Information about a stop in a route"""
    stop_order: int
    station_id: int
    station_name: str
    latitude: float
    longitude: float


class RouteWithStopsResponse(BaseModel):
    """Schema for route with stops"""
    id: int
    name: str
    from_location: str
    to_location: str
    route_type: RouteType
    is_active: bool
    stops: List[RouteStopInfo]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Route Stop Schemas ============

class RouteStopCreate(BaseModel):
    """Schema for adding a stop to a route"""
    route_id: int = Field(..., description="Route ID to add stop to")
    station_id: int = Field(..., description="Station ID to add")
    stop_order: int = Field(..., description="Order of this stop in the route (0-based)", ge=0)


class RouteStopResponse(BaseModel):
    """Schema for route stop response"""
    id: int
    route_id: int
    station_id: int
    stop_order: int
    created_at: datetime

    class Config:
        from_attributes = True
