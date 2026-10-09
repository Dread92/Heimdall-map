"""1.42: the replay — a past window of the last 7 days on the Tactical map, with a time bar.

The official alerts are rebuilt from the start / end events (the alerts table keeps one row per region and alert type,
so a region's second alert of the week overwrites its first); a restart, which loses the alerts the process held without
writing their end, closes every interval not started again right after it. The targets are read from the stored posts
with today's rules — the same functions as the live map — so a reading fixed since is fixed in the replay too.
Also here: Tactical ⇄ Light flipping back and forth through the browser's memory, and daylight / night readability."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, RJS, SRC = (_read("static/kyiv.html"), _read("static/light.html"), _read("static/i18n.js"),
                               _read("static/replay.js"), _read("app/server.py"))
T0 = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)


def _iso(minutes):
    return (T0 + timedelta(minutes=minutes)).isoformat()


def _ev(st, minutes, kind, rid, title="Броварський район", obl="14"):
    st.store.add_event({"ts": _iso(minutes), "kind": kind, "key": f"ua:{rid}:air_raid", "location_uid": f"ua-{rid}",
                        "location_title": title, "alert_type": "air_raid", "oblast_uid": obl, "detail": {}})


def _state():
    st = server.State(server.Store(":memory:"), {})
    st.store.upsert_alert({"key": "ua:79:air_raid", "source": "ukrainealarm", "location_uid": "ua-79", "location_title": "Броварський район",
                           "location_type": "raion", "oblast_uid": "14", "alert_type": "air_raid", "alert_level": "yellow",
                           "started_at": _iso(0), "finished_at": _iso(400)})
    return st


def _win(st, a=-60, b=600):
    return st.replay(int((T0 + timedelta(minutes=a)).timestamp()), int((T0 + timedelta(minutes=b)).timestamp()))


def test_a_region_alerted_twice_in_a_window_is_two_intervals():
    st = _state()
    _ev(st, 10, "start", 79); _ev(st, 40, "end", 79)
    _ev(st, 200, "start", 79); _ev(st, 260, "end", 79)
    iv = [a for a in _win(st)["alerts"] if a["k"] == "ua-79"]
    assert [(a["s"], a["e"]) for a in iv] == [(int((T0 + timedelta(minutes=m)).timestamp()), int((T0 + timedelta(minutes=n)).timestamp()))
                                             for m, n in ((10, 40), (200, 260))]
    assert iv[0]["rk"] == "brovary" and iv[0]["lt"] == "raion" and iv[0]["lv"] == "yellow"


def test_a_restart_closes_what_was_not_started_again_and_keeps_what_was():
    st = _state()
    _ev(st, 10, "start", 79); _ev(st, 10, "start", 74, "Вишгородський район")
    # the process restarts at +100: everything still on is written again as a start — Vyshhorod is, Brovary is not
    _ev(st, 100, "start", 74, "Вишгородський район")
    _ev(st, 150, "end", 74, "Вишгородський район")
    al = {a["k"]: a for a in _win(st)["alerts"]}
    assert al["ua-79"]["e"] == int((T0 + timedelta(minutes=100)).timestamp())       # ended while the server was down
    assert al["ua-74"]["s"] == int((T0 + timedelta(minutes=10)).timestamp())        # one interval, not two
    assert al["ua-74"]["e"] == int((T0 + timedelta(minutes=150)).timestamp())


def test_the_targets_are_read_with_todays_rules_and_never_include_an_example():
    st = _state()
    posts = [("kyiv_airdef", 20, "Бровари"), ("kyiv_airdef", 23, "Красилівка"),
             ("chyste_nebo", 30, "До прикладу- напрямок Бровари і все що за ними може бути ціль ми не вгадаємо з вами")]
    st.store.add_feed([{"post_id": f"{c}/{m}", "channel": c, "ts": _iso(m), "text": t, "tags": []} for c, m, t in posts])
    tr = _win(st)["tracks"]
    assert len(tr) == 1 and [p[3] for p in tr[0]["p"]] == ["Бровари", "Красилівка"]  # one target, reported twice
    assert all(not x["ty"].startswith("ballistic") for x in tr)                       # the lesson draws nothing
    assert "status" not in json.dumps(tr)                                             # outcomes are not part of it


def test_the_window_is_bounded_and_the_route_documented():
    i = SRC.index('if u.path == "/api/replay":')
    body = SRC[i:i + 1200]
    assert "st.REPLAY_MAX_H * 3600" in body and "(st.REPLAY_DAYS + 1) * 86400" in body
    assert server.State.REPLAY_MAX_H == 26 and server.State.REPLAY_DAYS == 7
    assert "/api/replay" in _read("docs/TECHNICAL.md")


def test_the_live_map_and_the_replay_share_one_reading():
    assert "self._marks_from_posts(sorted(self.store.feed_since(ttl)" in SRC
    assert "ms = self._marks_from_posts(posts, kyiv_ends, self._replay_parse, evidence=False)" in SRC
    assert "ms = self._chain(ms)" in SRC and SRC.count("def _chain(ms):") == 1


def test_the_page_loads_the_replay_only_when_asked_and_paints_no_live_colours_meanwhile():
    assert "s.src='/static/replay.js?v='+APP_VERSION" in PAGE and '<script src="/static/replay.js' not in PAGE
    assert "const AM=alertMap(S.active,k); if(!(window.RP&&RP.on)) applyAlertMap(AM);" in PAGE
    assert "applyAlertMap(alertMap(act.map(a=>a.al)))" in RJS


def test_nothing_personal_and_nothing_live_is_drawn_during_a_replay():
    rule = PAGE[PAGE.index("body.rp #markers"):PAGE.index("{display:none!important}", PAGE.index("body.rp #markers"))]
    for sel in ("#markers", "#edges", "#homeg", "#zones", "#pinhold", "#heatg", ".livebar"):        # 1.54: no #impactsg
        assert sel in rule, sel


def test_a_replayed_target_stands_where_a_post_put_it():
    assert "nothing is extrapolated" in RJS
    assert "h=last&&tr.h!=null&&tr.ty!=='unknown'?tr.h:0" in RJS                 # a course only where a post stated one
    assert "stated = m.get(\"heading\") is not None and hev.get(\"confidence\") not in (None, \"none\")" in SRC
    for word in ("not radar", "не радар", "pas un radar"):
        assert word in I18N, word
    assert len(re.findall(r"\brp_note:'", I18N)) == 3 and len(re.findall(r"\brp_note_s:'", I18N)) == 3


def test_the_switch_flips_through_history_when_the_other_version_is_next_to_this_one():
    i = I18N.index("function swNav(href)")
    body = I18N[i:I18N.index("function swGo", i)]
    assert "N.back()" in body and "N.forward()" in body and "new URL(e.url).origin===location.origin" in body
    assert "setTimeout(()=>{ if(!swNav(a.href)) location.assign(a.href); }" in I18N
    assert "addEventListener('pagehide',e=>{ if(e.persisted) try{ es&&es.close(); }catch(_){} });" in PAGE
    assert "addEventListener('pageshow',e=>{ if(!e.persisted) return; LIVE_SYNC=false; connect(); pulse(true); });" in PAGE
    assert "addEventListener('pageshow',e=>{ if(e.persisted){ LIVE_ON=false; connectLive(); refresh(true); } });" in LIGHT


def _lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4   # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _cr(a, b):
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def test_daylight_sheets_and_buttons_are_light_and_night_greys_are_readable():
    assert "body.m-day .sheet,body.m-day .nbar{background:#fff;color:var(--ink)" in PAGE
    assert "body.m-day .panel .mi2{background:#eceef2;border-color:#8d95a1;color:#12161c}" in PAGE
    assert "body.m-night .sheet,body.m-night .nbar,body.m-night .mbox{background:#070a0f" in PAGE
    ink3 = re.search(r"body\.m-night\{--bg:#04060a;--ink:#8fa3b8;--ink2:#61748a;--ink3:(#[0-9a-f]{6});", PAGE).group(1)
    assert _cr(ink3, "#070a0f") >= 3.5                                              # was 2.3:1
    for c in ("#14459c", "#0d6b3f", "#b8480a", "#7a5f00", "#b3140d"):                # the daylight swaps, on white
        assert _cr(c, "#ffffff") >= 4.5, c
    assert 'style="color:#ffd9d6"' not in PAGE                                      # pale pink on a white chip
