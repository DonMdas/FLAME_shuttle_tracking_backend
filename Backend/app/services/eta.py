"""
ETA (Estimated Time of Arrival) calculation service.

This service handles:
- Determining upcoming stops for a vehicle
- Filtering out already-passed stops
- Computing ETAs using OSRM
- Handling edge cases (off-route, stale location, etc.)
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.route_config import (
    Station, STATIONS, ROUTE_DEFINITIONS,
    get_route_stops, get_route_direction,
    haversine_distance, find_nearest_station
)
from services.osrm import osrm_service
from schemas.eta import Stop, StopWithETA
from app.db.models import Vehicle, Schedule


class ETAService:
    """Service for calculating ETAs to upcoming stops"""
    
    def __init__(self):
        # Configuration
        self.stale_threshold_seconds = 60  # Location older than 60s is stale
        self.off_route_threshold_meters = 500  # More than 500m from route = off-route
        self.arriving_threshold_meters = 100  # Within 100m of stop = arriving
        self.max_stops_limit = 10  # Maximum number of stops to return
    
    async def get_upcoming_stops_eta(
        self,
        vehicle: Vehicle,
        schedule: Schedule,
        current_location: Tuple[float, float],
        location_timestamp: datetime,
        max_stops: int = 2,
        mode: str = "driving"
    ) -> Dict[str, Any]:
        """
        Calculate ETA to upcoming stops for a vehicle on its route.
        
        Args:
            vehicle: Vehicle object
            schedule: Active schedule for the vehicle
            current_location: (latitude, longitude) of vehicle
            location_timestamp: When the location was recorded
            max_stops: Maximum number of upcoming stops to return
            mode: Travel mode ("driving" or "walking")
            
        Returns:
            Dict with route info, upcoming stops with ETAs, and status flags
        """
        # Limit max_stops
        max_stops = min(max_stops, self.max_stops_limit)
        
        # Determine if location is stale
        now_utc = datetime.now(timezone.utc)
        age_seconds = (now_utc - location_timestamp).total_seconds()
        is_stale = age_seconds > self.stale_threshold_seconds
        
        # Get route information from schedule's route_id
        route_id = schedule.route_id
        
        # Validate route exists in our definitions
        if route_id not in ROUTE_DEFINITIONS:
            return {
                "route_id": route_id,
                "direction": "Unknown Route",
                "upcoming_stops": [],
                "off_route": True,
                "stale": is_stale,
                "error": f"Route '{route_id}' not found in route definitions"
            }
        
        direction = get_route_direction(route_id)
        
        # Get ordered stops for this route
        route_stops = get_route_stops(route_id)
        
        if not route_stops:
            return {
                "route_id": route_id,
                "direction": direction,
                "upcoming_stops": [],
                "off_route": True,
                "stale": is_stale,
                "error": "No stops defined for route"
            }
        
        # Filter out stops that have been passed
        upcoming_stops_list = self._filter_upcoming_stops(
            current_location,
            route_stops
        )
        
        # Check if vehicle is off-route
        is_off_route = self._is_off_route(current_location, route_stops)
        
        # Limit to max_stops
        upcoming_stops_list = upcoming_stops_list[:max_stops]
        
        if not upcoming_stops_list:
            return {
                "route_id": route_id,
                "direction": direction,
                "upcoming_stops": [],
                "off_route": is_off_route,
                "stale": is_stale
            }
        
        # Calculate ETAs using OSRM
        stops_with_eta = await self._calculate_etas(
            current_location,
            upcoming_stops_list,
            mode
        )
        
        return {
            "route_id": route_id,
            "direction": direction,
            "upcoming_stops": stops_with_eta,
            "off_route": is_off_route,
            "stale": is_stale
        }
    
    def _filter_upcoming_stops(
        self,
        current_location: Tuple[float, float],
        route_stops: List[Station]
    ) -> List[Station]:
        """
        Filter stops to return only those that are upcoming (not yet passed).
        
        Direction-aware strategy that uses the ordered route sequence:
        1. Determine which segment of the route the vehicle is currently on
        2. Mark all stops before that segment as "passed"
        3. Return stops from current segment onwards
        
        This avoids the problem where geometric distance alone might be misleading
        (e.g., bus closer to a stop it already passed due to road layout).
        
        Args:
            current_location: (latitude, longitude) of vehicle
            route_stops: Ordered list of stops on route (direction-aware)
            
        Returns:
            List of upcoming stops (not yet passed)
        """
        if not route_stops:
            return []
        
        if len(route_stops) == 1:
            return route_stops
        
        lat, lon = current_location
        
        # Calculate distances to all stops
        distances = []
        for stop in route_stops:
            distance = haversine_distance(lat, lon, stop.lat, stop.lon)
            distances.append(distance)
        
        # Find which segment the vehicle is on by analyzing consecutive stop pairs
        current_segment_idx = self._find_current_segment(
            current_location,
            route_stops,
            distances
        )
        
        # If very close to a specific stop (arriving), include it
        min_distance = min(distances)
        if min_distance < self.arriving_threshold_meters:
            min_distance_idx = distances.index(min_distance)
            # Include this stop and all following
            return route_stops[min_distance_idx:]
        
        # Return stops from current segment onwards
        return route_stops[current_segment_idx:]
    
    def _find_current_segment(
        self,
        current_location: Tuple[float, float],
        route_stops: List[Station],
        distances: List[float]
    ) -> int:
        """
        Determine which route segment the vehicle is currently on.
        
        A segment is defined as the path between two consecutive stops.
        Uses directional logic: if traveling from stop[i] to stop[i+1],
        the vehicle should be getting closer to stop[i+1] and farther from stop[i].
        
        Args:
            current_location: (latitude, longitude) of vehicle
            route_stops: Ordered list of stops on route
            distances: Pre-calculated distances to each stop
            
        Returns:
            Index of the next upcoming stop (start of remaining route)
        """
        lat, lon = current_location
        
        # Check each consecutive pair of stops
        for i in range(len(route_stops) - 1):
            stop_current = route_stops[i]
            stop_next = route_stops[i + 1]
            
            dist_current = distances[i]
            dist_next = distances[i + 1]
            
            # Check if vehicle is on segment between stop[i] and stop[i+1]
            # Key indicator: closer to next stop than current stop
            if dist_next < dist_current:
                # Vehicle has passed stop[i] and is approaching stop[i+1]
                # Return i+1 as the first upcoming stop
                return i + 1
            
            # Alternative check: Use projection onto the segment line
            # to see if vehicle is between the two stops
            projection_ratio = self._project_onto_segment(
                current_location,
                (stop_current.lat, stop_current.lon),
                (stop_next.lat, stop_next.lon)
            )
            
            # If projection is between 0 and 1, vehicle is on this segment
            if 0 <= projection_ratio <= 1:
                # Check if closer to next stop (progressing forward)
                if projection_ratio > 0.5:
                    # Past midpoint, next stop is upcoming
                    return i + 1
                else:
                    # Before midpoint, current stop might still be upcoming
                    # But since we're on this segment, current stop is likely passed
                    # unless we're very close to it
                    if dist_current < self.arriving_threshold_meters:
                        return i
                    return i + 1
        
        # Default: if all checks fail, find nearest stop
        # This handles edge cases like vehicle off-route
        min_distance_idx = distances.index(min(distances))
        return min_distance_idx
    
    def _project_onto_segment(
        self,
        point: Tuple[float, float],
        seg_start: Tuple[float, float],
        seg_end: Tuple[float, float]
    ) -> float:
        """
        Project a point onto a line segment and return the projection ratio.
        
        Returns a value between 0 and 1 if the projection falls on the segment:
        - 0 = at seg_start
        - 1 = at seg_end
        - 0.5 = midpoint
        
        Values < 0 or > 1 indicate projection falls outside the segment.
        
        Args:
            point: (lat, lon) of the point to project
            seg_start: (lat, lon) of segment start
            seg_end: (lat, lon) of segment end
            
        Returns:
            Projection ratio (0-1 if on segment, outside otherwise)
        """
        # Convert to Cartesian-like coordinates (approximation for small distances)
        px, py = point[1], point[0]  # lon, lat
        ax, ay = seg_start[1], seg_start[0]
        bx, by = seg_end[1], seg_end[0]
        
        # Vector from A to B
        abx = bx - ax
        aby = by - ay
        
        # Vector from A to P
        apx = px - ax
        apy = py - ay
        
        # Dot product and magnitude
        ab_ab = abx * abx + aby * aby
        
        if ab_ab == 0:
            # Segment has zero length
            return 0
        
        ap_ab = apx * abx + apy * aby
        
        # Projection ratio
        t = ap_ab / ab_ab
        
        return t
    
    def _is_off_route(
        self,
        current_location: Tuple[float, float],
        route_stops: List[Station]
    ) -> bool:
        """
        Determine if vehicle is off-route based on distance to nearest stop.
        
        Args:
            current_location: (latitude, longitude) of vehicle
            route_stops: List of stops on route
            
        Returns:
            True if vehicle appears to be off the route
        """
        if not route_stops:
            return True
        
        # Find nearest stop
        nearest_station, distance = find_nearest_station(*current_location)
        
        # Check if this nearest station is on the route
        on_route = any(stop.id == nearest_station.id for stop in route_stops)
        
        if not on_route:
            return True
        
        # Check distance threshold
        return distance > self.off_route_threshold_meters
    
    async def _calculate_etas(
        self,
        origin: Tuple[float, float],
        stops: List[Station],
        mode: str
    ) -> List[StopWithETA]:
        """
        Calculate ETAs from origin to each stop using OSRM.
        
        Args:
            origin: (latitude, longitude) of starting point
            stops: List of destination stops
            mode: Travel mode
            
        Returns:
            List of StopWithETA objects
        """
        if len(stops) == 1:
            # Single stop - use route API
            result = await osrm_service.get_route(
                origin,
                (stops[0].lat, stops[0].lon),
                mode
            )
            
            # Determine status
            status = "arriving" if result["distance_meters"] < self.arriving_threshold_meters else "upcoming"
            source = result.get("source", "osrm")
            
            return [StopWithETA(
                stop_id=stops[0].id,
                name=stops[0].name,
                lat=stops[0].lat,
                lon=stops[0].lon,
                eta_seconds=result["duration_seconds"],
                distance_meters=result["distance_meters"],
                status=status,
                source=source,
                osrm_request=result.get("osrm_request")
            )]
        else:
            # Multiple stops - use table API for efficiency
            destinations = [(stop.lat, stop.lon) for stop in stops]
            results = await osrm_service.get_table(origin, destinations, mode)
            
            stops_with_eta = []
            for stop, result in zip(stops, results):
                # Determine status
                status = "arriving" if result["distance_meters"] < self.arriving_threshold_meters else "upcoming"
                source = result.get("source", "osrm")
                
                stops_with_eta.append(StopWithETA(
                    stop_id=stop.id,
                    name=stop.name,
                    lat=stop.lat,
                    lon=stop.lon,
                    eta_seconds=result["duration_seconds"],
                    distance_meters=result["distance_meters"],
                    status=status,
                    source=source,
                    osrm_request=result.get("osrm_request")
                ))
            
            return stops_with_eta
    
    async def calculate_etas_to_coordinates(
        self,
        origin: Tuple[float, float],
        targets: List[Tuple[str, float, float]],  # (id, lat, lon)
        mode: str = "driving"
    ) -> List[Dict[str, Any]]:
        """
        Calculate ETAs from origin to arbitrary target coordinates.
        
        Args:
            origin: (latitude, longitude) of starting point
            targets: List of (id, latitude, longitude) tuples
            mode: Travel mode
            
        Returns:
            List of dicts with ETA information for each target
        """
        if not targets:
            return []
        
        if len(targets) == 1:
            # Single target - use route API
            target_id, lat, lon = targets[0]
            result = await osrm_service.get_route(origin, (lat, lon), mode)
            
            return [{
                "id": target_id,
                "lat": lat,
                "lon": lon,
                "eta_seconds": result["duration_seconds"],
                "distance_meters": result["distance_meters"],
                "source": result.get("source", "osrm"),
                "osrm_request": result.get("osrm_request")
            }]
        else:
            # Multiple targets - use table API
            destinations = [(lat, lon) for _, lat, lon in targets]
            results = await osrm_service.get_table(origin, destinations, mode)
            
            etas = []
            for (target_id, lat, lon), result in zip(targets, results):
                etas.append({
                    "id": target_id,
                    "lat": lat,
                    "lon": lon,
                    "eta_seconds": result["duration_seconds"],
                    "distance_meters": result["distance_meters"],
                    "source": result.get("source", "osrm"),
                    "osrm_request": result.get("osrm_request")
                })
            
            return etas


# Singleton instance
eta_service = ETAService()
