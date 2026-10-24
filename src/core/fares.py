"""Illustrative fare rules (proposal 5.8). Sample numbers, not a pricing engine.

Individual fare = base + per-km + per-minute, with a minimum.
Shared fare (per rider) = individual fare x (1 + detour allowance) / riders, never below the shared minimum.
"""
BASE_ZAR = 15.0
PER_KM_ZAR = 8.5
PER_MIN_ZAR = 1.2
MIN_FARE_ZAR = 35.0
SHARED_DETOUR_FACTOR = 0.20  # pickups/drop-offs for other riders make the trip ~20% longer
SHARED_MIN_ZAR = 25.0


def _round(x):
    # Fares end in 0 or 5 cents like taxi/ride-hailing prices, rounded to the nearest 50c.
    return round(x * 2) / 2


def individual_fare(distance_m, duration_s):
    raw = BASE_ZAR + PER_KM_ZAR * distance_m / 1000 + PER_MIN_ZAR * duration_s / 60
    return _round(max(MIN_FARE_ZAR, raw))


def shared_fare(distance_m, duration_s, riders):
    if riders < 2:
        return individual_fare(distance_m, duration_s)
    total = individual_fare(distance_m, duration_s) * (1 + SHARED_DETOUR_FACTOR)
    return _round(max(SHARED_MIN_ZAR, total / riders))


def quote(distance_m, duration_s):
    single = individual_fare(distance_m, duration_s)
    options = [{"type": "individual", "riders": 1, "fare_zar": single, "saving_zar": 0.0, "saving_pct": 0}]
    for riders in (2, 3):
        fare = shared_fare(distance_m, duration_s, riders)
        options.append({
            "type": "shared",
            "riders": riders,
            "fare_zar": fare,
            "saving_zar": round(single - fare, 2),
            "saving_pct": round(100 * (single - fare) / single),
            "extra_minutes": round(duration_s / 60 * SHARED_DETOUR_FACTOR),
        })
    return {
        "distance_km": round(distance_m / 1000, 1),
        "duration_min": round(duration_s / 60),
        "currency": "ZAR",
        "options": options,
        "rules": {
            "base": BASE_ZAR, "per_km": PER_KM_ZAR, "per_min": PER_MIN_ZAR, "minimum": MIN_FARE_ZAR,
            "shared_detour_factor": SHARED_DETOUR_FACTOR, "shared_minimum": SHARED_MIN_ZAR,
        },
        "simulated": True,
    }
