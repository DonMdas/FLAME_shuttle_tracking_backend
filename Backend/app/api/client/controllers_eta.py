"""
Controllers for ETA (Estimated Time of Arrival) endpoints.

This module handles the business logic for:
- GET /eta/upcoming - ETA to upcoming stops for a vehicle
- POST /eta/by-coordinates - ETA to arbitrary coordinates
"""

from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from fastapi import HTTPException

from db import crud
from schemas.eta import (
    ETAUpcomingResponse,
    ETAByCoordinatesRequest,
    ETAByCoordinatesResponse,
    Coordinate,
    TargetWithETA
)
from services.gps import gps_service
from services.eta import eta_service


async def get_upcoming_stops_eta(
    db: Session,
    vehicle_id: int,
    mode: str = "driving",
    max_stops: int = 2
) -> ETAUpcomingResponse:
    """
    Get ETA to upcoming stops for a vehicle.
    
    Only returns data for vehicles that are both active AND have active schedules.
    This ensures users can only see vehicles that admins want to be publicly visible.
    
    Args:
        db: Database session
        vehicle_id: Vehicle identifier
        mode: Travel mode ("driving" or "walking")
        max_stops: Maximum number of upcoming stops to return
        
    Returns:
        ETAUpcomingResponse with upcoming stops and ETAs
        
    Raises:
        HTTPException: If vehicle not found, not active, or has no active schedule
    """
    # First check: Vehicle must have at least one active schedule
    # This ensures we only expose vehicles the admin wants users to see
    active_schedules = crud.get_active_schedules(db)
    vehicle_ids_with_active_schedules = {s.vehicle_id for s in active_schedules}
    
    if vehicle_id not in vehicle_ids_with_active_schedules:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found or not currently available"
        )
    
    # Get vehicle from database
    vehicle = crud.get_vehicle(db, vehicle_id)
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if not vehicle.is_active:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found or not currently available"
        )
    
    # Get active schedules for this specific vehicle
    vehicle_active_schedules = [s for s in active_schedules if s.vehicle_id == vehicle_id]
    
    if not vehicle_active_schedules:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found or not currently available"
        )
    
    # Use the first active schedule
    # TODO: In production, you may want to determine which schedule is currently active
    # based on time-of-day
    schedule = vehicle_active_schedules[0]
    
    try:
        # Fetch current location from GPS API
        device_data = await gps_service.get_device_info(vehicle.access_token)
        
        current_location = (device_data["latitude"], device_data["longitude"])
        
        # Parse timestamp
        timestamp_str = device_data["timestamp"]
        try:
            # Try parsing ISO format
            location_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            # Fallback to current time if parsing fails
            location_timestamp = datetime.now(timezone.utc)
        
        # Update cached location
        crud.update_vehicle_location(
            db,
            vehicle_id,
            current_location[0],
            current_location[1]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to fetch vehicle location: {str(e)}"
        )
    
    # Calculate ETAs to upcoming stops
    eta_result = await eta_service.get_upcoming_stops_eta(
        vehicle=vehicle,
        schedule=schedule,
        current_location=current_location,
        location_timestamp=location_timestamp,
        max_stops=max_stops,
        mode=mode
    )
    
    # Build response
    response = ETAUpcomingResponse(
        vehicle_id=vehicle.vehicle_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        current_location=Coordinate(
            lat=current_location[0],
            lon=current_location[1]
        ),
        route_id=eta_result.get("route_id", "unknown"),
        direction=eta_result.get("direction", "unknown"),
        upcoming_stops=eta_result.get("upcoming_stops", []),
        stale=eta_result.get("stale", False),
        off_route=eta_result.get("off_route", False)
    )
    
    return response


async def get_eta_by_coordinates(
    request: ETAByCoordinatesRequest
) -> ETAByCoordinatesResponse:
    """
    Get ETA from origin to arbitrary target coordinates.
    
    Args:
        request: Request with origin and target coordinates
        
    Returns:
        ETAByCoordinatesResponse with ETAs to each target
        
    Raises:
        HTTPException: If OSRM service fails
    """
    origin = (request.origin.lat, request.origin.lon)
    
    # Prepare targets list
    targets = [(t.id, t.lat, t.lon) for t in request.targets]
    
    try:
        # Calculate ETAs
        eta_results = await eta_service.calculate_etas_to_coordinates(
            origin=origin,
            targets=targets,
            mode=request.mode
        )
        
        # Convert to response format
        targets_with_eta = [
            TargetWithETA(
                id=result["id"],
                lat=result["lat"],
                lon=result["lon"],
                eta_seconds=result["eta_seconds"],
                distance_meters=result["distance_meters"],
                source=result.get("source", "osrm"),
                osrm_request=result.get("osrm_request")
            )
            for result in eta_results
        ]
        
        response = ETAByCoordinatesResponse(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            origin=request.origin,
            mode=request.mode,
            targets=targets_with_eta
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ETA calculation failed: {str(e)}"
        )
