"""1.58.41 — a target heading for Kyiv, from a side the post named, is drawn outside the city on that side.

The owner, of "Реактивний БпЛА курсом на Київ з півночі" drawn over Podil: "it says heading to Kyiv, from the north,
and yet the icon is placed right inside the city". 1.51 stood an approach mark off its town by 30 px on the screen —
enough for a town, not for a city 20-40 km across. Now the server says how far out the city ends on that side
(`off_km`: Kyiv's outline + 1.5 km) and the Tactical page, Light and the bot's picture draw it at least that far.
Nothing is invented: the side is the post's, the distance is the city's own outline; where it is was still not said,
and its position (`lon`, `lat`) stays the destination for the alerts, the tracks and the lists.
"""
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import areas  # noqa: E402
import geo  # noqa: E402
import server  # noqa: E402

TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
SHOT = open(os.path.join(ROOT, "app", "mapshot.py"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
POST = "Реактивний БпЛА курсом на Київ з півночі."


def _state():
    return server.State(server.Store(":memory:"), {})


def _at(lon, lat, bearing, km):
    a = math.radians(bearing)
    return lon + km * math.sin(a) / areas._BASE["kx"], lat + km * math.cos(a) / areas._BASE["ky"]


def test_the_citys_edge_on_each_side():
    want = {0: 10.1, 45: 21.7, 90: 16.9, 135: 14.5, 180: 14.2, 225: 9.4, 270: 19.7, 315: 19.1}
    for b, km in want.items():
        e = areas.edge_km(30.52, 50.45, b)
        assert abs(e - km) < 0.3, (b, e)
        assert areas.area_at(*_at(30.52, 50.45, b, e - 0.5)) == ("31", "kyiv-city")         # just inside
        assert areas.area_at(*_at(30.52, 50.45, b, e + 1.5))[1] != "kyiv-city"             # where it is drawn


def test_not_inside_the_city_nothing_to_measure():
    assert areas.edge_km(30.79, 50.51, 0) is None                                          # Brovary
    assert areas.edge_km(None, 50.45, 0) is None and areas.edge_km(30.52, 50.45, None) is None


def test_the_post_the_owner_showed_stands_north_of_the_city():
    ms = geo.parse_for_channel("kyiv_airdef", POST)
    assert len(ms) == 1 and ms[0]["approach"] and ms[0]["place"] == "→ Київ" and ms[0]["heading"] == 180
    _state()._approach_edge(ms)
    m = ms[0]
    assert abs(m["off_km"] - 11.6) < 0.3
    a = math.radians(m["heading"])
    lon, lat = m["lon"] - m["off_km"] * math.sin(a) / areas._BASE["kx"], m["lat"] - m["off_km"] * math.cos(a) / areas._BASE["ky"]
    assert lat > m["lat"] and areas.area_at(lon, lat) == ("14", "vyshhorod")              # north, outside the city
    assert (m["lon"], m["lat"]) == (30.52, 50.45)                                          # its position is unchanged


def test_only_an_approach_to_the_city_with_a_side():
    st = _state()
    ap = dict(type="drones", place="→ Київ", target="Київ", lon=30.52, lat=50.45, oblast_uid="31", approach=True,
              heading=90)
    cases = [dict(ap, heading=None),                                                        # no side: as before
             dict(ap, status="down"),                                                       # an outcome is where it was
             dict(ap, approach=False, place="Київ"),                                        # where it IS
             dict(ap, place="→ Оболонь", target="Оболонь", lon=30.50, lat=50.51),           # a district: in the city
             dict(ap, place="→ Бровари", target="Бровари", lon=30.79, lat=50.51, oblast_uid="14")]
    st._approach_edge(cases)
    assert not [m for m in cases if "off_km" in m]
    m = dict(ap, off_km=99.0)
    st._approach_edge([m])
    assert abs(m["off_km"] - (19.7 + 1.5)) < 0.3                                           # flying east, from the west
    m = dict(ap, dest_only=True, approach=False, off_km=3.0, heading=None)
    st._approach_edge([m])
    assert "off_km" not in m                                                                # a stale value never stays


def test_it_runs_on_every_pass_after_the_hold():
    assert "self._hold(out)\n        self._approach_edge(out)\n        out.sort(" in SRV
    assert "APPROACH_MARGIN_KM = 1.5" in SRV


def test_the_pages_and_the_picture_draw_it_at_least_that_far():
    assert "D=Math.max(Math.min(30*MSK,12),+m.off_km||0)" in TAC
    assert "if(m.approach&&statedCourse(m)&&+m.off_km>0){" in LIGHT
    assert 'max(min(60 * SS, 12 * k), float(m.get("off_km") or 0) * k)' in SHOT


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.41" in s and "off_km" in s, doc
    assert "## 1.58.41" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()


def test_from_a_side_is_a_course_the_other_way_wherever_it_is_written():
    # found while checking the owner's report: before "курсом" the compass word was the course (since 1.0), and "із"
    # was no "from" — both drew the target on the wrong side, pointing away
    for text, h in (("Реактивний БпЛА курсом на Київ з півночі.", 180), ("Реактивний БпЛА з півночі курсом на Київ.", 180),
                    ("Реактивний БпЛА із півночі курсом на Київ.", 180), ("Шахед курсом на Київ із заходу.", 90),
                    ("Шахед зі сходу на Київ.", 270), ("Шахед з північного заходу на Бровари.", 135),
                    ("Група шахедів на Бровари, заходять із півночі", 180), ("Шахед на південь курсом на Обухів", 180)):
        ms = geo.parse_for_channel("kpszsu", text)
        assert len(ms) == 1 and ms[0]["heading"] == h, (text, ms[0].get("heading"))
    assert geo.stated_origin("Шахед курсом на Київ із заходу.")["o"] == "w"
    m = geo.parse_for_channel("kpszsu", "Реактивний БпЛА з півночі курсом на Київ.")
    _state()._approach_edge(m)
    assert abs(m[0]["off_km"] - 11.6) < 0.3                                                 # north of the city, as said


def test_the_kyiv_hpp_dam_is_a_hreblia():
    # the owner: "«Гребля» is the actual hydro-dam holding back the reservoir, «Дамба» just a protective embankment"
    i18n = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
    assert "br_ges:'Гребля Київської ГЕС'" in i18n and "br_ges:'Kyiv HPP Dam'" in i18n
    assert "'Kyiv HPP Dam':'гребля Київської ГЕС'" in i18n and "Дамба" not in i18n
    assert "ges:'Гребля Київської ГЕС'" in TAC and "['pow','Kyiv HPP Dam',30.5123,50.5883]" in TAC
    b = next(x for x in server.BRIDGES if x["id"] == "ges")
    assert (b["uk"], b["en"]) == ("Гребля Київської ГЕС", "Kyiv HPP Dam") and "Гребля Київської ГЕС" in geo.PLACES
    assert "Дамба Київської ГЕС" not in geo.PLACES
    assert server.BRIDGE_BY_PLACE["Дамба Київської ГЕС"] == "ges"                       # older records still name it
    assert [m["place"] for m in geo.parse_for_channel("kyiv_airdef", "дамба ГЕС")] == ["Гребля Київської ГЕС"]
