"""1.57.5: a target with no stated course faces the way its own reports moved — the icon only.

The owner, a jet drone at Obolon drawn facing north while its reported path came down from the north over the
reservoir (19:05): "the drone should face downward when it is possible to guess"."""
import os
from datetime import datetime, timedelta, timezone

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T0 = datetime(2026, 10, 11, 16, 20, tzinfo=timezone.utc)


def _m(lon, lat, hist, **kw):
    m = {"type": "drones", "jet": True, "oblast_uid": "31", "lon": lon, "lat": lat, "ts": T0.isoformat(), "heading": None,
         "history": [{"id": f"h{i}", "lon": a, "lat": b, "ts": (T0 - timedelta(minutes=mins)).isoformat()} for i, (a, b, mins) in enumerate(hist)]}
    m.update(kw)
    server.face_of(m)
    return m


def test_obolon_faces_down_the_way_it_came():
    m = _m(30.500, 50.515, [(30.470, 50.640, 15)])                  # from above the reservoir, 14 km north, to Obolon
    assert m["face_by"] == "track" and 165 <= m["face"] <= 185
    assert m["heading"] is None                                      # no course is made of it


def test_only_when_it_can_be_told():
    assert "face" not in _m(30.500, 50.515, [(30.505, 50.519, 4)])              # 0.5 km: one place, a tracker's jitter
    assert "face" not in _m(30.500, 50.515, [(30.470, 50.640, 60)])             # an hour old: not this leg
    assert "face" not in _m(30.500, 50.515, [(30.470, 50.640, 15)], heading=90)  # a stated course is its own
    assert "face" not in _m(30.500, 50.515, [(30.470, 50.640, 15)], status="down")
    assert "face" not in _m(30.500, 50.515, [])                                  # no track: north
    # the last leg that moved: a jitter after it is skipped
    m = _m(30.500, 50.515, [(30.470, 50.640, 15), (30.502, 50.518, 2)])
    assert m["face_by"] == "track" and 165 <= m["face"] <= 185


def test_never_back_across_the_border():
    # Chernihiv oblast: reports moving north, towards Belarus — not a way to draw it; it faces into Ukraine
    m = _m(30.70, 51.60, [(30.72, 51.45, 10)], oblast_uid="25", type="unknown")
    assert m.get("face_by") is None and 150 <= m["face"] <= 210


def test_the_card_says_why():
    page = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    i18n = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
    assert "t(m.face_by==='track'?'face_track':m.face_by==='south'?'face_south':'face_note')" in page and i18n.count("face_track:'") == 3
    assert "face_of(m)" in open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
