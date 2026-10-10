"""1.55: the drones' direction patterns, area by area — the dashboard only.

The owner (10 Oct 2026): "One crucial detail of the report that we need to aggregate through time and accumulate is the
pattern of direction of the drones, in order to determine what pattern the typical drone follows depending on its
location. We need proper foundations so we can then calculate the % of probability that the drone goes to X, Y or Z.
Those data shouldn't be seen yet inside the app, but on the admin dashboard."
"""
import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


ADMIN, DOC = _read("static/admin.html"), _read("docs/TECHNICAL.md")
P = {"Чернігів": (31.29, 51.49), "Козелець": (31.11, 50.91), "Бровари": (30.79, 50.51), "Київ": (30.52, 50.45),
     "Бобровиця": (31.40, 50.75), "Одеса": (30.72, 46.48), "Остер": (30.88, 50.95)}


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _track(st, n, steps, typ="drones", jet=0, origin=None, osrc=None, night=None, base=0):
    """steps: [(place, minutes ago)]; each report also logged as a mark (its jet flag, a stated course for some)."""
    night = night or server.tag_night(ago(base + 300))
    st.conn.execute("INSERT OR REPLACE INTO targets(night,n,prefix,origin,osrc,type) VALUES(?,?,?,?,?,?)", (night, n, "?", origin, osrc, typ))
    for i, (pl, m) in enumerate(steps):
        rid = f"t{n}/{i}#0"
        lon, lat = P[pl]
        st.conn.execute("INSERT INTO target_points(report,night,n,ts,lon,lat,place,alt_m) VALUES(?,?,?,?,?,?,?,?)",
                        (rid, night, n, ago(base + m), lon, lat, pl, None))
        st.conn.execute("INSERT INTO marker_log(id,ts,post_id,channel,type,status,place,oblast_uid,lon,lat,heading,count,jet,pos_conf,evidence) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, ago(base + m), rid.split("#")[0], "c", typ, None, pl, "14", lon, lat, None, 1, jet, "high", "{}"))
    st.conn.commit()
    return night


# ---- a move: one report to the next, the physics of a drone -----------------------------------------------------------------
def test_a_track_becomes_its_moves():
    pts = [(ago(m), *P[pl], pl, a) for pl, m, a in
           [("Чернігів", 180, 2000), ("Козелець", 140, None), ("Козелець", 132, 900), ("Одеса", 128, None),     # a teleport: another target's
            ("Бровари", 100, None), ("Київ", 80, None), ("Остер", -100, None)]]                                    # 3 h later: starts again
    mv = server.Patterns.moves_of(pts)
    assert [(m["place_from"], m["place_to"]) for m in mv] == [("Чернігів", "Козелець"), ("Козелець", "Бровари"), ("Бровари", "Київ")]
    assert mv[1]["ts_from"] == ago(132) and mv[1]["alt_from"] == 900      # the latest sighting where it still was
    assert mv[0]["minutes"] == 40.0 and 60 < mv[0]["km"] < 70 and 185 <= mv[0]["bearing"] <= 200
    assert all(m["km"] / m["minutes"] * 60 <= server.VMAX_KMH[False] for m in mv)


def test_the_kinds():
    assert [server.move_kind(t, j) for t, j in (("drones", 0), ("drones", 1), ("banderol", 1), ("unknown", 0), (None, 0),
                                                 ("cruise_missiles", 0))] == ["drone", "jet", "banderol", "unstated", "unstated", "cruise_missiles"]
    assert server.PATTERN_KINDS["drones"] == ("drone", "jet", "unstated", "banderol")


def test_the_moves_are_built_every_hour_and_kept_for_good():
    st = server.Store(":memory:")
    night = _track(st, 1, [("Чернігів", 180), ("Козелець", 140), ("Бровари", 100), ("Київ", 80)], origin="belarus", osrc="rules")
    _track(st, 2, [("Козелець", 150), ("Бобровиця", 120)], typ="unknown", night=night)
    _track(st, 3, [("Чернігів", 170), ("Козелець", 150)], jet=1, night=night)
    pat = server.Patterns(st)
    assert pat.tick() == 5 and st.kv_get("moves_v") == server.MOVES_VERSION
    rows = st.conn.execute("SELECT n, seq, place_from, place_to, kind, origin, ver FROM track_moves ORDER BY n, seq").fetchall()
    assert rows == [(1, 0, "Чернігів", "Козелець", "drone", "belarus", server.MOVES_VERSION), (1, 1, "Козелець", "Бровари", "drone", "belarus", server.MOVES_VERSION),
                    (1, 2, "Бровари", "Київ", "drone", "belarus", server.MOVES_VERSION), (2, 0, "Козелець", "Бобровиця", "unstated", None, server.MOVES_VERSION),
                    (3, 0, "Чернігів", "Козелець", "jet", None, server.MOVES_VERSION)]
    assert pat.tick() == 5 and st.conn.execute("SELECT COUNT(*) FROM track_moves").fetchone()[0] == 5      # rebuilt, not doubled
    # an old night: its points go after TAG_KEEP_DAYS, its moves stay
    old = _track(st, 9, [("Бровари", 100), ("Київ", 80)], base=80 * 1440)
    pat.build([old])
    st.conn.execute("DELETE FROM target_points WHERE night=?", (old,))
    st.conn.commit()
    pat.tick()
    assert st.conn.execute("SELECT COUNT(*) FROM track_moves WHERE night=?", (old,)).fetchone()[0] == 1
    assert "track_moves" in DOC and "kept for good" in DOC


# ---- the %, with its range -------------------------------------------------------------------------------------------------
def test_wilson():
    assert server.wilson(0, 0) == (0.0, 0.0)
    lo, hi = server.wilson(2, 3)
    assert round(lo, 3) == 0.208 and round(hi, 3) == 0.939
    lo, hi = server.wilson(200, 300)
    assert round(lo, 3) == 0.612 and round(hi, 3) == 0.718                  # the same 67%, a far narrower range
    assert server.wilson(5, 5)[1] == 1.0 and server.wilson(0, 5)[0] == 0.0


def test_the_report_area_by_area():
    st = server.Store(":memory:")
    night = None
    for n in range(1, 4):                                                    # three through Kozelets to Brovary and Kyiv
        night = _track(st, n, [("Чернігів", 180), ("Козелець", 140), ("Бровари", 100), ("Київ", 80)], origin="belarus", osrc="rules",
                       night=night)
    _track(st, 4, [("Чернігів", 175), ("Козелець", 150), ("Бобровиця", 120)], night=night, origin="n", osrc="region")
    _track(st, 5, [("Козелець", 150), ("Бобровиця", 120)], typ="unknown", night=night)
    st.conn.execute("UPDATE marker_log SET heading=225, target='Київ' WHERE id='t1/1#0'")
    st.conn.commit()
    server.Patterns(st).tick()
    d = server.Patterns.report(st, days=30, kind="drones", res=1, min_n=1)
    assert d["coverage"]["moves"] == 12 and d["coverage"]["tracks"] == 5 and d["coverage"]["nights"] == 1
    assert d["coverage"]["by_kind"] == {"drone": 11, "unstated": 1} and d["coverage"]["stated"] == 1
    koz = next(c for c in d["cells"] if c["name"] == "Козелець")
    assert koz["moves"] == 5 and koz["tracks"] == 5 and koz["through"] == 5
    nxt = {x["place"]: x for x in koz["next_places"]}
    assert nxt["Бровари"]["n"] == 3 and nxt["Бровари"]["p"] == 60.0 and nxt["Бобровиця"]["p"] == 40.0
    assert (nxt["Бровари"]["lo"], nxt["Бровари"]["hi"]) == tuple(round(100 * v, 1) for v in server.wilson(3, 5))
    assert {x["place"]: x["p"] for x in koz["final_places"]} == {"Київ": 60.0, "Бобровиця": 40.0}
    assert koz["origins"] == [{"place": "belarus", "n": 3, "p": 60.0, "lo": koz["origins"][0]["lo"], "hi": koz["origins"][0]["hi"]}]  # "probably" is not said
    assert koz["stated"][server.State.COMPASS.index("SW")] == 1 and koz["said"][0]["place"] == "Київ"
    assert koz["dir"][server.State.COMPASS.index("SW")] == 3 and koz["mean_bearing"] is not None and 0 < koz["consistency"] <= 1
    assert koz["speed_kmh"] and koz["gap_min"] == 40
    # the kinds, the threshold, the raw moves
    assert server.Patterns.report(st, 30, "unstated", 1, 1)["coverage"]["moves"] == 1
    assert server.Patterns.report(st, 30, "jet", 1, 1)["cells"] == []
    assert all(c["moves"] >= 4 or c["stated_n"] >= 4 for c in server.Patterns.report(st, 30, "drones", 1, 4)["cells"])
    raw = server.Patterns.report(st, 0, "drones", 2, 1, raw=True)
    assert len(raw["moves"]) == 12 and raw["cell_km"] == 28 and set(raw["moves"][0]) >= {"place_from", "place_to", "bearing", "km", "minutes"}
    assert "moves" not in d


# ---- the dashboard's, never the app's ------------------------------------------------------------------------------------------
def test_the_route_is_the_dashboards():
    st = server.State(server.Store(":memory:"), {})
    _track(st.store, 1, [("Чернігів", 180), ("Козелець", 140), ("Бровари", 100)])
    server.Patterns(st.store).tick()
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    get = lambda path: json.loads(urllib.request.urlopen(base + path, timeout=10).read())      # noqa: E731
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            for path in ("/api/admin/patterns", "/api/admin/patterns?raw=1"):
                try:
                    urllib.request.urlopen(base + path, timeout=10)
                    raise AssertionError("open without the key")
                except urllib.error.HTTPError as e:
                    assert e.code == 403
            d = get("/api/admin/patterns?days=30&res=1&min=1&key=adm-test")
            assert d["coverage"]["moves"] == 2 and d["cells"]
            assert len(get("/api/admin/patterns?days=30&min=1&raw=1&key=adm-test")["moves"]) == 2
            try:
                urllib.request.urlopen(base + "/api/admin/patterns?res=3&key=adm-test", timeout=10)
                raise AssertionError("res=3 taken")
            except urllib.error.HTTPError as e:
                assert e.code == 400
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_the_app_shows_none_of_it():
    for f in ("static/kyiv.html", "static/light.html", "static/mobile.html", "static/i18n.js", "static/live.js", "static/replay.js",
              "static/sw.js", "static/index.html", "static/guide.html"):
        s = _read(f)
        assert "patterns" not in s.lower() or "/api/admin/patterns" not in s, f
        assert "track_moves" not in s and "/api/admin/patterns" not in s, f


def test_the_dashboard_tab():
    assert '<button data-tab="patterns" role="tab" data-tr="tab_pat">Patterns</button>' in ADMIN
    assert '<section class="tabsec" id="tab-patterns" hidden>' in ADMIN and "if(t==='patterns'&&!PT) loadPatterns();" in ADMIN
    assert "fetch('/api/admin/patterns?'+ptQ())" in ADMIN and "fetch('/api/admin/patterns?raw=1&'+ptQ())" in ADMIN
    for k in ("tab_pat", "pt_note", "pt_map", "pt_next", "pt_final", "pt_h_ci", "pt_csv_moves", "pt_compass", "pt_o"):
        assert len(re.findall(r"(?<![\w])" + k + ":", ADMIN)) == 2, k                  # English and Ukrainian
    assert "not radar" in ADMIN and "не радар" in ADMIN
    assert "if(!b||!AN||!b.dataset.csv) return;" in ADMIN                           # Analytics' CSV leaves these buttons alone
