"""1.52: the AI reader's targets on the map, and what its first real readings showed (9 Oct 2026).

The owner's decisions: a target only the AI found goes on the map — marked "AI", under the dashboard's kill switch,
with the "near you" pushes of any other — because a target missed is worse than a duplicate; it is placed only at a
place the post names, one the server offered it. A tag is given only when it is sure which target it is: never to a
target reported for a whole oblast. Where no post says where a target came from, the oblast it was first reported in
says it probably (Chernihiv — Belarus; Cherkasy — the south or the east), in lower case. And what the readings showed:
the AI had one place for a target (where it is OR where it goes), read 🛵 as "weapon unknown", gave nothing for a bare
"Яготин", could not place a village the gazetteer lacks or a misspelt one, and took an alert message for a drone; the
rules read power-cut news and an advert as targets, a channel's signature as a second jet, "з Чорного моря" as a
position in the sea and "З Житомирської" as a village; and a relay's height ("Вишеньки 2900") was lost with the relay.
"""
import os
from datetime import datetime, timedelta, timezone

import ai_reader as A
import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, ADMIN, SAFETY, DOC = (_read("static/kyiv.html"), _read("static/i18n.js"), _read("static/admin.html"),
                                  _read("docs/SAFETY.md"), _read("docs/TECHNICAL.md"))
NOW = datetime.now(timezone.utc)
OBL = {u: uk for u, uk, _ in server.OBLASTS}


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _state():
    st = server.State(server.Store(":memory:"), {})
    st.ai = A.AIReader({"openrouter_key": "sk-or-test"}, st.store, geo, rules_fn=lambda *a: [], oblast_names=OBL)
    return st, server.Telegram(st, {})


def _t(**kw):
    t = A._t(**kw)
    t["place"], t["toward"] = kw.get("place"), kw.get("toward")
    return t


def _read_ai(st, pid, text, targets, minutes=2, stored=0):
    st.store.ai_save({"post_id": pid, "ts": ago(minutes), "channel": pid.split("/")[0], "text": text, "stored": stored,
                      "verdict": "ai_only", "rules": [], "ai": {"targets": targets, "uncertain": None}})


def _marks(st):
    return {m["id"]: m for m in st.markers()}


# ---- the prompt, version 4 ------------------------------------------------------------------------------------------
def test_two_places_the_channels_emoji_bare_names_and_alert_messages():
    assert A.PROMPT_VERSION == "5"                       # 1.58.42: no emoji is a weapon
    for rule in ("Two places per target: where it is (place_id, with its relation) and where it is going (toward_id)",
                 '"на Житомирщині в напрямку Житомира" = place o10 in_oblast, toward Житомир',
                 "a tracker's line that is only a place name", '"на Київщині, н.п. Гребінка"', "never by an emoji",
                 "the channels put 🚀 on jet drones", '"шахед", "герань"', "that is an alert, not a target", '"спускається"'):
        assert rule in A.SYSTEM, rule
    assert "toward_id" in A.TARGET["required"] and "missile" in A.KINDS
    assert '"🛵"' not in A.SYSTEM and '"🏍" = jet_drone' not in A.SYSTEM and not hasattr(A, "EMOJI_KIND")


def test_an_emoji_is_no_weapon_and_toward_is_checked_like_a_place():
    # 1.58.42, the owner: "stop using the emojis to determine the nature of the threat" (1.52 took 🏍 for a quote)
    cands = [("c1", "Коростень", "Коростень | Житомирська область"), ("c2", "Житомир", "Житомир | Житомирська область"),
             ("o10", "o10", "Житомирська область")]
    post = "🏍 Повз околиці Коростеня на Житомир"
    out = {"targets": [A._t(kind="jet_drone", kind_quote="🏍", place_id="c1", place_quote="Повз околиці Коростеня",
                            relation="near", toward_id="c2", toward_quote="на Житомир")]}
    (t,), d = A.validate(out, post, cands)
    assert d == 1 and t["kind"] == "unknown" and t["place"] == "Коростень" and t["toward"] == "Житомир"
    # only where it is going: that is the place, heading to it
    out = {"targets": [A._t(kind="jet_drone", kind_quote="🏍", toward_id="c2", toward_quote="на Житомир")]}
    (t,), _ = A.validate(out, post, cands)
    assert (t["place"], t["relation"], t["toward"]) == ("Житомир", "heading_to", None)
    # nor an emoji the post does not hold
    out = {"targets": [A._t(kind="shahed", kind_quote="🛵", place_id="c1", place_quote="Повз околиці Коростеня", relation="near")]}
    assert A.validate(out, post, cands)[0][0]["kind"] == "unknown"


def test_a_target_drawn_at_where_it_goes_agrees_with_one_read_where_it_is_and_where_it_goes():
    rules = A.summarise_rules(geo.parse_for_channel("kpszsu", "🏍 Реактивний БпЛА на Київщині, курс Бориспіль"))
    ai = A.summarise_ai([dict(_t(kind="jet_drone", place="o14", relation="in_oblast", toward="Бориспіль"))])
    assert A.compare(rules, ai) == "agree"


# ---- the places the rules' matchers miss ----------------------------------------------------------------------------
def test_the_villages_of_kyiv_oblast_are_offered_to_the_ai_never_read_by_the_rules():
    assert {"Сомкова Долина", "Фарбоване", "Романівка (Бучанський р-н)"} <= set(geo.EXTRA_PLACES)
    assert all(k not in dict.keys(geo.PLACES) for k in geo.EXTRA_PLACES)
    assert not any(m.get("place") == "Сомкова Долина" for m in geo.parse_for_channel("chyste_nebo", "На Сомкова Долина"))
    keys = lambda txt, ch, home: [c[1] for c in A.candidates(geo, txt, ch, home, (), OBL)]   # noqa: E731
    assert "Сомкова Долина" in keys("На Сомкова Долина", "chyste_nebo", "31")
    assert "Фарбоване" in keys("Один з полтавської через черкаську на Фарбоване", "chyste_nebo", "31")
    assert "Переяслав" in keys("В київську на Пепеяслав", "chyste_nebocherkasy", "24")       # a slip of one letter
    assert A.place_of(geo, "Фарбоване")[2] == "14"


def test_the_spelling_match_is_strict():
    assert A._lev1("пепеяслав", "переяслав") and not A._lev1("бровар", "бориспіл")
    assert "Бровари" in A.fuzzy_places(geo, "шахед на бровари", {"14"})      # the core gazetteer's names too
    assert A.fuzzy_places(geo, "шахед на сумщині", set()) == []     # no oblast in play: nothing is guessed


# ---- the AI's targets on the map ------------------------------------------------------------------------------------
def test_a_target_only_the_ai_found_is_no_longer_on_the_map():
    # 1.54, the owner: "the AI placing things on the map — we forget it": a reading stored before 1.54 draws nothing
    st, tg = _state()
    _read_ai(st, "eRadarrua/901", "Повз околиці Коростеня на Житомир",
             [_t(kind="unknown", place="Коростень", place_quote="Повз околиці Коростеня", relation="near", toward="Житомир")])
    assert not any("#ai" in k for k in _marks(st)) and not hasattr(st, "_ai_marks")

def test_somkova_dolyna_is_not_dolyna():
    # the rules read "біля Сомкової Долини" as Dolyna (Ivano-Frankivsk oblast, off the map): nothing is drawn; 1.52–1.53
    # the AI's reading was, and 1.54 no longer (the village is not in the gazetteer)
    st, tg = _state()
    text = "Мопедик кружляє біля Сомкової Долини, 800"
    tg.ingest("kyiv_airdef", [("kyiv_airdef/913", ago(2), text)], "tg:k")
    _read_ai(st, "kyiv_airdef/913", text, [_t(kind="shahed", place="Сомкова Долина", place_quote="біля Сомкової Долини",
                                              relation="near", altitude_m=800, altitude_quote="800")], 2, 1)
    # 1.54.7: the villages of Kyiv oblast are the rules' too — the village, not Dolyna 500 km off
    assert geo.parse_for_channel("kyiv_airdef", text)[0]["place"] == "Сомкова Долина"
    assert "kyiv_airdef/913#ai0" not in _marks(st) and "kyiv_airdef/913#0" in _marks(st)

def test_two_tracks_never_share_a_report_or_a_tag():
    st, tg = _state()
    tg.ingest("kyiv_airdef", [("kyiv_airdef/914", ago(14), "Шахед над Українкою")], "tg:k")
    tg.ingest("kpszsu", [("kpszsu/915", ago(12), "Група шахедів на Бровари, заходять із півночі")], "tg:k")
    tg.ingest("war_monitor", [("war_monitor/916", ago(8), "Реактивний над Ірпенем")], "tg:w")
    tg.ingest("kievinfo_kyiv", [("kievinfo_kyiv/917", ago(6), "Шахед над Вишгородом")], "tg:v")
    tags = [m["tag"]["id"] for m in st.markers() if m.get("tag")]
    assert tags and len(tags) == len(set(tags))
    (m,) = geo.parse_for_channel("kpszsu", "Шахед над Козельцем")          # Козелець declines with a soft sign
    assert m["place"] == "Козелець"


def test_never_a_tag_for_a_whole_oblast():
    st, tg = _state()
    tg.ingest("chyste_nebo", [("chyste_nebo/904", ago(3), "3 шахеди на Чернігівщині")], "tg:chyste_nebo")
    ms = [m for m in _marks(st).values() if m["id"].startswith("chyste_nebo/904#")]
    assert ms and all(m["place"] == "область" and m.get("tag") is None for m in ms)


# ---- heights ---------------------------------------------------------------------------------------------------------
def test_a_relays_height_is_kept_on_the_report_it_relays():
    st, tg = _state()
    tg.ingest("kyiv_airdef", [("kyiv_airdef/905", ago(4), "Вишеньки")], "tg:k")
    tg.ingest("chyste_nebo", [("chyste_nebo/906", ago(3), "Вишеньки 2900")], "tg:c")
    m = _marks(st)["kyiv_airdef/905#0"]
    assert m["alt"]["m"] == 2900 and m["alt"]["by"] == "chyste_nebo"
    assert m["evidence"]["altitude"]["method"].startswith("stated by @chyste_nebo relaying the same report")


def test_the_tracks_last_height_is_shown_when_its_latest_report_gave_none():
    st, tg = _state()
    tg.ingest("kyiv_airdef", [("kyiv_airdef/907", ago(5), "Лісники 1000"), ("kyiv_airdef/908", ago(2), "Ходосівка")], "tg:k")
    m = next(m for m in st.markers() if m["id"] == "kyiv_airdef/908#0")
    assert m["tag"]["alt"]["m"] == 1000 and m["tag"]["alt"]["cur"] is False
    assert "altOld!=null?` (${altOld}′)`:''" in PAGE


def test_a_height_and_a_descent_said_together_are_both_read():
    (m,) = geo.parse_for_channel("chyste_nebo", "Хотів 1200 знижується")
    assert m["alt"]["m"] == 1200 and m["alt"]["state"] == "descending"


# ---- where it came from, when no post said ----------------------------------------------------------------------------
def test_the_first_oblast_says_probably_and_a_stated_origin_wins():
    st, tg = _state()
    tg.ingest("chernihiv_nebo", [("chernihiv_nebo/909", ago(5), "Шахед на Козелець"), ("chernihiv_nebo/910", ago(2), "Шахед над Остером")], "tg:c")
    tg.ingest("kpszsu", [("kpszsu/911", ago(3), "БпЛА на Черкащині курсом на Канів")], "tg:k")
    tg.ingest("kpszsu", [("kpszsu/912", ago(2), "БпЛА з півдня на Ніжин")], "tg:k")
    ms = _marks(st)
    a = ms["chernihiv_nebo/910#0"]["tag"]
    assert a["p"] == "n" and a["os"] == "region" and a["o"] == "belarus" and a["ou"] == "25" and a["id"].startswith("#")     # 1.53.2: kept, never shown
    assert ms["kpszsu/911#0"]["tag"]["p"] == "s" and ms["kpszsu/911#0"]["tag"]["o"] == "se"
    assert ms["kpszsu/912#0"]["tag"]["p"] == "S" and ms["kpszsu/912#0"]["tag"]["os"] == "rules"      # Nizhyn is Chernihiv oblast
    assert server.TAG_REGION == {"25": ("n", "belarus"), "24": ("s", "se")}


# ---- the rules' errors the AI showed --------------------------------------------------------------------------------
def test_the_rules_errors_the_readings_showed():
    rd = lambda ch, t: [(m.get("place"), m.get("oblast_uid")) for m in geo.parse_for_channel(ch, t)]   # noqa: E731
    assert rd("zt_radar", "Житомирщина:\nРеактивний БпЛА курсом на Радомишль\n‼️ RND | Житомир") == [("→ Радомишль", "10")]
    (m,) = geo.parse_for_channel("kpszsu", "🏍 Реактивні БпЛА з Чорного моря в напрямку Миколаївщини")
    assert m["place"] == "область" and m["oblast_uid"] == "17" and m["origin"]["o"] == "s"
    assert rd("chyste_nebo", "З Житомирської повертається. Курс на р-н Макарів ‼") == [("область", "10")]
    assert not any(p == "Черкаси" for p, _ in rd("chyste_nebo", "Один з полтавської через черкаську на Фарбоване"))
    # 1.54.2: the oblast for a Kyiv tracker too ("В Житомирській", @chyste_nebo); the metro station only when it says so
    assert rd("kyiv_airdef", "БпЛА на Житомирську") == [("область", "10")]
    assert rd("kyiv_airdef", "БпЛА біля метро Житомирська") == [("Житомирська", "31")]
    rel = lambda ch, t: server.is_relevant(t, server.tag_feed_text(server._clean_post(t), ch), ch)  # noqa: E731
    assert not rel("kievinfo_kyiv", "⚡️💡Графік відключення світла на завтра для Київщини")
    assert not rel("xydessa_live", "кто подпишется на 🐦‍⬛️ Ищу Одесса, тот найдёт айфон")
    assert rel("kyiv_airdef", "Шахед на Бровари. Підписуйтесь на канал")
    assert rel("kievinfo_kyiv", "Після удару по Броварах частина міста без світла")


def test_a_post_the_server_set_aside_is_compared_with_nothing():
    r = A.AIReader({"openrouter_key": "sk-or-test"}, None, geo, rules_fn=lambda *a: [{"place": "Одеса", "type": "unknown"}],
                   oblast_names=OBL)
    src = open(os.path.join(ROOT, "app", "ai_reader.py"), encoding="utf-8").read()
    assert "marks = self.rules_fn(ch, text, list(near)) if stored else []" in src and r.rules_fn


# ---- the page --------------------------------------------------------------------------------------------------------
def test_the_page():
    # 1.54: nothing of the AI on the map — no "AI" mark, label, compact tag or oblast chip
    assert "m.ai" not in PAGE and ".mk.ai" not in PAGE and "t('ai_placed')" not in PAGE and "aiOnly" not in PAGE and "obai" not in PAGE
    assert '<g id="selpath"></g>' in PAGE and "function drawSelPath()" in PAGE and "if(SELP) drawSelPath();" in PAGE
    assert "const ct=tg?tg.id:'';" in PAGE                                   # zoomed out: the tag alone
    assert "#selpath .selp{fill:none;stroke:#ff3b3f;" in PAGE and "SELP=id;" in PAGE and "closeSheet(){ SELP=null;" in PAGE
    assert "body.m-day .mk .lbl .tid,body.m-day .mk .tgc{fill:#7a4b00;stroke:#fff}" in PAGE      # the tag in daylight
    assert "tagOrigin" not in PAGE                                     # 1.53.2: where it came from is not shown
    for k in ("tg_inf_belarus", "tg_inf_se"):
        assert I18N.count(f"{k}:'") == 3, k
    assert "k_missile:" in ADMIN and "t.toward?tr('ai_toward',aiPlace(t.toward)):''" in ADMIN
    assert ADMIN.count("v_descending:") == 2 and "m[1]==='14'?(L==='uk'?'Київська область':'Kyiv oblast')" in ADMIN


def test_docs():
    assert "### 7.9 The AI reader's targets on the map (1.52; gone in 1.54)" in DOC and "extra_places.json" in DOC
    assert "## A target only the AI reader found (1.52)" in SAFETY
