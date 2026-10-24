"""Small geometry helpers (metres, WGS84). Accurate enough for city-scale distances."""
import math

EARTH_R = 6_371_000.0


def haversine(a, b):
    """Distance in metres between (lat, lng) points."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def _xy(p, lat0):
    """Equirectangular projection around lat0, in metres."""
    return (
        EARTH_R * math.radians(p[1]) * math.cos(math.radians(lat0)),
        EARTH_R * math.radians(p[0]),
    )


def distance_to_polyline(p, line):
    """Shortest distance in metres from point p to a polyline [(lat, lng), ...]."""
    if not line:
        return float("inf")
    if len(line) == 1:
        return haversine(p, line[0])
    px, py = _xy(p, p[0])
    best = float("inf")
    for a, b in zip(line, line[1:]):
        ax, ay = _xy(a, p[0])
        bx, by = _xy(b, p[0])
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def polyline_length(line):
    return sum(haversine(a, b) for a, b in zip(line, line[1:]))
