"""Build static/towns-ua.json — the towns of every oblast, for finding one's way on the map (1.49).

    python scripts/build_towns.py [UA.txt alternatenames-UA.txt]

The page's own list (TOWNS in static/kyiv.html) has every town of Kyiv oblast and the oblast and regional centres
elsewhere; zoomed out over Kharkiv or Poltava oblast it showed four names in a region the size of Belgium. This file
adds, for all of Ukraine (Kyiv city aside), the raion centres and every town of 10,000 people or more, from GeoNames'
Ukraine dumps (https://download.geonames.org/export/dump/UA.zip and .../alternatenames/UA.zip, CC BY 4.0 —
downloaded when no files are given), named as scripts/build_places.py names them (the Ukrainian name, the curated
and de-Sovietised ones first).

Each entry: [Ukrainian name, lon, lat, population (0 = unknown), tier] — tier 2: an oblast or raion centre, or
20,000 people or more; tier 1: the others. A town within 3 km of one already in TOWNS is left out (it has its name).
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_places as bp  # noqa: E402  (the same GeoNames reading and the same names)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GeoNames admin1 → the app's oblast uid: all of them but Kyiv city (12), which has its own districts map
ADMIN1 = dict(bp.ADMIN1, **{"03": "26", "05": "28", "06": "13", "11": "29", "13": "14", "14": "16", "20": "30",
                            "25": "11", "26": "12"})
MIN_POP = 10000
CENTRES = {"PPLA", "PPLA2"}          # oblast centre, raion centre
# GeoNames' Ukrainian name is wrong or out of date for a few: the official name, by GeoNames id
NAMES = {"700119": "Миколаївка",      # Donetsk oblast (GeoNames: "Миколаїв")
         "704202": "Хрустальний"}     # Krasnyi Luch, renamed in 2016
# city sections GeoNames files as towns
SECTIONS = {"Черемушки", "Масани", "Нові Кодаки"}


def page_towns():
    """[lon, lat] of the towns the page already names (TOWNS in static/kyiv.html)."""
    with open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8") as f:
        s = f.read()
    i = s.index("const TOWNS=[")
    body = s[i:s.index("];", i)]
    return [(float(a), float(b)) for a, b in re.findall(r"\['[^']+',([\d.]+),([\d.]+)", body)]


def km(a, b):
    return math.hypot((a[0] - b[0]) * 111.32 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110.57)


def main():
    if len(sys.argv) >= 3:
        with open(sys.argv[1], encoding="utf-8") as f:
            main_txt = f.read()
        with open(sys.argv[2], encoding="utf-8") as f:
            alt_txt = f.read()
    else:
        main_txt = bp.fetch("https://download.geonames.org/export/dump/UA.zip")
        alt_txt = bp.fetch("https://download.geonames.org/export/dump/alternatenames/UA.zip")
    places = {}
    for r in bp.rows(main_txt):
        if r[6] != "P" or r[7] not in bp.KEEP or r[7] == "PPLX" or r[10] not in ADMIN1:
            continue
        pop = int(r[14] or 0)
        if r[7] not in CENTRES and pop < MIN_POP:
            continue
        places[r[0]] = {"en": r[1], "lat": float(r[4]), "lon": float(r[5]), "code": r[7], "a1": r[10], "pop": pop, "uk": []}
    for r in bp.rows(alt_txt):
        p = places.get(r[1])
        if not p or r[2] != "uk" or r[7] == "1":
            continue
        name = r[3].strip()
        if bp.CYR.match(name):
            p["uk"].append((name, r[4] == "1"))
    have = page_towns()
    out, seen = [], []
    for gid, p in sorted(places.items(), key=lambda kv: -kv[1]["pop"]):
        uid = ADMIN1[p["a1"]]
        cur = bp.CURATED_BY_ID.get(gid) or bp.CURATED_BY_NAME.get((uid, p["en"]))
        uk = [n for n, pref in sorted(p["uk"], key=lambda x: not x[1]) if not bp.RU_ONLY.search(n)]
        uk.sort(key=lambda n: bool(bp.SOVIET.search(n)))
        name = NAMES.get(gid) or (cur[0] if cur else (uk[0] if uk else None))
        if not name or name in SECTIONS:
            continue
        pt = (p["lon"], p["lat"])
        if any(km(pt, h) < 3 for h in have) or any(km(pt, s) < 3 for s in seen):
            continue
        seen.append(pt)
        tier = 2 if p["code"] in CENTRES or p["pop"] >= 20000 else 1
        out.append([name, round(p["lon"], 4), round(p["lat"], 4), p["pop"], tier])
    doc = {"_about": "built by scripts/build_towns.py from GeoNames (CC BY 4.0, geonames.org): the raion centres and the "
                     "towns of 10,000+ of every oblast that static/kyiv.html's TOWNS does not name — "
                     "[Ukrainian name, lon, lat, population (0 = unknown), tier 2 = centre or 20,000+]",
           "towns": out}
    path = os.path.join(ROOT, "static", "towns-ua.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(path, len(out), "towns,", sum(1 for t in out if t[4] == 2), "tier 2,", os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
