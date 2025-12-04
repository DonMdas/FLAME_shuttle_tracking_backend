import httpx
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import logger, log_gps_request


class GPSService:
    """Service for interacting with EERA GPS House API"""
    
    def __init__(self):
        self.base_url = settings.EERA_BASE_URL
        self.endpoint = settings.EERA_ENDPOINT
        self.api_key = settings.EERA_API_KEY
    
    async def get_all_vehicles_info(self) -> List[Dict[str, Any]]:
        """
        Fetch all vehicles information from EERA API using the single API key.
        This is used for syncing the vehicle list.
        
        Returns:
            List of vehicle data dictionaries
            
        Raises:
            HTTPException: If the API request fails
        """
        try:
            logger.debug(f"Fetching all vehicles data from EERA API")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}{self.endpoint}",
                    params={"accessToken": self.api_key}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Check if API call was successful
                if not data.get("successful", False):
                    error_msg = data.get('message', 'Unknown error')
                    logger.error(f"EERA API request failed: {error_msg}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"GPS service error: {error_msg}"
                    )
                
                # Validate that we got vehicle data
                vehicles = data.get("object", [])
                if not vehicles:
                    logger.warning(f"No vehicle data returned from EERA API")
                    return []
                
                logger.debug(f"Fetched {len(vehicles)} vehicles from EERA API")
                return vehicles
                
        except httpx.TimeoutException:
            logger.error(f"GPS API request timeout (>10s)")
            raise HTTPException(
                status_code=504,
                detail="GPS service timeout. The GPS provider is not responding."
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"GPS API HTTP error {e.response.status_code}: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GPS service error (HTTP {e.response.status_code})."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected GPS service error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected GPS service error."
            )
    
    async def get_vehicle_info_by_device_id(self, device_unique_id: str) -> Dict[str, Any]:
        """
        Fetch specific vehicle information by device ID from EERA API.
        
        Args:
            device_unique_id: Device unique ID (IMEI)
            
        Returns:
            Vehicle information including location, status, and attributes
            
        Raises:
            HTTPException: If the API request fails or vehicle not found
        """
        vehicles = await self.get_all_vehicles_info()
        
        for vehicle in vehicles:
            if vehicle.get("deviceUniqueId") == device_unique_id:
                return vehicle
        
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle with device ID {device_unique_id} not found in GPS system"
        )
    
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
            logger.debug(f"Fetching GPS data from EERA API")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}{self.endpoint}",
                    params={"accessToken": access_token}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Check if API call was successful
                if not data.get("successful", False):
                    error_msg = data.get('message', 'Unknown error')
                    logger.error(f"EERA API request failed: {error_msg}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"GPS service error: {error_msg}. Please check the device access token."
                    )
                
                # Validate that we got device data
                if not data.get("object") or len(data["object"]) == 0:
                    logger.warning(f"No device data returned from EERA API")
                    raise HTTPException(
                        status_code=404,
                        detail="No GPS data found for this device. Please verify the device is online."
                    )
                
                logger.debug(f"GPS data fetched successfully")
                return data["object"][0]
                
        except httpx.TimeoutException:
            logger.error(f"GPS API request timeout (>10s)")
            raise HTTPException(
                status_code=504,
                detail="GPS service timeout. The GPS provider is not responding. Please try again later."
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"GPS API HTTP error {e.response.status_code}: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GPS service error (HTTP {e.response.status_code}). Please contact support if this persists."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected GPS service error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected GPS service error. Please try again later."
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
