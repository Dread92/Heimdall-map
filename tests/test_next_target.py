"""1.41.3: "1 знищено.\nНаступний Нивки" is one target destroyed (where, it does not say) and the next one at Nyvky.
Read as one sentence it was a confirmed shoot-down at Nyvky, kept 24 hours in the history layer (@eRadarrua,
6 Oct 2026, 05:45). The post is kept verbatim."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402

POST = "1 знищено.\nНаступний Нивки"


def _seen(ch, t):
    return [(m["type"], m.get("status"), m.get("place"), bool(m.get("needs_context"))) for m in geo.parse_for_channel(ch, t)]


def test_the_shoot_down_is_not_placed_where_the_next_target_is():
    for ch in ("eRadarrua", "kyiv_airdef", "chyste_nebo"):
        for typ, status, place, _ in _seen(ch, POST):
            assert not (status and place and "Нивки" in place), (ch, typ, status, place)


def test_the_next_target_is_a_position():
    assert ("unknown", None, "Нивки", False) in _seen("eRadarrua", POST)
    assert _seen("kyiv_airdef", POST) == [("drones", "down", None, True), ("unknown", None, "Нивки", False)]
    assert _seen("kyiv_airdef", "Збили. Другий на Бровари")[0] == ("drones", "down", None, True)


def test_a_second_target_without_an_outcome_and_a_placed_outcome_are_unchanged():
    assert _seen("kyiv_airdef", "Від Славутича другий йде") == [("unknown", None, "Славутич", False)]
    assert _seen("kyiv_airdef", "Знищено над Троєщиною")[0][1:3] == ("down", "Троєщина")
