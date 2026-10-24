from core import fares, places


def test_minimum_fare():
    assert fares.individual_fare(500, 60) == fares.MIN_FARE_ZAR


def test_individual_fare_formula():
    # 10 km, 20 min: 15 + 85 + 24 = 124
    assert fares.individual_fare(10_000, 1200) == 124.0


def test_shared_is_cheaper_and_scales():
    q = fares.quote(10_000, 1200)
    single, two, three = (o["fare_zar"] for o in q["options"])
    assert single > two > three >= fares.SHARED_MIN_ZAR
    assert two == round(124 * 1.2 / 2 * 2) / 2  # 74.4 -> 74.5
    assert q["options"][1]["saving_pct"] == 40


def test_every_route_quotes():
    for rid, r in places.ROUTES.items():
        q = fares.quote(r["distance_m"], r["duration_s"])
        assert q["options"][0]["fare_zar"] >= fares.MIN_FARE_ZAR, rid
