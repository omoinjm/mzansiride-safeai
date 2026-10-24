"""Demo driver/vehicle registry lookups (web + WhatsApp `CHECK <plate|name>`).

Records are SIMULATED. A lookup is a registry check against MzansiRide's own (demo) records,
not an official police or licensing check, and the wording says so.
"""
import json
import random
import re
from pathlib import Path

from . import store

SEED = json.loads((Path(__file__).parent / "drivers.json").read_text())["drivers"]
_cache = None


def normalize_plate(text):
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def all_drivers():
    global _cache
    if _cache is None:
        try:
            _cache = store.scan("drivers") or SEED
        except Exception:
            _cache = SEED  # registry table unavailable: fall back to the bundled seed data
    return _cache


def assign_driver(rng=random):
    """Pick an active, report-free driver for a new simulated trip."""
    pool = [d for d in all_drivers() if d["status"] == "active" and not d.get("reports_open")]
    return dict(rng.choice(pool))


def public(d):
    return {k: d[k] for k in ("driver_id", "name", "plate", "vehicle", "colour", "rating", "trips_completed",
                              "registered_since", "status") if k in d}


def lookup(query):
    """Returns {"query", "matches": [...], "verdict": "registered|caution|not_found", "advice"}."""
    q = (query or "").strip()
    if len(q) < 3:
        return {"query": q, "matches": [], "verdict": "invalid",
                "advice": "Send at least 3 characters: a number plate (e.g. CA 123-456) or the driver's name."}
    plate = normalize_plate(q)
    drivers = all_drivers()
    matches = [d for d in drivers if normalize_plate(d["plate"]) == plate]
    if not matches:
        words = q.lower().split()
        matches = [d for d in drivers if all(w in d["name"].lower() for w in words)]
    matches = matches[:3]

    if not matches:
        return {
            "query": q, "matches": [], "verdict": "not_found",
            "advice": "No MzansiRide record matches this. That does not mean the driver is unsafe, but they "
                      "are not registered with us. Check that the plate, car and driver match your booking "
                      "app before getting in, and share your trip with someone you trust.",
        }
    if any(d["status"] != "active" or d.get("reports_open") for d in matches):
        return {
            "query": q, "matches": [public(d) for d in matches], "verdict": "caution",
            "advice": "This driver's MzansiRide account is not in good standing (it is suspended or under review "
                      "after passenger reports). We recommend that you do not take this ride: cancel it and "
                      "request another. If you are already in the vehicle and feel unsafe, ask to stop at a busy "
                      "public place and call 10111 or 112 if you are in danger.",
        }
    return {
        "query": q, "matches": [public(d) for d in matches], "verdict": "registered",
        "advice": "This driver is registered with MzansiRide with no open reports. Still check that the "
                  "car model, colour and the driver's face match before you get in.",
    }


def format_lookup(result):
    """Plain-text version for WhatsApp."""
    head = {
        "registered": "✅ *Registered driver*",
        "caution": "⚠️ *Caution*",
        "not_found": "❔ *No record found*",
        "invalid": "ℹ️ *Check a driver*",
    }[result["verdict"]]
    lines = [head]
    for d in result["matches"]:
        lines.append(f"{d['name']}: {d['colour']} {d['vehicle']}, {d['plate']} (rating {d['rating']}, "
                     f"{d['trips_completed']} trips, status: {d['status'].replace('_', ' ')})")
    lines.append(result["advice"])
    lines.append("_Demo registry: simulated records, not an official police check._")
    return "\n".join(lines)
