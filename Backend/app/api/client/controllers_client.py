from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException
from db import crud
from schemas.vehicle import VehiclePublic, VehicleLocation, VehicleStatus, ScheduleWithVehicle
from schemas.route import RouteStopsResponse, StationInfo
from services.gps import gps_service
from app.core.route_config import ROUTE_DEFINITIONS, STATIONS


async def get_active_schedules_with_vehicles(db: Session, schedule_type: str = "regular") -> List[ScheduleWithVehicle]:
    """
    Get all active schedules with their vehicle details.
    Only returns schedules marked as active.
    Defaults to regular schedules. Pass schedule_type="staff" for staff schedules.
    """
    schedules = crud.get_active_schedules(db, schedule_type=schedule_type)
    return schedules


async def get_available_vehicles(db: Session, schedule_type: str = "regular") -> List[VehiclePublic]:
    """
    Get list of vehicles that have active schedules.
    Only returns vehicles that are active and have active schedules.
    Defaults to regular schedules. Pass schedule_type="staff" for staff schedules.
    No sensitive data (tokens) included.
    """
    # Get active schedules (filtered by type)
    active_schedules = crud.get_active_schedules(db, schedule_type=schedule_type)
    # Get unique vehicle IDs from active schedules
    vehicle_ids = {s.vehicle_id for s in active_schedules}
    # Return vehicles that have these schedules
    vehicles = [crud.get_vehicle(db, vid) for vid in vehicle_ids]
    return [v for v in vehicles if v and v.is_active]


async def get_vehicle_live_location(db: Session, vehicle_id: int) -> VehicleLocation:
    """
    Get real-time location for a specific vehicle.
    Only returns data for vehicles with active schedules.
    Fetches live data from GPS API every time (called by frontend every 3-5 seconds).
    """
    # Security check: Only expose vehicles with active schedules
    active_schedules = crud.get_active_schedules(db)
    vehicle_ids_with_active_schedules = {s.vehicle_id for s in active_schedules}
    
    if vehicle_id not in vehicle_ids_with_active_schedules:
        raise HTTPException(status_code=404, detail="Vehicle not found or not currently available")
    
    vehicle = crud.get_vehicle(db, vehicle_id)
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if not vehicle.is_active:
        raise HTTPException(status_code=404, detail="Vehicle not found or not currently available")
    
    try:
        # Fetch live GPS data from API
        device_data = await gps_service.get_vehicle_info_by_device_id(vehicle.device_unique_id)
        
        # Update cached location
        crud.update_vehicle_from_live_data(db, vehicle_id, device_data)
        
        # Return location data
        attributes = device_data.get("attributes", {})
        return VehicleLocation(
            vehicle_id=vehicle.vehicle_id,
            name=vehicle.name,
            label=vehicle.label,
            latitude=device_data["latitude"],
            longitude=device_data["longitude"],
            speed=device_data["speed"],
            course=device_data["course"],
            timestamp=device_data["timestamp"],
            valid=device_data["valid"],
            ignition=attributes.get("ignition", False),
            motion=attributes.get("motion", False)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to fetch vehicle location: {str(e)}"
        )


async def get_vehicle_live_status(db: Session, vehicle_id: int) -> VehicleStatus:
    """
    Get operational status for a specific vehicle.
    Only returns data for vehicles with active schedules.
    Fetches live data from GPS API.
    """
    # Security check: Only expose vehicles with active schedules
    active_schedules = crud.get_active_schedules(db)
    vehicle_ids_with_active_schedules = {s.vehicle_id for s in active_schedules}
    
    if vehicle_id not in vehicle_ids_with_active_schedules:
        raise HTTPException(status_code=404, detail="Vehicle not found or not currently available")
    
    vehicle = crud.get_vehicle(db, vehicle_id)
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if not vehicle.is_active:
        raise HTTPException(status_code=404, detail="Vehicle not found or not currently available")
    
    try:
        # Fetch live GPS data from API
        device_data = await gps_service.get_vehicle_info_by_device_id(vehicle.device_unique_id)
        attributes = device_data.get("attributes", {})
        
        return VehicleStatus(
            vehicle_id=vehicle.vehicle_id,
            name=vehicle.name,
            ignition=attributes.get("ignition", False),
            motion=attributes.get("motion", False),
            charge=attributes.get("charge", False),
            batteryLevel=attributes.get("batteryLevel", 0),
            totalDistance=attributes.get("totalDistance", 0),
            todayDistance=attributes.get("todayDistance", 0),
            timestamp=device_data["timestamp"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to fetch vehicle status: {str(e)}"
        )


async def get_all_vehicles_locations(db: Session) -> List[VehicleLocation]:
    """
    Get live locations for all available vehicles.
    Useful for map view showing all shuttles.
    """
    vehicles = crud.get_vehicles_with_active_schedules(db)
    locations = []
    
    for vehicle in vehicles:
        try:
            location = await get_vehicle_live_location(db, vehicle.vehicle_id)
            locations.append(location)
        except Exception:
            # Skip vehicles that fail to fetch data
            continue
    
    return locations


async def get_route_stops_info(route_id: str) -> RouteStopsResponse:
    """
    Get all station information for a given route.
    Returns station names and coordinates in order.
    """
    # Check if route exists
    route_def = ROUTE_DEFINITIONS.get(route_id)
    if not route_def:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found")
    
    # Get station details for all stops in route
    stops_info = []
    for stop_id in route_def["stops"]:
        station = STATIONS.get(stop_id)
        if station:
            stops_info.append(StationInfo(
                id=station.id,
                name=station.name,
                lat=station.lat,
                lon=station.lon
            ))
    
    return RouteStopsResponse(
        route_id=route_def["route_id"],
        route_name=route_def["name"],
        from_location=route_def["from_location"],
        to_location=route_def["to_location"],
        stops=stops_info
    )
