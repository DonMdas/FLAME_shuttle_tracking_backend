from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException
from db import crud
from schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleAdmin
from services.gps import gps_service


async def list_all_vehicles(db: Session) -> List[VehicleAdmin]:
    """Get all vehicles (admin view with sensitive data)"""
    vehicles = crud.get_vehicles(db)
    return vehicles


async def get_vehicle_details(db: Session, vehicle_id: int) -> VehicleAdmin:
    """Get a specific vehicle by ID"""
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


async def add_vehicle(db: Session, vehicle_data: VehicleCreate) -> VehicleAdmin:
    """
    Add a new vehicle to the system.
    Validates the access token by testing the GPS API.
    """
    # Check if device already exists
    existing = crud.get_vehicle_by_device_id(db, vehicle_data.device_unique_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Vehicle with device ID {vehicle_data.device_unique_id} already exists"
        )
    
    # Validate access token by testing GPS API
    try:
        await gps_service.get_device_info(vehicle_data.access_token)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access token or unable to fetch GPS data: {str(e)}"
        )
    
    # Create vehicle
    vehicle = crud.create_vehicle(db, vehicle_data)
    return vehicle


async def modify_vehicle(db: Session, vehicle_id: int, vehicle_data: VehicleUpdate) -> VehicleAdmin:
    """Update an existing vehicle"""
    vehicle = crud.update_vehicle(db, vehicle_id, vehicle_data)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


async def remove_vehicle(db: Session, vehicle_id: int) -> dict:
    """Delete a vehicle from the system"""
    success = crud.delete_vehicle(db, vehicle_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"message": "Vehicle deleted successfully"}


async def test_vehicle_connection(db: Session, vehicle_id: int) -> dict:
    """
    Test GPS connection for a vehicle.
    Fetches live data from EERA API to verify the access token is working.
    """
    vehicle = crud.get_vehicle(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    try:
        device_data = await gps_service.get_device_info(vehicle.access_token)
        
        # Update cached location
        crud.update_vehicle_location(
            db,
            vehicle_id,
            device_data["latitude"],
            device_data["longitude"]
        )
        
        return {
            "status": "success",
            "message": "GPS connection successful",
            "device_name": device_data.get("name"),
            "last_update": device_data.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"GPS connection failed: {str(e)}"
        )


async def toggle_vehicle_visibility(db: Session, vehicle_id: int, visible: bool) -> VehicleAdmin:
    """Toggle vehicle visibility for clients"""
    vehicle = crud.update_vehicle(db, vehicle_id, VehicleUpdate(is_visible=visible))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


async def toggle_vehicle_active(db: Session, vehicle_id: int, active: bool) -> VehicleAdmin:
    """Toggle vehicle active status"""
    vehicle = crud.update_vehicle(db, vehicle_id, VehicleUpdate(is_active=active))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle
