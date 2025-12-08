from pydantic import BaseModel
from typing import List


class StationInfo(BaseModel):
    """Station information"""
    id: str
    name: str
    lat: float
    lon: float


class RouteStopsResponse(BaseModel):
    """Response model for route stops"""
    route_id: str
    route_name: str
    from_location: str
    to_location: str
    stops: List[StationInfo]
