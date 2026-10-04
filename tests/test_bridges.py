"""1.34: the Kyiv bridges. From 1 October 2026 the Dnipro bridges are the targets (the Southern bridge five times in two
days, the Northern bridge on 3 and 4 October, jet drones among them, with cars on them). The live trackers post just
the bridge's name — "Південний міст", "🔻Зниження Північний міст", "на міст патона" — and the app dropped those posts
as saying nothing. Read on the real posts of 1–4 October (tests/fixtures/bridge_posts_2026_10.json, each with the
bridge it puts a live mark on, read by hand), then: the state bridge by bridge, the push to the phones that asked,
the faster reading while a threat is near a bridge, and the heat layer of where drones were reported."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "bridge_posts_2026_10.json"), encoding="utf-8"))
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def _bridge_of(channel, text):
    tags = server.tag_feed_text(text, channel)
    if not server.is_relevant(text, tags, channel):
        return None
    for m in geo.parse_for_channel(channel, text):
        if m.get("status"):
            continue
        pl = (m.get("place") or "").replace("→", "").strip()
        if pl in server.BRIDGE_BY_PLACE:
            return server.BRIDGE_BY_PLACE[pl]
    return None


def test_the_real_posts_put_their_mark_on_the_right_bridge_and_the_news_on_none():
    wrong = {pid: (_bridge_of(pid.split("/")[0], c["text"]), c["bridge"]) for pid, c in FIX.items()
             if _bridge_of(pid.split("/")[0], c["text"]) != c["bridge"]}
    assert not wrong, wrong


def test_every_spelling_of_the_five_bridges():
    for text, bid in (("Південного мосту", "pivdennyi"), ("над Північним мостом", "pivnichnyi"), ("на мосту Метро", "metro"),
                      ("метроміст", "metro"), ("міст ім. Патона", "paton"), ("Дарницький залізнично-автомобільний міст", "darnytskyi"),
                      ("Южный мост", "pivdennyi"), ("Северный мост", "pivnichnyi")):
        assert server.bridges_named(text) == [bid], text


def test_the_spans_and_the_distance_to_them():
    assert len(server.BRIDGES) == 5
    pd = next(b for b in server.BRIDGES if b["id"] == "pivdennyi")
    mid = ((pd["a"][0] + pd["b"][0]) / 2, (pd["a"][1] + pd["b"][1]) / 2)
    assert server.bridge_km(*mid, pd) < 0.01
    assert 2.0 < server.bridge_km(30.55, 50.38, pd) < 2.5                        # ТЕЦ-5
    # the page draws the same spans as the server measures
    for b in server.BRIDGES:
        assert f"['{b['id']}',[{b['a'][0]:.5f},{b['a'][1]:.5f}],[{b['b'][0]:.5f},{b['b'][1]:.5f}]]" in TAC.replace(" ", ""), b["id"]


def _state(marks, posts=()):
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    st.markers_now = lambda: marks
    st.store.add_feed(list(posts))
    return st


def _m(i, lon, lat, place, minutes=1, **kw):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    return dict({"id": i, "lon": lon, "lat": lat, "place": place, "oblast_uid": "31", "type": "drones", "ts": ts, "channel": "kyiv_airdef"}, **kw)


def test_bridge_by_bridge_at_near_hit_and_what_never_counts():
    marks = [
        _m("a", 30.5763, 50.3977, "Південний міст"),                            # on the Southern bridge
        _m("b", 30.55, 50.38, "ТЕЦ-5"),                                         # 2.3 km from it: near (it stays "at")
        _m("c", 30.592, 50.433, "Русанівка", jet=True),                         # a jet drone 0.3 km from Paton's east end: at
        _m("d", 30.50, 50.51, "Оболонь"),                                       # a Shahed 3.2 km from the Northern bridge: near
        _m("e", 30.52, 50.45, "Київ"),                                          # "Kyiv" alone: no bridge
        _m("f", 30.5644, 50.4426, "Міст Метро", stale=7),                       # stale: no
        _m("g", 30.5644, 50.4426, "Міст Метро", status="impact", minutes=10),   # a hit 10 min ago: hit
        _m("h", 30.5847, 50.4154, "Дарницький міст", oblast_uid="22"),          # wrong oblast (a misplacement): no
    ]
    B = _state(marks).bridges_now()
    assert B["pivdennyi"]["lvl"] == "at" and B["pivdennyi"]["n"] == 3           # a, b, and the jet drone (< 6 km)
    assert B["paton"]["lvl"] == "at" and B["paton"]["jet"] is True
    assert B["pivnichnyi"]["lvl"] == "near" and 3.0 < B["pivnichnyi"]["km"] < 3.5
    assert B["metro"]["lvl"] == "near"                                          # the jet drone 2 km away outranks the hit
    assert _state([marks[5], marks[6]]).bridges_now()["metro"]["lvl"] == "hit"    # alone: the hit 10 min ago; the stale one: nothing
    assert B["darnytskyi"]["lvl"] == "near" and B["darnytskyi"]["jet"] is True   # the jet drone, 1.7 km away
    # a Shahed 5 km out is nothing; a jet drone 5 km out is "near"
    far = [_m("x", 30.46, 50.33, "Новосілки")]
    assert not any(_state(far).bridges_now().values())


def test_a_post_that_names_a_bridge_lights_it_wherever_the_mark_went():
    now = datetime.now(timezone.utc)
    posts = [{"post_id": "kievinfo_kyiv/1", "channel": "kievinfo_kyiv", "ts": (now - timedelta(minutes=1)).isoformat(),
              "text": "❗️✈️Повз лівий берег на Південний міст", "tags": ["drones"]},
             {"post_id": "kievinfo_kyiv/2", "channel": "kievinfo_kyiv", "ts": (now - timedelta(minutes=2)).isoformat(),
              "text": "⛔️ На Північному мосту рух ПЕРЕКРИТИЙ", "tags": ["alert"]},
             {"post_id": "kyiv_airdef/3", "channel": "kyiv_airdef", "ts": (now - timedelta(minutes=9)).isoformat(),
              "text": "Міст Патона", "tags": []}]
    B = _state([], posts).bridges_now()
    assert B["pivdennyi"]["lvl"] == "at" and B["pivdennyi"]["how"] == "named"
    assert B["pivnichnyi"] == {} and B["paton"] == {}                           # traffic news; and 9 minutes is too old


def test_the_state_carries_the_bridges_and_the_trackers_read_faster_near_them():
    st = _state([_m("a", 30.5763, 50.3977, "Південний міст")])
    snap = st.snapshot()
    assert set(snap["bridges"]) == {b["id"] for b in server.BRIDGES} and snap["bridges"]["pivdennyi"]["lvl"] == "at"
    assert st.bridges_busy() and not _state([_m("z", 31.5, 49.5, "Черкаси", oblast_uid="14")]).bridges_busy()
    assert "time.sleep(rush if lvl >= 2 else fast if (lvl or busy) else interval)" in SRC
    assert "self.state.missile_active() or self.state.bridges_busy()" in SRC


def test_the_push_goes_to_the_phones_that_asked_in_their_language():
    store = server.Store(":memory:")
    store.push_add({"endpoint": "https://p/1", "keys": {}}, {}, ["bridges", "nonsense"], "fr")
    store.push_add({"endpoint": "https://p/2", "keys": {}}, {"lat": 50.45, "lon": 30.52}, [], "xx")
    subs = {s["endpoint"]: s for s in store.push_all()}
    assert subs["https://p/1"]["topics"] == ["bridges"] and subs["https://p/1"]["lang"] == "fr"
    assert subs["https://p/2"]["topics"] == [] and subs["https://p/2"]["lang"] == "uk"
    b = next(x for x in server.BRIDGES if x["id"] == "pivdennyi")
    tx = server.bridge_push_texts(b, {"lvl": "near", "km": 2.3, "type": "drones", "jet": True, "ts": datetime.now(timezone.utc).isoformat()})
    assert tx["uk"][0] == "🌉 Південний міст: ціль за 2,3 км" and tx["en"][0] == "🌉 Southern Bridge: target 2.3 km away"
    assert "Реактивний БпЛА" in tx["uk"][1] and "не радар" in tx["uk"][1] and tx["fr"][0].startswith("🌉 Pont Sud")
    i = SRC.index("    def _run(self):", SRC.index("class Pusher"))
    assert 'n["topic"] not in s_.get("topics", [])' in SRC[i:i + 1500]
    i = SRC.index("def bridge_watch(")
    body = SRC[i:i + 1800]
    assert "BRIDGE_PUSH_GAP" in body and 'queue_topic(bridge_push_texts(b, c), "threat", "bridges")' in body and "bridge_event" in body


def test_the_heat_layer_counts_places_never_outcomes_or_vague_points():
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    rows = [("1", "p1", "drones", None, "Бровари", 30.79, 50.51, "high"), ("2", "p1", "drones", None, "Бровари", 30.79, 50.51, "high"),
            ("3", "p2", "unknown", None, "Бровари", 30.79, 50.51, "high"), ("4", "p3", "drones", None, "→ Вишгород", 30.49, 50.58, "high"),
            ("5", "p4", "drones", "down", "Вишгород", 30.49, 50.58, "high"), ("6", "p5", "drones", None, "Київ", 30.52, 50.45, "high"),
            ("7", "p6", "drones", None, "Київська область", 30.2, 50.2, "low"), ("8", "p7", "cruise_missiles", None, "Бровари", 30.79, 50.51, "high")]
    with st.store.lock:
        st.store.conn.executemany("INSERT INTO marker_log(id,ts,post_id,type,status,place,lon,lat,pos_conf,oblast_uid) VALUES(?,?,?,?,?,?,?,?,?,'14')",
                                  [(r[0], now.isoformat(), *r[1:]) for r in rows])
        st.store.conn.commit()
    h = st.drone_heat(7)
    assert [(p[3], p[2]) for p in h["points"]] == [("Бровари", 2), ("Вишгород", 1)] and h["reports"] == 3
    i = SRC.index('if u.path == "/api/drone_heat":')
    body = SRC[i:SRC.index('if u.path == "/api/analytics":')]
    assert "_admin_ok" not in body and 'st.cached(f"drone_heat:{d}", 600' in body


def test_the_pages():
    # Tactical: the bar, the spans, the toggle, the topics on every subscribe; the heat layer never remembered
    assert 'id="brgbar"' in TAC and '<g id="bridgeg"></g>' in TAC and 'id="brgbtn"' in TAC
    assert TAC.count("topics:BRG_ON?['bridges']:[],lang:LANG") == 2
    assert "LAYERS.heat=false;" in TAC and "/api/drone_heat?days=" in TAC
    order = re.findall(r'<g id="(\w+)"></g>', TAC)
    assert order.index("heatg") < order.index("bridgeg") < order.index("markers")
    assert "@media (prefers-reduced-motion:reduce){.brg.at,.brgbar.at{animation:none}}" in TAC
    # Light: the bridges from the state
    assert "showBrg(STATE&&STATE.bridges)" in LIGHT and 'id="brg"' in LIGHT
    for k in ("br_pivnichnyi", "br_metro", "br_paton", "br_darnytskyi", "br_pivdennyi", "br_at", "br_near", "br_hit", "m_brg", "m_brg_on"):
        assert len(re.findall(rf"(?<![A-Za-z_]){k}:", I18N)) == 3, k
