"""Predefined safety rules (proposal 5.4). Pure functions: no AWS, no AI, fully unit-tested.

Detection is deliberately rule-based and separate from the AI explanation (proposal 6.1), so the
system's behaviour is predictable. An event is a *prompt for the passenger to check in*, never a
conclusion that the driver did something wrong: stops and detours often have innocent reasons.
"""
from .geo import distance_to_polyline, haversine

PROLONGED_STOP = "PROLONGED_STOP"
ROUTE_DEVIATION = "ROUTE_DEVIATION"

DEFAULTS = {
    "stop_radius_m": 30,  # moving less than this counts as "not moving"
    "stop_seconds": 180,  # stationary for 3 minutes (trip time) -> check-in
    "deviation_m": 250,  # further than this from the planned route...
    "deviation_ticks": 2,  # ...for this many consecutive readings -> check-in (filters GPS jitter)
    "endpoint_radius_m": 200,  # waiting near pickup or destination is normal
}


def new_state():
    return {"anchor": None, "anchor_ts": None, "last_ts": None, "off_route_ticks": 0, "latched": []}


def evaluate(state, tick, route_points, cfg=None):
    """Apply one position reading. Returns (new_state, [new events]).

    tick: {"lat", "lng", "ts"} where ts is trip time in seconds (the simulator's clock).
    A rule fires once, then stays latched until the condition clears (the car moves again or
    returns to the route), so one long stop produces one prompt rather than one per reading.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    s = {**new_state(), **(state or {})}
    s["latched"] = list(s.get("latched") or [])
    pos = (float(tick["lat"]), float(tick["lng"]))
    ts = float(tick["ts"])
    events = []

    if s["last_ts"] is not None and ts <= s["last_ts"]:
        return s, events  # duplicate or out-of-order reading
    s["last_ts"] = ts

    near_endpoint = bool(route_points) and min(
        haversine(pos, tuple(route_points[0])), haversine(pos, tuple(route_points[-1]))
    ) <= cfg["endpoint_radius_m"]

    # --- prolonged stop ---
    if s["anchor"] is None or haversine(pos, tuple(s["anchor"])) > cfg["stop_radius_m"]:
        s["anchor"], s["anchor_ts"] = [pos[0], pos[1]], ts
        if PROLONGED_STOP in s["latched"]:
            s["latched"].remove(PROLONGED_STOP)
    else:
        stationary = ts - s["anchor_ts"]
        if stationary >= cfg["stop_seconds"] and not near_endpoint and PROLONGED_STOP not in s["latched"]:
            s["latched"].append(PROLONGED_STOP)
            events.append(_event(PROLONGED_STOP, pos, ts, {"stationary_s": round(stationary)}))

    # --- route deviation ---
    off_by = distance_to_polyline(pos, [tuple(p) for p in route_points]) if route_points else 0
    if off_by > cfg["deviation_m"]:
        s["off_route_ticks"] += 1
        if s["off_route_ticks"] >= cfg["deviation_ticks"] and ROUTE_DEVIATION not in s["latched"]:
            s["latched"].append(ROUTE_DEVIATION)
            events.append(_event(ROUTE_DEVIATION, pos, ts, {"deviation_m": round(off_by)}))
    else:
        s["off_route_ticks"] = 0
        if ROUTE_DEVIATION in s["latched"]:
            s["latched"].remove(ROUTE_DEVIATION)

    return s, events


def _event(kind, pos, ts, details):
    return {"type": kind, "lat": pos[0], "lng": pos[1], "trip_ts": ts, "details": details}


def describe(event):
    """Short, neutral, non-AI description (also the fallback when Bedrock is unavailable)."""
    d = event.get("details") or {}
    if event["type"] == PROLONGED_STOP:
        mins = max(1, round(d.get("stationary_s", 0) / 60))
        return f"The vehicle has not moved for about {mins} minute{'s' if mins != 1 else ''}."
    if event["type"] == ROUTE_DEVIATION:
        return f"The vehicle is about {d.get('deviation_m', 0)} m away from the planned route."
    return "Something unusual happened on this trip."
