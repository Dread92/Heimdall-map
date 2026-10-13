"""1.58.8 — north of Kyiv, a drone with no course faces south.

The owner, with a screenshot of two drones over the Kyiv reservoir in Vyshhorod raion, one drawn facing north: "for
those drones here, take the habit by default to make them face south — it's the most likely direction they will go
anyway". The glyph only: no course, no ray, no ETA, and the card says why; the way its own reports moved still comes
first.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import mapshot  # noqa: E402
import server  # noqa: E402

I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
NOW = datetime.now(timezone.utc)


def test_a_drone_north_of_kyiv_with_no_course_faces_south():
    for lon, lat in ((30.45, 50.80), (30.15, 50.94), (30.95, 50.70)):       # the reservoir, Ivankiv, north of Brovary
        m = {"type": "drones", "oblast_uid": "14", "lon": lon, "lat": lat, "ts": NOW.isoformat()}
        server.face_of(m)
        assert (m["face"], m["face_by"]) == (180, "south"), (lon, lat)
    u = {"type": "unknown", "oblast_uid": "14", "lon": 30.45, "lat": 50.80, "ts": NOW.isoformat()}
    server.face_of(u)
    assert u["face"] == 180


def test_not_south_of_it_nor_with_a_course_nor_for_a_missile():
    for m in ({"type": "drones", "oblast_uid": "14", "lon": 30.79, "lat": 50.51},           # Brovary: as before
              {"type": "drones", "oblast_uid": "14", "lon": 30.49, "lat": 50.58},           # Vyshhorod
              {"type": "drones", "oblast_uid": "31", "lon": 30.50, "lat": 50.52},           # the city
              {"type": "drones", "oblast_uid": "14", "lon": 30.45, "lat": 50.80, "heading": 330},
              {"type": "cruise_missiles", "oblast_uid": "14", "lon": 30.45, "lat": 50.80},
              {"type": "drones", "oblast_uid": "14", "lon": 30.45, "lat": 50.80, "status": "down"}):
        m["ts"] = NOW.isoformat()
        server.face_of(m)
        assert "face" not in m, m
    assert server.SOUTH_FACE == {"14": 50.60}


def test_its_own_reports_still_come_first():
    m = {"type": "drones", "oblast_uid": "14", "lon": 30.45, "lat": 50.80, "ts": NOW.isoformat(),
         "history": [{"lon": 30.30, "lat": 50.78, "ts": (NOW - timedelta(minutes=8)).isoformat()}]}
    server.face_of(m)
    assert m["face_by"] == "track" and 60 <= m["face"] <= 110                  # it was reported moving east


def test_the_card_says_why_and_the_channel_turns_it_too():
    assert I18N.count("face_south:") == 3
    assert "m.face_by==='south'?'face_south'" in TAC
    m = {"type": "drones", "oblast_uid": "14", "lon": 30.45, "lat": 50.80, "ts": NOW.isoformat()}
    server.face_of(m)
    assert mapshot.orient(m) == 180
