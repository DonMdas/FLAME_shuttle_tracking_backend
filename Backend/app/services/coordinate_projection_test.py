from typing import Tuple, List, Dict

def project_points_onto_segment(
    segment_start: Tuple[float, float],
    segment_end: Tuple[float, float],
    points: List[Tuple[str, Tuple[float, float]]]
) -> List[Dict]:
    """
    Projects labeled points onto a line segment and returns projection data.

    Args:
        segment_start: (lat, lon) of segment start
        segment_end: (lat, lon) of segment end
        points: List of (label, (lat, lon)) tuples

    Returns:
        A list of dictionaries sorted by projection ratio:
        [
            {
                "label": ...,
                "ratio": ...,
                "projected_point": (lat, lon)
            },
            ...
        ]
    """

    def project(point, A, B):
        # Convert lat/lon → x/y (lon, lat)
        px, py = point[1], point[0]
        ax, ay = A[1], A[0]
        bx, by = B[1], B[0]

        # Vector AB
        abx = bx - ax
        aby = by - ay
        
        # Avoid division by zero
        ab_ab = abx * abx + aby * aby
        if ab_ab == 0:
            return 0, (A[0], A[1])

        # Vector AP
        apx = px - ax
        apy = py - ay

        # Projection ratio
        t = (apx * abx + apy * aby) / ab_ab

        # Compute projected point (in lon/lat)
        proj_x = ax + t * abx
        proj_y = ay + t * aby

        return t, (proj_y, proj_x)

    results = []
    for label, point in points:
        ratio, proj = project(point, segment_start, segment_end)
        results.append({
            "label": label,
            "ratio": ratio,
            "projected_point": proj
        })

    # Sort points along the segment based on projection ratio
    results.sort(key=lambda x: x["ratio"])

    return results



import sys
import os

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from Backend.app.core.route_config import Station, STATIONS

segment_start = (STATIONS["campus"].lat, STATIONS["campus"].lon)
segment_end   = (STATIONS["fc-road"].lat, STATIONS["fc-road"].lon)

points = [
    ("P1", (18.5301, 73.8602)),
    ("P2", (18.5450, 73.8700)),
    ("P3", (18.5550, 73.8900)),
    ("P4", (18.5230, 73.8530))
]

result = project_points_onto_segment(segment_start, segment_end, points)

for r in result:
    print(r)
