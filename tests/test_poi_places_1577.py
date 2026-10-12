"""1.57.7 — the landmarks are where they are, and their names stand beside them.

The owner, with screenshots: "some icons are shown in the wrong place, we need to make sure that it isn't badly placed".
Kyiv oblast's power plants and airfields had been typed rounded to 0.01° (ТЕЦ-6 4.6 km off, in Troieshchyna's flats;
the Bila Tserkva airfield 10 km off), and each name was set 2 km off its icon in map units — 200 px at the street view.
Every point below was checked on the satellite picture (the plant's main building, the dam, the runway).
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import geo  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()

# name → (lon, lat): Global Energy Monitor for the plants, Wikipedia for the dam and the airfields
TRUE = {
    "Boryspil airport": (30.8933, 50.3447),
    "Zhuliany airport": (30.4517, 50.4017),
    "Hostomel airfield": (30.1919, 50.6036),
    "Vasylkiv airbase": (30.3000, 50.2333),
    "Bila Tserkva airfield": (30.0244, 49.7961),
    "Ozerne airbase": (28.7383, 50.1583),
    "Trypillia TPP": (30.7467, 50.1334),
    "Kyiv HPP dam": (30.5123, 50.5883),
    "Kyiv CHP-5": (30.5695, 50.3932),
    "Kyiv CHP-6": (30.6623, 50.5317),
    "Darnytsia TPP": (30.6429, 50.4478),
    "Chornobyl NPP": (30.0994, 51.3892),
}


def km(a, b):
    kx = 111.32 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * kx, (a[1] - b[1]) * 111.32)


def page_pois():
    block = re.search(r"const POIS=\[(.*?)\];", TAC, re.S).group(1)
    return {n: (float(lo), float(la)) for _k, n, lo, la in re.findall(r"\['(\w+)','([^']+)',([\d.]+),([\d.]+)\]", block)}


def test_every_kyiv_oblast_landmark_is_on_its_own_point():
    got = page_pois()
    assert set(got) == set(TRUE)
    for n, p in TRUE.items():
        assert km(got[n], p) < 0.05, (n, got[n], p)


def test_the_points_the_owner_saw_moved_to_the_plants():
    got = page_pois()
    # ТЕЦ-6 had been drawn in the flats of Troieshchyna, ТЕЦ-5 on the Stolychne highway
    assert km((30.60, 50.52), TRUE["Kyiv CHP-6"]) > 4 and km(got["Kyiv CHP-6"], TRUE["Kyiv CHP-6"]) < 0.05
    assert km((30.55, 50.38), TRUE["Kyiv CHP-5"]) > 1.5 and km(got["Kyiv CHP-5"], TRUE["Kyiv CHP-5"]) < 0.05
    # and the Bila Tserkva airfield is west of the town, not east of it
    assert got["Bila Tserkva airfield"][0] < 30.05


def test_a_post_naming_the_plant_marks_the_plant():
    P = geo.PLACES
    assert km(P["ТЕЦ-5"][:2], TRUE["Kyiv CHP-5"]) < 0.05 and P["ТЕЦ-5"][2] == "31"
    assert km(P["ТЕЦ-6"][:2], TRUE["Kyiv CHP-6"]) < 0.05 and P["ТЕЦ-6"][2] == "31"
    assert km(P["Бориспіль аеропорт"][:2], TRUE["Boryspil airport"]) < 0.05
    assert km(P["Жуляни аеропорт"][:2], TRUE["Zhuliany airport"]) < 0.05
    assert km(P["Київська ГЕС"][:2], TRUE["Kyiv HPP dam"]) < 0.05
    # the rules' bare names still find them
    assert [m["place"] for m in geo.parse_for_channel("kyiv_airdef", "ТЕЦ-6")] == ["ТЕЦ-6"]
    assert [m["place"] for m in geo.parse_for_channel("kyiv_airdef", "ТЕЦ-5 уважно")] == ["ТЕЦ-5"]


def test_the_name_stands_on_its_icon_and_is_set_aside_in_pixels():
    # both builders put the label on the icon's own point …
    assert '<text class="poilbl minor" x="${x.toFixed(2)}" y="${y.toFixed(2)}">' in TAC
    assert '<text class="poilbl minor" x="${p.x}" y="${p.y}">' in TAC
    assert "x+2" not in re.search(r"POIS\.map\(.*?\.join\(''\)", TAC, re.S).group(0)
    # … and the CSS moves it aside in screen pixels (--k = km per pixel), as the icon is sized
    css = re.search(r"\.poilbl\{[^}]*\}", TAC).group(0)
    assert re.search(r"transform:translate\(calc\(var\(--k,1\)\*[\d.]+px\),calc\(var\(--k,1\)\*[\d.]+px\)\)", css)


def test_the_country_layer_has_the_south_ukraine_plant_on_its_reactors():
    base = json.load(open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8"))
    c0, c1 = base["center"]
    ua = json.load(open(os.path.join(ROOT, "static", "map-ua.json"), encoding="utf-8"))
    src = open(os.path.join(ROOT, "scripts", "build_mapdata.py"), encoding="utf-8").read()
    rows = {en: (float(lo), float(la)) for en, lo, la in
            re.findall(r'\("\w+", "([^"]+)", "[^"]+", "[^"]+", ([\d.]+), ([\d.]+)\)', src)}
    for p in ua["pois"]:                       # the committed file is the script's list, projected
        lo, la = rows[p["en"]]
        assert abs(p["x"] - (lo - c0) * base["kx"]) < 0.01 and abs(p["y"] + (la - c1) * base["ky"]) < 0.01, p["en"]
    assert km(rows["South Ukraine NPP"], (31.2190, 47.8127)) < 0.05
