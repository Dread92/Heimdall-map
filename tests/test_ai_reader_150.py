"""1.50: the AI reader, in shadow mode — a language model (OpenRouter) reads the channels' posts beside the rules.

Nothing it says reaches the map, the alerts, the feed or a push: it is a second opinion for the dashboard, to find what
the rules misread or miss. What these tests pin: the prompt holds SAFETY.md's rules; every fact the model gives must
quote the post and every place must be one this server offered; the two readings are compared fairly (a side of a town
the rules mark as its oblast, Kyiv named alone as the city); only public post text leaves the server, never a reader's
anything, and never a card number; the month's budget, the hourly limit and OpenRouter's refusals stop it; and the
ingest path hands it the posts of the channels on the map, never one on trial, without waiting on it.
"""
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import ai_reader as A
import geo
import server

ADM = {"X-Admin-Key": "adm-test"}   # 1.58.21: the dashboard key in a header — never in the address

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


SRC, SERVER, ADMIN, DOC = _read("app/ai_reader.py"), _read("app/server.py"), _read("static/admin.html"), _read("docs/TECHNICAL.md")
OBL = {u: uk for u, uk, _ in server.OBLASTS}


def _ans(**kw):
    return A._t(**kw)


# ---- the prompt ----------------------------------------------------------------------------------------------------
def test_the_prompt_carries_the_safety_rules():
    for rule in ("Never infer.", "Quote.", "Places only from CANDIDATES", "Never output coordinates",
                 "Banderol is a jet drone, never a cruise missile", "— the target is NOT at X",
                 "is the city itself", "PREVIOUS POSTS are context only", "targets []"):
        assert rule in A.SYSTEM, rule


def test_the_schema_is_strict_and_every_field_is_required():
    assert A.SCHEMA["additionalProperties"] is False and A.TARGET["additionalProperties"] is False
    assert set(A.TARGET["required"]) == set(A.TARGET["properties"]) and set(A.SCHEMA["required"]) == {"targets", "uncertain"}
    assert A.TARGET["properties"]["kind"]["enum"] == A.KINDS
    assert not {"lat", "lon", "latitude", "longitude", "coordinates", "eta", "trajectory"} & set(A.TARGET["properties"])   # never a position or an ETA of its own


def test_the_examples_are_right_by_the_validators_own_measure():
    """Each worked example gives only what its post states: the validator keeps every fact of it."""
    for ch, prev, post, cands, parser, on_map, ans in A.EXAMPLES:
        cs = [(line.split(" | ")[0], line.split(" | ")[0], line) for line in cands.split("\n")]
        kept, dropped = A.validate(ans, post, cs, [x.split(" · ")[0] for x in on_map])
        assert dropped == 0 and len(kept) == len(ans["targets"]), post
        for t in ans["targets"]:
            assert set(t) == set(A.TARGET["properties"])


def test_the_fixed_part_comes_first_and_is_marked_for_caching():
    m = A.messages(A.channel_block("x"), ["[21:00] Шахед на Бровари"], "Далі на Требухів", "c1 | Требухів | Київська область")
    assert m[0] == {"role": "system", "content": A.SYSTEM} and len(m) == 2 + 2 * len(A.EXAMPLES)
    assert m[-1]["role"] == "user" and "POST:\nДалі на Требухів" in m[-1]["content"] and "- [21:00] Шахед на Бровари" in m[-1]["content"]
    assert all(isinstance(x["content"], str) for x in m)
    c = A.messages(A.channel_block("x"), [], "Шахед", "", cache=True)
    assert c[-2]["content"][0]["cache_control"] == {"type": "ephemeral"} and c[-1]["content"].endswith("(none)")


# ---- the places offered ----------------------------------------------------------------------------------------------
def test_the_candidates_are_the_gazetteers_places_the_post_names_and_their_oblasts():
    cs = A.candidates(geo, "БпЛА на Сумщині курсом на Ромни", "kpszsu", None, (), OBL)
    assert ("c1", "Ромни", "Ромни | Сумська область") in cs and ("o20", "o20", "Сумська область") in cs
    cs = A.candidates(geo, "Збито ціль над Оболонню", "kyiv_airdef", "31", (), OBL)
    assert cs[0][1] == "Оболонь" and ("o31", "o31", "м. Київ") in cs
    assert len(A.candidates(geo, " ".join(["Бровари Бориспіль Ірпінь Буча Вишгород Обухів Фастів"] * 10), "kpszsu", "14", (), OBL)) <= A.MAX_CANDIDATES + 3


# ---- what the model says is checked against the post ----------------------------------------------------------------
CANDS = [("c1", "Бровари", "Бровари | Київська область"), ("o14", "o14", "Київська область")]


def test_a_fact_the_post_does_not_bear_out_is_dropped():
    post = "2 шахеди з півночі на Бровари"
    out = {"targets": [_ans(kind="shahed", kind_quote="шахеди", count=3, count_quote="3 шахеди", place_id="c9",
                            place_quote="на Бровари", relation="heading_to", heading="w", heading_quote="на захід",
                            altitude_m=2000, altitude_quote="висота 2000", status="impact", status_quote="вибух",
                            origin="n", origin_quote="з півночі")], "uncertain": None}
    kept, dropped = A.validate(out, post, CANDS)
    assert dropped == 5
    t = kept[0]          # the weapon and the side it came from are left: the post says them
    assert (t["kind"], t["count"], t["place_id"], t["relation"], t["heading"], t["altitude_m"], t["status"]) == \
        ("shahed", None, None, "none", None, None, "in_flight")
    assert t["origin"] == "n" and t["place"] is None
    out["targets"][0].update(kind="ballistic_missile", kind_quote="балістика")
    assert A.validate(out, post, CANDS) == ([], 7)          # nothing of it left but a side: not a target


def test_a_target_with_nothing_left_is_not_kept():
    kept, dropped = A.validate({"targets": [_ans(kind="shahed", kind_quote="шахед", place_id="c1", place_quote="на Бровари")]},
                               "Ціль на Київщину", CANDS)
    assert kept == [] and dropped == 3


def test_what_the_post_states_is_kept_and_the_place_named_by_its_key():
    post = "Бандерол за 15 км на північ від Броварів, висота 1,5 км. Мінус!"
    out = {"targets": [_ans(kind="jet_drone", kind_quote="Бандерол", place_id="c1", place_quote="на північ від Броварів",
                            relation="side_of", side="n", distance_km=15, altitude_m=1500, altitude_quote="висота 1,5 км",
                            status="shot_down", status_quote="Мінус")], "uncertain": None}
    (t,), dropped = A.validate(out, post, CANDS)
    assert dropped == 0 and t["place"] == "Бровари" and t["side"] == "n" and t["distance_km"] == 15 and t["altitude_m"] == 1500
    # a distance that is not written is dropped; a side only for side_of
    out["targets"][0].update(distance_km=20)
    assert A.validate(out, post, CANDS)[0][0]["distance_km"] is None
    out["targets"][0].update(relation="at", distance_km=None)
    assert A.validate(out, post, CANDS)[0][0]["side"] is None


def test_a_count_needs_a_number_in_its_words():
    out = {"targets": [_ans(kind="shahed", kind_quote="шахедів", count=5, count_quote="кілька шахедів")]}
    assert A.validate(out, "Кілька шахедів на Київщину", CANDS)[0][0]["count"] is None
    out = {"targets": [_ans(kind="shahed", kind_quote="шахеди", count=2, count_quote="Два шахеди")]}
    assert A.validate(out, "Два шахеди на Київщину", CANDS)[0][0]["count"] == 2


def test_a_card_number_never_leaves_the_server():
    t = "Збір на дрони: 4441 1144 2233 4455, Моно 5375-4112-0000-1234. Шахед на Бровари о 21:02, висота 2200, 2 шахеди"
    m = A.mask(t)
    assert "4441" not in m and "5375" not in m and m.count("[…]") == 2
    assert "21:02" in m and "висота 2200" in m and "2 шахеди" in m


# ---- the two readings side by side ----------------------------------------------------------------------------------
def _cmp(ch, text, out, cands):
    kept, _ = A.validate(out, text, cands)
    return A.compare(A.summarise_rules(geo.parse_for_channel(ch, text)), A.summarise_ai(kept, geo.PLACES))


def test_the_same_reading_agrees():
    assert _cmp("kpszsu", "2 шахеди з півночі на Бровари", {"targets": [_ans(
        kind="shahed", kind_quote="шахеди", place_id="c1", place_quote="на Бровари", relation="heading_to")]}, CANDS) == "agree"


def test_a_side_of_an_oblast_capital_agrees_with_the_rules_oblast():
    cands = A.candidates(geo, "БпЛА на півночі від Миколаєва, курс на захід.", "kpszsu", None, (), OBL)
    assert _cmp("kpszsu", "БпЛА на півночі від Миколаєва, курс на захід.", {"targets": [_ans(
        kind="drone", kind_quote="БпЛА", place_id="c1", place_quote="на півночі від Миколаєва", relation="side_of", side="n",
        heading="w", heading_quote="курс на захід")]}, cands) == "agree"


def test_kyiv_named_alone_is_the_city_to_both():
    cands = A.candidates(geo, "Шахед над Києвом", "kpszsu", None, (), OBL)
    assert _cmp("kpszsu", "Шахед над Києвом", {"targets": [_ans(
        kind="shahed", kind_quote="Шахед", place_id="c1", place_quote="над Києвом", relation="at")]}, cands) == "agree"


def test_a_jet_drone_is_the_rules_banderol_or_drone():
    cands = A.candidates(geo, "Бандерол на Бровари", "kpszsu", None, (), OBL)
    assert _cmp("kpszsu", "Бандерол на Бровари", {"targets": [_ans(
        kind="jet_drone", kind_quote="Бандерол", place_id="c1", place_quote="на Бровари", relation="heading_to")]}, cands) == "agree"
    assert _cmp("kpszsu", "Бандерол на Бровари", {"targets": [_ans(
        kind="cruise_missile", kind_quote="Бандерол", place_id="c1", place_quote="на Бровари", relation="heading_to")]}, cands) == "kind"


def test_the_disagreements():
    r = [{"where": "Бровари", "type": "drones", "status": None, "approach": True}]
    a = [{"where": "Бориспіль", "kind": "shahed", "status": None, "approach": True, "relation": "heading_to", "alt": None}]
    assert A.compare(r, a) == "place"
    assert A.compare(r, [dict(a[0], where="Бровари", status="down")]) == "status"
    assert A.compare(r, []) == "rules_only" and A.compare([], a) == "ai_only" and A.compare([], []) == "none"
    assert A.compare(r, [dict(a[0], where="Бровари", kind="unknown")]) == "agree"      # a weapon left unsaid
    assert A.compare([dict(r[0], type="unknown")], [dict(a[0], where="Бровари")]) == "agree"


# ---- the reader: what it sends, what it spends, when it stops --------------------------------------------------------
class _Store:
    def __init__(self):
        self.kv, self.saved = {}, []

    def kv_get(self, k):
        return self.kv.get(k)

    def kv_set(self, k, v):
        self.kv[k] = v

    def ai_save(self, r):
        self.saved.append(r)

    def ai_counts(self, month):
        return {"reads_month": len(self.saved)}


class _Resp:
    def __init__(self, data):
        self.body = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def _ok(out, cost=0.0004):
    return _Resp({"model": "anthropic/claude-haiku-5.5", "choices": [{"message": {"content": json.dumps(A.wire(out), ensure_ascii=False)}}],
                  "usage": {"prompt_tokens": 2400, "completion_tokens": 120, "cost": cost}})


def _reader(**cfg):
    cfg = {"openrouter_key": "sk-or-test-0000", **cfg}
    return A.AIReader(cfg, _Store(), geo, rules_fn=lambda ch, t, near: geo.parse_for_channel(ch, t, near or None),
                      oblast_names=OBL, previous_fn=lambda ch, ts: ["[20:58] Шахед на Бровари"], log=lambda *a: None)


POST = {"post_id": "kpszsu/1", "channel": "kpszsu", "ts": "2026-10-09T18:00:00+00:00", "text": "2 шахеди з півночі на Бровари",
        "tags": ["drones", "kyiv", "geo"], "text_en": "TRANSLATION-NOT-SENT", "home": "READER-HOME-NOT-SENT"}
GOOD = {"targets": [_ans(kind="shahed", kind_quote="шахеди", count=2, count_quote="2 шахеди", place_id="c1",
                         place_quote="на Бровари", relation="heading_to", origin="n", origin_quote="з півночі")], "uncertain": None}


def test_it_is_on_only_with_a_key_a_cap_and_not_switched_off():
    assert _reader().enabled() and not _reader(openrouter_key="").enabled()
    assert not _reader(ai_reader_monthly_usd=0).enabled() and not _reader(ai_reader=False).enabled()
    assert not _reader(ai_reader_monthly_usd="lots").enabled()
    assert _reader().model() == A.DEFAULT_MODEL == server.DEFAULT_CONFIG["ai_reader_model"]
    assert server.DEFAULT_CONFIG["ai_reader_monthly_usd"] == 10 and server.DEFAULT_CONFIG["openrouter_key"] == ""


def test_one_request_with_the_post_and_nothing_about_anybody():
    r, seen = _reader(), []

    def fake(req, timeout=None, context=None):
        seen.append(req)
        return _ok(GOOD)
    with mock.patch.object(A.urllib.request, "urlopen", fake):
        assert r.read(POST, ("14",), "") == "agree"
    (req,) = seen
    assert req.full_url == A.OPENROUTER_URL == "https://openrouter.ai/api/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer sk-or-test-0000"
    body = json.loads(req.data.decode())
    assert body["model"] == "anthropic/claude-haiku-5.5" and body["max_tokens"] == A.MAX_OUT == 2400   # 1.52.1: 1200 cut answers off
    # 1.50.1: nothing the model may not take — with require_parameters, a `temperature` claude-haiku-5.5 does not take
    # left OpenRouter no provider at all ("HTTP 404: No endpoints found that can handle the requested parameters")
    assert set(body) == {"model", "max_tokens", "messages", "response_format", "provider", "usage"}
    assert body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == A.SCHEMA
    assert body["provider"] == {"require_parameters": True} and body["usage"] == {"include": True}
    sent = json.dumps(body, ensure_ascii=False)
    assert "TRANSLATION-NOT-SENT" not in sent and "READER-HOME-NOT-SENT" not in sent and "kpszsu/1" not in sent
    last = body["messages"][-1]["content"]
    assert last.startswith("CHANNEL: @kpszsu\nCHANNEL'S OBLAST: none — a country-wide channel\nOBLASTS ITS LAST POSTS NAMED (30 min): Київська область")
    assert "c1 | Бровари | Київська область" in last and "o14 | Київська область" in last
    assert "PARSER READING (Heimdall's rules, for this post — may be wrong or incomplete):\n- drone ×2 · heading to Бровари · from n" in last
    assert "[20:58] Шахед на Бровари" in last
    (row,) = r.store.saved
    assert row["verdict"] == "agree" and row["post_id"] == "kpszsu/1" and row["cost"] == 0.0004 and row["prompt_v"] == A.PROMPT_VERSION
    assert row["ai"]["targets"][0]["place"] == "Бровари" and row["rules"][0]["where"] == "Бровари" and row["stored"] == 1
    assert r.spent == 0.0004 and r.store.kv[f"ai_usd:{r.month}"] == "0.000400"


def test_the_budget_stops_it_and_counts_from_what_was_spent():
    r = _reader(ai_reader_monthly_usd=1)
    r.store.kv[f"ai_usd:{datetime.now(timezone.utc):%Y-%m}"] = "1.0001"
    with mock.patch.object(A.urllib.request, "urlopen", side_effect=AssertionError("called past the cap")):
        assert r.read(POST) == "budget"
    assert r.stats()["usd_month"] == 1.0001 and r.stats()["cap_usd"] == 1.0


def test_the_hourly_limit():
    r = _reader()
    r.hour, r.n_hour = int(time.time() // 3600), A.PER_HOUR
    with mock.patch.object(A.urllib.request, "urlopen", side_effect=AssertionError("called past the limit")):
        assert r.read(POST) == "rate"


def _http(code, msg):
    return urllib.error.HTTPError(A.OPENROUTER_URL, code, "x", {}, io.BytesIO(json.dumps({"error": {"message": msg}}).encode()))


def test_a_refused_key_or_no_credit_pauses_it_and_is_shown():
    for code, pause in ((401, 600), (402, 600), (404, 600), (429, 60)):
        r = _reader()
        with mock.patch.object(A.urllib.request, "urlopen", side_effect=_http(code, "No credits")):
            assert r.read(POST) == "error"
        assert pause - 5 < r.down_until - time.time() <= pause and r.last_error == f"HTTP {code}: No credits"
        assert r.store.saved[-1]["verdict"] == "error" and r.store.saved[-1]["error"].startswith(f"HTTP {code}")
        with mock.patch.object(A.urllib.request, "urlopen", side_effect=AssertionError("called while paused")):
            assert r.read(POST) == "paused"
        assert r.stats()["paused"] is True


def test_an_answer_that_is_not_json_is_an_error_but_still_costs():
    r = _reader()
    bad = _Resp({"choices": [{"message": {"content": "Sure! Here is the JSON"}}], "usage": {"cost": 0.001}})
    with mock.patch.object(A.urllib.request, "urlopen", return_value=bad):
        assert r.read(POST) == "error"
    assert r.spent == 0.001 and r.store.saved[-1]["error"] == "not JSON"


def test_nothing_feeds_it_posts_any_more():
    # 1.54, the owner: "the AI placing things on the map — we forget it". No queue is fed: the reading of posts is kept
    # (read, check) but nothing calls it
    r = _reader()
    assert not hasattr(r, "add") and not hasattr(r, "run") and not hasattr(r, "mode")
    assert "def _to_ai(" not in SERVER and "ai.add(" not in SERVER and ".check_now()" not in SERVER


def test_it_reaches_nothing_but_openrouter_and_its_own_table():
    assert re.findall(r"https?://[^\s\"')]+", SRC) == ["https://openrouter.ai/api/v1/chat/completions"]
    for word in ("publish(", "push", ".state", "markers", "add_feed"):
        assert word not in SRC.split('"""', 2)[2], word


# ---- the store ------------------------------------------------------------------------------------------------------
def test_the_store_keeps_the_readings_for_ninety_days():
    st = server.Store(":memory:")
    old = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    st.ai_save({"post_id": "a/1", "at": old, "ts": old, "channel": "a", "text": "x", "verdict": "agree"})
    assert st.ai_reads(10, diff=False) == []                                # the first save prunes
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    for i, v in enumerate(("agree", "place", "ai_only", "none", "error")):
        st.ai_save({"post_id": f"a/{i + 2}", "ts": now(), "channel": "a", "text": "Шахед", "verdict": v, "cost": 0.001, "ms": 1000 + i,
                    "rules": [{"where": "Бровари"}], "ai": {"targets": [], "uncertain": None} if v != "error" else None,
                    "error": "HTTP 500" if v == "error" else None})
    diff = st.ai_reads(10)
    assert {r["verdict"] for r in diff} == {"place", "ai_only", "error"} and len(st.ai_reads(10, diff=False)) == 5
    assert diff[0]["rules"] == [{"where": "Бровари"}] and isinstance(diff[0]["ai"], (dict, type(None)))
    c = st.ai_counts(month)
    assert c["reads_month"] == 5 and c["by_verdict"]["place"] == 1 and c["usd_rows_month"] == 0.005 and c["ms_median"] == 1002


def now():
    return datetime.now(timezone.utc).isoformat()


def test_the_previous_posts_are_the_channels_last_ones_before_it():
    st = server.Store(":memory:")
    t0 = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
    st.add_feed([{"post_id": f"k/{i}", "channel": "k", "ts": (t0 + timedelta(minutes=m)).isoformat(), "text": f"пост {i}",
                  "tags": ["drones"], "text_en": "", "en_fallback": True} for i, m in enumerate((-60, -30, -20, -10, -5, 0, 5))])
    st.add_feed([{"post_id": "o/1", "channel": "other", "ts": (t0 - timedelta(minutes=1)).isoformat(), "text": "інший",
                  "tags": [], "text_en": "", "en_fallback": True}])
    assert st.ai_previous("k", t0.isoformat()) == ["[20:40] пост 2", "[20:50] пост 3", "[20:55] пост 4"]
    st.add_feed([{"post_id": "m/1", "channel": "m", "ts": (t0 - timedelta(minutes=2)).isoformat(), "text": "🛵 Житомирщина\n- 1 повз Овруч\n\n🛵 Київщина",
                  "tags": ["drones"], "text_en": "", "en_fallback": True}])
    assert st.ai_previous("m", t0.isoformat()) == ["[20:58] 🛵 Житомирщина / - 1 повз Овруч / 🛵 Київщина"]


# ---- the server: the posts handed to it, the dashboard's view of it -------------------------------------------------
def test_ingest_never_hands_the_ai_a_post():
    st = server.State(server.Store(":memory:"), {})
    st.ai = mock.Mock(side_effect=AssertionError("the AI was called"))
    tg = server.Telegram(st, {})
    ts = "2026-10-09T18:00:00+00:00"
    tg.ingest("kyiv_airdef", [("kyiv_airdef/1", ts, "Шахед на Бровари")], "tg:kyiv_airdef")
    tg.ingest("kpszsu", [("kpszsu/2", ts, "Ціль на Бровари")], "tg:kpszsu")
    assert st.store.has_post("kyiv_airdef/1") and not st.ai.method_calls


def test_the_route_is_the_dashboards_alone():
    st = server.State(server.Store(":memory:"), {})
    st.ai = _reader()
    st.store.ai_save({"post_id": "a/1", "ts": now(), "channel": "kpszsu", "text": "Ціль на Бровари", "stored": 0,
                      "verdict": "ai_only", "rules": [], "ai": {"targets": [], "uncertain": None}})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/ai_reads"
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            try:
                urllib.request.urlopen(base, timeout=10)
                raise AssertionError("open without the key")
            except urllib.error.HTTPError as e:
                assert e.code == 403
            d = json.loads(urllib.request.urlopen(urllib.request.Request(base + "?limit=x", headers=ADM), timeout=10).read())
    finally:
        srv.shutdown()
        server.Handler.state = old
    assert d["stats"]["enabled"] is True and d["stats"]["key"] is True and "sk-or" not in json.dumps(d)
    assert d["reads"][0]["verdict"] == "ai_only" and d["reads"][0]["stored"] == 0
    assert st.health()["ai_reader"]["model"] == A.DEFAULT_MODEL


def test_the_server_wiring():
    i = SERVER.index("def load_config(")
    assert '("OPENROUTER_API_KEY", "openrouter_key")' in SERVER[i:SERVER.index("return cfg", i)]
    i = SERVER.index("def main(")
    body = SERVER[i:]
    # 1.54: the AI is no thread of its own any more — the bulletins' thread and the night's reports ask it
    assert "state.ai = ai_reader.AIReader(cfg, store, log=log)" in body and "state.ai.ssl_ctx = _SSL_CTX" in body
    assert "state.ai.start()" not in body and "state.bulletins = Bulletins(state, cfg)" in body and "state.bulletins.start()" in body


def test_the_key_is_set_by_the_owner_through_fly_secrets():
    bat = open(os.path.join(ROOT, "scripts", "set-openrouter-key.bat"), "rb").read()
    assert b"\r\n" in bat and b"echo OPENROUTER_API_KEY=%KEY%| fly secrets import" in bat and b'set "KEY="' in bat


def test_the_dashboard_tab():
    assert '<button data-tab="ai" role="tab" data-tr="tab_ai">AI reader</button>' in ADMIN
    assert '<section class="tabsec" id="tab-ai" hidden><div id="aiv"></div></section>' in ADMIN
    assert "fetch('/api/ai_reads?limit=100&all='+(AI_ALL?1:0)+KEYQ)" in ADMIN and "if(t==='ai'){ loadAI(); loadPer(); }" in ADMIN
    # 1.52 drew a target only it found; 1.53: never pushed
    for s in ("<b>It never moves or removes a target, never touches the alerts, and never sends a push.</b>",
              "<b>Вона ніколи не переміщує й не прибирає ціль, не впливає на тривоги й не надсилає сповіщень.</b>"):
        assert s in ADMIN
    for v in A.STATUSES[1:]:
        assert ("st_" + {"shot_down": "down"}.get(v, v) + ":") in ADMIN
    for k in A.KINDS:
        assert ADMIN.count(f"k_{k}:") == 2, k
    for r in A.RELATIONS:
        assert len(re.findall(rf"[,{{\s]r_{r}:", ADMIN)) == 2, r


def test_the_documentation():
    assert "### 7.7 The AI reader (1.50; its facts in the target tags since 1.51; retired from the map in 1.54)" in DOC and "`OPENROUTER_API_KEY`" in DOC
    assert "set-openrouter-key.bat" in DOC and "ai_reader.py" in DOC


# ---- 1.50.2: "HTTP 400: Provider returned error" -----------------------------------------------------------------------
def test_no_field_is_nullable_on_the_wire():
    """Anthropic's structured outputs take at most 16 nullable ("union type") fields in a schema; 15 of ours, and a
    grammar they could not compile, came back as "HTTP 400: Provider returned error" for every post. Nothing on the
    wire is nullable now: "" / 0 / "none" say "not stated"."""
    txt = json.dumps(A.SCHEMA)
    assert "null" not in txt and '"type": [' not in txt and "anyOf" not in txt
    w = A.wire({"targets": [_ans(kind="shahed", kind_quote="шахед")], "uncertain": None})
    t = w["targets"][0]
    assert w["uncertain"] == "" and t["count"] == 0 and t["place_id"] == "" and t["origin"] == "none" and t["side"] == "none"
    assert A.unwire(t)["count"] is None and A.unwire(t)["origin"] is None and A.unwire(t)["kind"] == "shahed"
    for _, _, post, cands, _, _, ans in A.EXAMPLES:      # what the model is shown is what it is asked for
        for tt in A.wire(ans)["targets"]:
            assert set(tt) == set(A.TARGET["properties"]) and None not in tt.values()


def test_a_wire_answer_is_read_like_any_other():
    post = "Група шахедів з території Білорусі на Бровари, швидкість 180 км/год"
    out = {"targets": [{**A.wire({"targets": [_ans()]})["targets"][0], "kind": "shahed", "kind_quote": "шахедів",
                        "place_id": "c1", "place_quote": "на Бровари", "relation": "heading_to", "origin": "belarus",
                        "origin_quote": "з території Білорусі", "speed_kmh": 180, "speed_quote": "швидкість 180 км/год"}],
           "uncertain": ""}
    (t,), dropped = A.validate(out, post, CANDS)
    assert dropped == 0 and t["origin"] == "belarus" and t["speed_kmh"] == 180 and t["count"] is None and t["place"] == "Бровари"


def test_an_origin_must_be_a_direction_or_a_country_in_the_posts_words():
    def origin(o, q, post):
        return A.validate({"targets": [_ans(kind="shahed", kind_quote="шахед", origin=o, origin_quote=q)]}, post, [])[0][0]["origin"]
    assert origin("belarus", "з території Білорусі", "шахед з території Білорусі") == "belarus"
    assert origin("russia", "з Брянщини", "шахед з Брянщини") == "russia"
    assert origin("s", "з півдня", "шахед з півдня") == "s"
    assert origin("sea", "з моря", "шахед з моря") == "sea"
    assert origin("n", "з Чернігівщини", "шахед з Чернігівщини") is None        # a Ukrainian oblast: relation from
    assert origin("russia", "з Чернігівщини", "шахед з Чернігівщини") is None
    assert origin("belarus", "з Білорусі", "шахед на Бровари") is None          # not in the post


def test_a_speed_needs_its_figure_and_unit():
    def speed(v, q, post):
        return A.validate({"targets": [_ans(kind="shahed", kind_quote="шахед", speed_kmh=v, speed_quote=q)]}, post, [])[0][0]["speed_kmh"]
    assert speed(180, "180 км/год", "шахед 180 км/год") == 180
    assert speed(180, "швидко", "шахед швидко") is None and speed(9000, "9000 км/год", "шахед 9000 км/год") is None


def _http_raw(code, raw):
    body = {"error": {"message": "Provider returned error", "code": code,
                      "metadata": {"provider_name": "Anthropic", "raw": json.dumps({"type": "error", "error": {
                          "type": "invalid_request_error", "message": raw}})}}}
    return urllib.error.HTTPError(A.OPENROUTER_URL, code, "x", {}, io.BytesIO(json.dumps(body).encode()))


def test_the_providers_own_words_are_shown_and_it_asks_the_simpler_way():
    r, seen = _reader(), []

    def fake(req, timeout=None, context=None):
        body = json.loads(req.data.decode())
        seen.append(body)
        if "response_format" in body:
            raise _http_raw(400, "Schema is too complex for compilation.")
        return _Resp({"model": "anthropic/claude-haiku-5.5", "usage": {"cost": 0.0003},
                      "choices": [{"message": {"content": "```json\n" + json.dumps(A.wire(GOOD), ensure_ascii=False) + "\n```"}}]})
    with mock.patch.object(A.urllib.request, "urlopen", fake):
        assert r.read(POST) == "agree"
        assert r.read(dict(POST, post_id="kpszsu/2")) == "agree"
    assert "response_format" in seen[0] and "response_format" not in seen[1] and "response_format" not in seen[2]
    assert all(isinstance(m["content"], str) for m in seen[1]["messages"])            # no caching marks either
    assert len(seen) == 3 and r.way == 1 and r.stats()["format"] == "prompt" and r.store.saved[-1]["prompt_v"] == A.PROMPT_VERSION + "p"
    assert r.last_error is None and not r.stats()["paused"]


def test_refused_both_ways_it_pauses_and_says_why():
    r = _reader()
    with mock.patch.object(A.urllib.request, "urlopen", side_effect=lambda *a, **k: (_ for _ in ()).throw(
            _http_raw(400, "messages.3.content.0: cache_control is not allowed here"))):
        assert r.read(POST) == "error"
    err = r.store.saved[-1]["error"]
    assert err.startswith("HTTP 400: Provider returned error — Anthropic: messages.3.content.0: cache_control")
    assert r.stats()["paused"] and r.way == 0


def test_the_rules_now_ask_for_origin_and_speed():
    assert A.PROMPT_VERSION == "4"
    for rule in ("9. Origin:", '"з Білорусі"', "never an origin", "give them whenever the post states them", "the target just above it",
                 "Answer with the JSON object only"):
        assert rule.lower() in A.SYSTEM.lower(), rule


def test_an_approach_mark_is_not_spotted_at_the_town_it_heads_for():
    page = _read("static/kyiv.html")
    assert "const appr=!!cur.approach&&!cur.status&&!cur.endedBy;" in page
    assert "${appr?esc(t('sh_appr',apprTo(cur))):`${cur.status?t('tp_reported'):t('tp_spotted')}" in page


# ---- 1.51: the deterministic reading, the map and the oblast in the prompt -------------------------------------------
def test_it_is_told_what_the_rules_read_the_map_and_the_oblast_and_asked_to_add_what_they_missed():
    for rule in ("A deterministic parser has already read the post", "above all ADD the targets it missed",
                 "A target missed is worse than a duplicate", "But you never invent", "15. The PARSER READING may be wrong",
                 "14. ON THE MAP NOW", "in the CHANNEL'S OBLAST or in the OBLASTS ITS LAST POSTS NAMED",
                 "Height, vertical state and speed matter most"):
        assert rule in A.SYSTEM, rule
    assert A.channel_block("rivne_radar", "Рівненська область", ["Житомирська область"]) == (
        "@rivne_radar\nCHANNEL'S OBLAST: Рівненська область — a regional tracker: a place it names alone is in or near this "
        "oblast\nOBLASTS ITS LAST POSTS NAMED (30 min): Житомирська область")
    ms = geo.parse_for_channel("kpszsu", "Реактивний над Броварами, висота 2200, знижується")
    assert A.parser_lines(ms) == ["jet drone · at Бровари · 2200 m · descending"]      # 1.53: a jet says so
    msg = A.user_message("@x", [], "пост", "c1 | Бровари | Київська область", ["drone · at Бровари"], ["S-01 · drone · at Бровари · @x 21:00"])
    assert "PARSER READING" in msg and "- drone · at Бровари" in msg and "- S-01 · drone · at Бровари · @x 21:00" in msg


def test_same_as_only_a_tag_it_was_shown_and_a_vertical_state_only_in_its_words():
    post = "Ціль заходить на Бортничі, низько, знижується"
    cands = [("c1", "Бортничі", "Бортничі | м. Київ")]
    out = {"targets": [_ans(kind="unknown", place_id="c1", place_quote="на Бортничі", relation="heading_to",
                            vertical="descending", vertical_quote="знижується", same_as="S-07")]}
    (t,), d = A.validate(out, post, cands, ["S-07"])
    assert d == 0 and t["same_as"] == "S-07" and t["vertical"] == "descending"
    (t,), d = A.validate(out, post, cands, ["N-02"])
    assert d == 1 and t["same_as"] is None
    out["targets"][0].update(vertical="descending", vertical_quote="заходить")
    assert A.validate(out, post, cands, ["S-07"])[0][0]["vertical"] is None


def test_the_reader_sends_the_map_context_the_server_gives_it():
    r, seen = _reader(), []
    r.context_fn = lambda post, cands: (["S-01 · drone · heading to Бровари · @kyiv_airdef 20:58"], ["S-01"])
    good = {"targets": [dict(GOOD["targets"][0], same_as="S-01")], "uncertain": None}

    def fake(req, timeout=None, context=None):
        seen.append(json.loads(req.data.decode()))
        return _ok(good)
    with mock.patch.object(A.urllib.request, "urlopen", fake):
        r.read(POST, ("14",), "")
    assert "- S-01 · drone · heading to Бровари · @kyiv_airdef 20:58" in seen[0]["messages"][-1]["content"]
    assert r.store.saved[-1]["ai"]["targets"][0]["same_as"] == "S-01"
