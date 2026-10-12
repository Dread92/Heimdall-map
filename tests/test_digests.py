"""The written record of each night and week (dashboard only). The numbers are computed by the app from what it
recorded; the model only puts them into words — and is told to add nothing: no forecast, no guessed target."""
import io
import json
import os
from datetime import datetime, timedelta, timezone

import server
from alert_events import events_from_table  # 1.58.4: the alerts' start / end events

SRC = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "server.py"), encoding="utf-8").read()
T0 = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)          # 18:00 Kyiv
T1 = T0 + timedelta(hours=14)                                     # 08:00 Kyiv


def _alert(st, key, obl, title, s, e, level="yellow", typ="raion"):
    st.store.upsert_alert({"key": key, "source": "ukrainealarm_proxy", "location_uid": key, "location_title": title,
                           "location_title_en": None, "location_type": typ, "oblast_uid": obl, "alert_type": "air_raid",
                           "alert_level": level, "started_at": s.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "finished_at": e.strftime("%Y-%m-%dT%H:%M:%SZ") if e else None, "notes": None, "threats": []})


def _night():
    st = server.State(server.Store(":memory:"), {})
    _alert(st, "c1", "31", "м. Київ", T0 + timedelta(hours=2), T0 + timedelta(hours=3), "red", "oblast")
    _alert(st, "c2", "31", "м. Київ", T0 + timedelta(hours=2, minutes=20), T0 + timedelta(hours=4), "yellow", "oblast")
    _alert(st, "b1", "14", "Броварський район", T0 + timedelta(hours=1), T0 + timedelta(hours=2))
    _alert(st, "old", "31", "м. Київ", T0 - timedelta(days=2), T0 - timedelta(days=2, hours=-1), "red", "oblast")
    events_from_table(st)
    st.store.log_markers([
        {"id": "a/1#0", "ts": (T0 + timedelta(minutes=50)).isoformat(), "channel": "kyiv_airdef", "type": "drones", "jet": True,
         "status": None, "place": "Бровари", "oblast_uid": "14", "lon": 30.8, "lat": 50.5, "heading": 250},
        {"id": "a/2#0", "ts": (T0 + timedelta(minutes=90)).isoformat(), "channel": "kyiv_airdef", "type": "drones",
         "status": None, "place": "→ Київ", "oblast_uid": "31", "lon": 30.5, "lat": 50.4, "heading": 260},
        {"id": "a/3#0", "ts": (T0 + timedelta(minutes=95)).isoformat(), "channel": "war_monitor", "type": "drones",
         "status": "down", "place": "Бровари", "oblast_uid": "14", "lon": 30.8, "lat": 50.5},
    ])
    return st


def test_the_numbers_of_a_night():
    f = _night().digest_facts(T0, T1)
    oa = f["official_alerts"]
    assert oa["kyiv_city_minutes_under_alert"] == 120                # 20:00–22:00 Kyiv time: overlap counted once
    assert oa["kyiv_city_alerts"] == 2 and oa["kyiv_city_longest_alert_minutes"] == 100
    assert oa["alert_waves_kyiv_and_oblast"] == 2                     # 19:00, then 20:00 and 20:20 as one wave
    assert oa["kyiv_oblast_units_minutes_under_alert"] == {"Броварський район": 60}
    cr = f["channel_reports"]
    assert cr["reports"] == 2 and cr["by_type"] == {"jet_drones": 1, "drones": 1}
    assert cr["most_named_places"] == {"Бровари": 1, "Київ": 1}       # "→ Київ" is still Kyiv
    assert cr["reported_course"] == {"W": 2}
    assert f["outcomes_reported"]["by_kind"] == {"down": 1}
    assert f["map_ahead_of_alert"]["waves_with_a_mark_before"] == 2   # 19:50 before the 20:00 wave; 18:50 before 19:00
    assert "reports, not a count" in cr["note"]


def test_the_model_is_told_to_describe_and_nothing_else():
    s = server.AI_SYSTEM
    for rule in ("ONLY the facts", "Never predict", "Never guess intentions, targets", "not a count of drones"):
        assert rule in s, rule


def test_a_summary_is_parsed_from_the_answer(monkeypatch):
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ans = {"model": "m", "content": [{"type": "text", "text": '```json\n{"en": "Quiet night.", "uk": "Тиха ніч."}\n```'}]}
    seen = {}

    def fake(req, timeout=0, context=None):
        seen["body"] = json.loads(req.data.decode())
        seen["headers"] = dict(req.headers)
        return R(json.dumps(ans).encode())
    monkeypatch.setattr(server.urllib.request, "urlopen", fake)
    en, uk, model, err = server.ai_summary({"ai_key": "k", "ai_model": "claude-sonnet-5"}, {"x": 1}, "night")
    assert (en, uk, err) == ("Quiet night.", "Тиха ніч.", None)
    assert seen["body"]["model"] == "claude-sonnet-5" and seen["body"]["system"] == server.AI_SYSTEM
    assert '"x": 1' in seen["body"]["messages"][0]["content"]


def test_without_a_key_the_figures_are_still_kept():
    st = _night()
    dg = server.Digests(st, {"digest_hour": 9})
    d = dg.make("night", force=True)
    assert d["summary_en"] is None and d["error"] == "no ANTHROPIC_API_KEY"
    assert st.store.digest_get(d["id"])["facts"]["period"]["kind"] == "night"


def test_the_last_night_and_week_windows():
    dg = server.Digests(server.State(server.Store(":memory:"), {}), {"digest_hour": 9})
    s, e = dg.last_night(datetime(2026, 9, 27, 7, 30, tzinfo=timezone.utc))     # 10:30 Kyiv, Sunday
    assert e.hour == 8 and s.hour == 18 and (e - s) == timedelta(hours=14) and e.date().isoformat() == "2026-09-27"
    s, e = dg.last_night(datetime(2026, 9, 27, 4, 0, tzinfo=timezone.utc))      # 07:00 Kyiv: the night is not over
    assert e.date().isoformat() == "2026-09-26"
    ws, we = dg.last_week(datetime(2026, 9, 27, 7, 30, tzinfo=timezone.utc))
    assert we.weekday() == 0 and we.hour == 8 and (we - ws) == timedelta(days=7)


def test_only_the_owner_sees_or_runs_them_and_never_in_a_request():
    i = SRC.index('if u.path == "/api/digests":')
    assert "_admin_ok(q)" in SRC[i:i + 200]
    j = SRC.index('if u.path == "/api/digest/run":')
    body = SRC[j:j + 700]
    assert "_admin_ok(q)" in body and "dg.ask(kind)" in body and "ai_summary" not in body
