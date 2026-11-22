"""Small geodesy helpers (pure Python, no dependencies)."""
from __future__ import annotations
import math

EARTH_R_KM = 6371.0088
_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(bearing: float) -> str:
    return _COMPASS[int((bearing + 22.5) // 45) % 8]


def _xy(lat0, lon0, lat, lon):
    return (lon - lon0) * 111.32 * math.cos(math.radians(lat0)), (lat - lat0) * 110.57


def point_segment_km(lat, lon, a, b) -> float:
    ax, ay = _xy(lat, lon, *a)
    bx, by = _xy(lat, lon, *b)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    return math.hypot(ax + t * dx, ay + t * dy)


def point_polyline_km(lat, lon, pts) -> float:
    return min(point_segment_km(lat, lon, pts[i], pts[i + 1]) for i in range(len(pts) - 1))
