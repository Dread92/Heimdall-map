"""Two ways a post used to become a threat it was not.

A news item that mentions ballistic missiles in its fourth sentence put a ballistic missile on the map and, via
its tags, lit the red strip telling people to shelter. The news guard existed, but only for outcomes; a live
threat walked straight past it.

And a Banderol became a cruise missile three ways: a post that described it without naming it ("реактивна
ракета", "з Оріона") fell through to the bare "ракет"; its tags carried "cruise_missiles" into the feed; and on
the server it shared a track family with cruise missiles, so a later, vaguer "ракета" report renamed the track.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402
import server  # noqa: E402

SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()

NEWS = [
    "Минулої ночі росіяни атакували Київ балістичними ракетами. Внаслідок атаки постраждали троє людей, повідомив голова КМВА.",
    "Кличко: у Дніпровському районі внаслідок падіння уламків балістичної ракети пошкоджено будинок",
    "У Полтаві провели стратегічний форум «Безпека громад». Він об'єднав представників влади.",
    "СБУ затримала коригувальника, який наводив балістику на Київ",
    "Вчора ввечері Шахед влучив у склад на Київщині, загиблих немає, повідомили в ДСНС",
]
LIVE = [
    ("Балістика на Київ!", "ballistic_missiles"),
    ("За даними моніторингу, шахед над Броварами курсом на Київ", "drones"),
    ("Група шахедів над Білою Церквою курсом на Київ", "drones"),
    ("Крилаті ракети над Конотопом, зафіксовано пуски з Каспію", "cruise_missiles"),
]


def test_a_news_item_draws_nothing():
    for t in NEWS:
        assert geo.parse_post(t) == [], f"news drew a mark: {t[:60]!r}"


def test_a_news_item_carries_no_threat_tag_so_it_cannot_light_the_strip():
    for t in NEWS:
        assert server.tag_feed_text(t, "war_monitor") == ["news"], t[:60]


def test_the_guard_does_not_swallow_a_real_alert():
    """One sign of a report in a short post is normal — "за даними моніторингу, шахед над Броварами"."""
    for t, want in LIVE:
        got = [m["type"] for m in geo.parse_post(t)]
        assert got == [want], f"{t!r} → {got}"


def test_a_nightly_assessment_is_still_a_forecast_not_just_news():
    tags = server.tag_feed_text("Загальна оцінка загроз на ніч: запуск балістики може відбутись у будь-який момент.", "kpszsu")
    assert "forecast" in tags


def test_the_word_strategic_alone_is_not_strategic_aviation():
    """A youth forum in Poltava oblast was drawn as three Tu-95 formations."""
    assert geo.parse_post("Стратегічне партнерство громад Полтавщини") == []
    tags = server.tag_feed_text("Стратегічна авіація: Ту-95МС у повітрі", "kpszsu")
    assert "strategic_aircraft_activity" in tags


def test_every_post_from_the_six_channels_in_the_corpus_survives_except_the_tallies():
    """Measured, not assumed: of the real posts on record from the channels now read, the only ones the guard
    treats as news are the retrospective morning tallies, which were never drawn anyway."""
    import json
    rows = [json.loads(ln) for ln in open(os.path.join(ROOT, "data", "corpus.jsonl"), encoding="utf-8") if ln.strip()]
    six = set(server.AUTHORITATIVE_CHANNELS)
    flagged = [r["text"] for r in rows if r["channel"] in six and geo.looks_like_news(geo._norm(r["text"]))]
    assert all(geo.looks_like_summary(geo._norm(t)) for t in flagged), (
        "the news guard now swallows a post from the live channels that is not a retrospective tally")


# ── Banderol ───────────────────────────────────────────────────────────────────────────────────────────
def test_banderol_by_its_other_names():
    for t in ("Бандероль курсом на Конотоп", "Реактивна ракета над Броварами курсом на Київ",
              "Ракета з БпЛА Оріон на Чернігівщину", "С-8000 над Ніжином курсом на південь"):
        got = [m["type"] for m in geo.parse_post(t)]
        assert got == ["banderol_missiles"], f"{t!r} → {got}"


def test_a_banderol_post_carries_no_cruise_tag():
    tags = server.tag_feed_text("Реактивна ракета над Броварами курсом на Київ", "war_monitor")
    assert "banderol_missiles" in tags and "cruise_missiles" not in tags


def test_a_banderol_track_is_never_continued_by_a_cruise_report():
    body = SRC[SRC.index("def _chain(ms):"):]          # 1.42: the chaining is its own function, shared with the replay
    fam = body[body.index("def fam(m):"):body.index("for i, m in enumerate(tracks)")]
    assert '"banderol_missiles"' in fam and 'return "banderol"' in fam


def test_plain_rockets_are_still_cruise_missiles():
    """The widening must not swallow the ordinary case."""
    assert [m["type"] for m in geo.parse_post("Ракета над Черніговом курсом на південь")] == ["cruise_missiles"]


def test_banderol_is_never_labelled_a_cruise_missile_in_any_language():
    i18n = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
    import re
    for v in re.findall(r"th_band:'([^']*)'", i18n):
        assert "крилат" not in v.lower() and "cruise" not in v.lower() and "croisière" not in v.lower()


def test_a_metro_notice_is_news_not_a_route():
    """24 Sep: KCSA's red-line notice — trains "from Akademmistechko to Teatralna" — became a target flying across
    Kyiv, because two names joined by "від … до" read as a route."""
    text = ("🚇 Зміни в роботі червоної лінії метро Києва, – КМДА.\n\nПоїзди курсують:\n"
            "▪️у напрямку центру – від «Академмістечка» до «Театральної»;\n"
            "▪️у напрямку виїзду з міста – від «Арсенальної» до «Академмістечка».\n"
            "Повітряна тривога триває. Залишайтеся в укриттях.\n\n🇺🇦 Київ ІНФО")
    assert geo.looks_like_news(geo._norm(text))
    assert geo.parse_for_channel("kievinfo_kyiv", text) == []
    assert server.tag_feed_text(text, "kievinfo_kyiv") == ["news"]


def test_a_video_of_a_strike_is_news_not_a_fresh_explosion():
    """25 Sep 2026, 22:22: a video caption drawn as an explosion over Kyiv, as if it had just happened."""
    for ch, text in [
        ("kievinfo_kyiv", "😱 Момент прильоту Герань-5 бізнес-центром «Інком» у Києві"),
        ("kievinfo_kyiv", "😱 Момент прильоту Герань-5 бізнес-центром «Інком» у Києві\n\nЯкщо у вас є інші відео "
                          "прильоту, надсилайте нашому боту — купимо їх за $. Все анонімно!"),
        ("kyiv_airdef", "Кадри з місця влучання на Оболоні"),
        ("war_monitor", "Відео роботи ППО над Києвом"),
        ("xydessa_live", "Момент прилета по Одессе"),
    ]:
        assert geo.parse_for_channel(ch, text) == [], text
    # a live report of a hit is untouched
    assert geo.parse_for_channel("kyiv_airdef", "Прильот у Броварах")
