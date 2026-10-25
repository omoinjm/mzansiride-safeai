from core import places, rules
from core.geo import distance_to_polyline, haversine

ROUTE = places.get_route("rosebank", "sandton")["points"]


def drive(points, step_s=15, state=None):
    """Feed positions every step_s seconds; return (state, all events)."""
    events, ts = [], 0
    for p in points:
        ts += step_s
        state, ev = rules.evaluate(state, {"lat": p[0], "lng": p[1], "ts": ts}, ROUTE)
        events += ev
    return state, events


def interpolate(line, spacing_m=150):
    out = []
    for a, b in zip(line, line[1:]):
        n = max(1, int(haversine(a, b) // spacing_m))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return out + [tuple(line[-1])]


def test_normal_trip_raises_no_events():
    _, events = drive(interpolate(ROUTE))
    assert events == []


def test_prolonged_stop_detected_once():
    path = interpolate(ROUTE)
    mid = path[len(path) // 2]
    # 3 min at 15 s steps = 12 readings; 20 readings stationary should fire exactly once
    _, events = drive(path[: len(path) // 2] + [mid] * 20 + path[len(path) // 2:])
    assert [e["type"] for e in events] == [rules.PROLONGED_STOP]
    assert events[0]["details"]["stationary_s"] >= 180


def test_short_stop_ignored():
    path = interpolate(ROUTE)
    mid = path[len(path) // 2]
    _, events = drive(path[: len(path) // 2] + [mid] * 8 + path[len(path) // 2:])
    assert events == []


def test_waiting_at_pickup_is_normal():
    _, events = drive([tuple(ROUTE[0])] * 30)
    assert events == []


def test_stop_fires_again_after_moving():
    path = interpolate(ROUTE)
    a, b = path[len(path) // 3], path[2 * len(path) // 3]
    _, events = drive([a] * 15 + path[len(path) // 3: 2 * len(path) // 3] + [b] * 15)
    assert [e["type"] for e in events] == [rules.PROLONGED_STOP, rules.PROLONGED_STOP]


def test_route_deviation_needs_two_readings():
    mid = interpolate(ROUTE)[10]
    far = (mid[0] - 0.006, mid[1] + 0.006)  # roughly 850 m away, and further from the destination
    assert distance_to_polyline(far, ROUTE) > 250
    state, events = drive([mid, far])
    assert events == []
    state, events = rules.evaluate(state, {"lat": far[0] - 0.0005, "lng": far[1], "ts": 999}, ROUTE)
    assert [e["type"] for e in events] == [rules.ROUTE_DEVIATION]
    assert events[0]["details"]["deviation_m"] > 250


def test_out_of_order_ticks_ignored():
    s, _ = rules.evaluate(None, {"lat": ROUTE[0][0], "lng": ROUTE[0][1], "ts": 100}, ROUTE)
    s2, ev = rules.evaluate(s, {"lat": 0, "lng": 0, "ts": 50}, ROUTE)
    assert ev == [] and s2["last_ts"] == 100


def test_describe_is_neutral():
    text = rules.describe({"type": rules.PROLONGED_STOP, "details": {"stationary_s": 240}})
    assert "4 minutes" in text and "driver" not in text.lower()


# ---------- drivers following Waze / Google Maps ----------

ALT_ROUTE = places.get_route("wits", "sandton")


def test_alternative_route_is_not_a_deviation():
    """The planned Wits -> Sandton route uses the highway; the alternative uses city roads ~1.3 km away."""
    alt = ALT_ROUTE["alternatives"][0]
    assert max(distance_to_polyline(tuple(p), ALT_ROUTE["points"]) for p in alt) > 500  # genuinely different roads
    state, events = None, []
    for i, p in enumerate(interpolate(alt)):
        state, ev = rules.evaluate(state, {"lat": p[0], "lng": p[1], "ts": i * 15}, ALT_ROUTE["points"],
                                   alternatives=ALT_ROUTE["alternatives"])
        events += ev
    assert not [e for e in events if e["type"] == rules.ROUTE_DEVIATION]
    # Without the alternatives, the same drive would have raised a deviation.
    state, raised = None, []
    for i, p in enumerate(interpolate(alt)):
        state, ev = rules.evaluate(state, {"lat": p[0], "lng": p[1], "ts": i * 15}, ALT_ROUTE["points"])
        raised += ev
    assert [e for e in raised if e["type"] == rules.ROUTE_DEVIATION]


def line_towards(start, end, n):
    return [(start[0] + (end[0] - start[0]) * k / n, start[1] + (end[1] - start[1]) * k / n) for k in range(n + 1)]


def test_off_route_but_heading_to_destination_gets_more_leeway():
    dest = ROUTE[-1]
    mid = interpolate(ROUTE)[10]
    side = (mid[0], mid[1] + 0.0035)  # ~350 m off the route
    assert 250 < distance_to_polyline(side, ROUTE) < 500
    # Closing in on the destination while 250-500 m off: no alert (would have alerted before).
    pts = [mid] + line_towards(side, (dest[0] - 0.004, dest[1] + 0.0035), 3)
    state, events = drive(pts)
    assert not [e for e in events if e["type"] == rules.ROUTE_DEVIATION]


def test_heading_to_destination_still_alerts_when_far_off():
    dest = ROUTE[-1]
    mid = interpolate(ROUTE)[10]
    far = (mid[0], mid[1] + 0.012)  # ~1.2 km off, but still drifting north towards Sandton
    pts = [mid] + line_towards(far, (dest[0] - 0.002, far[1]), 6)
    state, events = drive(pts)
    dev = [e for e in events if e["type"] == rules.ROUTE_DEVIATION]
    assert dev and dev[0]["details"]["toward_destination"] is True
    assert "still heading towards the destination" in rules.describe(dev[0])
