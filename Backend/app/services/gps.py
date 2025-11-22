import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException
from core.config import settings


class GPSService:
    """Service for interacting with EERA GPS House API"""
    
    def __init__(self):
        self.base_url = settings.EERA_BASE_URL
        self.endpoint = settings.EERA_ENDPOINT
    
    async def get_device_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch device information from EERA API.
        
        Args:
            access_token: Device-specific access token
            
        Returns:
            Device information including location, status, and attributes
            
        Raises:
            HTTPException: If the API request fails
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}{self.endpoint}",
                    params={"accessToken": access_token}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Check if API call was successful
                if not data.get("successful", False):
                    raise HTTPException(
                        status_code=400,
                        detail=f"EERA API request failed: {data.get('message', 'Unknown error')}"
                    )
                
                # Validate that we got device data
                if not data.get("object") or len(data["object"]) == 0:
                    raise HTTPException(
                        status_code=404,
                        detail="No device data found"
                    )
                
                return data["object"][0]
                
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
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"GPS service error: {str(e)}"
            )
    
    async def get_location(self, access_token: str) -> Dict[str, Any]:
        """
        Get simplified location data from device.
        
        Args:
            access_token: Device-specific access token
            
        Returns:
            Location data (latitude, longitude, speed, etc.)
        """
        device_data = await self.get_device_info(access_token)
        
        return {
            "latitude": device_data["latitude"],
            "longitude": device_data["longitude"],
            "speed": device_data["speed"],
            "course": device_data["course"],
            "timestamp": device_data["timestamp"],
            "valid": device_data["valid"],
            "altitude": device_data.get("altitude", 0),
            "accuracy": device_data.get("accuracy", 0)
        }
    
    async def get_status(self, access_token: str) -> Dict[str, Any]:
        """
        Get vehicle operational status.
        
        Args:
            access_token: Device-specific access token
            
        Returns:
            Status data (ignition, motion, battery, etc.)
        """
        device_data = await self.get_device_info(access_token)
        attributes = device_data.get("attributes", {})
        
        return {
            "ignition": attributes.get("ignition", False),
            "motion": attributes.get("motion", False),
            "charge": attributes.get("charge", False),
            "batteryLevel": attributes.get("batteryLevel", 0),
            "totalDistance": attributes.get("totalDistance", 0),
            "todayDistance": attributes.get("todayDistance", 0),
            "timestamp": device_data["timestamp"]
        }


# Singleton instance
gps_service = GPSService()
