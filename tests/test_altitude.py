"""Height: read whenever a post states it, shown where it is seen first, and never guessed.

A low or falling drone may be diving. The channels write heights three ways — "висота 2200", "1600, Вороньків",
and for jet drones in kilometres with a decimal comma, "висота 4,4км" — and the last one was read as nothing at
all: the metre pattern cannot see a single digit. The height was also shown on the Light page only behind a tap,
and only when the post used a word like "низько" as well as a number."""
import os
import re
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
FULL = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def test_kilometres_with_a_decimal_comma_are_read():
    for text, m in (("висота 4,4км", 4400), ("висота 5км", 5000), ("висота 3,3км", 3300), ("висота 1.2 км", 1200),
                    ("4,4 км висота", 4400)):
        assert (geo.parse_altitude(text) or {}).get("m") == m, text


def test_metres_still_read_and_nonsense_is_not():
    assert geo.parse_altitude("висота 2200")["m"] == 2200
    assert geo.parse_altitude("висота 800 м")["m"] == 800
    assert geo.parse_altitude("висота 25 км") is None          # not a drone's height
    assert geo.parse_altitude("над Бориспільським районом") is None


def test_the_real_war_monitor_post_gets_its_height_and_keeps_its_count():
    text = "Київщина: 🅿️1х реактив у Бориспільському районі, висота 5км."
    ms = geo.parse_for_channel("war_monitor", text)
    assert ms, "no mark at all"
    m = ms[0]
    assert (m.get("alt") or {}).get("m") == 5000
    assert (m.get("count") or 1) == 1, "the height was read as a count"


def test_a_track_keeps_the_height_each_report_stated():
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    now = datetime.now(timezone.utc)
    def mk(i, lat, alt, mins):
        return {"id": f"kyiv_airdef/{i}#0", "type": "drones", "lon": 30.5, "lat": lat, "ts": (now - timedelta(minutes=mins)).isoformat(),
                "channel": "kyiv_airdef", "place": "X", "heading": 180, "count": 1, "oblast_uid": "14",
                "alt": {"state": None, "m": alt}, "evidence": {"heading": {"confidence": "stated"}}}
    kept = st._chain_and_prune([mk(1, 50.60, 2200, 4), mk(2, 50.57, 1600, 2), mk(3, 50.55, 800, 1)], 45)
    live = [m for m in kept if not m.get("superseded_by")]
    assert live and [h.get("alt_m") for h in live[-1]["history"]] == [2200, 1600]


def test_the_trend_is_only_stated_numbers():
    body = I18N[I18N.index("function altTrend(m)"):I18N.index("\n", I18N.index("return {hs"))]
    assert "h.alt_m" in body and "m.alt.m" in body
    assert "hs.length<2" in body.replace(" ", ""), "one height is not a trend"


def test_light_shows_the_height_on_the_row_and_beside_the_mark():
    i = LIGHT.index("const row=(")
    row = LIGHT[i:LIGHT.index("};", i)]
    assert "altTrend(m)" in row and "alt_desc_l" in row and "lt_alt_at" in row
    assert 'class="altl' in LIGHT, "no height beside the mark on the radar"
    # a height given as a number alone (no word like "низько") is shown too — it used to be dropped
    assert "m.alt&&m.alt.state?(m.alt.m" not in LIGHT


def test_the_tactical_track_lists_the_heights():
    assert "h.alt_m!=null" in FULL and "altTrend(m)" in FULL


def test_lt_alt_at_exists_in_three_languages():
    assert len(re.findall(r"lt_alt_at:'[^']*\{0\}[^']*'", I18N)) == 3


# ---- 1.50.2: a height belongs to its own target, not to every target of the post -----------------------------------
MONITOR_0910 = """2 реактиви у бік Києва з півдня.

 1 реактив пролетів Славутич курсом на Київщину, Вишгородський р-н.

 1 реактив на Кіровоградщині курсом на Вінниччину.

 2 реактиви вилетіли з Донецького аеропорту і летять вздовж Дніпропетровщини.

 1 реактив над Одесою.
3.5 км висоти"""


def test_a_height_on_its_own_line_is_the_height_of_the_target_above_it():
    """@monitor_ukr, 9 Oct 19:02: five jets from Kyiv to Odesa, and the last line, "3.5 км висоти", under the Odesa
    one. Every jet got 3.5 km — the two coming at Kyiv from the south showed "3500 м" on the map."""
    got = {m["place"]: (m.get("alt") or {}).get("m") for m in geo.parse_for_channel("monitor_ukr", MONITOR_0910)}
    assert got["Одеса"] == 3500
    assert all(v is None for k, v in got.items() if k != "Одеса"), got


def test_a_single_targets_height_is_still_read_wherever_it_is_written():
    for text in ("Шахед на Бровари\nвисота 1500", "Висота 1500\nШахед на Бровари", "Шахед на Бровари, висота 1500"):
        (m,) = geo.parse_for_channel("kpszsu", text)
        assert m["alt"]["m"] == 1500 and m["evidence"]["altitude"]["method"] == "stated in the post", text
    a, b = geo.parse_for_channel("kpszsu", "2 шахеди на Бровари, висота 900\n1 на Бориспіль")
    assert a["alt"]["m"] == 900 and not b.get("alt")
