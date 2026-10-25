from core import drivers


def test_plate_normalisation():
    assert drivers.normalize_plate("ca 123-456") == "CA123456"


def test_lookup_registered_by_plate(aws):
    r = drivers.lookup("ca123 456")
    assert r["verdict"] == "registered" and r["matches"][0]["name"] == "Lerato Dlamini"


def test_lookup_caution_for_suspended(aws):
    r = drivers.lookup("BX 33 KK GP")
    assert r["verdict"] == "caution" and "do not take this ride" in r["advice"]


def test_lookup_by_name(aws):
    assert drivers.lookup("sipho")["matches"][0]["plate"] == "JK 45 PL GP"


def test_not_found_does_not_accuse(aws):
    r = drivers.lookup("ZZ 99 ZZ GP")
    assert r["verdict"] == "not_found" and "does not mean the driver is unsafe" in r["advice"]


def test_assign_never_picks_flagged(aws):
    import random
    rng = random.Random(1)
    for _ in range(50):
        d = drivers.assign_driver(rng)
        assert d["status"] == "active" and not d["reports_open"]


def test_format_lookup_mentions_demo(aws):
    assert "demo registry" in drivers.format_lookup(drivers.lookup("sipho"))
