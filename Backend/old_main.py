from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from models import DeviceInfoResponse
from typing import Optional

app = FastAPI(
    title="Shuttle Tracker API",
    description="API for tracking shuttle vehicles using EERA GPS House platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["172.16.19.255:3000"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# EERA API configuration
EERA_BASE_URL = "https://track.eeragpshouse.com"
EERA_ENDPOINT = "/api/middleMan/getDeviceInfo"


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Shuttle Tracker API",
        "version": "1.0.0"
    }


@app.get("/api/vehicle/info", response_model=DeviceInfoResponse)
async def get_vehicle_info(
    accessToken: str = Query(..., description="Base64-encoded access token for the device")
):
    """
    Retrieve real-time vehicle information from EERA GPS tracking system.
    
    Parameters:
    - accessToken: Base64-encoded token containing device authentication and identifier (required)
    
    Returns:
    - Device information including location, status, motion, battery, and distance metrics
    """
    try:
        # Make request to EERA API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{EERA_BASE_URL}{EERA_ENDPOINT}",
                params={"accessToken": accessToken}
            )
            response.raise_for_status()
            
            # Parse and validate response
            data = response.json()
            
            # Check if API call was successful
            if not data.get("successful", False):
                raise HTTPException(
                    status_code=400,
                    detail=f"EERA API request failed: {data.get('message', 'Unknown error')}"
                )
            
            return data
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to EERA API timed out"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"EERA API returned error: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/vehicle/location")
async def get_vehicle_location(
    accessToken: str = Query(..., description="Base64-encoded access token for the device")
):
    """
    Get simplified vehicle location information.
    
    Returns only the essential location data: coordinates, speed, and timestamp.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{EERA_BASE_URL}{EERA_ENDPOINT}",
                params={"accessToken": accessToken}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("successful", False):
                raise HTTPException(
                    status_code=400,
                    detail=f"EERA API request failed: {data.get('message', 'Unknown error')}"
                )
            
            # Extract location data
            device_data = data["object"][0] if data.get("object") else None
            if not device_data:
                raise HTTPException(status_code=404, detail="No device data found")
            
            return {
                "name": device_data["name"],
                "deviceUniqueId": device_data["deviceUniqueId"],
                "latitude": device_data["latitude"],
                "longitude": device_data["longitude"],
                "speed": device_data["speed"],
                "course": device_data["course"],
                "timestamp": device_data["timestamp"],
                "valid": device_data["valid"]
            }
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vehicle/status")
async def get_vehicle_status(
    accessToken: Optional[str] = Query(None, description="Base64-encoded access token for the device")
):
    """
    Get vehicle operational status.
    
    Returns status information: ignition, motion, battery, and distances.
    """
    # Use default token if not provided
    token = accessToken or DEFAULT_ACCESS_TOKEN
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{EERA_BASE_URL}{EERA_ENDPOINT}",
                params={"accessToken": token}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("successful", False):
                raise HTTPException(status_code=400, detail="API request failed")
            
            device_data = data["object"][0] if data.get("object") else None
            if not device_data:
                raise HTTPException(status_code=404, detail="No device data found")
            
            attributes = device_data.get("attributes", {})
            
            return {
                "name": device_data["name"],
                "deviceUniqueId": device_data["deviceUniqueId"],
                "ignition": attributes.get("ignition", False),
                "motion": attributes.get("motion", False),
                "charge": attributes.get("charge", False),
                "batteryLevel": attributes.get("batteryLevel", 0),
                "totalDistance": attributes.get("totalDistance", 0),
                "todayDistance": attributes.get("todayDistance", 0),
                "timestamp": device_data["timestamp"]
            }
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
