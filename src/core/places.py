"""Predefined Johannesburg places and road routes between them (src/core/routes.json).

The routes were fetched once from OpenStreetMap/OSRM and simplified, so the prototype needs no
live mapping or GPS integration (out of scope per the proposal, section 8.2).
"""
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "routes.json").read_text())
PLACES = {p["id"]: p for p in _DATA["places"]}
ROUTES = _DATA["routes"]


def route_id(pickup, destination):
    return f"{pickup}__{destination}"


def get_route(pickup, destination):
    """Return {distance_m, duration_s, points} or None if the pair is unknown."""
    return ROUTES.get(route_id(pickup, destination))


def public_places():
    return list(PLACES.values())
