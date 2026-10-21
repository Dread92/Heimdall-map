"""1.58.43 — the three channels the owner added, read as they write; and a shared link shows the logo.

The owner: "@vseok450 for Kyiv oblast, @rocket_danger_lviv for Lviv, @tlknewsua for Kharkiv — I added them manually on
the dashboard but I don't know if they are effectively read and put on the map". Their latest posts, read by the rules,
showed: @tlknewsua's "РСЗО на Проходы/Липцы" (rocket artillery) as a target in the sky at Lyptsi, its Russian "Упал" and
"Не фиксируется" unread; @rocket_danger_lviv's Ternopil towns unknown ("🚀 Теребовля / 🚀 Збараж") and "Франик"
(Ivano-Frankivsk); @vseok450's "1 мінус / 1 до Узина / 1 в Чорнобильську" as one target shot down at Uzyn. Picked: all of
it — and, the owner's one exception to 1.58.42, on @rocket_danger_lviv the 🚀 is a missile (while one is reported).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import geo  # noqa: E402
import server  # noqa: E402

NOW = datetime.now(timezone.utc)


def _read(ch, text, home=None):
    if home:
        geo.CHANNEL_HOME[ch] = home
    return [(m["type"], m.get("status"), m["place"], m.get("oblast_uid")) for m in geo.parse_for_channel(ch, text)]


def _kept(ch, text):
    clean = server._clean_post(text)
    return server.is_relevant(text, server.tag_feed_text(clean, ch, None), ch)


# ---- @tlknewsua (Kharkiv, in Russian) ---------------------------------------------------------------------------------
def test_rocket_artillery_is_not_the_sky():
    assert _read("tlknewsua", "РСЗО на Проходы/Липцы⚠️", "22") == []
    assert not _kept("tlknewsua", "РСЗО на Проходы/Липцы⚠️")
    assert _read("tlknewsua", "Минометный обстрел Волчанска", "22") == []
    assert _read("tlknewsua", "БПЛА неизвестного типа курсом на Липцы⚠️", "22") == [("drones", None, "→ Липці", "22")]
    assert _read("tlknewsua", "КАБ на Приколотное/Бурлук⚠️", "22")[0][:1] == ("guided_aerial_bombs",)


def test_its_russian_outcomes_are_read():
    assert "tlknewsua" in geo.RU_CHANNELS
    assert _read("tlknewsua", "Упал😔", "22") == [("drones", "down", None, "22")]
    assert _read("tlknewsua", "Не фиксируется⚠️", "22") == [("drones", "lost", None, "22")]
    assert _kept("tlknewsua", "Упал😔") and _kept("tlknewsua", "Не фиксируется⚠️")


def test_a_kab_that_fell_hit_the_ground():
    st = server.State(server.Store(":memory:"), {})
    tg = server.Telegram(st, {})
    geo.CHANNEL_HOME["tlknewsua"] = "22"
    tg.ingest("tlknewsua", [("tlknewsua/91", (NOW - timedelta(minutes=4)).isoformat(), "КАБ по Купянску⚠️"),
                            ("tlknewsua/92", (NOW - timedelta(minutes=1)).isoformat(), "Упал😔")], "tg:tlknewsua")
    out = [m for m in st.markers() if m.get("channel") == "tlknewsua" and m.get("status")]
    assert [(m["status"], m["type"], m["place"]) for m in out] == [("impact", "guided_aerial_bombs", "Куп'янськ")]   # 1.44's rule
    # one only heading somewhere ("КАБ на Приколотное") has no place to fall at: nothing is drawn where it was not said
    st = server.State(server.Store(":memory:"), {})
    tg = server.Telegram(st, {})
    geo.CHANNEL_HOME["tlknewsua"] = "22"
    tg.ingest("tlknewsua", [("tlknewsua/93", (NOW - timedelta(minutes=4)).isoformat(), "КАБ на Приколотное/Бурлук⚠️"),
                            ("tlknewsua/94", (NOW - timedelta(minutes=1)).isoformat(), "Упал😔")], "tg:tlknewsua")
    assert not [m for m in st.markers() if m.get("status")]


# ---- @rocket_danger_lviv (Lviv) ---------------------------------------------------------------------------------------
def test_the_towns_of_ternopil_oblast_and_frankivsks_nickname():
    got = _read("rocket_danger_lviv", "🚀 Перемишляни\n🚀 Теребовля\n🚀 Монастирська\n🚀 Збараж\n🚀 Володимир", "27")
    assert [p for _, _, p, _ in got] == ["Перемишляни", "Теребовля", "Монастириська", "Збараж (Тернопільщина)", "Володимир"]
    assert _read("rocket_danger_lviv", "🚀 парочка може полетить на Франик", "27")[0][2] == "→ Івано-Франківськ"
    # a name a village elsewhere shares is "(Тернопільщина)": that oblast's own channel keeps its village
    assert not dict.__contains__(geo.PLACES, "Збараж") and not dict.__contains__(geo.PLACES, "Борщів")
    assert geo._plausible("збаражі", "Збараж (Тернопільщина)", "збараж")


def test_its_rocket_is_a_missile_while_one_is_reported():
    assert geo.ROCKET_IS_MISSILE == frozenset({"rocket_danger_lviv"})
    ms = geo.parse_for_channel("rocket_danger_lviv", "🚀 Перемишляни\n🚀 Теребовля")
    assert [(m["type"], m["msl_weak"], m["likely"]) for m in ms] == [("unspecified_missiles", True, None)] * 2
    assert "1.58.43" in ms[0]["evidence"]["type"]["method"]
    assert _read("rocket_danger_lviv", "Львів 3 хв‼️")[0][:1] == ("unknown",)                         # no 🚀: as any
    assert _read("kievinfo_kyiv", "🚀 Троєщина")[0][:1] == ("unknown",)                              # elsewhere: 1.58.42
    assert server.tag_feed_text("🚀 Перемишляни", "rocket_danger_lviv")[:1] == ["msl_weak"]


# ---- @vseok450 (Kyiv) -------------------------------------------------------------------------------------------------
def test_its_lists_line_by_line():
    assert _read("vseok450", "1 мінус\n1 до Узина\n1 в Чорнобильську", "31") == [("unknown", None, "→ Узин", "14")]
    assert [p for _, _, p, _ in _read("vseok450", "Яготин\nМінус\nБогуслав")] == ["Яготин", "Богуслав"]   # which was it?
    assert [p for _, _, p, _ in _read("vseok450", "Яготин\nБогуслав\n3 Чернігівська")] == ["Яготин", "Богуслав"]
    for t in ("Ці в Житомирську", "В Чернігівській 1+1", "Чорнобильська 2", "2 Чернігівська\n1+1 Черкаська"):
        assert _read("vseok450", t) == [], t                                     # a count with no place, those already seen
    assert _read("vseok450", "Мінус") == [("drones", "down", None, "31")]       # alone: the channel's last report, as before
    assert [(p, s) for _, s, p, _ in _read("vseok450", "Обухів\nзнижується")] == [("Обухів", None)]
    assert geo.CHANNEL_PARSER["vseok450"] is geo.parse_vseok450


# ---- a shared link ---------------------------------------------------------------------------------------------------
def test_a_shared_link_shows_the_logo():
    for page in ("kyiv.html", "light.html", "guide.html"):
        s = open(os.path.join(ROOT, "static", page), encoding="utf-8").read()
        head = s[:s.index("</head>")]
        assert '<meta property="og:image" content="https://heimdall.com.ua/static/heimdall-512.png">' in head, page
        assert '<meta property="og:title" content="Heimdall — мапа повітряних загроз">' in head, page
        assert "не радар" in head and '<meta name="twitter:card" content="summary">' in head, page
    assert os.path.exists(os.path.join(ROOT, "static", "heimdall-512.png"))


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.43" in s and "rocket_danger_lviv" in s, doc
    assert "## 1.58.43" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
