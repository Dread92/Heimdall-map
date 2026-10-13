"""1.58.6 — a part of the oblast the post placed it in is where it is, even when the post names where it is heading.

The owner, with the Air Force's "🛵 Реактивний БпЛА на сході Київщини, в напрямку столиці." drawn on Kyiv as "→ Київ",
turned east: "placement here is obviously wrong, it's towards Kyiv but not in Kyiv at least yet… alarm ALWAYS is
better, you see Kyiv isn't under alarm yet so why put a drone icon here, it's dangerous".
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import chanpost  # noqa: E402
import geo  # noqa: E402

AF = "🛵 Реактивний БпЛА на сході Київщини, в напрямку столиці."


def one(text, ch="kpszsu"):
    ms = geo.parse_for_channel(ch, text)
    assert len(ms) == 1, ms
    return geo._city_settle(ms[0])


def test_in_the_east_of_kyiv_oblast_heading_for_the_capital_is_in_the_east_not_on_kyiv():
    m = one(AF)
    pos = m["evidence"]["position"]
    assert m["place"] == "область" and m["oblast_uid"] == "14" and pos["quad"] == "e" and pos["confidence"] == "low"
    assert not m.get("approach") and m["lon"] > 31.0                    # east of Kyiv, not on it
    assert m["target"] == "Київ"                                         # the capital is a course to Kyiv
    assert 270 <= m["heading"] <= 320                                    # toward Kyiv: west-north-west, never east
    assert m["evidence"]["heading"]["confidence"] == "medium"


def test_the_side_is_never_read_as_the_course():
    m = one("БпЛА на півночі Київщини, курсом на Київ")
    assert m["evidence"]["position"]["quad"] == "n" and 140 <= m["heading"] <= 200
    m = one("БпЛА на сході Київщини курсом на захід")
    assert m["evidence"]["position"]["quad"] == "e" and m["heading"] == 270


def test_only_a_destination_is_still_an_approach():
    assert one("БпЛА на Київ")["place"] == "→ Київ"
    assert one("Київщина: БпЛА на Васильків з північного заходу")["place"] == "→ Васильків"     # an oblast as a header
    assert one("Чернігівщина: 3 реакти на Славутич з півночі")["place"] == "→ Славутич"


def test_the_channel_posts_it_as_the_part_of_the_oblast():
    m = dict(one(AF), channel="kpszsu", ts="2026-10-12T23:38:00+00:00", history=[])
    assert not chanpost.eligible(m)                         # 1.58.9: the channel's one source is @chyste_nebo
    m["channel"] = "chyste_nebo"
    assert chanpost.eligible(m) and chanpost.place_text(m) == "Схід Київщини"
    cap = chanpost.caption(m, None, "https://kyiv-air-watch-gb.fly.dev")
    assert "· Схід Київщини" in cap and "📍 Точного місця в дописі немає — лише частина області" in cap
    assert "➡️ Курс на Київ (так у дописі)" in cap and "Де саме зараз" not in cap
    assert not chanpost.eligible(dict(m, evidence={"position": {}}))      # the oblast with no part named: not posted
    got = []

    class Rec:
        def render(self, m, active, when, ray=True, missiles=(), others=()):
            got.append((m["place"], m.get("_area_km"), ray))
            return b"jpg"
    p = chanpost.ChannelPoster(object(), "x", "-1", "https://h", api=object(), shot=Rec(), log=lambda *a: None, kv=False)
    p.picture(m, [])
    assert got == [("Схід Київщини", chanpost.AREA_KM, True)]          # an area round it, and its stated course


def test_the_picture_draws_the_area():
    import pytest
    pytest.importorskip("PIL")
    import mapshot
    m = dict(one(AF), place="Схід Київщини", _area_km=chanpost.AREA_KM, history=[])
    assert mapshot.MapShot().render(m, [], "02:38")[:3] == b"\xff\xd8\xff"
