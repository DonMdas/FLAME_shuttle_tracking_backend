"""
OSRM (Open Source Routing Machine) service for routing and ETA calculations.

This service handles all interactions with the OSRM API, including:
- Route calculations
- Distance matrix (table) calculations
- Error handling and fallback logic
- Rate limiting and caching
"""

import httpx
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.core.route_config import haversine_distance
from app.core.logger import logger, log_osrm_request


class OSRMService:
    """Service for interacting with OSRM routing API"""
    
    def __init__(self):
        # OSRM public server
        self.base_url = "http://router.project-osrm.org"
        
        # Configuration
        self.timeout = 10.0
        self.default_profile = "driving"
        
        # Simple cache for OSRM responses (TTL: 60 seconds)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(seconds=60)
        
        # Average speeds for fallback calculations (meters per second)
        self.avg_speeds = {
            "driving": 13.89,  # ~50 km/h
            "walking": 1.39    # ~5 km/h
        }
    
    def _build_coords_string(self, coords: List[Tuple[float, float]]) -> str:
        """
        Build coordinate string for OSRM API.
        
        Args:
            coords: List of (latitude, longitude) tuples
            
        Returns:
            Coordinate string in OSRM format (lon,lat;lon,lat;...)
        """
        # OSRM expects lon,lat format
        return ";".join([f"{lon},{lat}" for lat, lon in coords])
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp < self._cache_ttl:
                return value
            else:
                # Expired, remove from cache
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set value in cache with current timestamp"""
        self._cache[key] = (value, datetime.utcnow())
    
    async def get_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "driving"
    ) -> Dict[str, Any]:
        """
        Get route from origin to destination using OSRM Route API.
        
        Args:
            origin: (latitude, longitude) of starting point
            destination: (latitude, longitude) of ending point
            profile: Routing profile ("driving" or "walking")
            
        Returns:
            Dict with keys: duration_seconds, distance_meters, osrm_request
            
        Raises:
            HTTPException: If OSRM request fails
        """
        coords_str = self._build_coords_string([origin, destination])
        url = f"{self.base_url}/route/v1/{profile}/{coords_str}"
        params = {"overview": "false"}
        
        # Check cache
        cache_key = f"route:{coords_str}:{profile}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            logger.debug(f"OSRM route request: {origin} -> {destination} ({profile})")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") != "Ok":
                    # OSRM returned an error
                    error_msg = data.get('message', 'No route found')
                    logger.warning(f"OSRM route error: {error_msg}")
                    log_osrm_request(origin, 1, success=False, error=error_msg)
                    # Use fallback instead of raising error
                    return self._fallback_estimate(origin, destination, profile)
                
                if not data.get("routes") or len(data["routes"]) == 0:
                    logger.warning(f"OSRM returned no routes")
                    log_osrm_request(origin, 1, success=False, error="No routes returned")
                    return self._fallback_estimate(origin, destination, profile)
                
                route = data["routes"][0]
                result = {
                    "duration_seconds": int(route["duration"]),
                    "distance_meters": int(route["distance"]),
                    "osrm_request": f"{url}?{params}"
                }
                
                # Cache the result
                self._set_cache(cache_key, result)
                log_osrm_request(origin, 1, success=True)
                
                return result
                
        except httpx.TimeoutException:
            logger.warning(f"OSRM route timeout, using fallback estimate")
            log_osrm_request(origin, 1, success=False, error="Timeout")
            return self._fallback_estimate(origin, destination, profile)
        except httpx.HTTPStatusError as e:
            logger.error(f"OSRM HTTP error {e.response.status_code}: {e.response.text}")
            log_osrm_request(origin, 1, success=False, error=f"HTTP {e.response.status_code}")
            if e.response.status_code >= 500:
                # OSRM server error, use fallback
                return self._fallback_estimate(origin, destination, profile)
            # Client error, use fallback
            return self._fallback_estimate(origin, destination, profile)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected OSRM error: {type(e).__name__} - {str(e)}")
            log_osrm_request(origin, 1, success=False, error=str(e))
            return self._fallback_estimate(origin, destination, profile)
    
    async def get_table(
        self,
        origin: Tuple[float, float],
        destinations: List[Tuple[float, float]],
        profile: str = "driving"
    ) -> List[Dict[str, Any]]:
        """
        Get distance/duration matrix from origin to multiple destinations using OSRM Table API.
        
        Args:
            origin: (latitude, longitude) of starting point
            destinations: List of (latitude, longitude) tuples for destinations
            profile: Routing profile ("driving" or "walking")
            
        Returns:
            List of dicts with keys: duration_seconds, distance_meters, osrm_request
            One entry per destination in the same order.
            
        Raises:
            HTTPException: If OSRM request fails
        """
        # Build coordinate string: origin first, then all destinations
        all_coords = [origin] + destinations
        coords_str = self._build_coords_string(all_coords)
        
        # Sources=0 (origin), destinations=1,2,3... (all the rest)
        sources = "0"
        destinations_indices = ";".join(str(i) for i in range(1, len(all_coords)))
        
        url = f"{self.base_url}/table/v1/{profile}/{coords_str}"
        params = {
            "sources": sources,
            "destinations": destinations_indices,
            "annotations": "duration,distance"
        }
        
        # Check cache
        cache_key = f"table:{coords_str}:{profile}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") != "Ok":
                    raise HTTPException(
                        status_code=503,
                        detail=f"OSRM error: {data.get('message', 'No route found')}"
                    )
                
                # Extract durations and distances
                durations = data.get("durations", [[]])[0]  # First row (from origin)
                distances = data.get("distances", [[]])[0]  # First row (from origin)
                
                if len(durations) != len(destinations) or len(distances) != len(destinations):
                    raise HTTPException(
                        status_code=503,
                        detail="OSRM returned incomplete matrix"
                    )
                
                results = []
                for i, (duration, distance) in enumerate(zip(durations, distances)):
                    if duration is None or distance is None:
                        # No route found for this destination, use fallback
                        fallback = self._fallback_estimate(origin, destinations[i], profile)
                        results.append(fallback)
                    else:
                        results.append({
                            "duration_seconds": int(duration),
                            "distance_meters": int(distance),
                            "osrm_request": f"{url}?sources={sources}&destinations={destinations_indices}&annotations=duration,distance"
                        })
                
                # Cache the results
                self._set_cache(cache_key, results)
                
                return results
                
        except httpx.TimeoutException:
            # Fallback for all destinations
            return [self._fallback_estimate(origin, dest, profile) for dest in destinations]
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                # OSRM server error, use fallback for all
                return [self._fallback_estimate(origin, dest, profile) for dest in destinations]
            raise HTTPException(
                status_code=503,
                detail=f"OSRM service error: {e.response.text}"
            )
        except HTTPException:
            raise
        except Exception as e:
            # Any other error, use fallback for all
            return [self._fallback_estimate(origin, dest, profile) for dest in destinations]
    
    def _fallback_estimate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "driving"
    ) -> Dict[str, Any]:
        """
        Calculate fallback ETA using great-circle distance and average speed.
        
        Args:
            origin: (latitude, longitude) of starting point
            destination: (latitude, longitude) of ending point
            profile: Routing profile for speed selection
            
        Returns:
            Dict with estimated duration and distance, marked as fallback
        """
        lat1, lon1 = origin
        lat2, lon2 = destination
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        avg_speed = self.avg_speeds.get(profile, self.avg_speeds["driving"])
        duration = distance / avg_speed
        
        logger.debug(f"Using fallback estimate: {distance}m, {int(duration)}s")
        
        return {
            "duration_seconds": int(duration),
            "distance_meters": int(distance),
            "source": "estimate_fallback",
            "osrm_request": None
        }


# Singleton instance
osrm_service = OSRMService()
