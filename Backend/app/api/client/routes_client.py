from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from db.session import get_db
from schemas.vehicle import VehiclePublic, VehicleLocation, VehicleStatus, ScheduleWithVehicle
from schemas.route import RouteStopsResponse
from api.client import controllers_client
from app.core.security import get_authenticated_user

router = APIRouter(prefix="/client", tags=["Client"])


# ============ Authenticated Endpoints ============
# All endpoints require authentication.
# User's role is extracted from JWT token for filtering.

@router.get("/schedules", response_model=List[ScheduleWithVehicle])
async def get_active_schedules(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get all active schedules with vehicle details.
    
    Authentication: Required
    Returns schedules based on user's role:
    - student role -> regular schedules
    - staff role -> staff schedules
    
    **Security:**
    - Requires valid JWT token
    - Role is extracted from token (server-side)
    """
    # Use user's role from JWT token (trusted source)
    schedule_type = "staff" if current_user.get("role") == "staff" else "regular"
    
    return await controllers_client.get_active_schedules_with_vehicles(db, schedule_type)


@router.get("/vehicles", response_model=List[VehiclePublic])
async def get_vehicles_list(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get list of vehicles that have active schedules.
    
    Authentication: Required
    Returns vehicles based on user's role:
    - student role -> vehicles with regular schedules
    - staff role -> vehicles with staff schedules
    
    **Security:**
    - Requires valid JWT token
    - Role is extracted from token (server-side)
    """
    # Use user's role from JWT token (trusted source)
    schedule_type = "staff" if current_user.get("role") == "staff" else "regular"
    
    return await controllers_client.get_available_vehicles(db, schedule_type)


@router.get("/vehicles/{vehicle_id}/location", response_model=VehicleLocation)
async def get_vehicle_location(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get real-time location for a specific vehicle.
    
    Authentication: Required
    """
    return await controllers_client.get_vehicle_live_location(db, vehicle_id)


@router.get("/vehicles/{vehicle_id}/status", response_model=VehicleStatus)
async def get_vehicle_status(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get operational status for a specific vehicle.
    
    Authentication: Required
    """
    return await controllers_client.get_vehicle_live_status(db, vehicle_id)


@router.get("/vehicles/locations/all", response_model=List[VehicleLocation])
async def get_all_locations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get live locations for all available vehicles.
    Useful for displaying all shuttles on a map.
    
    Authentication: Required
    """
    return await controllers_client.get_all_vehicles_locations(db)


@router.get("/routes/{route_id}/stops", response_model=RouteStopsResponse)
async def get_route_stops(
    route_id: str,
    current_user: dict = Depends(get_authenticated_user)
):
    """
    Get all station information for a specific route.
    Returns ordered list of stops with names and coordinates.
    
    Authentication: Required
    """
    return await controllers_client.get_route_stops_info(route_id)
