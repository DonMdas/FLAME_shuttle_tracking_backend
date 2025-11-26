from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException
from db import crud
from schemas.vehicle import VehiclePublic, VehicleLocation, VehicleStatus, ScheduleWithVehicle
from services.gps import gps_service


async def get_active_schedules_with_vehicles(db: Session) -> List[ScheduleWithVehicle]:
    """
    Get all active schedules with their vehicle details.
    Only returns schedules marked as active.
    """
    schedules = crud.get_active_schedules(db)
    return schedules


async def get_available_vehicles(db: Session) -> List[VehiclePublic]:
    """
    Get list of vehicles that have active schedules.
    Only returns vehicles that are active and have active schedules.
    No sensitive data (tokens) included.
    """
    vehicles = crud.get_vehicles_with_active_schedules(db)
    return vehicles


async def get_vehicle_live_location(db: Session, vehicle_id: int) -> VehicleLocation:
    """
    Get real-time location for a specific vehicle.
    Only returns data for vehicles with active schedules.
    Fetches live data from GPS API and updates cache.
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
        # Fetch live GPS data
        device_data = await gps_service.get_device_info(vehicle.access_token)
        
        # Update cached location
        crud.update_vehicle_location(
            db,
            vehicle_id,
            device_data["latitude"],
            device_data["longitude"]
        )
        
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
        # Fetch live GPS data
        device_data = await gps_service.get_device_info(vehicle.access_token)
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
