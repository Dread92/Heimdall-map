"""Build data/extra_places.json — the villages of Kyiv oblast, for the AI reader alone (1.52).

    python scripts/build_extra_places.py [UA.txt alternatenames-UA.txt]

The rules read Kyiv oblast through the core gazetteer in app/geo.py (its towns and the places the Kyiv trackers name),
deliberately not through every village: "Іванівка" from a Kyiv channel is nothing. But the trackers do name small
villages — "На Сомкова Долина", "Один … на Фарбоване", "З зони на Романівку" (@chyste_nebo, 9 Oct) — and the AI reader
could not place them: it may only name a place the server offers it. This file holds every populated place of Kyiv
oblast with its Ukrainian name (named as scripts/build_places.py names them) and its raion; app/ai_reader.py offers
those whose name the post's words match (spelling slips included) as CANDIDATES. The rules never read this file.

From GeoNames' Ukraine dumps (https://download.geonames.org/export/dump/UA.zip and .../alternatenames/UA.zip,
CC BY 4.0 — downloaded when no files are given). Each entry: [Ukrainian name, lon, lat, raion].
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_places as bp  # noqa: E402  (the same GeoNames reading and the same names)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN1 = {"13": "14"}               # GeoNames admin1 → the app's oblast uid: Kyiv oblast
RAION = {"3202": "Білоцерківський р-н", "3204": "Бориспільський р-н", "3206": "Броварський р-н",
         "3208": "Бучанський р-н", "3210": "Вишгородський р-н", "3212": "Обухівський р-н", "3214": "Фастівський р-н"}


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
        places[r[0]] = {"en": r[1], "lat": float(r[4]), "lon": float(r[5]), "a2": r[11], "uk": []}
    for r in bp.rows(alt_txt):
        p = places.get(r[1])
        if not p or r[2] != "uk" or r[7] == "1":
            continue
        name = r[3].strip()
        if bp.CYR.match(name):
            p["uk"].append((name, r[4] == "1"))
    out = []
    for gid, p in places.items():
        uk = [n for n, pref in sorted(p["uk"], key=lambda x: not x[1]) if not bp.RU_ONLY.search(n)]
        uk.sort(key=lambda n: bool(bp.SOVIET.search(n)))
        if not uk:
            continue
        out.append([uk[0], round(p["lon"], 4), round(p["lat"], 4), RAION.get(p["a2"], "")])
    out.sort()
    doc = {"_about": "built by scripts/build_extra_places.py from GeoNames (CC BY 4.0, geonames.org): the populated places "
                     "of Kyiv oblast, offered to the AI reader alone — [Ukrainian name, lon, lat, raion]",
           "oblasts": {"14": out}}
    path = os.path.join(ROOT, "data", "extra_places.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(path, len(out), "places,", os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
