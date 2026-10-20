"""1.54.8: no "unknown" for what is most likely a drone; a record that says everything it knows, kept; more room to write.

The owner (10 Oct 2026): "'unknown' is badly worded — in the AI summary as well as in the app. In that case it's most likely
a drone (a jet Shahed). The only exception is when we are aware that ballistic and cruise missiles are also coming: then we
cannot precisely know whether it is a drone or a missile." — "Those data from the AI are precious, because the goal will be
pattern recognition too: we need to be aware of the maximum amount of things possible." — "Let's push the token cutoff more
if needed, give it more leeway."
"""
import os
import re
from datetime import datetime, timedelta, timezone

import ai_reader as A
import server
from alert_events import events_from_table  # 1.58.4: the alerts' start / end events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, LIGHT, DOC, SAFETY = (_read("static/kyiv.html"), _read("static/i18n.js"), _read("static/light.html"),
                                  _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md"))
NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _mark(st, mid, minutes, place, uid, typ="drones", **kw):
    cols = dict(id=mid, ts=ago(minutes), post_id=mid.split("#")[0], channel="kpszsu", type=typ, status=None, place=place,
                oblast_uid=uid, jet=0, count=1)
    cols.update(kw)
    st.store.conn.execute(f"INSERT INTO marker_log({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
    st.store.conn.commit()


def _state():
    return server.State(server.Store(":memory:"), {})


# ---- the words ---------------------------------------------------------------------------------------------------------------
def test_an_unstated_weapon_is_a_probable_drone_or_with_missiles_a_drone_or_a_missile():
    assert server.kind_name("unknown") == "probable drone (type not stated)" == server.kind_name(None)
    assert server.kind_name("unknown", missiles=True) == "drone or missile (type not stated)"
    assert server.kind_name("drones", True) == "jet drone" and server.kind_name("cruise_missiles") == "cruise missiles"
    assert server.kind_name("cruise_missiles", raw=True) == "cruise_missiles"
    st = _state()
    _mark(st, "k/1#0", 20, "Бровари", "14", typ="unknown", likely="drones", alt_m=1300)
    _mark(st, "k/2#0", 10, "Бровари", "14")
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    assert d["reports"]["kinds"] == {"probable drone (type not stated)": 1, "drone": 1} and not d["missiles"]["in_window"]
    text = server.State.activity_text(d)
    assert "unknown" not in text and "most likely Shahed-type drones" in text and "1 with a drone tracker's signs" in text
    # a ballistic report in the window: the same report may be either
    _mark(st, "k/3#0", 5, "Київ", "31", typ="ballistic_missiles")
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    assert d["missiles"]["in_window"] and d["reports"]["kinds"]["drone or missile (type not stated)"] == 1
    assert "MISSILES AND CARRIERS REPORTED: ballistic missiles 1" in server.State.activity_text(d)
    # a strategic bomber airborne anywhere is missiles coming too
    st2 = _state()
    _mark(st2, "k/4#0", 20, "Бровари", "14", typ="unknown")
    st2.store.conn.execute("INSERT INTO air_reports(post_id,kind,phase,channel,ts,h) VALUES(?,?,?,?,?,?)", ("a/1", "strategic", "up", "kpszsu", ago(15), "h"))
    st2.store.conn.commit()
    d = st2.activity_summary(NOW - timedelta(hours=1), NOW)
    assert d["missiles"]["carriers"] == [{"kind": "strategic bombers", "phase": "up", "at": d["missiles"]["carriers"][0]["at"]}]
    assert "drone or missile (type not stated)" in d["reports"]["kinds"]


def test_the_page_never_says_unknown_for_what_is_most_likely_a_drone():
    # 1.56.6: the missile context is the target's own (a missile within MSL_NEAR_KM, the reader's warning near the reader)
    assert "function mslCtx(m){" in PAGE and "return MSLP.some(p=>Math.hypot(p[0]-x,p[1]-y)<=MSL_NEAR_KM); }" in PAGE
    assert "m.type==='unknown'?(mslCtx(m)?'⚠ '+t('unk_mix'):t('unk_likely'))" in PAGE                  # the label on the map
    assert "m.type==='unknown'?(mslCtx(m)?'⚠ '+t('th_unk_mix'):'🛸 '+t('th_unk_dr'))" in PAGE          # the card's title
    assert "t('unk_note_dr')" in PAGE and "t('unk_note_mix')" in PAGE and "m.type==='unknown'?unkKind(m)" in PAGE   # note, Near
    assert "⚠ ${esc(t(mslCtx()?'lb_unk_mix':'lb_unk_dr'))}" in PAGE                                    # the counts
    assert "t('k_unknown'):THREAT" not in PAGE and "'⚠ '+t('th_unknown2')" not in PAGE
    assert "t(lMsl(m)?'th_unk_mix':'th_unk_dr')" in LIGHT
    for k in ("unk_mix", "th_unk_dr", "th_unk_mix", "k_unk_dr", "k_unk_mix", "lb_unk_dr", "lb_unk_mix", "unk_note_dr", "unk_note_mix"):
        assert len(re.findall(r"(?<![\w])" + k + ":", I18N)) == 3, k
    assert "Ймовірно, дрон — тип не вказано" in I18N and "Дрон чи ракета — тип не вказано" in I18N


# ---- the record says what it knows ----------------------------------------------------------------------------------------------
def test_the_record_carries_courses_heights_speeds_origins_and_raions():
    st = _state()
    _mark(st, "r/1#0", 40, "Бровари", "14", heading=315, alt_m=1800, alt_state="descending", speed_kmh=180, origin="ne")
    _mark(st, "r/2#0", 30, "Вишгород", "14", heading=300, alt_m=900)
    _mark(st, "r/3#0", 20, "Бровари", "14", jet=1, heading=90)
    st.store.conn.execute("INSERT INTO alerts(key, source, location_uid, location_title, location_type, oblast_uid, alert_type, "
                          "alert_level, started_at, finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          ("a2", "t", "r1", "Броварський район", "raion", "14", "air_raid", "red", ago(50), None))
    st.store.conn.commit()
    events_from_table(st, active=("a2",))
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    assert d["courses"] == [{"oblast": d["courses"][0]["oblast"], "NW": 2, "E": 1}]
    assert d["heights_all"]["reports"] == 2 and d["heights_all"]["descending"] == 1 and d["heights_all"]["max"] == 1800
    assert d["speeds"] == {"reports": 1, "min": 180, "max": 180} and d["origins_stated"] == {"ne": 1}
    assert d["alerts"][0]["raion_names"] == ["Броварський район"] and d["reports"]["first"] and d["reports"]["peak"]
    t = server.State.activity_text(d)
    for s in ("COURSES THE MARKS CARRIED", "descending in 1", "SPEEDS STATED: 1 reports, 180–180 km/h",
              "not for the bulletin", "(Броварський район)", "By band:"):
        assert s in t, s
    assert "kpszsu" not in t                                                       # still no channel, no post's text


def test_each_mark_keeps_what_it_stated():
    st = _state()
    st.store.log_markers([{"id": "m/1#0", "ts": ago(1), "type": "unknown", "place": "Бровари", "oblast_uid": "14", "lon": 30.79,
                           "lat": 50.51, "alt": {"m": 500, "state": "descending"}, "speed": {"kmh": 190}, "origin": {"o": "n"},
                           "target": "Київ", "likely": "drones", "tag": {"night": "2026-10-09", "n": 178}, "approach": False}])
    row = st.store.conn.execute("SELECT alt_m, alt_state, speed_kmh, origin, target, likely, tag, approach FROM marker_log").fetchone()
    assert row == (500, "descending", 190, "n", "Київ", "drones", "2026-10-09#178", 0)


def test_the_bulletins_are_kept_one_an_hour_and_one_a_day_after_90_days():
    st = server.Store(":memory:")
    tz = server.kyiv_tz()
    base = (NOW - timedelta(days=120)).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    for h in range(24):
        for mnt in (5, 25, 45):
            rows.append(("1h", base + timedelta(hours=h, minutes=mnt), 0, None))
        rows.append(("24h", base + timedelta(hours=h, minutes=10), 0, None))
    rows += [("1h", base + timedelta(hours=3), 1, None), ("24h", base + timedelta(hours=5), 0, "HTTP 500")]
    rows.append(("1h", NOW - timedelta(days=10), 0, None))
    for kind, at, quiet, err in rows:
        st.conn.execute("INSERT INTO ai_bulletins(kind, at, quiet, error, input) VALUES(?,?,?,?,?)",
                        (kind, at.astimezone(timezone.utc).isoformat(), quiet, err, "RECORD"))
    st.conn.commit()
    kept, dropped = st.bulletin_prune()
    left = st.conn.execute("SELECT kind, at, kept FROM ai_bulletins ORDER BY at").fetchall()
    old = [r for r in left if r[2]]
    assert kept == 25 and len(old) == 25 and dropped == len(rows) - 1 - 25
    assert sum(1 for r in old if r[0] == "24h") == 1                              # the one nearest noon
    noon = [r for r in old if r[0] == "24h"][0]
    assert server.parse_iso(noon[1]).astimezone(tz).hour in (11, 12)
    assert all(server.parse_iso(r[1]).astimezone(tz).minute == 5 for r in old if r[0] == "1h")
    assert len(left) == 26                                                          # and the recent one, untouched
    assert st.bulletin_prune() == (0, 0)                                            # once kept, kept


# ---- room to write ---------------------------------------------------------------------------------------------------------------
def test_the_bulletins_have_room():
    assert A.MAX_OUT_BULLETIN == {"1h": 4000, "24h": 8000} and A.BULLETIN_CHARS == {"1h": 1100, "24h": 2600}
    assert A.BULLETIN_TIMEOUT == 120 and A.BULLETIN_VERSION == "3"            # 1.58.30
    p = A.BULLETIN_SYSTEM
    assert "at most 90 words" in p and "at most 220 words" in p
    assert 'Never write "unknown", "unidentified" or "unspecified" for a target' in p and "Never turn \"probably\" into a certainty" in p
    assert "kept for the record, not for the bulletin" in p
    assert "timeout=BULLETIN_TIMEOUT * (2 if kind == \"period\" else 1) if (bk or kind in (\"text\", \"period\")) else 40" in _read("app/ai_reader.py")


def test_the_docs_tell_it():
    for s in ("probable drone (type not stated)", "bulletin_prune", "MLOG_EXTRA", "MAX_OUT_BULLETIN"):
        assert s in DOC, s
    assert "probably a drone" in SAFETY
