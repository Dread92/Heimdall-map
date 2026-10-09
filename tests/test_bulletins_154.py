"""1.54: the AI's bulletins, the AI off the map, a whole-oblast target that reads as an area, no explosions layer.

The owner (9 Oct 2026): "for the AI we switch completely: instead of all that on the map, summaries of the activity of the
last hour / the last 24 hours, a bit like a weather bulletin — the AI placing things on the map, we forget it". His
choices: in the app behind a dashboard switch; the last hour every 20 minutes and the last 24 hours every hour, only
while there is activity; Ukrainian, English and French in one call; the 10-minute checks stopped. And: "this tiny square
marking looks really bad" (a target somewhere in an oblast: the name lit, a badge, the border glowing from the inside),
and the 24 hours' explosions filter "does not help much for now".
"""
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, ADMIN, DOC, SAFETY, SRC = (_read("static/kyiv.html"), _read("static/i18n.js"), _read("static/admin.html"),
                                       _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md"), _read("app/server.py"))
NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _mark(st, mid, minutes, place, uid, typ="drones", status=None, jet=0, count=1):
    st.store.conn.execute("INSERT INTO marker_log(id, ts, post_id, channel, type, status, place, oblast_uid, jet, count) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?)", (mid, ago(minutes), mid.split("#")[0], "kpszsu", typ, status, place, uid, jet, count))


def _busy_state():
    st = server.State(server.Store(":memory:"), {})
    _mark(st, "kpszsu/1#0", 50, "Бровари", "14")
    _mark(st, "kpszsu/2#0", 30, "Бровари", "14", jet=1)
    _mark(st, "kpszsu/3#0", 20, "область", "25", count=3)
    _mark(st, "kpszsu/4#0", 10, "Ніжин", "25")
    _mark(st, "kpszsu/5#0", 90, "Ірпінь", "14")                      # the hour before
    _mark(st, "kpszsu/6#0", 15, "Одеса", "18")                       # an oblast the map covers
    _mark(st, "kpszsu/7#0", 15, "Ужгород", "11")                     # one it does not: left out
    st.store.conn.execute("INSERT INTO outcomes(id, ts, post_id, channel, status, type, place, oblast_uid, count) VALUES(?,?,?,?,?,?,?,?,?)",
                          ("kpszsu/8#0", ago(5), "kpszsu/8", "kpszsu", "down", "drones", "Бровари", "14", 1))
    st.store.conn.execute("INSERT INTO alerts(key, source, location_uid, location_title, location_type, oblast_uid, alert_type, "
                          "alert_level, started_at, finished_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          ("a1", "t", "31", "м. Київ", "city", "31", "air_raid", "red", ago(40), None))
    night = server.tag_night(ago(30))
    st.store.conn.execute("INSERT INTO targets(night,n,prefix,origin,osrc,oquote,opost,first_ts,last_ts,type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (night, 3, "?", None, None, None, "kpszsu/1", ago(50), ago(30), "drones"))
    for i, (pl, m, alt) in enumerate([("Ніжин", 50, None), ("Козелець", 40, 1800), ("Бровари", 30, 1200)]):
        st.store.conn.execute("INSERT INTO target_points VALUES(?,?,?,?,?,?,?,?)", (f"p/{i}#0", night, 3, ago(m), 30.0, 50.5, pl, alt))
    st.store.conn.commit()
    return st


# ---- the record ------------------------------------------------------------------------------------------------------
def test_the_record_of_the_hour_is_counts_places_and_times_kyiv_first():
    st = _busy_state()
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    r = d["reports"]
    assert r["total"] == 5 and r["before"] == 1 and r["kinds"] == {"drone": 4, "jet drone": 1}
    assert r["by_oblast"][0]["oblast"].startswith("Київська область") and r["slice_min"] == 10
    assert not any("Закарпат" in o["oblast"] for o in r["by_oblast"])                 # out of the map's oblasts
    assert r["region_wide"][0]["targets"] == 3 and r["places"][0] == {"place": "Бровари (Kyiv oblast)", "reports": 2, "last": r["places"][0]["last"]}
    assert d["alerts"][0]["uid"] == "31" and d["alerts"][0]["on_now"] and d["outcomes"][0]["down"] == 1
    assert d["followed"][0]["path"][0].startswith("Ніжин") and d["followed"][0]["path"][-1].startswith("Бровари")
    assert d["heights"] == {"reports": 2, "min": 1200, "median": 1800, "max": 1800}
    text = server.State.activity_text(d)
    assert "not radar, not a count of drones" in text and "ON NOW" in text and "the window before: 1 reports" in text
    assert "Ніжин" in text and "kpszsu" not in text                                 # no channel, and never a post's text
    assert server.State.activity_active(d)


def test_a_quiet_window_is_quiet():
    st = server.State(server.Store(":memory:"), {})
    d = st.activity_summary(NOW - timedelta(hours=1), NOW)
    assert not server.State.activity_active(d) and "TARGETS REPORTED: 0 reports" in server.State.activity_text(d)


def test_the_24_hours_carry_their_dates():
    st = _busy_state()
    d = st.activity_summary(NOW - timedelta(hours=24), NOW)
    assert d["reports"]["slice_min"] == 60 and "." in d["from"] and d["reports"]["total"] == 6


# ---- the thread ------------------------------------------------------------------------------------------------------
class _AI:
    def __init__(self, res=None, on=True):
        self.res, self.on, self.asked = res, on, []

    def enabled(self):
        return self.on

    def model(self):
        return "m"

    def ask_bulletin(self, kind, text, span=""):
        self.asked.append((kind, text, span))
        return self.res or {"out": {"uk": "Укр.", "en": "Eng.", "fr": "Fr."}, "cost": 0.002, "tok_in": 900, "tok_out": 300, "model": "m"}


def test_a_quiet_window_gets_the_servers_line_once_and_no_call():
    st = server.State(server.Store(":memory:"), {})
    st.ai = _AI()
    bl = server.Bulletins(st, {})
    row = bl.write("1h")
    assert row["quiet"] == 1 and row["en"].startswith("Over the last hour the channels reported no targets") and not st.ai.asked
    assert bl.write("1h") is None and "said already" in bl.why["1h"] and len(st.store.bulletins()) == 1
    assert st.store.kv_get("bul_checked:1h")


def test_activity_is_written_once_in_three_languages():
    st = _busy_state()
    st.ai = _AI()
    bl = server.Bulletins(st, {})
    row = bl.write("1h", now=NOW)
    assert row["uk"] == "Укр." and row["en"] == "Eng." and row["fr"] == "Fr." and row["cost"] == 0.002 and not row["error"]
    kind, text, span = st.ai.asked[0]
    assert kind == "1h" and "TARGETS REPORTED: 5 reports" in text and "–" in span and row["input"] == text
    assert bl.write("1h", now=NOW) is None and bl.why["1h"].startswith("the same record")       # nothing new: no call
    assert len(st.ai.asked) == 1
    assert bl.write("1h", force=True, now=NOW)["en"] == "Eng." and len(st.ai.asked) == 2          # "write it now"


def test_the_ai_off_or_out_of_budget_stores_nothing_and_the_bulletin_goes_stale():
    st = _busy_state()
    st.ai = _AI(on=False)
    bl = server.Bulletins(st, {})
    assert bl.write("1h") is None and "off" in bl.why["1h"] and not st.store.bulletins()
    st.ai = _AI(res={"error": "budget"})
    assert bl.write("1h") is None and bl.why["1h"] == "not asked: budget" and not st.store.bulletins()
    st.ai = _AI(res={"error": "HTTP 500", "cost": 0})
    row = bl.write("1h")
    assert row["error"] == "HTTP 500" and st.store.bulletin_last("1h") is None and st.store.bulletin_last("1h", ok=False)


def test_the_24_hours_again_only_after_an_hour_with_activity_or_six_hours():
    st = server.State(server.Store(":memory:"), {})
    _mark(st, "kpszsu/1#0", 300, "Бровари", "14")                   # five hours ago: in the 24 h, not in the last hour
    st.store.conn.commit()
    st.ai = _AI()
    bl = server.Bulletins(st, {})
    assert bl.write("24h")["en"] == "Eng."
    assert bl.write("24h") is None and bl.why["24h"] == "nothing new in the last hour"
    _mark(st, "kpszsu/2#0", 5, "Бровари", "14")
    st.store.conn.commit()
    assert bl.write("24h")["en"] == "Eng." and len(st.ai.asked) == 2


def test_the_app_sees_the_latest_still_checked_and_only_with_the_switch_on():
    st = server.State(server.Store(":memory:"), {})
    st.ai = _AI()
    bl = server.Bulletins(st, {})
    bl.write("1h")
    assert bl.public() == {"on": False}
    st.store.kv_set("ai_bulletin_public", "1")
    p = bl.public()
    assert p["on"] and p["h1"]["quiet"] == 1 and set(p["h1"]) == {"at", "since", "until", "quiet", "uk", "en", "fr"} and p["h24"] is None
    old = (NOW - timedelta(minutes=50)).isoformat()
    st.store.conn.execute("UPDATE ai_bulletins SET at=?", (old,))
    st.store.kv_set("bul_checked:1h", old)
    assert bl.public()["h1"] is None                                # neither written nor checked for 35 minutes
    st.store.kv_set("bul_checked:1h", server.now_iso())
    assert bl.public()["h1"]["quiet"] == 1


def test_on_the_clock():
    bl = server.Bulletins(server.State(server.Store(":memory:"), {}), {"ai_bulletin_minutes": 20})
    t = 1_000_000_200.0
    assert bl.every("1h") == 20 and bl.every("24h") == 60
    assert bl.slot("1h", t) != bl.slot("1h", t + 1200) and bl.slot("1h", t - (t % 1200)) == bl.slot("1h", t - (t % 1200) + 1199)
    assert server.Bulletins(None, {"ai_bulletin_minutes": 1}).every("1h") == 10


# ---- the model's answer ----------------------------------------------------------------------------------------------
def test_an_answer_is_plain_text_without_links_channels_or_card_numbers_and_short():
    out = A.bulletin_clean({"uk": "**Київ**: 3 звіти. Див. https://t.me/x і @kyiv_airdef",
                            "en": "# Kyiv\n- Brovary 2 reports\n- card 4149 4993 1234 5678",
                            "fr": "Une phrase. " * 200}, "1h")
    assert out["uk"] == "Київ: 3 звіти. Див. і" and "#" not in out["en"] and "- " not in out["en"] and "4149" not in out["en"]
    assert len(out["fr"]) <= A.BULLETIN_CHARS["1h"] and out["fr"].endswith(".")
    assert A.bulletin_clean({"uk": "x", "en": "y"}, "1h") is None and A.bulletin_clean({"uk": "x", "en": "y", "fr": "  "}, "24h") is None


class _Resp:
    def __init__(self, d):
        self.d = json.dumps(d).encode()

    def read(self):
        return self.d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_one_call_three_languages_in_a_strict_schema_within_the_budget():
    store = server.Store(":memory:")
    r = A.AIReader({"openrouter_key": "sk-or-test", "ai_reader_monthly_usd": 10}, store)
    seen = {}

    def fake(req, timeout=None, context=None):
        seen.update(json.loads(req.data.decode()))
        return _Resp({"model": "m", "choices": [{"message": {"content": json.dumps({"uk": "У", "en": "E", "fr": "F"})}}],
                      "usage": {"cost": 0.0015, "prompt_tokens": 1000, "completion_tokens": 200}})
    with mock.patch.object(A.urllib.request, "urlopen", fake):
        res = r.ask_bulletin("24h", "RECORD …", "08.10 23:00–09.10 23:00")
    assert res["out"] == {"uk": "У", "en": "E", "fr": "F"} and res["cost"] == 0.0015 and r.spent == 0.0015
    assert seen["max_tokens"] == A.MAX_OUT_BULLETIN["24h"] and seen["response_format"]["json_schema"]["name"] == "heimdall_bulletin"
    assert seen["messages"][0]["content"] == A.BULLETIN_SYSTEM and "the last 24 hours (08.10 23:00–09.10 23:00, Kyiv time)" in seen["messages"][1]["content"]
    with mock.patch.object(A.urllib.request, "urlopen", lambda req, timeout=None, context=None: _Resp(
            {"choices": [{"message": {"content": json.dumps({"uk": "У", "en": "E"})}}], "usage": {"cost": 0.001}})):
        bad = r.ask_bulletin("1h", "RECORD")
    assert bad["error"] == "the answer lacks a language (uk, en, fr)" and bad["out"] is None


def test_the_prompt_holds_the_safety_rules():
    p = A.BULLETIN_SYSTEM
    for rule in ('say "reported"', "Kyiv first", "only from the official alerts", "Never say a place is safe",
                 "never forecast", "Never say where the targets came from", "Kyiv time", "at most 60 words",
                 "no channel names", '"uk"', '"en"', '"fr"'):
        assert rule in p, rule


# ---- the routes ------------------------------------------------------------------------------------------------------
def test_the_apps_route_and_the_dashboards():
    st = server.State(server.Store(":memory:"), {})
    st.ai = A.AIReader({"openrouter_key": "sk-or-test"}, st.store)
    st.bulletins = server.Bulletins(st, {})
    st.bulletins.write("1h")
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    get = lambda path: json.loads(urllib.request.urlopen(base + path, timeout=10).read())      # noqa: E731
    try:
        assert get("/api/bulletin") == {"on": False}
        st.store.kv_set("ai_bulletin_public", "1")
        d = get("/api/bulletin")
        assert d["on"] and d["h1"]["quiet"] == 1 and "input" not in d["h1"] and "cost" not in d["h1"]
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            try:
                urllib.request.urlopen(base + "/api/ai_reads", timeout=10)
                raise AssertionError("open without the key")
            except urllib.error.HTTPError as e:
                assert e.code == 403
            a = get("/api/ai_reads?key=adm-test")
        assert a["bulletin"]["public"] is True and a["bulletins"][0]["kind"] == "1h" and a["stats"]["mode"] == "bulletins"
    finally:
        srv.shutdown()
        server.Handler.state = old


# ---- the pages -------------------------------------------------------------------------------------------------------
def test_the_bulletin_card():
    assert '<div class="bul" id="bul" hidden></div>\n    <div class="sec" id="near"></div>' in PAGE
    assert '<div class="bul" id="bulL" hidden></div>\n    <div class="nearl" id="nearL"></div>' in PAGE
    assert "BUL=await jget('/api/bulletin',10000);" in PAGE and "const b=BUL[BUL_K], txt=b[LANG]||b.en||b.uk||'';" in PAGE
    assert "esc(t('bul_note'))" in PAGE and "bl.classList.toggle('off',id!=='near')" in PAGE and "body.rp .bul{display:none!important}" in PAGE
    for k in ("bul_title", "bul_h1", "bul_h24", "bul_at", "bul_note", "ob_kyiv"):
        assert I18N.count(f"{k}:'") == 3, k
    assert "not radar" in I18N and "не радар" in I18N and "pas un radar" in I18N


def test_the_dashboard():
    assert "sw('bulletin_public',!!BL.public,tr('sw_bul'))" in ADMIN and "data-bn=\"1h\"" in ADMIN and "bulletin_now:b.dataset.bn" in ADMIN
    for k in ("bul_note:", "bul_h:", "sw_bul:", "bul_now1:", "bul_now24:", "bul_quiet:", "ai_hist:"):
        assert ADMIN.count(k) == 2, k
    assert "data-mode=" not in ADMIN and "sw('live'" not in ADMIN


def test_a_whole_oblast_target_reads_as_an_area():
    chip = PAGE[PAGE.index("function paintOblEvents(){"):PAGE.index("function oblEventSheet")]
    assert "<clipPath id=\"obclip${uid}\">" in chip and '<path class="g1" d="${o.path}"/>' in chip
    assert "#oblevt .obglow .g1{stroke-width:26px;stroke-opacity:.05}" in PAGE and "@keyframes obbreath" in PAGE
    assert "body:not(.rp) #obllbl .oblbl.hot{fill:#f4f1e8;" in PAGE and 'data-o="${o.uid}" x="${o.cx}"' in PAGE
    assert "g.innerHTML=drawn.map(d=>d[0]).join('')+drawn.map(d=>d[1]).join('');" in chip          # outlines under badges
    assert "function fitOblChips()" in PAGE and "tx.getComputedTextLength()/k" in PAGE and "function layoutOblChips()" in PAGE
    assert "const OBL_UNNAMED=new Set(['14','31','30','29']);" in PAGE and "t('ob_kyiv')" in chip
    assert "layoutOblChips();\n  document.querySelectorAll('#obllbl .oblbl.hot')" in PAGE        # the towns give way
    assert "body.m-day #oblevt .obring.live,body.m-day #oblevt .obglow path{stroke:#1d2533}" in PAGE
    assert "body.lite #oblevt .obglow{display:none}" in PAGE


def test_the_docs():
    assert "### 7.11 The bulletins (1.54)" in DOC and "`GET /api/bulletin`" in DOC and "| `ai_bulletins` |" in DOC
    assert "## The AI writes bulletins, and puts nothing on the map (1.54)" in SAFETY
