"""1.58.42 — no emoji says what a threat is; a missile with no course has no front.

The owner: "stop using the emojis to determine the nature of the threat, because it is very common for the rocket /
cruise missile emoji to be used for jet drones" (picked: no emoji at all — 🚀 was "a missile", 💣 a KAB, 🛵 🛸 🏍 🚁 🅿 and
the arrows channel's ✈️ a drone, its 🎯 a ballistic missile). The words say what it is; a sign alone says only that a
target is reported — the same posts make marks as before, of no stated type ("probably a drone", 1.54.8).

And of a ballistic missile "в напрямку Києва" drawn nose-up on Kyiv: "how to rotate the missile like a direction it takes
usually?" — picked: no direction drawn at all. A missile, a Banderol or a guided bomb whose post gave no course, and
that has no track of its own to face along, is a disc with a "?" on the Tactical map, on Light's radar and on the
channel's picture; its label, the lists and the cards still say what it is.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import ai_reader as A  # noqa: E402
import geo  # noqa: E402
import mapshot  # noqa: E402
from test_chanpost_158 import mark  # noqa: E402

TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
GLY = open(os.path.join(ROOT, "static", "glyphs.js"), encoding="utf-8").read()
SIGNS = "🚀💣🛸🛵🏍🚁🅿"


def _read(channel, text):
    return [(m["type"], m["place"], m.get("likely")) for m in geo.parse_for_channel(channel, text)]


# ---- the signs --------------------------------------------------------------------------------------------------------
def test_no_type_rule_holds_an_emoji():
    for name, rx in geo.TYPE_RX:
        assert not any(ch in rx.pattern or f"\\U{ord(ch):08x}" in rx.pattern for ch in SIGNS + "🎯✈🛩"), name
    assert "\\U0001f680" not in geo.MSL_WEAK_RX.pattern and not hasattr(geo, "ARROW_TYPE") and not hasattr(geo, "_PLANE_RX")
    assert all(geo.WEAPON_SIGN_RX.search(ch) for ch in SIGNS)


def test_a_sign_alone_is_a_target_of_no_stated_type():
    for text in ("🚀 Троєщина", "🛵 Бровари", "Козин🛸", "🏍 Бровари", "🅿️ Бровари"):
        assert _read("kyiv_airdef", text) == [("unknown", text.strip("🚀🛵🛸🏍🅿️ ") if "Козин" not in text else "Козин", "drones")], text
    assert _read("eRadarrua", "🛵 Наливайківка") == [("unknown", "Наливайківка", "drones")]
    assert _read("kyiv_airdef", "✈️Соломʼянка")[0][:1] == ("unknown",)
    assert geo.missile_said("🚀🚀Оболонь, Труханів") is None and geo.missile_said("🚀КАБи на Харківщину", "kpszsu") is None


def test_the_words_still_say_it():
    assert _read("kievinfo_kyiv", "🚀 Реактивний БпЛА Троєщина")[0][0] == "drones"
    assert geo.parse_for_channel("kievinfo_kyiv", "🚀 Реактивний БпЛА Троєщина")[0]["jet"]
    assert _read("kpszsu", "💣 КАБи на Харківщину")[0][0] == "guided_aerial_bombs"
    assert _read("kpszsu", "🚀 Балістична ракета в напрямку Києва.")[0][0] == "ballistic_missiles"
    assert _read("kpszsu", "🚀 Швидкісна ціль на Дніпропетровщині")[0][0] == "ballistic_missiles"   # the Air Force's word


def test_the_arrows_channel_reads_its_words_not_its_icons():
    got = geo.parse_for_channel("povitryanatrivogaaa", "🚀Харківщина:\n→Богодухів/Харків")
    assert [(m["type"], m["likely"]) for m in got] == [("unknown", "drones")]
    assert got[0]["evidence"]["type"]["confidence"] == "none"
    got = geo.parse_for_channel("povitryanatrivogaaa", "Харківщина: реактивні БпЛА\n→Богодухів/Харків")
    assert [(m["type"], m["jet"], m["likely"]) for m in got] == [("drones", True, None)]
    assert geo.parse_for_channel("povitryanatrivogaaa", "🎯Харківщина:\n→Богодухів/Харків")[0]["type"] == "unknown"


def test_the_ai_reader_takes_no_emoji_for_a_weapon():
    assert A.PROMPT_VERSION == "6" and A.CHECK_VERSION == "6" and not hasattr(A, "EMOJI_KIND")      # 1.58.60: "6"
    assert "never by an emoji" in A.SYSTEM and '"🛵", "шахед"' not in A.SYSTEM
    cands = [("c1", "Бровари", "Бровари | Київська область")]
    for q in ("🛵", "🚀", "💣"):
        out = {"targets": [A._t(kind="missile" if q == "🚀" else "shahed", kind_quote=q, place_id="c1", place_quote="Бровари")]}
        assert A.validate(out, f"{q} Бровари", cands)[0][0]["kind"] == "unknown", q
    out = {"targets": [A._t(kind="shahed", kind_quote="Шахед", place_id="c1", place_quote="Бровари")]}
    assert A.validate(out, "🛵 Шахед Бровари", cands)[0][0]["kind"] == "shahed"


# ---- no course, no front ------------------------------------------------------------------------------------------------
def test_the_disc_is_one_rule_in_one_file():
    assert "const NOFRONT=new Set(['ballistic','missile','supersonic','banderol','bomb']);" in GLY
    assert "const noFront=(gk,m,stated)=>NOFRONT.has(gk)&&!m.status&&!m.endedBy&&!stated&&m.face==null;" in GLY
    assert re.search(r"G\.nofront='<circle class=\"glyph nf\" cx=\"0\" cy=\"0\" r=\"8\.4\"/><text class=\"nfq\"", GLY)
    assert mapshot.NOFRONT_R == 8.4
    # Tactical: the map's mark; its lists keep the weapon, upright
    assert ":(!asDrone(m)&&noFront(wpnGlyph(m),m,statedHdg(m)))?'nofront'" in TAC
    assert "function silSvg(m,col){ const k=/^(arrow|nofront)$/.test(glyphKey(m))?" in TAC
    assert ".mk .nfq,.sil .nfq{font:800 12px var(--mono);fill:#080b10" in TAC and "body.m-night .mk .nfq{fill:#ff6b60}" in TAC
    # Light: the radar's mark; a row's icon stays the weapon
    assert "const silKey=m=>noFront(wpnKey(m),m,statedCourse(m))?'nofront':wpnKey(m);" in LIGHT
    assert "${G[wpnKey(m)]||''}" in LIGHT and ".sil .nfq{" in LIGHT
    assert "else if(!statedCourse(m)&&silKey(m)!=='nofront') q+=`<text class=\"qm\"" in LIGHT      # one "?", the disc's


def test_the_channels_picture_draws_it_the_same_way():
    bal = mark(type="ballistic_missiles", place="→ Київ", lon=30.52, lat=50.45, uid="31", approach=True)
    assert mapshot.no_front(bal)
    assert not mapshot.no_front(dict(bal, heading=200, evidence={"heading": {"confidence": "medium"}}))   # a course said
    assert not mapshot.no_front(dict(bal, face=180))                                                       # its track
    assert not mapshot.no_front(dict(bal, status="down"))
    for t in ("cruise_missiles", "banderol_missiles", "guided_aerial_bombs", "supersonic_missiles", "unspecified_missiles"):
        assert mapshot.no_front(dict(bal, type=t)), t
    for t in ("drones", "unknown", "mig31k_departure", "tactic_aircraft_activity"):
        assert not mapshot.no_front(dict(bal, type=t)), t
    assert not mapshot.no_front(dict(bal, type="unknown"), drone_like=True)
    shot = mapshot.MapShot()
    calls = []
    real = shot._glyph

    def spy(d, m, here, sc, alpha=255, drone_like=False):
        calls.append(mapshot.no_front(m, drone_like))
        return real(d, m, here, sc, alpha, drone_like)
    shot._glyph = spy
    assert shot.render(bal, [], "22:08")[:2] == b"\xff\xd8"                        # a JPEG, drawn with the disc
    assert calls and calls[0] is True


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.42" in s and "WEAPON_SIGN_RX" in s and "nofront" in s, doc
    assert "## 1.58.42" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
