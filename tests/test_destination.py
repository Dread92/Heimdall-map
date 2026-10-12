"""Where a target IS and where it is GOING are two different places.

25 Sep 2026, 21:06: "🏍 Київщина: реактивний БпЛА на Васильків з північного заходу" — a jet drone north-west of
Vasylkiv, on its way in. The map drew it ON Vasylkiv, turned south-east, with its course ray pointing on past the
town: a drone that had already gone through. The same evening @kyiv_airdef's "Від Глевахи два на Васильків" was
drawn at Vasylkiv too, while they were still at Hlevakha.

"на X", "в район X", "до X", "в напрямку X": where it is going. "від X", "з X", "повз X", "над X": where it is.
A place after "на" in the locative ("на Позняках") says where it is.
"""
from datetime import datetime, timedelta, timezone

import geo
import server


def one(channel, text):
    ms = geo.parse_for_channel(channel, text)
    assert len(ms) == 1, ms
    return ms[0]


def test_heading_for_a_town_from_a_side_is_an_approach_not_a_position():
    m = one("kpszsu", "🏍 Київщина: реактивний БпЛА на Васильків з північного заходу.")
    assert m["approach"] is True and m["place"] == "→ Васильків" and m["target"] == "Васильків"
    assert m["heading"] == 135                                    # coming from the north-west: flying south-east
    assert m["evidence"]["position"]["confidence"] == "low"


def test_from_the_north_after_the_destination_is_not_the_course():
    """"з півночі" after "курсом на Вишгород" says where it comes from; it was read as "flying north"."""
    m = one("kpszsu", "🏍 Київщина: реактивні БпЛА курсом на Вишгород/Київ з півночі.")
    assert m["heading"] == 180 and m["approach"] is True


def test_the_oblast_heading_of_a_post_is_not_a_position_when_a_town_in_it_is_named():
    m = one("kpszsu", "🏍 Дніпропетровщина: реактивний БпЛА курсом на Кам'янське.")
    assert m["place"] == "→ Кам'янське"
    # another oblast named as the origin still places it there
    assert one("war_monitor", "БпЛА з Чернігівщини курсом на Київ")["place"] == "область"


def test_from_a_to_b_on_a_live_channel_is_at_a_heading_for_b():
    m = one("kyiv_airdef", "Від Глевахи два на Васильків")
    assert m["place"] == "Глеваха" and m["target"] == "Васильків" and not m["approach"]
    assert 150 <= m["heading"] <= 200                             # Hlevakha → Vasylkiv is southward
    m = one("kyiv_airdef", "Від Васильків на Макарів йде")
    assert m["place"] == "Васильків" and m["target"] == "Макарів"


def test_only_a_destination_on_a_live_channel_is_marked_as_such():
    for text in ("Два керованих йдуть на Васильків", "В район Василькова йде", "БпЛА на Бориспіль✈️"):
        m = one("kyiv_airdef", text)
        assert m["dest_only"] and m["approach"] and m["place"].startswith("→ "), text


def test_a_place_in_the_locative_after_na_is_where_it_is():
    assert one("kyiv_airdef", "на Позняках")["place"] == "Позняки"
    assert one("kyiv_airdef", "Васильків над вами")["place"] == "Васильків"
    assert one("eRadarrua", "🛵Повз Кагарлик на Васильків")["place"] == "Кагарлик"


def _state(posts):
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    # post ids unique to the test: parsed posts are cached by id
    tag = str(abs(hash(tuple(posts))))[:8]
    st.store.add_feed([{"post_id": f"{ch}/{tag}{i}", "channel": ch, "ts": (now - timedelta(minutes=ago)).isoformat(),
                        "text": text, "tags": ["drones"]} for i, (ch, ago, text) in enumerate(posts)])
    return st


def test_a_live_destination_keeps_the_target_where_the_channel_last_saw_it():
    st = _state([("kyiv_airdef", 3, "Глеваха"), ("kyiv_airdef", 2, "Два на Васильків")])
    live = [m for m in st.markers() if not m.get("status")]
    assert len(live) == 1
    m = live[0]
    assert m["place"] == "Глеваха" and not m.get("approach")
    assert 150 <= m["heading"] <= 200


def test_a_later_heading_for_post_turns_the_track_instead_of_moving_it():
    st = _state([("kyiv_airdef", 4, "✈️Глеваха"),
                 ("kpszsu", 2, "🏍 Київщина: реактивний БпЛА на Васильків з північного заходу.")])
    live = [m for m in st.markers() if not m.get("status")]
    assert [m["place"] for m in live] == ["Глеваха"]               # still where it was seen, not on Vasylkiv
    assert live[0]["target"] == "Васильків"


def test_the_map_never_moves_a_destination_on_or_counts_down_to_it():
    page = open(server.os.path.join(server.ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    assert "||m.approach) return [x0,y0,x0,y0]" in page             # no dead reckoning from a destination
    assert "m.stale||m.approach) return null" in page               # no ETA
    assert "&&!appr){ // reported heading" in page                 # no course ray ahead of it
    light = open(server.os.path.join(server.ROOT, "static", "light.html"), encoding="utf-8").read()
    assert "d>1&&!m.approach" in light


def test_a_destination_is_given_only_to_a_report_of_the_same_weapon():
    # 1.58: "Балістика на Київ!" 20 s after "Шахед Княжичі" had put the ballistic missile on the drone's village
    st = _state([("kyiv_airdef", 3, "Шахед Княжичі, курсом на Київ"), ("kyiv_airdef", 2, "Балістика на Київ!")])
    bal = [m for m in st.markers() if m.get("type") == "ballistic_missiles" and not m.get("status")]
    assert len(bal) == 1 and bal[0]["place"] == "→ Київ" and bal[0].get("approach")
    assert server.same_weapon({"type": "drones"}, {"type": "unknown"})
    assert not server.same_weapon({"type": "ballistic_missiles"}, {"type": "drones"})
