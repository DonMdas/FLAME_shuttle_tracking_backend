from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from db.session import get_db
from schemas.vehicle import VehiclePublic, VehicleLocation, VehicleStatus, ScheduleWithVehicle
from schemas.route import RouteStopsResponse
from api.client import controllers_client

router = APIRouter(prefix="/client", tags=["Client"])


# ============ Public Endpoints (No Authentication Required) ============

@router.get("/schedules", response_model=List[ScheduleWithVehicle])
async def get_active_schedules(
    schedule_type: str = "regular",
    db: Session = Depends(get_db)
):
    """
    Get all active schedules with vehicle details.
    Defaults to regular schedules for backward compatibility.
    Pass schedule_type=staff for staff schedules.
    Public endpoint - no authentication required.
    """
    return await controllers_client.get_active_schedules_with_vehicles(db, schedule_type)


@router.get("/vehicles", response_model=List[VehiclePublic])
async def get_vehicles_list(
    schedule_type: str = "regular",
    db: Session = Depends(get_db)
):
    """
    Get list of vehicles that have active schedules.
    Defaults to regular schedules for backward compatibility.
    Pass schedule_type=staff for staff schedules.
    Public endpoint - no authentication required.
    Returns only basic info, no sensitive data.
    """
    return await controllers_client.get_available_vehicles(db, schedule_type)


@router.get("/vehicles/{vehicle_id}/location", response_model=VehicleLocation)
async def get_vehicle_location(
    vehicle_id: int,
    db: Session = Depends(get_db)
):
    """
    Get real-time location for a specific vehicle.
    Public endpoint - no authentication required.
    """
    return await controllers_client.get_vehicle_live_location(db, vehicle_id)


@router.get("/vehicles/{vehicle_id}/status", response_model=VehicleStatus)
async def get_vehicle_status(
    vehicle_id: int,
    db: Session = Depends(get_db)
):
    """
    Get operational status for a specific vehicle.
    Public endpoint - no authentication required.
    """
    return await controllers_client.get_vehicle_live_status(db, vehicle_id)


@router.get("/vehicles/locations/all", response_model=List[VehicleLocation])
async def get_all_locations(db: Session = Depends(get_db)):
    """
    Get live locations for all available vehicles.
    Useful for displaying all shuttles on a map.
    Public endpoint - no authentication required.
    """
    return await controllers_client.get_all_vehicles_locations(db)


@router.get("/routes/{route_id}/stops", response_model=RouteStopsResponse)
async def get_route_stops(route_id: str):
    """
    Get all station information for a specific route.
    Returns ordered list of stops with names and coordinates.
    Public endpoint - no authentication required.
    """
    return await controllers_client.get_route_stops_info(route_id)
