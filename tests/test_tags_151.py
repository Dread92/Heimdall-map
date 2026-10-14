"""1.51: target tags — S-07 ×2 · 3500 м.

Every target in the air gets Heimdall's own number for the night (from 12:00 Kyiv time) and a letter for where a post
SAID it came from — N north or Belarus, E east or Russia, S south, the sea or Crimea, W west, ? not said. The letter
is never worked out from where the target was first seen. The rules' reading comes first; with the dashboard's switch
on, the AI reader's quoted, checked reading fills what the rules did not read (origin, height, speed), marked as the
AI's; off, the tags carry the rules' reading alone. A tag does not change while the target is tracked, even after its
first report has left the window, and it survives a restart. It is not an official or military designation.
"""
import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, ADMIN, REPLAY, SAFETY, DOC = (_read("static/kyiv.html"), _read("static/i18n.js"), _read("static/admin.html"),
                                          _read("static/replay.js"), _read("docs/SAFETY.md"), _read("docs/TECHNICAL.md"))
NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


# ---- what a post says about where it comes from -------------------------------------------------------------------
def test_the_origin_is_what_the_post_says():
    cases = {"2 реактиви у бік Києва з півдня.": "s", "Група шахедів з території Білорусі на Житомирщину": "belarus",
             "Шахеди з Брянщини на Сумщину": "russia", "БпЛА з моря на Одесу": "sea", "Крилаті ракети з Криму": "crimea",
             "Шахед з північного сходу на Бровари": "ne", "Шахед з ТОТ на Запоріжжя": "occupied",
             "Шахеды со стороны Беларуси на Овруч": "belarus"}
    for text, o in cases.items():
        (m,) = geo.parse_for_channel("kpszsu", text)
        assert (m.get("origin") or {}).get("o") == o, text
    # a Ukrainian oblast it comes from is a place, not an origin; and nothing is worked out from a position
    for text in ("Шахеди з Чернігівщини на Київщину", "Шахед над Броварами", "Реактивний на півночі Чернігівщини"):
        assert not any(m.get("origin") for m in geo.parse_for_channel("kpszsu", text)), text


def test_a_speed_only_when_written():
    assert geo.parse_speed("швидкість 180 км/год") == {"kmh": 180, "q": "швидкість 180 км/год"}
    assert geo.parse_speed("летить 400 км/год")["kmh"] == 400
    assert geo.parse_speed("висота 2200") is None and geo.parse_speed("за 20 км від Броварів") is None
    (m,) = geo.parse_for_channel("kpszsu", "Реактивний над Коростенем, швидкість 400 км/год")
    assert m["speed"]["kmh"] == 400


def test_the_letters():
    P = server.TAG_PREFIX
    assert (P["belarus"], P["n"], P["nw"], P["russia"], P["ne"], P["e"], P["se"]) == ("N", "N", "N", "E", "E", "E", "E")
    assert (P["sea"], P["crimea"], P["s"], P["sw"], P["w"], P["occupied"]) == ("S", "S", "S", "S", "W", "?")


def test_a_night_runs_from_noon_to_noon_and_is_named_by_the_day_it_starts():
    k = server.kyiv_tz()
    at = lambda d, h, mi=0: datetime(2026, 10, d, h, mi, tzinfo=k).astimezone(timezone.utc).isoformat()   # noqa: E731
    assert server.tag_night(at(9, 12)) == server.tag_night(at(10, 3)) == server.tag_night(at(10, 11, 59)) == "2026-10-09"
    assert server.tag_night(at(9, 11, 59)) == "2026-10-08"


# ---- the tags ------------------------------------------------------------------------------------------------------
def _state(**cfg):
    # post ids are unique in life; the parse cache is shared by every State (a class attribute), so each test here
    # uses ids of its own
    st = server.State(server.Store(":memory:"), cfg)
    return st, server.Telegram(st, cfg)


def _tags(st):
    return {m["id"]: m.get("tag") for m in st.markers() if not m.get("status")}


def test_a_track_keeps_its_tag_and_the_letter_its_first_report_stated():
    st, tg = _state()
    tg.ingest("kyiv_airdef", [("kyiv_airdef/1", ago(6), "Шахед з півдня на Обухів"), ("kyiv_airdef/2", ago(3), "Шахед над Українкою")],
              "tg:kyiv_airdef")
    tg.ingest("kpszsu", [("kpszsu/9", ago(2), "2 реактиви з території Білорусі на Овруч")], "tg:kpszsu")
    tg.ingest("kpszsu", [("kpszsu/10", ago(1), "3 реактиви на Чернігівщині")], "tg:kpszsu")
    t = _tags(st)
    assert t["kyiv_airdef/2#0"]["id"] == "#01" and t["kyiv_airdef/2#0"]["os"] == "rules" and t["kyiv_airdef/2#0"]["oq"] == "з півдня"
    assert t["kpszsu/9#0"]["id"] == "#02" and t["kpszsu/9#0"]["o"] == "belarus"
    # 1.52, the owner's rule: a number only when we are sure which target it is — never for one reported for a whole oblast
    assert t["kpszsu/10#0"] is None
    assert _tags(st) == t                                           # recomputed: the same tags
    row = st.tags.row(("%s" % t["kpszsu/9#0"]["night"], 2))
    assert row["prefix"] == "N" and row["origin"] == "belarus" and row["osrc"] == "rules"


def test_the_tag_is_found_by_any_report_so_it_survives_the_window_and_a_restart():
    store = server.Store(":memory:")
    tt = server.TargetTags(store)
    k1 = tt.assign({"id": "a/1#0", "ts": ago(50), "reports": ["a/1#0", "a/2#0"], "history": [{"ts": ago(50)}]})
    k2 = tt.assign({"id": "a/3#0", "ts": ago(5), "reports": ["a/2#0", "a/3#0"]})          # a/1 has left the window
    other = tt.assign({"id": "b/1#0", "ts": ago(4), "reports": ["b/1#0"]})
    assert k1 == k2 and other[1] == k1[1] + 1
    again = server.TargetTags(store)                                                     # a restart
    assert again.assign({"id": "a/4#0", "ts": ago(1), "reports": ["a/3#0", "a/4#0"]}) == k1
    assert again.assign({"id": "c/1#0", "ts": ago(1), "reports": ["c/1#0"]})[1] == other[1] + 1
    assert again.find(["a/1#0"]) == f"#{k1[1]:02d}" and again.find(["zz/1#0"]) is None


# ---- the AI's facts: only with the switch on, only its own target's, only what the rules did not read ---------------
def _with_ai(st, post_id, targets):
    st.ai = A.AIReader({"openrouter_key": "sk-or-test"}, st.store, geo, rules_fn=lambda *a: [], oblast_names={})
    st.store.ai_save({"post_id": post_id, "ts": ago(1), "channel": post_id.split("/")[0], "text": "", "verdict": "ai_only",
                      "rules": [], "ai": {"targets": targets, "uncertain": None}})


def _ait(**kw):
    t = A._t(**kw)
    t["place"] = kw.get("place")
    return t


def test_the_ai_never_fills_a_tag():
    # 1.54, the owner: "the AI placing things on the map — we forget it": a reading stored by the AI before 1.54 adds
    # nothing to a tag — no origin, no height — whatever the switches say
    st2, tg2 = _state()
    tg2.ingest("kpszsu", [("kpszsu/6", ago(2), "Група шахедів на Бровари, ідуть від кордону")], "tg:kpszsu")
    _with_ai(st2, "kpszsu/6", [_ait(kind="shahed", place="Бровари", relation="heading_to", origin="belarus",
                                    origin_quote="від кордону", altitude_m=1500, altitude_quote="висота 1500")])
    t = _tags(st2)["kpszsu/6#0"]
    assert t["id"] == "#01" and t["p"] == "?" and t["os"] is None and t["alt"] is None

def test_the_rules_reading_alone_and_no_target_of_the_ais():
    st, tg = _state()
    tg.ingest("kpszsu", [("kpszsu/7", ago(2), "Шахед з півдня на Обухів, висота 800\nРеактивний на Бровари")], "tg:kpszsu")
    _with_ai(st, "kpszsu/7", [_ait(kind="shahed", place="Обухів", relation="heading_to", origin="belarus", origin_quote="x",
                                   altitude_m=2000, altitude_quote="y"),
                              _ait(kind="cruise_missile", place="Київ", relation="heading_to", origin="russia", origin_quote="z",
                                   speed_kmh=500, speed_quote="w")])
    t = _tags(st)
    ob = next(v for k, v in t.items() if k.startswith("kpszsu/7#") and v and v.get("oq") == "з півдня")
    assert ob["p"] == "S" and ob["os"] == "rules" and {k: ob["alt"][k] for k in ("m", "s", "cur")} == {"m": 800, "s": "rules", "cur": True}
    jet = next(v for k, v in t.items() if k.startswith("kpszsu/7#") and v is not ob)
    assert jet["p"] == "?" and jet["spd"] is None
    assert not any("#ai" in k for k in t)                           # 1.54: no target the AI alone found

def test_match():
    a, b = _ait(kind="shahed", place="Бровари"), _ait(kind="shahed", place="Бориспіль")
    assert A.match([a], {"Обухів"}, True) is a                     # one target each way: the same one
    assert A.match([a, b], {"Бориспіль"}, False) is b and A.match([a, b], {"Обухів"}, False) is None
    assert A.match([a], {"Обухів"}, False) is None
    assert A.match([_ait(kind="shahed", place="Київ")], {"o31"}, False) is not None   # Kyiv alone is the city


def test_switched_off_the_ai_asks_nothing():
    st, _ = _state()
    r = A.AIReader({"openrouter_key": "sk-or-test"}, st.store)
    assert r.enabled()
    st.store.kv_set("ai_reader_on", "0")
    assert not r.enabled() and r.ask_bulletin("1h", "RECORD") == {"error": "off"} and r.stats()["reader_on"] is False

def test_the_switches_are_the_dashboards_alone():
    st, _ = _state()
    st.ai = A.AIReader({"openrouter_key": "sk-or-test"}, st.store)
    st.bulletins = server.Bulletins(st, {})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/admin/ai"
    post = lambda url, body: urllib.request.urlopen(urllib.request.Request(   # noqa: E731
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=10)
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            try:
                post(base, {"bulletin_public": True})
                raise AssertionError("switched without the key")
            except urllib.error.HTTPError as e:
                assert e.code == 401
            assert st.store.kv_get("ai_bulletin_public") is None
            d = json.loads(post(base + "?key=adm-test", {"bulletin_public": True}).read())
            assert d["ok"] and d["bulletin_public"] is True and st.store.kv_get("ai_bulletin_public") == "1"
            d = json.loads(post(base + "?key=adm-test", {"reader": False, "bulletin_now": "1h"}).read())
            assert d["stats"]["reader_on"] is False and not st.ai.enabled() and st.bulletins.asked == ["1h"]
    finally:
        srv.shutdown()
        server.Handler.state = old


# ---- the analytics and the replay ---------------------------------------------------------------------------------
def test_the_nights_counts_by_letter():
    st, tg = _state()
    tg.ingest("kpszsu", [("kpszsu/1", ago(9), "Шахед з півдня на Обухів"), ("kpszsu/2", ago(8), "2 реактиви з території Білорусі на Житомирщину"),
                         ("kpszsu/3", ago(7), "Шахед на Бровари")], "tg:kpszsu")
    st.markers()
    night = server.tag_night(NOW)
    rows = st._an_targets([night])
    # the Zhytomyr group is reported for its whole oblast: no tag (1.52), so not counted
    assert rows[0]["S"] == 1 and rows[0]["N"] == 0 and rows[0]["?"] == 1 and rows[0]["total"] == 2 and rows[0]["ai"] == 0


def test_the_replay_shows_the_tags_the_live_map_gave():
    st, tg = _state()
    tg.ingest("kpszsu", [("kpszsu/1", ago(9), "Шахед з півдня на Обухів"), ("kpszsu/3", ago(7), "Шахед над Броварами")], "tg:kpszsu")
    st.markers()
    tracks = st._replay_tracks(NOW - timedelta(hours=1), NOW, [])
    assert sorted(t["tg"] for t in tracks) == ["#01", "#02"]


# ---- the pages -----------------------------------------------------------------------------------------------------
def test_the_map_label_carries_the_tag_and_the_bottom_line_the_telemetry():
    assert "l1.innerHTML=`<tspan class=\"tid\">${esc(tg.id)}</tspan> ${esc(name)}`" in PAGE
    assert ".mk .lbl .tid{fill:#ffd500}svg.wide .mk .lbl .tid{display:none}" in PAGE
    assert "spdK?t('tg_spd',spdK):''" in PAGE and "telAi" not in PAGE and "aitag" not in PAGE       # 1.54: no AI on the map
    assert "${tagLine(m)}" in PAGE and "t('tg_what')" in PAGE and "<span class=\"tagid\">${esc(cur.tag.id)}</span>" in PAGE
    # the card's style is never the map's: a 12.5 px font inside the map's SVG is 12.5 km tall
    assert ".tagid{font:800 12.5px" in PAGE and not re.search(r"(?m)^\.tid\{", PAGE)
    assert "<text class=\"tgc\" x=\"0\" y=\"0\"></text>" in PAGE and "svg:not(.close):not(.wide) .mk:not(.inbound)" in PAGE


def test_an_approach_mark_stands_off_the_town_on_the_side_the_post_named():
    assert "const apOff=!!m.approach&&!m.status&&!m.endedBy&&m.heading!=null;" in PAGE
    # 1.58.18: 30 px at a glyph's full size, less as it shrinks zoomed out (MSK)
    assert "if(apOff){ const a=m.heading*Math.PI/180, D=Math.min(30*MSK,12); gx=x-D*Math.sin(a); gy=y+D*Math.cos(a); }" in PAGE
    assert "b.g.setAttribute('transform',`translate(${gx.toFixed(3)} ${gy.toFixed(3)})`);" in PAGE
    assert "lblPos.push({b,m,sx:gx/KPX,sy:gy/KPX});" in PAGE


def test_the_strings_exist_in_three_languages():
    for k in ["tg_what", "tg_nofrom", "tg_said", "tg_ai", "tg_ai_chip", "tg_spd", "tg_spd_l", "tg_alt_l"] + [f"tg_o_{o}" for o in A.ORIGINS]:
        assert I18N.count(f"{k}:'") == 3, k
    assert "Not an official or military designation." in I18N and "Це не офіційне й не військове позначення." in I18N


def test_the_replay_and_the_dashboard():
    assert "lb.textContent=(tr.tg&&typeof TAGS_SHOWN!=='undefined'&&TAGS_SHOWN?tr.tg+' ':'')" in REPLAY   # 1.56.5: shown only with TAGS_SHOWN
    assert "card('c13',tr('an_c_tags')" in ADMIN and "if(k==='targets') csvDownload(" in ADMIN
    assert "sw('bulletin_public',!!BL.public,tr('sw_bul'))" in ADMIN and "fetch('/api/admin/ai'" in ADMIN and "sw('live'" not in ADMIN


def test_safety_and_docs():
    assert "## A target's tag is a number, not a designation (1.51)" in SAFETY
    assert "### 7.8 Target tags (1.51)" in DOC


# ---- 1.51: the AI is given the map; descent and height are always shown when given ---------------------------------
def test_the_ai_is_given_nothing_of_the_map_any_more():
    # 1.54: the map's context for the AI (ai_context, ai_map) went with its reading of the posts
    st, _ = _state()
    assert not hasattr(st, "ai_context") and not hasattr(st, "ai_map") and not hasattr(st, "ai_live")

def test_a_descent_is_in_the_tag_when_the_rules_read_it_and_never_from_the_ai():
    st, tg = _state()
    tg.ingest("kpszsu", [("kpszsu/9108", ago(2), "Шахед над Броварами, пішов униз")], "tg:kpszsu")
    _with_ai(st, "kpszsu/9108", [_ait(kind="shahed", place="Бровари", relation="at", vertical="descending", vertical_quote="пішов униз")])
    assert _tags(st)["kpszsu/9108#0"]["vs"] is None                   # 1.54: the AI's reading is not used
    st2, tg2 = _state()
    tg2.ingest("kpszsu", [("kpszsu/9109", ago(2), "Шахед над Броварами, знижується")], "tg:kpszsu")
    assert _tags(st2)["kpszsu/9109#0"]["vs"] == {"v": "descending", "s": "rules"}

def test_height_and_descent_are_shown_whenever_given():
    assert "svg.veryfar .mk .dn{display:none}" not in PAGE                   # at every zoom
    assert "const dtx=[altM?((dscAny?'↓':'')+altM+' '+t('m_unit')+(altOld!=null?` (${altOld}′)`:'')):(dscAny?'↓':'')" in PAGE   # also once stale
    assert "tv0.vs&&tv0.vs.v==='descending'" in PAGE
    assert "function oblAlt(m)" in PAGE and "if(al2) seg(`<text class=\"obtxt obalt\"" in PAGE   # region-wide reports too


# ---- 1.51: a target "somewhere in the oblast" says so, and is not drawn in the alert's colours ------------------------
def test_a_region_wide_target_is_outlined_and_says_somewhere_in_the_oblast():
    chip = PAGE[PAGE.index("function paintOblEvents(){"):PAGE.index("function oblEventSheet")]
    # 1.54, the owner: "this tiny square marking looks really bad": the oblast's own name lights up, a rounded badge under
    # it, and the border glows from the inside; "somewhere in the oblast" under the badge from the regional view in
    assert "<text class=\"obtxt obwhere\" text-anchor=\"middle\"" in chip and "svg.veryfar #oblevt .obwhere{display:none}" in PAGE
    assert "obhatch" not in PAGE and "obhp" not in PAGE and "3fe0ff" not in PAGE
    assert "tid=TAGS_SHOWN&&en[k]===1&&m.tag?m.tag.id:''" in chip                                   # its tag, when it is one report
    assert "#oblevt .obring.live{fill:none;stroke:#f4f1e8;" in PAGE                   # never the alerts' amber or red
    assert '<g class="obglow" clip-path="url(#obclip${uid})">' in chip and "e.classList.toggle('hot',hot.has(e.dataset.o))" in chip
    assert "#oblevt .obglow{pointer-events:none}" in PAGE and "obbreath" not in PAGE        # 1.54.3: the glow is still
