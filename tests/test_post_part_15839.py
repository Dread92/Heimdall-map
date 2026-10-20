"""1.58.39 — a target's card shows the part of the post it was read from, its course stands out, and zoomed out its
second line is no longer written.

The owner, of a jet drone drawn at Viitivtsi whose card quoted a whole Air Force post (Chernihiv, Zhytomyr, Rivne,
Volyn, Khmelnytskyi): "when the post tied to a drone names several places, it must absolutely be trimmed to where the
drone is — if a post with several places mentions Hnidyn, the drone we placed at Hnidyn gets ONLY the Hnidyn part";
"the direction is interesting and important data — it should stand out more"; and of "→ Oster / Desna (Chernihivskyi
raion) from the N · 06:23" written beside a drone on the whole-country view: "it must not take so much space when zoomed
out — ideally the destination appears only when you click the drone".
"""
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import geo  # noqa: E402
import server  # noqa: E402

TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()

AF = """Чернігівщина:
3х реактивних БпЛА курсом на Славутич

Житомирщина:
Реактивний БпЛА курсом на Овруч

Волинь:
2х реактивних БпЛА курсом на Ковель
Реактивний БпЛА курсом на Володимир

Хмельниччина:
2х реактивних БпЛА курсом на Віїтівці"""


def parts(text):
    return [geo.post_part(text, (m.get("evidence") or {}).get("segment")) for m in geo.parse_post(text)]


def test_each_target_gets_its_own_lines_with_their_heading():
    p = parts(AF)
    assert p[0] == {"part": "Чернігівщина:\n3х реактивних БпЛА курсом на Славутич", "lines": [0, 1]}
    assert p[2] == {"part": "Волинь:\n2х реактивних БпЛА курсом на Ковель", "lines": [6, 7]}
    assert p[3] == {"part": "Волинь:\nРеактивний БпЛА курсом на Володимир", "lines": [6, 8]}       # up its block to the heading
    assert p[-1]["part"] == "Хмельниччина:\n2х реактивних БпЛА курсом на Віїтівці"                # as written, not lowercased


def test_no_heading_is_borrowed_from_another_block():
    t = "Волинь:\n2х реактивних БпЛА курсом на Ковель\n\nРеактивний БпЛА курсом на Луцьк"
    assert parts(t)[-1] == {"part": "Реактивний БпЛА курсом на Луцьк", "lines": [3]}


def test_a_target_read_from_the_whole_post_keeps_the_whole_post():
    for t in ("Шахед над Гнідином курсом на Бориспіль", "Київ:\n🅿️1х Голосіїв Деміївка 4,4 км"):
        assert all(x is None for x in parts(t)), t
    assert geo.post_part("Шахед над Гнідином", "") is None and geo.post_part("", "шахед") is None
    assert geo.post_part(AF, "реактивний бпла курсом на ужгород") is None                         # not in the post: nothing
    one = geo.post_part("БпЛА над Броварами; ще один шахед курсом на Бориспіль", "ще один шахед курсом на бориспіль")
    assert one == {"part": "ще один шахед курсом на Бориспіль", "lines": None}                     # one line: the words


def test_the_marks_carry_it_and_the_pages_show_it():
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    p = {"post_id": "kpszsu/1", "channel": "kpszsu", "ts": datetime.now(timezone.utc).isoformat(), "text": AF,
         "tags": server.tag_feed_text(AF, "kpszsu")}
    st.store.add_feed([p])
    st.publish({"kind": "feed", "ts": p["ts"], "post": p})
    ms = [m for m in st.markers() if m.get("channel") == "kpszsu"]
    kov = [m for m in ms if "Ковель" in (m.get("place") or "") + str(m.get("target"))]
    assert kov and kov[0]["evidence"]["part"] == "Волинь:\n2х реактивних БпЛА курсом на Ковель"
    assert kov[0]["evidence"]["lines"] == [6, 7] and kov[0]["text"] == AF                          # the whole post is still there
    assert "pp = geo.post_part(p[\"text\"], ev.get(\"segment\")) if geo else None" in SRV
    # the pages: the hover card, the sheet, an oblast's events, Light — the part; the sheet's details keep the whole post
    assert "function postPart(m,ua,lang)" in I18N and "L.length===(m.text||'').split('\\n').length" in I18N
    assert "${esc((cur._txt||postPart(cur,showUA(),LANG)).slice(0,260))}" in TAC
    assert "${esc(ev.part?postPart(m,showUA(),LANG):" in TAC and "${(ev.part||(ev.segment&&" in TAC
    assert "${esc((m._txt||postPart(m,showUA(),LANG)).slice(0,220))}" in TAC
    assert "const said=postPart(m,LANG==='uk',LANG);" in LIGHT


def test_the_course_has_a_line_of_its_own():
    assert "function courseHtml(m,inb)" in TAC
    assert TAC.count("${courseHtml(") == 2                                                           # the hover card and the sheet
    assert "<span class=\"crsa\" aria-hidden=\"true\"><span style=\"display:inline-block;transform:rotate(${Math.round(m.heading)}deg)\">↑</span></span>" in TAC
    assert re.search(r"\.crs\{display:flex;[^}]*color:#ffd166", TAC) and "body.m-day .crs{color:#8a4b00}" in TAC
    assert "t('tp_heading')} ${cur.heading==null?t('tp_nr')" not in TAC                            # the old grey line
    assert "→ ${dirName(m.heading)}${m.target?' '+t('sh_towards')" not in TAC                       # not twice in the sheet
    assert "m.target?'→ '+tgtName(m):''" in TAC                                                     # the shared text names the town


def test_zoomed_out_the_second_line_waits_for_a_tap():
    assert "svg.far .mk:not(.tohome):not(.desc) .lbl2{display:none}" in TAC
    assert "svg.far .mk:not(.inbound):not(.tohome):not(.desc) .lbl2{display:none}" not in TAC


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.39" in s and "post_part" in s, doc
    assert "## 1.58.39" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
