from sqlalchemy.orm import Session
from typing import List
from fastapi import HTTPException
from db import crud
from db.models import Station
from schemas.vehicle import VehicleUpdate, VehicleAdmin, VehicleSyncResponse, VehicleInfoComplete
from schemas.user import UserResponse, UserUpdate
from schemas.route import (
    StationCreate, StationUpdate, StationResponse,
    RouteCreate, RouteUpdate, RouteResponse, RouteWithStopsResponse,
    RouteStopCreate, RouteStopResponse, RouteStopInfo, StopData
)
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


async def get_all_vehicles_info(db: Session) -> List[VehicleInfoComplete]:
    """
    Get complete real-time information for all vehicles from EERA API.
    Returns all vehicle data including attributes, location, speed, etc.
    """
    try:
        vehicles_data = await gps_service.get_all_vehicles_info()
        return [VehicleInfoComplete(**vehicle) for vehicle in vehicles_data]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch vehicle information: {str(e)}"
        )


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


# ============ User Management (Admin Only) ============

async def list_all_users(db: Session, role: str = None, skip: int = 0, limit: int = 1000) -> List[UserResponse]:
    """
    Get all users with optional role filter.
    Admin endpoint to view all registered users.
    """
    users = crud.get_users(db, skip=skip, limit=limit, role=role)
    return [UserResponse.from_orm(user) for user in users]


async def get_user_details(db: Session, user_id: int) -> UserResponse:
    """Get a specific user by ID"""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_orm(user)


async def update_user_role_by_admin(db: Session, user_id: int, role_data: UserUpdate) -> UserResponse:
    """
    Update user's role (admin only).
    Users cannot change their own roles.
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update role
    updated_user = crud.update_user_role(db, user_id, role_data.role)
    if not updated_user:
        raise HTTPException(status_code=500, detail="Failed to update user role")
    
    return UserResponse.from_orm(updated_user)


async def toggle_user_active(db: Session, user_id: int, active: bool) -> UserResponse:
    """Toggle user active status (admin control)"""
    user = crud.update_user_status(db, user_id, active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_orm(user)


async def delete_user_by_admin(db: Session, user_id: int) -> dict:
    """
    Delete a user from the system (admin only).
    Warning: This permanently deletes the user and cannot be undone.
    Consider using toggle_user_active to deactivate instead.
    """
    # Check if user exists first
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete the user
    success = crud.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    
    return {"message": f"User {user.email} deleted successfully"}


# ============ Station Management ============

async def create_station_admin(db: Session, station_data: StationCreate) -> StationResponse:
    """Create a new station"""
    station = crud.create_station(
        db,
        name=station_data.name,
        latitude=station_data.latitude,
        longitude=station_data.longitude
    )
    return station


async def list_all_stations(db: Session, active_only: bool = False) -> List[StationResponse]:
    """Get all stations"""
    stations = crud.get_all_stations(db, active_only=active_only)
    return stations


async def get_station_details(db: Session, station_id: int) -> StationResponse:
    """Get a specific station by ID"""
    station = crud.get_station(db, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


async def update_station_admin(db: Session, station_id: int, station_data: StationUpdate) -> StationResponse:
    """Update a station"""
    station = crud.update_station(
        db,
        station_id=station_id,
        name=station_data.name,
        latitude=station_data.latitude,
        longitude=station_data.longitude,
        is_active=station_data.is_active
    )
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


async def delete_station_admin(db: Session, station_id: int) -> dict:
    """Delete a station (will fail if referenced by routes)"""
    success = crud.delete_station(db, station_id)
    if not success:
        raise HTTPException(status_code=404, detail="Station not found")
    return {"message": f"Station {station_id} deleted successfully"}


# ============ Route Management ============

def _find_or_create_station(db: Session, stop_data: dict) -> int:
    """
    Find existing station by name or create new one.
    Returns station ID.
    """
    # Check if station with same name exists (case-insensitive)
    existing = db.query(Station).filter(
        Station.name.ilike(stop_data["name"])
    ).first()
    
    if existing:
        # Check if coordinates are significantly different (>100m difference ~0.001 degrees)
        lat_diff = abs(existing.latitude - stop_data["latitude"])
        lon_diff = abs(existing.longitude - stop_data["longitude"])
        
        if lat_diff > 0.001 or lon_diff > 0.001:
            # Same name but different location - create new with unique name
            base_name = stop_data["name"]
            counter = 1
            while True:
                new_name = f"{base_name} ({counter})"
                check = db.query(Station).filter(Station.name == new_name).first()
                if not check:
                    break
                counter += 1
            
            new_station = crud.create_station(
                db,
                name=new_name,
                latitude=stop_data["latitude"],
                longitude=stop_data["longitude"]
            )
            return new_station.id
        else:
            # Same name, same location - reuse existing
            return existing.id
    
    # Station doesn't exist - create new
    new_station = crud.create_station(
        db,
        name=stop_data["name"],
        latitude=stop_data["latitude"],
        longitude=stop_data["longitude"]
    )
    return new_station.id


async def create_route_admin(db: Session, route_data: RouteCreate) -> RouteWithStopsResponse:
    """
    Create a new route with stops.
    
    Supports two methods:
    1. stop_ids: Use existing station IDs
    2. stops: Provide station data (creates stations if needed)
    """
    stop_ids = []
    
    if route_data.stop_ids:
        # Method 1: Using existing station IDs
        for station_id in route_data.stop_ids:
            station = crud.get_station(db, station_id)
            if not station:
                raise HTTPException(status_code=400, detail=f"Station {station_id} not found")
        stop_ids = route_data.stop_ids
    
    elif route_data.stops:
        # Method 2: Create/find stations from inline data
        for stop in route_data.stops:
            station_id = _find_or_create_station(db, {
                "name": stop.name,
                "latitude": stop.latitude,
                "longitude": stop.longitude
            })
            stop_ids.append(station_id)
    
            stop_ids.append(station_id)
    
    # Create route with collected station IDs
    route = crud.create_route(
        db,
        name=route_data.name,
        from_location=route_data.from_location,
        to_location=route_data.to_location,
        route_type=route_data.route_type,
        stop_ids=stop_ids
    )
    
    if not route:
        raise HTTPException(status_code=500, detail="Failed to create route")
    
    # Get route with stops for response
    stops = crud.get_route_stops_ordered(db, route.id)
    return RouteWithStopsResponse(
        id=route.id,
        name=route.name,
        from_location=route.from_location,
        to_location=route.to_location,
        route_type=route.route_type,
        is_active=route.is_active,
        stops=[RouteStopInfo(**stop) for stop in stops],
        created_at=route.created_at,
        updated_at=route.updated_at
    )


async def list_all_routes_admin(db: Session, active_only: bool = False) -> List[RouteWithStopsResponse]:
    """Get all routes with stops"""
    routes = crud.get_all_routes(db, active_only=active_only)
    
    result = []
    for route in routes:
        stops = crud.get_route_stops_ordered(db, route.id)
        result.append(RouteWithStopsResponse(
            id=route.id,
            name=route.name,
            from_location=route.from_location,
            to_location=route.to_location,
            route_type=route.route_type,
            is_active=route.is_active,
            stops=[RouteStopInfo(**stop) for stop in stops],
            created_at=route.created_at,
            updated_at=route.updated_at
        ))
    
    return result


async def get_route_details_admin(db: Session, route_id: int) -> RouteWithStopsResponse:
    """Get a specific route by ID with stops"""
    route = crud.get_route(db, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    stops = crud.get_route_stops_ordered(db, route_id)
    return RouteWithStopsResponse(
        id=route.id,
        name=route.name,
        from_location=route.from_location,
        to_location=route.to_location,
        route_type=route.route_type,
        is_active=route.is_active,
        stops=[RouteStopInfo(**stop) for stop in stops],
        created_at=route.created_at,
        updated_at=route.updated_at
    )


async def update_route_admin(db: Session, route_id: int, route_data: RouteUpdate) -> RouteWithStopsResponse:
    """
    Update a route.
    
    Supports two methods for updating stops:
    1. stop_ids: Use existing station IDs
    2. stops: Provide station data (creates stations if needed)
    """
    stop_ids = None
    
    # Handle stops update if provided
    if route_data.stop_ids:
        # Method 1: Using existing station IDs
        for station_id in route_data.stop_ids:
            station = crud.get_station(db, station_id)
            if not station:
                raise HTTPException(status_code=400, detail=f"Station {station_id} not found")
        stop_ids = route_data.stop_ids
    
    elif route_data.stops:
        # Method 2: Create/find stations from inline data
        stop_ids = []
        for stop in route_data.stops:
            station_id = _find_or_create_station(db, {
                "name": stop.name,
                "latitude": stop.latitude,
                "longitude": stop.longitude
            })
            stop_ids.append(station_id)
    
    # Update route
    route = crud.update_route(
        db,
        route_id=route_id,
        name=route_data.name,
        from_location=route_data.from_location,
        to_location=route_data.to_location,
        route_type=route_data.route_type,
        is_active=route_data.is_active,
        stop_ids=stop_ids
    )
    
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Get route with stops for response
    stops = crud.get_route_stops_ordered(db, route.id)
    return RouteWithStopsResponse(
        id=route.id,
        name=route.name,
        from_location=route.from_location,
        to_location=route.to_location,
        route_type=route.route_type,
        is_active=route.is_active,
        stops=[RouteStopInfo(**stop) for stop in stops],
        created_at=route.created_at,
        updated_at=route.updated_at
    )


async def delete_route_admin(db: Session, route_id: int) -> dict:
    """Delete a route (will fail if referenced by schedules)"""
    success = crud.delete_route(db, route_id)
    if not success:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"message": f"Route {route_id} deleted successfully"}


# ============ Route Stop Management ============

async def add_stop_to_route(db: Session, stop_data: RouteStopCreate) -> RouteWithStopsResponse:
    """Add a stop to an existing route at a specific position"""
    # Verify route exists
    route = crud.get_route(db, stop_data.route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Verify station exists
    station = crud.get_station(db, stop_data.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    # Get current stops
    current_stops = crud.get_route_stops_ordered(db, stop_data.route_id)
    stop_ids = [stop["station_id"] for stop in current_stops]
    
    # Insert new station at specified position
    if stop_data.stop_order > len(stop_ids):
        stop_ids.append(stop_data.station_id)
    else:
        stop_ids.insert(stop_data.stop_order, stop_data.station_id)
    
    # Update route with new stop order
    updated_route = crud.update_route(
        db,
        route_id=stop_data.route_id,
        stop_ids=stop_ids
    )
    
    if not updated_route:
        raise HTTPException(status_code=500, detail="Failed to add stop to route")
    
    # Get updated route with stops
    stops = crud.get_route_stops_ordered(db, updated_route.id)
    return RouteWithStopsResponse(
        id=updated_route.id,
        name=updated_route.name,
        from_location=updated_route.from_location,
        to_location=updated_route.to_location,
        route_type=updated_route.route_type,
        is_active=updated_route.is_active,
        stops=[RouteStopInfo(**stop) for stop in stops],
        created_at=updated_route.created_at,
        updated_at=updated_route.updated_at
    )


