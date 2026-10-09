"""1.53: the AI reads every 10 minutes, not every post — and writes up each night.

The owner (9 Oct 2026): one call a post costs too much at the channels' pace (~150 posts an hour at ~$0.0004: the
month's $10 gone in a week). Every `ai_check_minutes` one call reads the posts of those minutes, grouped by the oblast
they concern, with what the rules drew from each and what the map shows in each oblast, and answers only where the
rules are wrong or incomplete (findings) plus a short note per oblast. A target only it found is still drawn, marked
AI, but never pushed "near you" — it is up to ten minutes old. After each night the whole record (alerts, every tag
with its path, heights, origins, outcomes, the Air Force, the checks) is summed up for any AI to read, and the AI writes
its report on it for the dashboard.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


ADMIN, SRC, DOC, SAFETY = _read("static/admin.html"), _read("app/server.py"), _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md")
NOW = datetime.now(timezone.utc)
OBL = {u: uk for u, uk, _ in server.OBLASTS}


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


class _Resp:
    def __init__(self, obj):
        self.b = json.dumps(obj).encode()

    def read(self):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _answer(content, tin=9000, tout=400, cost=0.0011, finish="stop"):
    return _Resp({"choices": [{"message": {"content": content}, "finish_reason": finish}],
                  "usage": {"prompt_tokens": tin, "completion_tokens": tout, "cost": cost}, "model": "anthropic/claude-haiku-5.5"})


def _reader(store=None, map_fn=None):
    return A.AIReader({"openrouter_key": "sk-or-test"}, store or server.Store(":memory:"), geo,
                      rules_fn=lambda ch, t, near: geo.parse_for_channel(ch, t, near or None), oblast_names=OBL,
                      map_fn=map_fn or (lambda uids: ({"14": ["#07 · drone · heading to Бортничі · @kyiv_airdef 22:10"]}, ["#07"])))


def _post(pid, minutes, text):
    return {"post_id": pid, "channel": pid.split("/")[0], "ts": ago(minutes), "text": text, "tags": ["drones", "geo"]}


ITEMS = [(_post("kyiv_airdef/1531", 8, "Ціль заходить на Бортничі, низько, знижується"), ("31",), "31", True),
         (_post("trevoga_kartaa_noviny/1532", 7, "🚨Повітряна тривога · жовтий рівень🟡\nБучанський р-н\nДронова загроза"), (), None, True),
         (_post("monitor_ukr/1533", 5, "1 реактив над Коростенем\nшвидкість 400 км/год, висота 3 км"), (), None, True),
         (_post("kpszsu/1534", 4, "2 шахеди з півночі на Бровари"), (), None, True),
         (_post("kyiv_airdef/1535", 3, "Мопедик кружляє біля Сомкової Долини, 800"), ("14",), "31", False)]


def _ids(msg):
    """the labels and candidate ids the check gave, by channel and by place name"""
    import re
    labels = {ch + "/" + str(i): lab for i, (lab, ch) in enumerate(re.findall(r"\[(p\d+)\] \S+ @(\S+)", msg))}
    cands = dict((name, cid) for cid, name in re.findall(r"^(c\d+) \| ([^|\n]+?) \|", msg, re.M))
    return labels, cands


# ---- one call for the posts of ten minutes ------------------------------------------------------------------------
def test_one_call_reads_the_posts_grouped_by_oblast_and_keeps_only_what_the_post_bears_out():
    store, seen = server.Store(":memory:"), []
    r = _reader(store)

    def fake(req, timeout=None, context=None):
        body = json.loads(req.data.decode())
        seen.append(body)
        msg = body["messages"][-1]["content"]
        lab, c = _ids(msg)
        p = lambda ch: next(v for k, v in lab.items() if k.startswith(ch))   # noqa: E731
        ans = {"findings": [
            {"post": p("kyiv_airdef"), "finding": "missed", "why": "a tracker's target", "target": A._t(
                place_id=c["Бортничі"], place_quote="на Бортничі", relation="heading_to", vertical="descending",
                vertical_quote="знижується", same_as="#07")},
            {"post": p("trevoga_kartaa_noviny"), "finding": "not_sky", "why": "an alert message", "target": A._t()},
            {"post": p("monitor_ukr"), "finding": "missed", "why": "height", "target": A._t(
                kind="jet_drone", kind_quote="реактив", place_id=c["Коростень"], place_quote="над Коростенем", relation="at",
                altitude_m=3000, altitude_quote="висота 3 км", speed_kmh=900, speed_quote="швидкість 900 км/год")},
            {"post": p("kpszsu"), "finding": "place", "why": "invented", "target": A._t(place_id="c99", place_quote="на Київ")},
            {"post": "p77", "finding": "missed", "why": "no such post", "target": A._t(kind="shahed", kind_quote="шахед")},
            {"post": p("kyiv_airdef/1535") if False else p("kyiv_airdef"), "finding": "weapon", "why": "x", "target": A._t()}],
            "notes": [{"oblast": "o10", "note": "One jet drone over Korosten at 3 km."}, {"oblast": "o99", "note": "not shown"}],
            "uncertain": ""}
        return _answer(json.dumps(A.wire_check(ans), ensure_ascii=False))
    with mock.patch.object(A.urllib.request, "urlopen", fake):
        assert r.check(ITEMS) == 1
    (body,) = seen
    assert body["max_tokens"] == A.MAX_OUT_CHECK and body["response_format"]["json_schema"]["name"] == "heimdall_check"
    assert body["response_format"]["json_schema"]["schema"] == A.CHECK_SCHEMA
    sysm, msg = body["messages"][0]["content"], body["messages"][-1]["content"]
    assert sysm == A.SYSTEM_CHECK and A.RULES_READ in sysm and len(body["messages"]) == 4
    assert "=== OBLAST o31 · м. Київ ===" in msg and "=== OBLAST o10 · Житомирська область ===" in msg
    assert "- #07 · drone · heading to Бортничі · @kyiv_airdef 22:10" in msg
    assert "RULES: set aside — nothing drawn" in msg and "RULES: jet drone · at Коростень · 3000 m · 400 km/h" in msg
    rows = {x["post_id"]: x for x in store.ai_reads(20, diff=False)}
    assert len(rows) == 5 and len({x["chk"] for x in rows.values()}) == 1
    a = rows["kyiv_airdef/1531"]
    # the rules drew it at Bortnychi too: what the AI adds there is facts, not a second target
    assert a["verdict"] == "facts" and a["ai"]["targets"][0]["f"] == "facts" and a["ai"]["targets"][0]["vertical"] == "descending"
    assert rows["trevoga_kartaa_noviny/1532"]["verdict"] == "none" and rows["trevoga_kartaa_noviny/1532"]["dropped"] == 1
    k = rows["monitor_ukr/1533"]["ai"]["targets"][0]
    assert k["altitude_m"] == 3000 and k["speed_kmh"] is None              # 900 km/h is not what the post says
    assert rows["kpszsu/1534"]["verdict"] == "agree"                       # an invented candidate is dropped
    assert rows["kyiv_airdef/1535"]["verdict"] == "none" and rows["kyiv_airdef/1535"]["stored"] == 0
    (ck,) = store.ai_checks(5)
    assert ck["posts"] == 5 and ck["cost"] == 0.0011 and ck["tok_in"] == 9000 and ck["prompt_v"] == A.CHECK_VERSION
    assert ck["notes"] == [{"oblast": "o10", "note": "One jet drone over Korosten at 3 km."}]
    assert ck["findings"] == {"facts": 2, "returned": 6} and set(ck["oblasts"]) >= {"31", "10"}    # 1.53.4: what it gave
    assert store.ai_check_counts(NOW.strftime("%Y-%m"))["checks_month"] == 1


def test_a_failed_check_is_kept_and_its_posts_are_read_at_the_next_one():
    store = server.Store(":memory:")
    r = _reader(store)
    with mock.patch.object(A.urllib.request, "urlopen", lambda *a, **k: _answer('{"findings": [', tout=6000, finish="length")):
        r.check(ITEMS[:2])
    (ck,) = store.ai_checks(5)
    assert ck["error"] == f'cut off at {A.MAX_OUT_CHECK} tokens — began: {{"findings": [' and len(r.q) == 2      # 1.53.4 and not store.ai_reads(5, diff=False)


def test_the_checks_are_stopped():
    # 1.54, the owner chose to stop them: nothing schedules a check, the dashboard has no switch for it; check() is kept
    r = _reader(server.Store(":memory:"))
    assert not hasattr(r, "_tick_check") and not hasattr(r, "check_now") and r.stats()["mode"] == "bulletins"
    assert "ai.check_now()" not in SRC and "\"ai_mode\"" not in SRC and callable(r.check)

def test_the_worked_example_is_borne_out_by_its_own_posts():
    text, ans = A.CHECK_EXAMPLE
    cands = [tuple(x.split(" | ", 1)) for x in text.split("CANDIDATES (id | name | oblast):\n")[1].split("\n\n")[0].split("\n")]
    posts = {}
    for block in text.split("\n[")[1:]:
        lab = block.split("]")[0]
        posts[lab] = block.split("\n", 1)[1].split("\nRULES:")[0]
    for f in ans["findings"]:
        if f["finding"] == "not_sky":
            continue
        cs = [(cid, rest.split(" | ")[0], rest) for cid, rest in cands]
        ts, dropped = A.validate(A.wire({"targets": [f["target"]]}), posts[f["post"]], cs, ("#07", "#04"))
        assert ts and dropped == 0, f
    assert {n["oblast"] for n in ans["notes"]} == {"o14", "o5", "o10"}


def test_a_post_word_from_what_the_check_found():
    assert A.check_verdict([], [{"x": 1}]) == "agree" and A.check_verdict([], []) == "none"
    assert A.check_verdict(["facts", "missed"], []) == "ai_only" and A.check_verdict(["missed"], [{"x": 1}]) == "place"
    assert A.check_verdict(["facts", "not_sky"], [{"x": 1}]) == "rules_only" and A.check_verdict(["weapon"], [{}]) == "kind"


# ---- on the map, never pushed ---------------------------------------------------------------------------------------
def test_what_a_check_found_is_never_drawn():
    # 1.54: what a check found before 1.54 adds nothing to the map (the AI's marks went with its reading)
    assert not hasattr(server.State, "_ai_marks_of") and not hasattr(server.State, "_ai_facts")
    missed = dict(A._t(kind="shahed", relation="at"), place="Українка", toward=None, f="missed")
    facts = dict(A._t(kind="shahed", relation="at", altitude_m=900), place="Обухів", toward=None, f="facts")
    assert A.match([dict(missed)], {"Обухів"}, True) is None and A.match([dict(facts)], {"x"}, True)["f"] == "facts"


# ---- the night, in full, and the AI's report on it ------------------------------------------------------------------
def _night_state():
    st = server.State(server.Store(":memory:"), {})
    night = server.tag_night(ago(30))
    st.store.conn.execute("INSERT INTO targets(night,n,prefix,origin,osrc,oquote,opost,first_ts,last_ts,type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (night, 7, "N", "belarus", "rules", "з Білорусі", "kpszsu/1", ago(90), ago(30), "drones"))
    for i, (pl, mins, alt) in enumerate([("Ріпки", 90, None), ("Чернігів", 70, 1800), ("Козелець", 45, None), ("Вишгород", 30, 1200)]):
        lon, lat, _ = geo.PLACES[pl]
        st.store.conn.execute("INSERT INTO target_points VALUES(?,?,?,?,?,?,?,?)", (f"x/{i}#0", night, 7, ago(mins), lon, lat, pl, alt))
        st.store.conn.execute("INSERT INTO target_reports VALUES(?,?,?,?)", (f"x/{i}#0", night, 7, ago(mins)))
    st.store.conn.commit()
    st.store.ai_check_save({"id": "c1", "at": ago(20), "first": ago(35), "last": ago(25), "posts": 12, "oblasts": ["14"], "cost": 0.0015,
                            "findings": {"missed": 1}, "notes": [{"oblast": "o14", "note": "One Shahed from Belarus down to Vyshhorod."}]})
    return st, night


def test_the_night_in_full_for_any_ai_to_read():
    st, night = _night_state()
    d = st.night_summary(night)
    (t,) = d["targets"]["list"]
    assert t["id"] == "#07" and t["letter"] == "N" and t["origin"] == "belarus" and t["reports"] == 4 and t["minutes"] == 60
    assert [p["place"] for p in t["path"]] == ["Ріпки", "Чернігів", "Козелець", "Вишгород"] and t["path_km"] > 100
    assert t["heights_m"] == [1800, 1200] and d["targets"]["entry_places"] == {"Ріпки": 1}
    assert d["ai"]["checks"] == 1 and d["ai"]["cost_usd"] == 0.0015 and d["ai"]["notes"][0]["note"].startswith("One Shahed")
    txt = server.State.night_text(d)
    assert "#07 drones · origin as a post said: belarus «з Білорусі»" in txt and "Ріпки" in txt and "Вишгород" in txt
    assert "not a count of drones" in txt and "AI CHECKS: 1" in txt
    assert json.dumps(d, ensure_ascii=False)                                  # the download is plain JSON
    an = st._an_ai([night])
    assert an[0]["checks"] == 1 and an[0]["missed"] == 1 and an[0]["posts"] == 12


def test_the_report_is_written_after_the_hour_once_and_on_demand():
    st, night = _night_state()
    rp = server.NightReports(st, {"ai_report_hour": 9})
    k = server.kyiv_tz()
    morning = datetime(2026, 10, 10, 8, 59, tzinfo=k)
    assert rp.due(morning) is None and rp.due(morning + timedelta(minutes=1)) == "2026-10-09"
    asked = []

    class AI:
        def enabled(self):
            return True

        def model(self):
            return "m"

        def ask_text(self, system, text):
            asked.append((system, text))
            return {"out": "1. The night in brief\nOne tag.", "cost": 0.004, "tok_in": 5000, "tok_out": 300, "model": "m"}
    st.ai = AI()
    row = rp.write(night)
    assert row["text"].startswith("1. The night") and st.store.ai_report(night)["cost"] == 0.004
    assert asked[0][0] == A.REPORT_SYSTEM and "#07" in asked[0][1] and "never invent a number" in A.REPORT_SYSTEM
    st.ai = None
    assert "AI reader is off" in rp.write(night)["error"]
    assert night in st.store.ai_report_nights()


def test_the_dashboard_and_the_docs():
    for k in ("v_facts:", "ai_mode_check:", "sw_q_mode_post:", "h_checks:", "f_not_sky:", "an_c_night:", "an_n_json:", "an_c_ai:",
              "an_tg_paths:"):
        assert ADMIN.count(k) == 2, k
    assert "${nightCard(A)}" in ADMIN and "card('c14',tr('an_c_ai')" in ADMIN and "fileDownload(`heimdall-night-${NIGHT.night}.json`" in ADMIN
    assert 'u.path == "/api/admin/night"' in SRC and 'u.path == "/api/admin/ai_report"' in SRC
    assert "### 7.10 The 10-minute check (1.53; stopped in 1.54) and the night's report" in DOC and "### 7.11 The bulletins (1.54)" in DOC
    assert "## The AI reads every 10 minutes and writes up the night (1.53)" in SAFETY


# ---- what the owner showed on the night of 9 October ------------------------------------------------------------------
def test_a_namesake_is_never_a_second_target():
    text = "З Козина на Ходосівку"
    cands = A.candidates(geo, text, "chyste_nebo", None, ["14", "25"], OBL)
    far = next(c for c in cands if "Прилуцький" in c[1])
    to = next(c for c in cands if c[1] == "Ходосівка")
    ts, _ = A.validate(A.wire({"targets": [A._t(place_id=far[0], place_quote="З Козина", relation="from", toward_id=to[0],
                                                toward_quote="на Ходосівку")]}), text, cands)
    marks = geo.parse_for_channel("chyste_nebo", text, ["14", "25"])
    A.pick_namesakes(ts, cands, geo, A.anchors_of(geo, marks, None, "chyste_nebo"))
    assert ts[0]["place"] == "Козин" and ts[0]["toward"] == "Ходосівка"      # the one by Kyiv, beside Khodosivka


def test_an_alert_said_to_be_coming_is_not_where_the_target_is():
    rd = lambda t: [(m["place"], m.get("target")) for m in geo.parse_for_channel("eRadarrua", t)]   # noqa: E731
    assert rd("🛵 Буде тривога в столиці. БпЛА на Козин") == [("→ Козин", "Козин")]
    assert rd("Тривога в столиці через шахед на Бровари") == [("→ Бровари", "Бровари")]
    assert rd("Шахед над столицею") == [("Столиця", None)]                   # over the capital is still over it


def test_a_tag_holds_under_a_target():
    tt = server.TargetTags(server.Store(":memory:"))
    a = tt.assign({"id": "x/1#0", "ts": ago(30), "reports": ["x/1#0"]})                    # N-1, shown
    tt.show("x/1#0", a)
    b = tt.assign({"id": "y/1#0", "ts": ago(20), "reports": ["y/1#0"]})                    # another, N-2, shown
    tt.show("y/1#0", b)
    # the chains recomputed: one track now holds both — it keeps the number its latest shown report had
    assert tt.assign({"id": "z/1#0", "ts": ago(5), "reports": ["x/1#0", "y/1#0", "z/1#0"]}) == b
    # another channel's word for the same target at the same moment: the same number, both shown
    st = server.State(server.Store(":memory:"), {})
    lon, lat, _ = geo.PLACES["Бровари"]
    o = {"id": "kpszsu/1538#0", "ts": ago(4), "type": "drones", "lon": lon, "lat": lat, "history": []}
    n = {"id": "monitor_ukr/1539#0", "ts": ago(2), "type": "drones", "lon": lon + 0.03, "lat": lat, "history": []}
    far = dict(n, id="monitor_ukr/1540#0", lon=lon + 0.5)
    assert st._twin(n, [(o, ("2026-10-09", 4))]) == ("2026-10-09", 4) and st._twin(far, [(o, ("2026-10-09", 4))]) is None
    k1 = st.tags.assign(o)
    k2 = st.tags.assign(n, {k1}, twin=k1)
    assert k1 == k2 and st.tags.assign(n, {k1}) == k1                                       # and it holds next time


def test_the_map_on_the_whole_screen():
    page, i18n = _read("static/kyiv.html"), _read("static/i18n.js")
    assert '<button id="fsbtn" type="button" data-t-title="m_full"' in page and "$('fsbtn').onclick=()=>setFull(!FULL);" in page
    assert "body.fullmap #top,body.fullmap #drawer" in page and "el.requestFullscreen({navigationUI:'hide'})" in page
    assert '<div id="fmchip" role="button"' in page and "if(!document.fullscreenElement&&FULL) setFull(false);" in page
    assert i18n.count("m_full:'") == 3 and i18n.count("m_full_exit:'") == 3


def test_nothing_is_written_over_a_target():
    page = _read("static/kyiv.html")
    assert "if(drawn(dn)){ const w=dn.textContent.length*6.4+12; glyphs.push({x:p.sx-w/2,y:p.sy+4,w,h:17,p}); }" in page   # 1.54.6: the pill
    # 1.54: the explosions layer is gone, and with it the explosions' names giving way
    assert "querySelectorAll('#impactsg .imp')" not in page
    assert "bx=placed.concat(glyphs.filter(q=>q.p))" in page


def test_a_short_card_and_a_map_that_opens_at_once():
    page, i18n, sw = _read("static/kyiv.html"), _read("static/i18n.js"), _read("static/sw.js")
    assert ".sheet.mark:not(.more){max-height:38vh;max-height:38dvh}" in page and ".sheet.mark:not(.more) .sec{display:none}" in page
    assert '<button class="shmore" type="button" id="shmore">' in page and "$('sheet').classList.remove('more');" in page
    assert i18n.count("sh_more:'") == 3 and i18n.count("sh_less:'") == 3
    assert '<div class="kv1 tagl">' in page and "kv1 tgl" not in page      # the tag line is no 44 px button box
    # the satellite tiles cache-first, the map's drawing at once then refreshed; the data never
    assert "if (u.pathname.startsWith('/tiles/sat/')) { e.respondWith(tile(e.request)" in sw and "const TILES_MAX = 5000;" in sw
    assert "/api/" not in sw.split("const FAST")[1].split("self.addEventListener('push'")[0].replace("(/api/…)", "")
    assert "sw.postMessage({warm:urls}); localStorage.setItem('satwarm2',SAT_V);" in page and "c.saveData" in page


# ---- 1.53.1 ----------------------------------------------------------------------------------------------------------
def test_a_check_cut_off_keeps_what_came_complete():
    full = json.dumps(A.wire_check(A.CHECK_EXAMPLE[1]), ensure_ascii=False)
    assert list(json.loads(full)) == ["notes", "findings", "uncertain"]          # the notes first: a cut spares them
    part = A.salvage_check(full[:int(len(full) * 0.7)])
    assert len(part["notes"]) == 3 and 0 < len(part["findings"]) < len(A.CHECK_EXAMPLE[1]["findings"])
    assert A.salvage_check('{"notes": [') is None and A.MAX_CHECK_POSTS == 30 and A.MAX_OUT_CHECK == 12000
    store = server.Store(":memory:")
    r = _reader(store)
    with mock.patch.object(A.urllib.request, "urlopen", lambda *a, **k: _answer(full[:int(len(full) * 0.7)], tout=12000, finish="length")):
        r.check(ITEMS[:2])
    (ck,) = store.ai_checks(5)
    assert ck["error"] is None and ck["uncertain"].startswith("answer cut off at 12000 tokens") and not r.q
    assert r.last_error is None


# ---- 1.53.2 ----------------------------------------------------------------------------------------------------------
def test_a_tag_is_its_number_and_no_direction_is_shown():
    page, replay = _read("static/kyiv.html"), _read("static/replay.js")
    assert server.tag_id(82) == "#82" and server.tag_id(7) == "#07"
    st = server.State(server.Store(":memory:"), {})
    tg = server.Telegram(st, {})
    tg.ingest("kpszsu", [("kpszsu/15321", ago(3), "Шахед з Брянщини на Чернігів"), ("kpszsu/15322", ago(2), "Шахед над Козельцем")], "tg:k")
    tags = [m["tag"] for m in st.markers() if m.get("tag")]
    assert tags and all(t["id"].startswith("#") and t["id"][1:].isdigit() for t in tags)
    assert "tagOrigin" not in page and "t('tg_num')" in page and "tr.tg" in replay


def test_no_arrows_along_the_edge_of_the_map():
    page = _read("static/kyiv.html")
    assert "edges.push(" not in page and "class=\"edge " not in page and ".edge .arrow" not in page
    assert "if($('edges').innerHTML) $('edges').innerHTML='';" in page


# ---- 1.53.4: what the first real checks showed (9 Oct, 18:40–19:41) ---------------------------------------------------
def test_a_finding_is_flat_and_short():
    assert len(A.FIND["required"]) == 18 and "origin" not in A.FIND["properties"] and "speed_kmh" not in A.FIND["properties"]
    assert A.CHECK_SCHEMA["properties"]["findings"]["items"] is A.FIND
    f = A.wire_check(A.CHECK_EXAMPLE[1])["findings"][0]
    assert "target" not in f and f["place_id"] == "c1" and A.find_target(f)["same_as"] == ""
    (t,), _ = A.validate({"targets": [A.find_target(f)]}, "Ціль заходить на Бортничі, низько, знижується",
                         [("c1", "Бортничі", "Бортничі | м. Київ")])
    assert t["place"] == "Бортничі" and t["vertical"] == "descending"


def test_the_rules_errors_the_first_checks_found():
    rd = lambda ch, t, near=None: [m["place"] for m in geo.parse_for_channel(ch, t, near)]   # noqa: E731
    assert rd("chyste_nebo", "На Лозовик") == ["→ Лозовик"]             # Lozovyk by Kyiv is not Lozova in Kharkiv oblast
    assert geo.PLACES["Лозовик"][2] == "14"                              # 1.54.7: the Kyiv oblast village, now known
    assert rd("kyiv_airdef", "Шахед над Лозовою") == ["Лозова"] and rd("kyiv_airdef", "Шахед над Оболонню") == ["Оболонь"]
    assert rd("kyiv_airdef", "Ціль на Бориспіль") == ["→ Бориспіль"] and rd("kyiv_airdef", "Шахед над Броварами") == ["Бровари"]
    with mock.patch.dict(geo.CHANNEL_HOME, {"trevoga_kartaa_noviny": "10"}):
        assert rd("trevoga_kartaa_noviny", "🟢 Відбій повітряної тривоги\n• Коростенський р-н\n• Житомирський р-н", ["10"]) == []
