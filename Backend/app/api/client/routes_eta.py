"""
Routes for ETA (Estimated Time of Arrival) endpoints.

Public endpoints for getting ETAs to upcoming shuttle stops.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.eta import (
    ETAUpcomingResponse,
    ETAByCoordinatesRequest,
    ETAByCoordinatesResponse
)
from api.client import controllers_eta

router = APIRouter(prefix="/eta", tags=["ETA"])


# ============ Public ETA Endpoints ============

@router.get("/upcoming", response_model=ETAUpcomingResponse)
async def get_upcoming_stops_eta(
    vehicle_id: int = Query(..., description="Vehicle ID"),
    mode: str = Query("driving", description="Travel mode (driving or walking)"),
    max_stops: int = Query(2, ge=1, le=10, description="Maximum number of upcoming stops to return"),
    db: Session = Depends(get_db)
):
    """
    Get ETA to upcoming stops for a specific vehicle.
    
    This endpoint returns the estimated time of arrival (ETA) from the vehicle's
    current location to the next N upcoming stops on its scheduled route.
    
    **Query Parameters:**
    - `vehicle_id` (required): ID of the vehicle
    - `mode` (optional): Travel mode - "driving" or "walking" (default: "driving")
    - `max_stops` (optional): Number of upcoming stops to return (default: 2, max: 10)
    
    **Response:**
    - Vehicle and route information
    - Current location coordinates
    - List of upcoming stops with ETA and distance
    - Status flags (stale location, off-route)
    
    **Error Responses:**
    - `400`: Missing or invalid vehicle_id
    - `404`: Vehicle not found or no active route
    - `503`: OSRM service unavailable
    
    **Example:**
    ```
    GET /api/client/eta/upcoming?vehicle_id=1&max_stops=2
    ```
    """
    return await controllers_eta.get_upcoming_stops_eta(
        db=db,
        vehicle_id=vehicle_id,
        mode=mode,
        max_stops=max_stops
    )


@router.post("/by-coordinates", response_model=ETAByCoordinatesResponse)
async def get_eta_by_coordinates(
    request: ETAByCoordinatesRequest
):
    """
    Calculate ETA from origin to arbitrary target coordinates.
    
    This endpoint computes ETAs from a given origin point to one or more
    target locations. Useful for debugging or when coordinates are already known.
    
    **Request Body:**
    ```json
    {
      "origin": {"lat": 18.5230, "lon": 73.7600},
      "targets": [
        {"id": "stop1", "lat": 18.518468, "lon": 73.765785},
        {"id": "stop2", "lat": 18.507034, "lon": 73.805283}
      ],
      "mode": "driving"
    }
    ```
    
    **Response:**
    - Origin coordinates
    - List of targets with ETA and distance information
    - OSRM request details for debugging
    
    **Error Responses:**
    - `400`: Invalid request format
    - `503`: OSRM service unavailable
    
    **Example:**
    ```
    POST /api/client/eta/by-coordinates
    Content-Type: application/json
    
    {
      "origin": {"lat": 18.5230, "lon": 73.7600},
      "targets": [
        {"id": "bavdhan", "lat": 18.518468, "lon": 73.765785}
      ],
      "mode": "driving"
    }
    ```
    """
    return await controllers_eta.get_eta_by_coordinates(request)
