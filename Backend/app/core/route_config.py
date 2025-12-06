"""
Route configuration and constants for shuttle tracking system.

This module defines:
- Fixed station coordinates
- Route definitions with ordered stops
- Helper functions for route management
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class Station:
    """Represents a fixed station/stop"""
    id: str
    name: str
    lat: float
    lon: float


# ============ Fixed Station Coordinates ============

STATIONS = {
    "campus": Station(
        id="campus",
        name="FLAME Campus",
        lat=18.525778,
        lon=73.733243
    ),
    "bavdhan-guard-post": Station(
        id="bavdhan-guard-post",
        name="Bavdhan Check Post",
        lat=18.518468,
        lon=73.765785
    ),
    "fc-road": Station(
        id="fc-road",
        name="FC Road",
        lat=18.522335,
        lon=73.843739
    ),
    "vanaz-station": Station(
        id="vanaz-station",
        name="Vanaz Metro Station",
        lat=18.507034,
        lon=73.805283
    ),
    "anand-nagar-station": Station(
        id="anand-nagar-station",
        name="Anand Nagar Metro Station",
        lat=18.509569,
        lon=73.813995
    )
}


# ============ Route Definitions ============
# Each route is defined as a tuple: (route_id, from_station, to_station, ordered_stop_ids)

ROUTE_DEFINITIONS = {
    # Campus to FC Road (via Bavdhan Guard Post, then Vanaz Station)
    "campus-fcroad": {
        "route_id": "campus-fcroad",
        "name": "Campus → FC Road",
        "from_location": "Campus",
        "to_location": "FC Road",
        "stops": ["campus", "bavdhan-guard-post", "vanaz-station","anand-nagar-station", "fc-road"]
    },
    
    # FC Road to Campus (reverse route)
    "fcroad-campus": {
        "route_id": "fcroad-campus",
        "name": "FC Road → Campus",
        "from_location": "FC Road",
        "to_location": "Campus",
        "stops": ["fc-road","anand-nagar-station", "vanaz-station", "bavdhan-guard-post", "campus"]
    },
    
    # Campus to Bavdhan Guard Post (direct, no intermediate stops)
    "campus-bavdhan": {
        "route_id": "campus-bavdhan",
        "name": "Campus → Bavdhan Guard Post",
        "from_location": "Campus",
        "to_location": "Bavdhan Guard post",
        "stops": ["campus", "bavdhan-guard-post"]
    },
    
    # Bavdhan Guard Post to Campus (reverse)
    "bavdhan-campus": {
        "route_id": "bavdhan-campus",
        "name": "Bavdhan Guard Post → Campus",
        "from_location": "Bavdhan Guard post",
        "to_location": "Campus",
        "stops": ["bavdhan-guard-post", "campus"]
    }
}


# ============ Helper Functions ============

def get_route_by_locations(from_location: str, to_location: str) -> Dict:
    """
    Get route definition based on from and to locations.
    
    Args:
        from_location: Starting location name
        to_location: Ending location name
        
    Returns:
        Route definition dict or None if not found
    """
    # Normalize location names (case-insensitive, strip whitespace)
    from_loc_norm = from_location.strip().lower()
    to_loc_norm = to_location.strip().lower()
    
    for route_id, route_def in ROUTE_DEFINITIONS.items():
        route_from = route_def["from_location"].strip().lower()
        route_to = route_def["to_location"].strip().lower()
        
        if route_from == from_loc_norm and route_to == to_loc_norm:
            return route_def
    
    return None


def get_route_stops(route_id: str) -> List[Station]:
    """
    Get ordered list of stations for a given route.
    
    Args:
        route_id: Route identifier
        
    Returns:
        List of Station objects in order
    """
    if route_id not in ROUTE_DEFINITIONS:
        return []
    
    stop_ids = ROUTE_DEFINITIONS[route_id]["stops"]
    return [STATIONS[stop_id] for stop_id in stop_ids if stop_id in STATIONS]


def get_station_by_name(name: str) -> Station:
    """
    Get station by its display name (case-insensitive).
    
    Args:
        name: Display name of the station
        
    Returns:
        Station object or None if not found
    """
    name_norm = name.strip().lower()
    
    for station in STATIONS.values():
        if station.name.lower() == name_norm:
            return station
    
    return None


def get_all_route_ids() -> List[str]:
    """Get list of all route IDs"""
    return list(ROUTE_DEFINITIONS.keys())


def get_route_direction(route_id: str) -> str:
    """
    Get human-readable direction string for a route.
    
    Args:
        route_id: Route identifier
        
    Returns:
        Direction string (e.g., "Campus → FC Road")
    """
    if route_id not in ROUTE_DEFINITIONS:
        return "Unknown"
    
    return ROUTE_DEFINITIONS[route_id]["name"]


# ============ Geospatial Helper Functions ============

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        
    Returns:
        Distance in meters
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Earth's radius in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    # Haversine formula
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


def find_nearest_station(lat: float, lon: float) -> Tuple[Station, float]:
    """
    Find the nearest station to a given coordinate.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Tuple of (nearest_station, distance_in_meters)
    """
    nearest_station = None
    min_distance = float('inf')
    
    for station in STATIONS.values():
        distance = haversine_distance(lat, lon, station.lat, station.lon)
        if distance < min_distance:
            min_distance = distance
            nearest_station = station
    
    return nearest_station, min_distance
