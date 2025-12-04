from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException
from db import crud
from schemas.vehicle import VehicleUpdate, VehicleAdmin, VehicleSyncResponse
from services.gps import gps_service
from services.vehicle_sync import vehicle_sync_service


async def list_all_vehicles(db: Session) -> List[VehicleAdmin]:
    """Get all vehicles (admin view with all data)"""
    vehicles = crud.get_vehicles(db)
    return vehicles


async def sync_vehicles_from_api(db: Session) -> VehicleSyncResponse:
    """
    Manually trigger vehicle sync from EERA API.
    Fetches all vehicles from API and updates database.
    """
    result = await vehicle_sync_service.sync_vehicles(db)
    return VehicleSyncResponse(**result)


async def get_vehicle_details(db: Session, vehicle_id: int) -> VehicleAdmin:
    """Get a specific vehicle by ID with live data from API"""
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Fetch live data from API and update cache
    try:
        api_data = await gps_service.get_vehicle_info_by_device_id(vehicle.device_unique_id)
        crud.update_vehicle_from_live_data(db, vehicle_id, api_data)
        # Refresh vehicle to get updated data
        db.refresh(vehicle)
    except Exception as e:
        # If API fetch fails, return cached data
        pass
    
    return vehicle


async def toggle_vehicle_active(db: Session, vehicle_id: int, active: bool) -> VehicleAdmin:
    """Toggle vehicle active status (admin control)"""
    vehicle = crud.update_vehicle(db, vehicle_id, VehicleUpdate(is_active=active))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


async def test_vehicle_connection(db: Session, vehicle_id: int) -> dict:
    """
    Test GPS connection for a vehicle.
    Fetches live data from EERA API to verify the vehicle is available.
    """
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    try:
        device_data = await gps_service.get_vehicle_info_by_device_id(vehicle.device_unique_id)
        
        # Update cached location
        crud.update_vehicle_from_live_data(db, vehicle_id, device_data)
        
        return {
            "status": "success",
            "message": "GPS connection successful",
            "device_name": device_data.get("name"),
            "last_update": device_data.get("timestamp"),
            "speed": device_data.get("speed"),
            "location": {
                "latitude": device_data.get("latitude"),
                "longitude": device_data.get("longitude")
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"GPS connection failed: {str(e)}"
        )


# ============ Deprecated Functions (kept for backward compatibility) ============

async def add_vehicle(db: Session, vehicle_data) -> VehicleAdmin:
    """
    DEPRECATED: Vehicles are now auto-synced from API.
    Use sync_vehicles_from_api instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Manual vehicle addition is deprecated. Vehicles are automatically synced from EERA API. Use /admin/vehicles/sync endpoint."
    )


async def modify_vehicle(db: Session, vehicle_id: int, vehicle_data: VehicleUpdate) -> VehicleAdmin:
    """
    DEPRECATED: Vehicle metadata is synced from API.
    Only is_active and label can be updated manually.
    """
    # Only allow updating label and is_active
    allowed_updates = VehicleUpdate(
        label=vehicle_data.label if vehicle_data.label is not None else None,
        is_active=vehicle_data.is_active if vehicle_data.is_active is not None else None
    )
    
    vehicle = crud.update_vehicle(db, vehicle_id, allowed_updates)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


async def remove_vehicle(db: Session, vehicle_id: int) -> dict:
    """
    DEPRECATED: Vehicles should not be deleted, only deactivated.
    Use toggle_vehicle_active instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Vehicle deletion is deprecated. Use PATCH /admin/vehicles/{id}/active to deactivate instead."
    )


async def toggle_vehicle_visibility(db: Session, vehicle_id: int, visible: bool) -> VehicleAdmin:
    """
    DEPRECATED: is_visible field no longer exists.
    Use is_active instead via toggle_vehicle_active.
    """
    raise HTTPException(
        status_code=410,
        detail="is_visible field is deprecated. Use is_active instead."
    )

