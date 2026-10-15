"""1.58.30 — the bulletins' record, and the dashboard saying what each bulletin was written from.

The owner (15 Oct 2026): "I have the impression the current AI reports don't take the data of the dashboard's 'AI' part at
all to compile each 'last hour' / 'last 24 hours' report". They are written from the window's record (State.activity_summary
/ activity_text), kept with each one; the AI tab's readings of posts and its checks are 1.50–1.53's, stopped in 1.54, and
feed nothing. But the record, replayed from that night's posts, said less than it held: the jet drone followed from Pyriatyn
to Borshchiv was "drone" (a track's kind came from its tag alone, never from its reports); the heights counted 18 reports
and gave the range and the bands of the 5 the map's marks carried; and 37 of 61 reports were only where a target was
heading ("→ Славутич"), listed among the places the targets were at.
"""
import json
import os
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


ADMIN, DOC = _read("static", "admin.html"), _read("docs", "TECHNICAL.md")
with open(os.path.join(ROOT, "tests", "data", "chyste_nebo_2026_10_15_0328.json"), encoding="utf-8") as _f:
    NIGHT = json.load(_f)["posts"]


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _mark(st, mid, minutes, place, uid, typ="drones", **kw):
    cols = dict(id=mid, ts=ago(minutes), post_id=mid.split("#")[0], channel="kpszsu", type=typ, status=None, place=place,
                oblast_uid=uid, jet=0, count=1)
    cols.update(kw)
    st.store.conn.execute(f"INSERT INTO marker_log({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
    st.store.conn.commit()


def _track(st, n, typ, points):
    night = server.tag_night(ago(30))
    st.store.conn.execute("INSERT INTO targets(night,n,prefix,origin,first_ts,last_ts,type) VALUES(?,?,?,?,?,?,?)",
                          (night, n, "?", None, ago(50), ago(10), typ))
    for rep, pl, m, alt in points:
        st.store.conn.execute("INSERT INTO target_points VALUES(?,?,?,?,?,?,?,?)", (rep, night, n, ago(m), 31.0, 50.4, pl, alt))
    st.store.conn.commit()


def _state():
    return server.State(server.Store(":memory:"), {})


# ---- what the record says --------------------------------------------------------------------------------------------
def test_a_followed_target_keeps_the_kind_its_reports_said():
    st = _state()
    _track(st, 3, "drones", [("c/1#0", "Яготин", 40, None), ("c/2#0", "Березань", 35, None), ("c/3#0", "Борщів", 30, None)])
    _mark(st, "c/2#0", 35, "Березань", "14", jet=1)                    # "Березань реактивний"
    _track(st, 4, "unknown", [("c/4#0", "Бровари", 20, None), ("c/5#0", "Погреби", 15, None)])
    _mark(st, "c/5#0", 15, "Погреби", "14", typ="drones")              # a later report named the weapon
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    kinds = {f["tag"]: f["kind"] for f in d["followed"]}
    assert kinds == {"#03": "jet drone", "#04": "drone"}
    assert "#03 jet drone, 3 reports" in server.State.activity_text(d)


def test_the_night_of_the_owners_screenshot_its_jet_drone_is_one():
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "marker_ttl_minutes": 45})
    server.Telegram(st, {}).ingest("chyste_nebo", [(p["id"], (NOW - timedelta(seconds=p["ago"])).isoformat(), p["text"])
                                                   for p in NIGHT], "tg:chyste_nebo")
    st.markers()
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    (f,) = [f for f in d["followed"] if f["path"][0].startswith("Пирятин")]
    assert f["kind"] == "jet drone" and f["path"][-1].startswith("Борщів")


def test_the_heights_are_one_list_each_report_once():
    st = _state()
    _mark(st, "h/1#0", 50, "Бровари", "14", alt_m=1800)                # a mark of the map, not followed
    _track(st, 5, "drones", [("h/2#0", "Козелець", 40, 6700), ("h/3#0", "Бровари", 30, 300), ("h/4#0", "Бровари", 29, None)])
    _mark(st, "h/3#0", 30, "Бровари", "14", alt_m=300)                 # a followed report the map logged too: once
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    ha = d["heights_all"]
    assert (ha["reports"], ha["min"], ha["median"], ha["max"]) == (3, 300, 1800, 6700)
    assert ha["bands"] == {"0-500 m": 1, "500-1000 m": 0, "1000-2000 m": 1, "2000-3000 m": 0, "3000+ m": 1}
    t = server.State.activity_text(d)
    assert "HEIGHTS REPORTED: 3 reports, from 300 m to 6700 m (median 1800 m)" in t and "3000+ m 1" in t
    assert server.State.band(3000, 99999) == "3000+ m" and server.State.band(500, 1000) == "500-1000 m"


def test_where_a_target_was_heading_is_not_where_it_was():
    st = _state()
    _mark(st, "a/1#0", 30, "→ Славутич", "14", approach=1)
    _mark(st, "a/2#0", 25, "→ Славутич", "14", approach=1)
    _mark(st, "a/3#0", 20, "Вишгород", "14")
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    r = d["reports"]
    assert [p["place"] for p in r["places"]] == ["Вишгород (Kyiv oblast)"] and r["total"] == 3
    assert r["heading_for"] == [{"place": "Славутич (Kyiv oblast)", "reports": 2}]
    assert r["heading_by_oblast"] == [{"oblast": r["heading_by_oblast"][0]["oblast"], "reports": 2}]
    t = server.State.activity_text(d)
    assert "Places most reported (where a post put a target): Вишгород (Kyiv oblast) ×1" in t
    assert "Reported only by where they were heading: 2 reports — Славутич (Kyiv oblast) ×2 (where they were going" in t
    assert "Of these, reported only heading for a place in that oblast:" in t
    assert '"reported only by where they were heading" are kept for the record, not for the bulletin' in A.BULLETIN_SYSTEM


# ---- what the dashboard says of each bulletin ---------------------------------------------------------------------------
def test_each_bulletin_says_what_its_record_held():
    st = _state()
    _mark(st, "f/1#0", 30, "→ Славутич", "14", approach=1)
    _mark(st, "f/2#0", 20, "Бровари", "14", alt_m=900)
    _track(st, 6, "drones", [("f/3#0", "Ніжин", 40, None), ("f/4#0", "Бровари", 21, None)])
    st.store.conn.execute("INSERT INTO outcomes(id, ts, post_id, channel, status, type, place, oblast_uid, count) VALUES(?,?,?,?,?,?,?,?,?)",
                          ("f/5#0", ago(5), "f/5", "kpszsu", "down", "drones", "Бровари", "14", 2))
    st.store.conn.commit()
    t = server.State.activity_text(st.activity_summary(NOW - timedelta(hours=1), NOW))
    f = server.State.record_facts(t)
    assert f == {"reports": 2, "followed": 1, "heights": 1, "heading": 1, "alerts": 0, "alerts_on": 0, "outcomes": 2,
                 "on_map": 0, "missiles": False, "air_force": False, "weather": False}
    assert server.State.record_facts(None) is None and server.State.record_facts("Over the last hour …") is None
    on = server.State.record_facts("RECORD 01:00–02:00\n\nOFFICIAL AIR-RAID ALERTS (…):\n- м. Київ: 40 min · ON NOW · started 01:20 · "
                                   "whole oblast\n- Київська область: 30 min · not now · started 01:25\n\nTARGETS REPORTED: 0 reports\n\n"
                                   "ON THE MAP WHEN THIS WAS RECORDED: м. Київ (Kyiv city): drone 1; Київська область (Kyiv oblast): "
                                   "jet drone 3, probable drone (type not stated) 2")
    assert (on["alerts"], on["alerts_on"], on["on_map"]) == (2, 1, 6)


def test_the_dashboard_gets_them_and_shows_them():
    st = _state()
    st.store.bulletin_save({"kind": "1h", "at": ago(1), "since": ago(61), "until": ago(1), "quiet": 0, "sig": "s",
                            "input": "RECORD 01:00–02:00\n\nTARGETS REPORTED: 7 reports", "en": "Seven.", "uk": "Сім.", "fr": "Sept."})
    st.store.bulletin_save({"kind": "24h", "at": ago(2), "since": ago(1442), "until": ago(2), "quiet": 1, "sig": "quiet",
                            "en": "Quiet.", "uk": "Тихо.", "fr": "Calme."})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/ai_reads",
                                                              headers={"X-Admin-Key": "adm-test"}), timeout=20)
            bs = {b["kind"]: b for b in json.loads(r.read().decode("utf-8"))["bulletins"]}
    finally:
        srv.shutdown()
        server.Handler.state = old
    assert bs["1h"]["facts"]["reports"] == 7 and bs["24h"]["facts"] is None
    assert "r.facts?`<div class=\"bulf\">${esc(bulFacts(r.facts))}</div>`:''" in ADMIN
    for k in ("bul_from:", "bf_rep:", "bf_head:", "bf_fol:", "bf_alt:", "bf_al:", "bf_on:", "bf_out:", "bf_map:", "bf_msl:", "bf_af:", "bf_wx:"):
        assert ADMIN.count(k) == 2, k                                         # English and Ukrainian
    assert "not used by the bulletins" in ADMIN and "зведення цього не використовують" in ADMIN


def test_the_docs_tell_it():
    for s in ("record_facts", "heading_for", "3000+ m", "1.58.30"):
        assert s in DOC, s
