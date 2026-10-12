"""1.32: the dashboard's Analytics tab, the admin's message in loud colours, and the nuclear event — the one message
that covers the map, behind two locks on the server (a one-time code, then the phrase) and a 3-second hold on the
dashboard. A false one would be the worst thing this app could ever show; these tests hold the locks in place."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import server
from alert_events import events_from_table  # 1.58.4: the alerts' start / end events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
NUKE = open(os.path.join(ROOT, "static", "nuke.js"), encoding="utf-8").read()
TEXT = {"uk": "Радіаційна небезпека. Зайдіть у приміщення.", "en": "Radiation danger. Go indoors."}


def _state():
    return server.State(server.Store(":memory:"), {})


def test_the_nuclear_event_needs_the_code_and_the_phrase_one_attempt_per_arming():
    st = _state()
    assert st.nuke_fire("ABCDEF", "NUCLEAR EVENT", TEXT)[0] is False          # never armed
    code = st.nuke_arm()
    assert len(code) == 6
    assert st.nuke_fire("ZZZZZZ", "NUCLEAR EVENT", TEXT)[0] is False          # a wrong code…
    assert st.nuke_fire(code, "NUCLEAR EVENT", TEXT)[0] is False              # …spends the arming
    code = st.nuke_arm()
    assert st.nuke_fire(code, "NUCLEAR", TEXT)[0] is False                    # the phrase in full, or nothing
    code = st.nuke_arm()
    st._nuke_arm = (code, st._nuke_arm[1] - 121)                               # two minutes, not more
    assert st.nuke_fire(code, "NUCLEAR EVENT", TEXT)[0] is False
    assert st.nuke is None and st.store.kv_get("nuke") in (None, "")


def test_fired_it_reaches_every_page_survives_a_restart_and_ends_in_one_step():
    st = _state()
    q = st.subscribe()
    code = st.nuke_arm()
    ok, _ = st.nuke_fire(code.lower(), " nuclear event ", TEXT)                 # typed in any case, spaces trimmed
    assert ok and st.nuke["text"] == TEXT and st.nuke["id"]
    assert any(e["kind"] == "nuke" and e["nuke"] for e in q)                   # the live line wakes every page
    assert st._state_obj()["nuke"]["id"] == st.nuke["id"]                      # it travels in the alerts state
    assert server.State(st.store, {}).nuke["id"] == st.nuke["id"]              # a restart keeps it on
    st.nuke_end()
    assert st.nuke is None and st._state_obj()["nuke"] is None
    assert server.State(st.store, {}).nuke is None


def test_the_nuke_route_is_admin_only_and_cannot_be_armed_twice():
    i = SRC.index('if u.path == "/api/admin/nuke":')
    body = SRC[i:i + 1800]
    assert "if not self._admin_ok(q):" in body[:200]
    assert 'if st.nuke:' in body and '"already active"' in body                # no second arming while one is on
    assert 'st.nuke_fire(data.get("code"), data.get("phrase"), text)' in body
    assert '[:600]' in body                                                     # the text is bounded


def test_the_dashboard_adds_a_third_lock_and_the_pages_draw_it_safely():
    # the button unlocks only when the code and the phrase are typed exactly, and fires only when held 3 s
    assert "function nkReady()" in ADMIN and "(now-t0)/3000" in ADMIN and "<details class=\"nk\"" in ADMIN
    # the pages download static/nuke.js only when there is one, and pass the state's `nuke`
    assert "showNuke(S.nuke)" in TAC and "showNuke(STATE&&STATE.nuke)" in LIGHT
    for page in (TAC, LIGHT):
        assert "if(n&&!showNuke.l)" in page and "/static/nuke.js" in page
    # the admin's text is set as text, never as HTML
    assert ".querySelector('.hnkt').textContent=tx" in NUKE and "innerHTML=tx" not in NUKE
    # no flashing faster than once a second (three a second can trigger a seizure); still for reduced motion
    for d in re.findall(r"animation:\w+ ([\d.]+)s", NUKE):
        assert float(d) >= 1.0, d
    assert "prefers-reduced-motion:reduce" in NUKE
    assert "pointer-events:none" in NUKE                                        # the map under it still works


def test_the_admins_message_is_loud_green_or_pulsing_red_on_both_pages():
    for page in (TAC, LIGHT):
        assert re.search(r"\.notice\.lv-info[^{]*\{background:#0d7a3e", page)
        assert re.search(r"\.notice\.lv-alert[^{]*\{background:#c4121c[^}]*animation:ntp 1\.6s", page)
        assert "@media (prefers-reduced-motion:reduce){.notice.lv-alert{animation:none}}" in page
    assert ".ntprev.lv-alert{background:#c4121c" in ADMIN                      # the dashboard previews the same


def _seed(st):
    tz = server.kyiv_tz()
    today = datetime.now(timezone.utc).astimezone(tz).date()
    d1 = (today - timedelta(days=1)).isoformat()

    def at(d, h):
        return datetime.combine(d, datetime.min.time()).replace(hour=h, tzinfo=tz).astimezone(timezone.utc)
    # a night and a day of the same date, the night with missiles named without a number
    st.store.af_save("kpszsu/1", "kpszsu", at(today - timedelta(days=1), 7).isoformat(),
                     {"period": "night", "date": d1, "launched": {"drones": 200, "jet": 50, "cruise": 10},
                      "down": {"drones": 180, "cruise": 8, "ballistic": 2, "total": 190}, "used": ["ballistic"],
                      "impacts": 12, "debris": 3, "areas": ["Орел", "Курськ"], "directions": ["Київщина"], "models": ["Калібр"]})
    st.store.af_save("kpszsu/2", "kpszsu", at(today - timedelta(days=1), 19).isoformat(),
                     {"period": "day", "date": d1, "launched": {"drones": 40, "jet": 10}, "down": {"drones": 30, "total": 30},
                      "used": [], "impacts": 2, "debris": 0, "areas": ["Орел"], "directions": [], "models": []})
    a = at(today - timedelta(days=1), 2)
    with st.store.lock:
        st.store.conn.executemany("INSERT INTO alerts(key,source,location_uid,location_title,location_type,oblast_uid,alert_type,"
                                  "alert_level,started_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  [("c1", "t", "ua-31", "м. Київ", "city", "31", "air_raid", "red", a.isoformat(), (a + timedelta(minutes=90)).isoformat()),
                                   ("o1", "t", "ua-14-1", "район", "raion", "14", "air_raid", "red", a.isoformat(), (a + timedelta(minutes=120)).isoformat()),
                                   ("x1", "t", "ua-9", "інша", "oblast", "9", "air_raid", "red", a.isoformat(), None)])
        st.store.conn.executemany("INSERT INTO marker_log(id,ts,post_id,channel,type,status,oblast_uid,heading,jet) VALUES(?,?,?,?,?,?,?,?,?)",
                                  [("m1", a.isoformat(), "p1", "c", "drones", None, "31", 90, 0),
                                   ("m2", a.isoformat(), "p2", "c", "drones", None, "14", None, 1),
                                   ("m3", a.isoformat(), "p3", "c", "banderol_missiles", None, "14", None, 0),
                                   ("m4", a.isoformat(), "p4", "c", "drones", "down", "31", None, 0),
                                   ("m5", a.isoformat(), "p5", "c", "drones", None, "5", 0, 0)])
        st.store.conn.commit()
    events_from_table(st)
    return d1, a.astimezone(tz)


def test_analytics_add_up_a_date_and_count_only_what_was_said():
    st = _state()
    d1, a = _seed(st)
    A = st.analytics(14)
    assert (A["days"], len(A["af"]), len(A["kyiv"]), len(A["reports"])) == (14, 14, 14, 14)
    row = next(r for r in A["af"] if r["date"] == d1)
    assert sorted(row["periods"]) == ["day", "night"]
    assert row["launched"] == {"drones": 240, "jet": 60, "cruise": 10} and row["down"]["total"] == 220
    assert row["used"] == ["ballistic"] and "ballistic" not in row["launched"]    # used, never a 0 launched
    assert row["impacts"] == 14 and dict(A["af_areas"])["Орел"] == 2
    empty = next(r for r in A["af"] if r["date"] != d1)
    assert empty["periods"] == [] and empty["launched"] == {}                     # no summary: nothing, not zeros
    k = next(r for r in A["kyiv"] if r["date"] == d1)
    assert (k["city_min"], k["oblast_min"], k["city_alerts"]) == (90, 120, 1)     # another oblast never counts
    assert A["starts"][a.weekday()][a.hour] == 1 and len(A["starts"]) == 7 and len(A["starts"][0]) == 24
    rep = next(r for r in A["reports"] if r.get("drones"))
    assert rep["drones"] == 1 and rep["jet"] == 1 and rep["banderol_missiles"] == 1 and rep["down"] == 1
    assert sum(A["hours"]) == 3 and A["headings"][2] == 1                          # only a stated course; oblast 5 is out
    json.dumps(A)                                                                  # the dashboard gets it as JSON


def test_analytics_are_admin_only_and_banderol_is_drawn_as_a_jet_drone():
    i = SRC.index('if u.path == "/api/analytics":')
    assert "if not self._admin_ok(q):" in SRC[i:i + 200]
    assert "jet:(r.jet||0)+(r.banderol_missiles||0)" in ADMIN                     # never with the missiles
    assert "(r.banderol_missiles||0)" not in ADMIN.split("missiles:(r.cruise_missiles")[1].split("};")[0]


def test_every_dashboard_string_exists_in_both_languages():
    en = ADMIN[ADMIN.index(" en:{"):ADMIN.index(" uk:{")]
    uk = ADMIN[ADMIN.index(" uk:{"):ADMIN.index("let L='en'")]
    keys = set(re.findall(r"\btr\('([a-z0-9_]+)'(?!\+)", ADMIN)) | set(re.findall(r'data-tr="([a-z0-9_]+)"', ADMIN))
    keys |= {"an_m_" + k for k in ("cruise", "ballistic", "aeroballistic", "antiship", "guided")}
    keys |= {"an_r_" + k for k in ("drones", "jet", "missiles", "other")}
    missing = sorted(k for k in keys if not re.search(r"[{,\s]" + k + ":", en) or not re.search(r"[{,\s]" + k + ":", uk))
    assert not missing, missing
    for tab in ("live", "analytics", "nights", "sources", "usage"):
        assert f'data-tab="{tab}"' in ADMIN and f'id="tab-{tab}"' in ADMIN


def test_142_2_an_arming_survives_a_restart_and_is_still_one_attempt():
    store = server.Store(":memory:")
    st = server.State(store, {})
    code = st.nuke_arm()
    st2 = server.State(store, {})                       # the process restarted between arming and firing
    assert st2.nuke_fire(code, "NUCLEAR EVENT", TEXT)[0] is True
    st2.nuke_end()
    code = st2.nuke_arm()
    st3 = server.State(store, {})
    assert st3.nuke_fire("ZZZZZZ", "NUCLEAR EVENT", TEXT)[0] is False           # wrong: spent, in the database too
    assert server.State(store, {}).nuke_fire(code, "NUCLEAR EVENT", TEXT)[0] is False
    assert store.kv_get("nuke_arm") in (None, "")


def test_142_2_the_phrase_in_ukrainian_too_never_a_part_of_it():
    st = _state()
    assert st.nuke_fire(st.nuke_arm(), "  ядерна   подія ", TEXT)[0] is True
    st.nuke_end()
    assert st.nuke_fire(st.nuke_arm(), "ЯДЕРНА", TEXT)[0] is False
    assert "NK_PHRASES=['NUCLEAR EVENT','ЯДЕРНА ПОДІЯ']" in ADMIN


def test_142_2_the_hold_survives_a_drift_and_a_preview_sends_nothing():
    assert "$('nk_fire').setPointerCapture(e.pointerId)" in ADMIN
    i = ADMIN.index("function nkPreview(open)")
    body = ADMIN[i:ADMIN.index("\n$('nk_prev')", i)]
    assert "HNuke.show(" in body and "nkPost" not in body and "fetch(" not in body          # drawn here, never sent
    assert 'id="nk_prev"' in ADMIN and 'id="nk_pv"' in ADMIN
    assert "tr('nk_wrong',d.error||d.message||'?')" in ADMIN                   # what the server said, in full
