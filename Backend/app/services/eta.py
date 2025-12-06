"""
ETA (Estimated Time of Arrival) calculation service.

This service handles:
- Determining upcoming stops for a vehicle
- Filtering out already-passed stops
- Computing ETAs using OSRM
- Handling edge cases (off-route, stale location, etc.)
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import math

from core.route_config import (
    Station, STATIONS, ROUTE_DEFINITIONS,
    get_route_stops, get_route_direction,
    haversine_distance
)
from services.osrm import osrm_service
from schemas.eta import StopWithETA, Stop, SegmentProgress
from app.db.models import Vehicle, Schedule
from core.logger import logger


class ETAService:
    """Service for calculating ETAs to upcoming stops"""
    
    def __init__(self):
        # Configuration
        self.stale_threshold_seconds = 60  # Location older than 60s is stale
        # Increased threshold to avoid false positives on curved roads
        self.off_route_threshold_meters = 1000 
        self.arriving_threshold_meters = 100  # Within 100m of stop = arriving
        self.max_stops_limit = 10  # Maximum number of stops to return
        
        # Cache for OSRM segment distances (route_id -> {segment_key: distance})
        self._segment_distance_cache: Dict[str, Dict[str, float]] = {}
    
    async def get_upcoming_stops_eta(
        self,
        vehicle: Vehicle,
        schedule: Schedule,
        current_location: Tuple[float, float],
        location_timestamp: datetime,
        max_stops: int = 3,
        mode: str = "driving"
    ) -> Dict[str, Any]:
        """
        Calculate ETA to upcoming stops for a vehicle on its route.
        """
        # Limit max_stops
        max_stops = min(max_stops, self.max_stops_limit)
        
        # 1. Stale Check
        now_utc = datetime.now(timezone.utc)
        age_seconds = (now_utc - location_timestamp).total_seconds()
        is_stale = age_seconds > self.stale_threshold_seconds
        
        # 2. Route Validation
        route_id = schedule.route_id
        if route_id not in ROUTE_DEFINITIONS:
            return self._build_error_response(route_id, "Unknown Route", is_stale, "Route definition not found")
        
        direction = get_route_direction(route_id)
        route_stops = get_route_stops(route_id)
        
        if not route_stops:
            return self._build_error_response(route_id, direction, is_stale, "No stops defined")
        
        # 3. Determine Route Progress (Filter passed stops)
        upcoming_stops_list = self._filter_upcoming_stops(
            current_location,
            route_stops
        )
        
        # 4. Off-Route Check (For UI flag only - NOT for blocking)
        # We calculate this just to tell the frontend, but we proceed with ETA anyway.
        is_off_route_flag = self._is_off_route(current_location, route_stops, upcoming_stops_list)
        
        # Slice to requested limit
        stops_slice = upcoming_stops_list[:max_stops]
        stops_with_eta = []

        # 5. Calculate ETAs
        if not stops_slice:
            pass # No stops left
            
        else:
            # ALWAYS Try OSRM (Since we run locally, it's cheap)
            try:
                stops_with_eta = await self._calculate_etas(
                    current_location,
                    stops_slice,
                    mode
                )
            except Exception as e:
                print(f"OSRM Calculation crashed: {e}")
                stops_with_eta = []
            
            # 6. FAILSAFE: If OSRM returned empty (API Error), fallback to basic list
            if not stops_with_eta:
                print("WARNING: OSRM failed/empty. Returning static stop data.")
                stops_with_eta = [
                    StopWithETA(
                        stop_id=s.id, 
                        name=s.name, 
                        lat=s.lat, 
                        lon=s.lon,
                        eta_seconds=-1,      
                        distance_meters=-1, 
                        status="upcoming", 
                        source="estimate_fallback" 
                    ) for s in stops_slice
                ]
        
        # 7. Calculate segment progress if vehicle is on route using OSRM distances
        current_segment = None
        
        logger.info(f"Segment Progress Check - off_route={is_off_route_flag}, stale={is_stale}, upcoming_stops_count={len(upcoming_stops_list) if upcoming_stops_list else 0}, eta_stops_count={len(stops_with_eta) if stops_with_eta else 0}")
        
        # Calculate segment progress even if data is stale - position calculation is still valid
        if not is_off_route_flag and upcoming_stops_list and stops_with_eta:
            # Find current segment based on full route
            current_segment_idx = self._find_current_segment(current_location, route_stops)
            
            logger.info(f"Segment Progress - current_segment_idx={current_segment_idx}, total_stops={len(route_stops)}")
            logger.info(f"Segment Progress - upcoming_stops_list={[s.id for s in upcoming_stops_list]}")
            logger.info(f"Segment Progress - all_route_stops={[s.id for s in route_stops]}")
            
            # Segment index tells us vehicle is between stop[i] and stop[i+1]
            # We need both stops to exist
            if current_segment_idx >= 0 and current_segment_idx < len(route_stops) - 1:
                from_station = route_stops[current_segment_idx]
                to_station = route_stops[current_segment_idx + 1]
                
                logger.info(f"Segment Progress - detected segment={from_station.id}->{to_station.id}")
                
                # Verify that to_station is actually in upcoming stops (not already passed)
                # This handles edge case where vehicle is past all stops
                to_station_in_upcoming = any(s.id == to_station.id for s in upcoming_stops_list)
                
                logger.info(f"Segment Progress - to_station_in_upcoming={to_station_in_upcoming}")
                
                if to_station_in_upcoming:
                    # Get OSRM-based total segment distance (cached)
                    try:
                        total_distance = await self._get_segment_distance(
                            route_id,
                            from_station,
                            to_station,
                            mode
                        )
                        logger.info(f"Segment Progress - total_distance={total_distance}")
                        
                        # Get remaining distance from first stop in ETA results (already OSRM-calculated)
                        # The first stop in stops_with_eta is the next stop (to_station)
                        remaining_distance = None
                        for stop_eta in stops_with_eta:
                            if stop_eta.stop_id == to_station.id:
                                # Use OSRM distance if available, otherwise fallback to haversine
                                if stop_eta.source == "osrm" and stop_eta.distance_meters > 0:
                                    remaining_distance = float(stop_eta.distance_meters)
                                break
                        
                        logger.info(f"Segment Progress - remaining_distance from ETA={remaining_distance}")
                        
                        # Fallback to haversine if OSRM data not available
                        if remaining_distance is None:
                            remaining_distance = haversine_distance(
                                current_location[0], current_location[1],
                                to_station.lat, to_station.lon
                            )
                            logger.info(f"Segment Progress - using haversine fallback={remaining_distance}")
                        
                        # Calculate progress ratio (clamped to [0, 1])
                        progress_ratio = max(0.0, min(1.0, (total_distance - remaining_distance) / total_distance if total_distance > 0 else 0.0))
                        
                        logger.info(f"Segment Progress - progress_ratio={progress_ratio}")
                        
                        current_segment = SegmentProgress(
                            from_stop=Stop(
                                stop_id=from_station.id,
                                name=from_station.name,
                                lat=from_station.lat,
                                lon=from_station.lon
                            ),
                            to_stop=Stop(
                                stop_id=to_station.id,
                                name=to_station.name,
                                lat=to_station.lat,
                                lon=to_station.lon
                            ),
                            total_distance_meters=total_distance,
                            remaining_distance_meters=remaining_distance,
                            progress_ratio=progress_ratio
                        )
                        logger.info(f"Segment Progress - current_segment created successfully")
                    except Exception as e:
                        logger.error(f"Segment Progress - Failed to calculate: {e}", exc_info=True)
        
        return {
            "route_id": route_id,
            "direction": direction,
            "current_segment": current_segment,
            "upcoming_stops": stops_with_eta,
            "off_route": is_off_route_flag,
            "stale": is_stale
        }

    def _filter_upcoming_stops(
        self,
        current_location: Tuple[float, float],
        route_stops: List[Station]
    ) -> List[Station]:
        """
        Identify upcoming stops based on geometric progression along the route.
        """
        if not route_stops:
            return []
        
        if len(route_stops) == 1:
            return route_stops
            
        # Find the segment index the vehicle is currently on
        current_segment_idx = self._find_current_segment(current_location, route_stops)
        
        # If segment is i, it means we have passed stop[i] and are heading to stop[i+1]
        next_stop_idx = current_segment_idx + 1
        
        if next_stop_idx >= len(route_stops):
            return []
            
        return route_stops[next_stop_idx:]

    def _find_current_segment(
        self,
        current_location: Tuple[float, float],
        route_stops: List[Station]
    ) -> int:
        """
        Finds the route segment closest to the vehicle.
        Robust version: calculates distance to every segment and picks the minimum.
        """
        best_segment_idx = 0
        min_dist = float('inf')
        
        for i in range(len(route_stops) - 1):
            stop_a = route_stops[i]
            stop_b = route_stops[i+1]
            
            # Calculate distance to the segment (clamped to endpoints)
            dist, _ = self._point_to_segment_distance(
                current_location, 
                (stop_a.lat, stop_a.lon), 
                (stop_b.lat, stop_b.lon)
            )
            
            # Simple minimization
            if dist < min_dist:
                min_dist = dist
                best_segment_idx = i

        return best_segment_idx

    def _is_off_route(
        self,
        current_location: Tuple[float, float],
        all_stops: List[Station],
        upcoming_stops: List[Station]
    ) -> bool:
        """
        Determines off-route status by checking distance to the active route segment.
        """
        if not upcoming_stops or not all_stops:
            return True

        # Identify the "active" segment. 
        next_stop = upcoming_stops[0]
        
        # Find index of next_stop in all_stops
        try:
            next_idx = [i for i, s in enumerate(all_stops) if s.id == next_stop.id][0]
        except IndexError:
            return True

        # Previous stop (start of segment)
        prev_idx = max(0, next_idx - 1)
        prev_stop = all_stops[prev_idx]
        
        # If we are at the very start of route (prev == next), check radius
        if prev_stop.id == next_stop.id:
            dist = haversine_distance(current_location[0], current_location[1], next_stop.lat, next_stop.lon)
            return dist > self.off_route_threshold_meters

        # Calculate distance to the line segment (Prev -> Next)
        dist_to_segment, _ = self._point_to_segment_distance(
            current_location,
            (prev_stop.lat, prev_stop.lon),
            (next_stop.lat, next_stop.lon)
        )
        
        return dist_to_segment > self.off_route_threshold_meters

    async def _calculate_etas(
        self,
        origin: Tuple[float, float],
        stops: List[Station],
        mode: str
    ) -> List[StopWithETA]:
        """
        Calculates sequential ETAs using OSRM Waypoints.
        """
        if not stops:
            return []

        # Construct coordinate list: [Origin, Stop 1, Stop 2, ..., Stop N]
        coordinates = [origin]
        for stop in stops:
            coordinates.append((stop.lat, stop.lon))
            
        # Call OSRM Route Service
        route_result = await osrm_service.get_route_with_waypoints(coordinates, mode)
        
        # Check if the result is valid
        if not route_result or "legs" not in route_result:
            return []

        legs = route_result.get("legs", [])
        
        stops_with_eta = []
        accumulated_duration = 0
        accumulated_distance = 0
        
        for i, leg in enumerate(legs):
            if i >= len(stops):
                break
                
            stop = stops[i]
            
            accumulated_duration += leg["duration"]
            accumulated_distance += leg["distance"]
            
            status = "upcoming"
            if i == 0 and accumulated_distance < self.arriving_threshold_meters:
                status = "arriving"
            
            stops_with_eta.append(StopWithETA(
                stop_id=stop.id,
                name=stop.name,
                lat=stop.lat,
                lon=stop.lon,
                eta_seconds=int(accumulated_duration), 
                distance_meters=int(accumulated_distance), 
                status=status,
                source="osrm",
                osrm_request=route_result.get("osrm_request")
            ))
            
        return stops_with_eta

    def _point_to_segment_distance(
        self,
        point: Tuple[float, float],
        seg_start: Tuple[float, float],
        seg_end: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Calculates the perpendicular distance from a point to a line segment.
        """
        lat, lon = point
        slat, slon = seg_start
        elat, elon = seg_end

        R = 6371000  # Earth radius in meters
        rad = math.pi / 180
        
        avg_lat = (lat + slat + elat) / 3 * rad
        cos_lat = math.cos(avg_lat)
        
        px, py = lon * rad * cos_lat * R, lat * rad * R
        ax, ay = slon * rad * cos_lat * R, slat * rad * R
        bx, by = elon * rad * cos_lat * R, elat * rad * R
        
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        
        ab_sq = abx**2 + aby**2
        
        if ab_sq == 0:
            return math.sqrt(apx**2 + apy**2), 0.0
            
        t = (apx * abx + apy * aby) / ab_sq
        t_clamped = max(0, min(1, t))
        
        cx = ax + t_clamped * abx
        cy = ay + t_clamped * aby
        
        distance = math.sqrt((px - cx)**2 + (py - cy)**2)
        
        return distance, t

    async def _get_segment_distance(
        self,
        route_id: str,
        from_station: Station,
        to_station: Station,
        mode: str = "driving"
    ) -> float:
        """
        Get OSRM route distance between two consecutive stops.
        Uses cache to avoid repeated API calls for same segments.
        Falls back to haversine if OSRM fails.
        """
        # Create cache key
        segment_key = f"{from_station.id}->{to_station.id}"
        
        # Check cache
        if route_id not in self._segment_distance_cache:
            self._segment_distance_cache[route_id] = {}
        
        if segment_key in self._segment_distance_cache[route_id]:
            return self._segment_distance_cache[route_id][segment_key]
        
        # Calculate using OSRM
        try:
            result = await osrm_service.get_route(
                origin=(from_station.lat, from_station.lon),
                destination=(to_station.lat, to_station.lon),
                profile=mode  # Changed from mode= to profile=
            )
            
            if result and result.get("distance_meters", 0) > 0:
                distance = float(result["distance_meters"])
                # Cache the result
                self._segment_distance_cache[route_id][segment_key] = distance
                logger.info(f"Cached OSRM segment distance: {segment_key} = {distance}m")
                return distance
        except Exception as e:
            logger.warning(f"OSRM failed for segment {segment_key}: {e}")
        
        # Fallback to haversine (don't cache fallback - retry OSRM next time)
        fallback_distance = haversine_distance(
            from_station.lat, from_station.lon,
            to_station.lat, to_station.lon
        )
        
        logger.info(f"Using haversine fallback for {segment_key}: {fallback_distance}m (not cached)")
        return fallback_distance

    def _build_error_response(self, route_id, direction, is_stale, error_msg):
        return {
            "route_id": route_id,
            "direction": direction,
            "upcoming_stops": [],
            "off_route": True,
            "stale": is_stale,
            "error": error_msg
        }

# Singleton instance
eta_service = ETAService()