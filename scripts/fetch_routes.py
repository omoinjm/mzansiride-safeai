#!/usr/bin/env python3
"""Add alternative road routes to src/core/routes.json (one-off data refresh; no runtime dependency).

Drivers often follow Waze or Google Maps, which may pick a different, perfectly sensible road than our
planned route. The deviation rule compares a car against the planned route AND these alternatives, so
following a plausible alternative is not flagged. Source: OSRM demo server (OpenStreetMap data).
The planned routes themselves are left unchanged.

    python3 scripts/fetch_routes.py
"""
import json
import math
import time
import urllib.request
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "src/core/routes.json"
OSRM = "https://router.project-osrm.org/route/v1/driving/{coords}?alternatives={alts}&overview=full&geometries=geojson"
MAX_DETOUR = 1.4   # a "via" alternative may be at most 40% longer than the planned route
MIN_APART_M = 150  # ...and must actually use different roads (median distance from the planned route)
TOLERANCE_M = 8  # same simplification as the planned routes


def _xy(p, lat0):
    return (p[1] * 111_320 * math.cos(math.radians(lat0)), p[0] * 110_540)


def _seg_dist(p, a, b, lat0):
    (px, py), (ax, ay), (bx, by) = _xy(p, lat0), _xy(a, lat0), _xy(b, lat0)
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def simplify(points, tol=TOLERANCE_M):
    """Douglas-Peucker on [lat, lng] points."""
    if len(points) < 3:
        return points
    lat0 = points[0][0]
    keep, stack = {0, len(points) - 1}, [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0.0, None
        for k in range(i + 1, j):
            d = _seg_dist(points[k], points[i], points[j], lat0)
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep.add(idx)
            stack += [(i, idx), (idx, j)]
    return [points[k] for k in sorted(keep)]


def _fetch(coords, alts=3):
    url = OSRM.format(coords=";".join(f"{lng},{lat}" for lat, lng in coords), alts=str(alts).lower())
    req = urllib.request.Request(url, headers={"User-Agent": "mzansiride-hackathon-prototype"})
    with urllib.request.urlopen(req, timeout=30) as r:
        routes = json.loads(r.read())["routes"]
    time.sleep(1.1)  # be polite to the free demo server
    return [([[round(lat, 5), round(lng, 5)] for lng, lat in x["geometry"]["coordinates"]], x["distance"]) for x in routes]


def _apart(points, planned):
    lat0 = planned[0][0]
    d = sorted(min(_seg_dist(p, planned[i], planned[i + 1], lat0) for i in range(len(planned) - 1)) for p in points)
    return d[len(d) // 2]


def _via_alternatives(a, b, planned, distance_m):
    """Routes through a waypoint 0.7-1.5 km either side of the straight line (what Waze might pick)."""
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    dy, dx = b[0] - a[0], (b[1] - a[1]) * math.cos(math.radians(mid[0]))
    norm = math.hypot(dx, dy) or 1
    found = []
    for side in (1, -1):
        for off_deg in (0.006, 0.009, 0.014):  # ~0.7, 1 and 1.5 km
            off = off_deg * side
            via = (mid[0] + dx / norm * off, mid[1] - dy / norm * off / math.cos(math.radians(mid[0])))
            pts, dist = _fetch([a, via, b], alts=False)[0]
            if dist <= distance_m * MAX_DETOUR and _apart(pts, planned) >= MIN_APART_M:
                found.append(simplify(pts))
                break  # one alternative per side is enough
    return found


def main():
    data = json.loads(ROUTES.read_text())
    places = {p["id"]: p for p in data["places"]}
    total = 0
    for rid, route in data["routes"].items():
        a, b = ((places[x]["lat"], places[x]["lng"]) for x in rid.split("__"))
        # The first OSRM route is the main one, which our planned route already is.
        alts = [simplify(pts) for pts, _ in _fetch([a, b])[1:] if _apart(pts, route["points"]) >= MIN_APART_M]
        if not alts:
            alts = _via_alternatives(a, b, route["points"], route["distance_m"])
        route["alternatives"] = alts
        total += len(alts)
        print(f"{rid}: {len(alts)} alternative(s)")
    data["source"] = data["source"].split(";")[0] + f"; alternatives fetched {time.strftime('%Y-%m-%d')}"
    ROUTES.write_text(json.dumps(data, separators=(",", ":")))
    print(f"{total} alternatives across {len(data['routes'])} routes")


if __name__ == "__main__":
    main()
