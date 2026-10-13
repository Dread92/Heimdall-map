"""1.58.5 — the channel's picture shows where the target is in the oblast, and what else is in the sky.

The owner, of a post with a target "→ Переяслав" alone on fields: "not bad but the map isn't zoomed out enough, we get
no situational awareness from this screenshot". Kyiv is now always in the picture (90 km of the oblast at least, the
whole city for a target in it, up to 220 km), and the other targets of the moment are drawn too, smaller and fainter.
1.58.7, the owner: "it needs to be zoomed as it was before, but mark the name of the villages" — the closer view is back
(tests/test_channel_1587.py); the other targets stay.
"""
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import mapshot  # noqa: E402
from test_chanpost_158 import T0, mark, poster  # noqa: E402

PIL = pytest.importorskip("PIL")


def test_the_other_targets_are_drawn_beside_the_one_the_post_is_about():
    shot = mapshot.MapShot()
    m = mark(place="Бровари")
    others = [mark(place="Обухів", lon=30.95, lat=50.35, tag="#2"), mark(place="Васильків", lon=30.6, lat=50.58, tag="#3")]
    calls = []
    real = shot._glyph
    shot._glyph = lambda d, o, here, sc, alpha=255, drone_like=False: (calls.append((o["place"], round(sc / mapshot.SS, 1), alpha)),
                                                                       real(d, o, here, sc, alpha, drone_like))
    assert shot.render(m, [], "21:40", others=others)[:3] == b"\xff\xd8\xff"
    o, g = mapshot.OTHER_SC, mapshot.GLYPH_SC                  # 1.58.7: both smaller ("the Shahed is far too big")
    assert ("Обухів", o, 175) in calls and ("Васильків", o, 175) in calls and ("Бровари", g, 255) == calls[-1]


def test_the_channel_hands_the_picture_the_other_targets_of_the_moment():
    got = []

    class Rec:
        def render(self, m, active, when, ray=True, missiles=(), others=()):
            got.append((m["place"], sorted(o["place"] for o in others)))
            return b"jpg"
    p, st = poster(shot=Rec())
    st.marks = [mark(place="Бровари", tag="#1", t=T0), mark(place="Обухів", lon=30.62, lat=50.11, tag="#2", t=T0 - 60),
                mark(place="Ірпінь", uid="25", tag="#9", t=T0)]                 # another oblast: not the channel's
    p.tick()
    assert ("Бровари", ["Обухів"]) in got and ("Обухів", ["Бровари"]) in got
    assert all("Ірпінь" not in o for _, o in got)


def test_town_names_move_aside_rather_than_vanish_under_a_target():
    src = open(os.path.join(ROOT, "app", "mapshot.py"), encoding="utf-8").read()
    assert 'for dx, dy, an in ((gg, 0, "lm"), (-gg, 0, "rm"), (0, -gg, "mb"), (0, gg, "mt"))' in src
