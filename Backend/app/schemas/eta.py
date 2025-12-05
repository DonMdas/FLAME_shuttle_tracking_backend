from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ============ Common Schemas ============

class Coordinate(BaseModel):
    """Coordinate schema for latitude/longitude pairs"""
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class Stop(BaseModel):
    """Stop information schema"""
    stop_id: str = Field(..., description="Unique identifier for the stop")
    name: str = Field(..., description="Display name of the stop")
    lat: float = Field(..., description="Latitude of the stop")
    lon: float = Field(..., description="Longitude of the stop")


class SegmentProgress(BaseModel):
    """Progress along current route segment for visual display"""
    from_stop: Stop = Field(..., description="Previous stop (segment start)")
    to_stop: Stop = Field(..., description="Next stop (segment end)")
    total_distance_meters: float = Field(..., description="Total distance between the two stops")
    remaining_distance_meters: float = Field(..., description="Distance from vehicle to next stop")
    progress_ratio: float = Field(..., description="Progress along segment (0.0 to 1.0)", ge=0, le=1)


class StopWithETA(Stop):
    """Stop with ETA information"""
    eta_seconds: int = Field(..., description="Estimated time of arrival in seconds")
    distance_meters: int = Field(..., description="Distance to stop in meters")
    status: Literal["upcoming", "arriving", "skipped", "off_route"] = Field(
        default="upcoming",
        description="Status of this stop"
    )
    source: Literal["osrm", "estimate_fallback"] = Field(
        default="osrm",
        description="Source of the ETA calculation"
    )
    osrm_request: Optional[str] = Field(
        None,
        description="OSRM API request URL used for debugging"
    )


# ============ ETA Upcoming Endpoint ============

class ETAUpcomingResponse(BaseModel):
    """Response schema for /eta/upcoming endpoint"""
    vehicle_id: int = Field(..., description="Vehicle identifier")
    timestamp_utc: str = Field(..., description="Timestamp of the response in UTC")
    current_location: Coordinate = Field(..., description="Current vehicle location")
    route_id: str = Field(..., description="Active route identifier")
    direction: str = Field(..., description="Direction of travel (from -> to)")
    current_segment: Optional[SegmentProgress] = Field(
        None,
        description="Progress along current route segment for visual display"
    )
    upcoming_stops: List[StopWithETA] = Field(
        default_factory=list,
        description="List of upcoming stops with ETA"
    )
    stale: bool = Field(
        default=False,
        description="True if location data is older than threshold"
    )
    off_route: bool = Field(
        default=False,
        description="True if vehicle appears to be off the expected route"
    )


# ============ ETA By Coordinates Endpoint ============

class TargetLocation(BaseModel):
    """Target location with identifier"""
    id: str = Field(..., description="Unique identifier for this target")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class ETAByCoordinatesRequest(BaseModel):
    """Request schema for /eta/by-coordinates endpoint"""
    origin: Coordinate = Field(..., description="Starting point coordinates")
    targets: List[TargetLocation] = Field(
        ...,
        description="List of target locations to compute ETA to",
        min_items=1
    )
    mode: Literal["driving", "walking"] = Field(
        default="driving",
        description="Travel mode for routing"
    )


class TargetWithETA(BaseModel):
    """Target location with ETA information"""
    id: str = Field(..., description="Target identifier")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    eta_seconds: int = Field(..., description="Estimated time of arrival in seconds")
    distance_meters: int = Field(..., description="Distance in meters")
    source: Literal["osrm", "estimate_fallback"] = Field(
        default="osrm",
        description="Source of the ETA calculation"
    )
    osrm_request: Optional[str] = Field(
        None,
        description="OSRM API request URL used for debugging"
    )


class ETAByCoordinatesResponse(BaseModel):
    """Response schema for /eta/by-coordinates endpoint"""
    timestamp_utc: str = Field(..., description="Timestamp of the response in UTC")
    origin: Coordinate = Field(..., description="Origin coordinates")
    mode: str = Field(..., description="Travel mode used")
    targets: List[TargetWithETA] = Field(
        default_factory=list,
        description="List of targets with ETA information"
    )


# ============ Error Response ============

class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
