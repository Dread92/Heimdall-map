"""1.58.37: the dashboard after the owner's review of 19–20 October.

"we should have thousands of drones by now yet the number of recorded drones is fairly minimal — we need more accurate
data"; "it would make sense that it is included within the AI tab … the main goal is to aggregate as many data as
possible to make a report, so we need a wider range of dates, not only one day at a time"; "some days throw back: Not
written: empty answer"; "this should go away, it's mostly useless data since it targets only Kyiv"; "this one too,
vastly inaccurate, it can go" (the carriers); "the nights and weeks tab can also go away".
"""
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


ADMIN, SRC, DOC = _read("static/admin.html"), _read("app/server.py"), _read("docs/TECHNICAL.md")


def at(night, h, m=0):
    """A UTC time on the night that began at 12:00 Kyiv on `night`, `h` hours after its noon."""
    k = server.kyiv_tz()
    d = datetime.fromisoformat(night)
    return (datetime(d.year, d.month, d.day, 12, tzinfo=k) + timedelta(hours=h, minutes=m)).astimezone(timezone.utc).isoformat()


def _tag(st, night, n, path):
    st.store.conn.execute("INSERT INTO targets(night,n,prefix,origin,osrc,oquote,opost,first_ts,last_ts,type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (night, n, "N", None, None, None, None, at(night, 10), at(night, 11), "drones"))
    for i, (pl, h, mi) in enumerate(path):
        lon, lat, _ = geo.PLACES[pl]
        st.store.conn.execute("INSERT INTO target_points VALUES(?,?,?,?,?,?,?,?)", (f"{night}/{n}/{i}#0", night, n, at(night, h, mi), lon, lat, pl, None))
        st.store.conn.execute("INSERT INTO target_reports VALUES(?,?,?,?)", (f"{night}/{n}/{i}#0", night, n, at(night, h, mi)))


def _af(st, night, drones, down):
    morning = (datetime.fromisoformat(night) + timedelta(days=1)).date().isoformat()
    st.store.af_save(f"kpszsu/{night}", "kpszsu", at(night, 20), {"period": "night", "date": morning,
                                                                   "launched": {"drones": drones}, "down": {"drones": down}})


def _nights(k=3, ago_days=12):
    st = server.State(server.Store(":memory:"), {})
    first = (NOW - timedelta(days=ago_days)).date()
    ns = [(first + timedelta(days=i)).isoformat() for i in range(k)]
    for i, n in enumerate(ns):
        _tag(st, n, 1, [("Чернігів", 10, 0), ("Козелець", 10, 40), ("Бровари", 11, 20)])
        _tag(st, n, 2, [("Ніжин", 11, 0)])
        _af(st, n, 100 + 10 * i, 90)
    st.store.conn.commit()
    return st, ns


# ---- the moves: every night kept is built --------------------------------------------------------------------------
def test_a_night_whose_moves_were_never_built_is_built_now():
    st, ns = _nights(3, ago_days=12)                     # all older than the last two days
    st.store.kv_set("moves_v", server.MOVES_VERSION)     # not a full build: before 1.58.37 these nights stayed empty
    pat = server.Patterns(st.store)
    assert pat.gaps() == ns
    pat.tick(replay=False)
    got = {r[0] for r in st.store.conn.execute("SELECT DISTINCT night FROM track_moves")}
    assert got == set(ns) and pat.gaps() == [] and pat.last["gaps"] == 3
    assert json.loads(st.store.kv_get("moves_last"))["gaps"] == 3
    # a night whose tags gave no move (one place each) is remembered, not built again every hour
    lone = (NOW - timedelta(days=20)).date().isoformat()
    _tag(st, lone, 1, [("Ніжин", 11, 0)])
    st.store.conn.commit()
    pat.tick(replay=False)
    assert lone in json.loads(st.store.kv_get("moves_empty")) and pat.gaps() == []


def test_an_alert_left_open_for_days_does_not_hold_the_old_nights_back():
    st = server.Store(":memory:")

    class S:
        lock = threading.Lock()

        def missile_active(self):
            return 0
    s = S()
    pat = server.Patterns(st, s)
    s.active = {"k": {"oblast_uid": "14", "alert_type": "air_raid", "started_at": (NOW - timedelta(hours=40)).isoformat()}}
    assert not pat.busy()
    s.active = {"k": {"oblast_uid": "14", "alert_type": "air_raid", "started_at": (NOW - timedelta(hours=2)).isoformat()}}
    assert pat.busy()


def test_the_patterns_say_the_scale_tags_and_the_air_force():
    st, ns = _nights(3, ago_days=12)
    st.store.kv_set("moves_v", server.MOVES_VERSION)
    server.Patterns(st.store).tick(replay=False)
    rep = server.Patterns.report(st.store, 30)
    sc = rep["coverage"]["scale"]
    assert (sc["tagged"], sc["followed"], sc["af_nights"], sc["af_drones"], sc["af_drones_down"]) == (6, 3, 3, 330, 270)
    assert rep["coverage"]["tag_nights_kept"] == 3 and rep["coverage"]["builder"]["gaps"] == 3
    head = rep["plain"]["en"][0]
    assert "tagged as 6 targets, 3 of them followed" in head and "the Air Force reported 330 drones launched over all of Ukraine" in head
    assert "за Повітряними силами: 330" in rep["plain"]["uk"][0]


# ---- the period: the record of several nights, the AI's report on it ----------------------------------------------
def test_the_record_of_a_period_adds_up_its_nights():
    st, ns = _nights(3, ago_days=12)
    d = st.period_summary(ns[0], ns[-1])
    assert d["nights"] == 3 and [p["night"] for p in d["per_night"]] == ns
    assert [p["tags"] for p in d["per_night"]] == [2, 2, 2] and [p["followed"] for p in d["per_night"]] == [1, 1, 1]
    assert d["per_night"][1]["air_force"] == {"launched": {"drones": 110}, "down": {"drones": 90}}
    T = d["totals"]
    assert (T["tags"], T["followed"]) == (6, 3) and T["air_force"] == {"nights": 3, "launched": {"drones": 330}, "down": {"drones": 270}}
    assert d["entry_places"] == {"Чернігів": 3, "Ніжин": 3}
    txt = server.State.period_text(d)
    assert f"THE NIGHTS {ns[0]} → {ns[-1]} (3 nights" in txt and "NIGHT BY NIGHT" in txt and "AF launched drones 110 / down drones 90" in txt
    assert "not a count of drones" in txt and json.dumps(d, ensure_ascii=False)
    # at most PERIOD_MAX nights: the latest of them
    long_ = st.period_nights("2026-01-01", "2026-03-31")
    assert len(long_) == server.State.PERIOD_MAX and long_[-1] == "2026-03-31"


def test_the_ai_writes_the_period_and_one_night_stays_the_nights_own():
    st, ns = _nights(3, ago_days=12)
    rp = server.NightReports(st, {})
    asked = []

    class AI:
        def enabled(self):
            return True

        def model(self):
            return "m"

        def ask_text(self, system, text, kind="text"):
            asked.append((system, kind, text))
            return {"out": "1. The period in brief\nThree nights.", "cost": 0.01, "tok_in": 9000, "tok_out": 800, "model": "m"}
    st.ai = AI()
    row = rp.write_period(ns[0], ns[-1])
    assert row["text"].startswith("1. The period") and row["nights"] == 3
    assert asked[0][0] == A.PERIOD_SYSTEM and asked[0][1] == "period" and "NIGHT BY NIGHT" in asked[0][2]
    assert st.store.ai_period(ns[0], ns[-1])["cost"] == 0.01 and st.store.ai_periods()[0] == {"from": ns[0], "to": ns[-1], "at": row["at"], "written": True}
    rp.ask_period(ns[0], ns[0])
    rp.ask_period(ns[0], ns[-1])
    assert rp.asked == [ns[0], f"{ns[0]}..{ns[-1]}"]
    assert "never invent a number" in A.PERIOD_SYSTEM and "how many nights it rests on" in A.PERIOD_SYSTEM


# ---- "Not written: empty answer" -------------------------------------------------------------------------------------
class _Resp:
    def __init__(self, obj):
        self.b = json.dumps(obj).encode()

    def read(self):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ans(content, tout, finish):
    return _Resp({"choices": [{"message": {"content": content}, "finish_reason": finish}],
                  "usage": {"prompt_tokens": 40000, "completion_tokens": tout, "cost": 0.02}, "model": "anthropic/claude-haiku-5.5"})


def _ai():
    return A.AIReader({"openrouter_key": "sk-or-test", "ai_reader_monthly_usd": 50}, server.Store(":memory:"), geo)


def test_a_report_cut_off_while_thinking_is_asked_again_with_more_room():
    ai = _ai()
    bodies = []

    def fake(req, timeout=None, context=None):
        bodies.append(json.loads(req.data))
        return _ans(None, A.MAX_OUT_REPORT, "length") if len(bodies) == 1 else _ans("1. The night in brief\n…", 2400, "stop")
    with mock.patch("urllib.request.urlopen", fake):
        res = ai.ask_text(A.REPORT_SYSTEM, "the record")
    assert [b["max_tokens"] for b in bodies] == [A.MAX_OUT_REPORT, A.MAX_OUT_RETRY]
    assert res["out"].startswith("1. The night") and abs(res["cost"] - 0.04) < 1e-9
    assert A.MAX_OUT_REPORT >= 10000 and A.MAX_OUT_RETRY > A.MAX_OUT_PERIOD > A.MAX_OUT_REPORT


def test_an_empty_answer_says_why_and_parts_are_read():
    ai = _ai()
    with mock.patch("urllib.request.urlopen", lambda req, timeout=None, context=None: _ans("", 12, "content_filter")):
        res = ai.ask_text(A.REPORT_SYSTEM, "the record")
    assert res["error"] == "empty answer (the model stopped: content_filter, 12 tokens out)" and not res.get("cut")
    parts = [{"type": "text", "text": "1. The night "}, {"type": "text", "text": "in brief"}]
    with mock.patch("urllib.request.urlopen", lambda req, timeout=None, context=None: _ans(parts, 300, "stop")):
        assert ai.ask_text(A.REPORT_SYSTEM, "the record", kind="period")["out"] == "1. The night in brief"
    bodies = []
    with mock.patch("urllib.request.urlopen", lambda req, timeout=None, context=None: bodies.append(json.loads(req.data)) or _ans(None, 99999, "length")):
        res = ai.ask_text(A.PERIOD_SYSTEM, "the record", kind="period")
    assert [b["max_tokens"] for b in bodies] == [A.MAX_OUT_PERIOD, A.MAX_OUT_RETRY] and "thinking and wrote nothing" in res["error"]
    assert all("response_format" not in b for b in bodies)


# ---- the routes ----------------------------------------------------------------------------------------------------
def test_the_period_route_is_the_owners_and_asks_the_writer():
    st, ns = _nights(3, ago_days=12)
    st.reports = server.NightReports(st, {})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(path, body=None, **hd):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=dict(hd, **({"Content-Type": "application/json", "Origin": base} if body is not None else {})))
        try:
            r = urllib.request.urlopen(req, timeout=30)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            assert call(f"/api/admin/period?from={ns[0]}&to={ns[-1]}")[0] == 403
            k = {"X-Admin-Key": "adm-test"}
            assert call(f"/api/admin/period?from={ns[-1]}&to={ns[0]}", **k)[0] == 400
            code, d = call(f"/api/admin/period?from={ns[0]}&to={ns[-1]}", **k)
            assert code == 200 and d["summary"]["totals"]["tags"] == 6 and "NIGHT BY NIGHT" in d["text"] and d["report"] is None
            assert d["max"] == server.State.PERIOD_MAX
            code, d = call("/api/admin/ai_report", {"from": ns[0], "to": ns[-1]}, **k)
            assert code == 200 and d["asked"] == f"{ns[0]}..{ns[-1]}" and st.reports.asked == [f"{ns[0]}..{ns[-1]}"]
            code, d = call("/api/admin/ai_report", {"night": ns[1]}, **k)                  # the old way still asks one night
            assert code == 200 and d["asked"] == ns[1]
    finally:
        srv.shutdown()
        server.Handler.state = old


# ---- the dashboard -----------------------------------------------------------------------------------------------------
def test_the_dashboard_moved_and_cleared():
    # the report is on the AI tab, over a period, kept across the tab's redraws
    assert '<div id="perslot"></div>' in ADMIN and "slot.replaceWith(PER_BOX)" in ADMIN and "fetch(`/api/admin/period?from=${f}&to=${to}`" in ADMIN
    assert "body:JSON.stringify({from:PER_FROM,to:PER_TO})" in ADMIN and "[1,7,14,31]" in ADMIN
    for k in ("per_h:", "per_src:", "per_from:", "per_to:", "per_stats:", "per_af:", "per_none:", "per_prev:", "pt_gaps:", "pt_berr:", "pt_kept:"):
        assert ADMIN.count(k) == 2, k
    # the analytics no longer carry the night, the Kyiv reports or the carriers; the nights-and-weeks tab is gone
    for gone in ("nightCard(", "an_c_reports", "an_c_air", "an_air_", 'data-tab="nights"', "loadDigests", "drawDigests", "dg_"):
        assert gone not in ADMIN, gone
    assert "if(!$('tab-'+t)) t='live';" in ADMIN
    assert "state.digests = None" in SRC and "Digests(state, cfg)" not in SRC and '"air": self._an_air' not in SRC
    assert "/api/admin/period" in DOC and "ai_period_reports" in DOC
