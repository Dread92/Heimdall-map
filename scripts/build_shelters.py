"""Build `static/shelters.json`: the shelters Kyiv city lists, for the phone to find the nearest ones itself.

1.57, the owner's colleague: "a layer of the official shelters — only the government's data: metro, official shelters,
underpasses — baked into the app, so finding the nearest one works offline". The owner chose every shelter the city
lists, each labelled with what it is. The source is the city's own shelter map (https://gis.kyivcity.gov.ua/shelter/,
KMDA, ІАС «Майно»), layer `public_protection/Укриття_редактор`, the records it shows (`actual = 1`).

The city's firewall refuses a script, so the file is saved from a browser (the link is in docs/TECHNICAL.md, §10.7)
and turned into the app's file here:

    python scripts/build_shelters.py imagery/shelters-kyiv.json [--asof YYYY-MM-DD]

Nothing is invented: a record keeps the city's address, hours, phone and note as written; its category and kind are
read from the city's own "Тип укриття" and "Вид укриття" (`classify`), and a pair the rules do not know is a
"simplest shelter" of no stated kind — never ranked higher than the city ranked it — and listed at the end so the
rules can be taught it.

What the file holds (compact JSON, version `FORMAT`): `asof` (the day the city's data was saved), `src`, `url`, `n`,
`cat` and `kind` (the names the indices below stand for) and `s`, the shelters:
`[lon, lat, category, kind, ramp (1 or 0), address, access, phone, note]` — access is `_access`'s code: "" round the clock,
"?" not stated, "s" a school's, for its pupils and staff during the school day, "S" for them only, "r" under repair,
or the hours as written.
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "shelters.json")
FORMAT = 1
SRC = "КМДА · ІАС «Майно» — мапа укриттів Києва"
URL = "https://gis.kyivcity.gov.ua/shelter/"
# what the shelter is, strongest first; the first three are what the colleague's rule kept ("metro, underpasses and
# the official shelters") and what the pages call a shelter of the strong kind
CATS = ["metro", "underpass", "shelter", "dual", "simple", "mobile"]
KINDS = ["", "station", "entrance", "underpass", "pru", "basement", "semib", "ground", "parking", "school", "building"]
BBOX = (30.1, 50.1, 31.0, 50.7)          # Kyiv city and a margin: a point outside is a mistake in the record


def _kind(k):
    """The kind of room, from the city's "Вид укриття"."""
    k = (k or "").lower()
    if "метро" in k:
        return "entrance" if "вхід" in k else "station"
    if "перехід" in k:
        return "underpass"
    if "пру" in k:
        return "pru"
    if "паркінг" in k:
        return "parking"
    if "цоколь" in k:
        return "semib"
    if "підвал" in k:
        return "basement"
    if "поверх" in k:
        return "ground"
    if "школа" in k or "освіти" in k:
        return "school"
    if "будівля" in k:
        return "building"
    return ""


def classify(typ, kind):
    """(category, kind, known) for the city's "Тип укриття" and "Вид укриття"."""
    t = (typ or "").strip().lower()
    k = _kind(kind)
    if k in ("station", "entrance") or "метро" in t:
        return "metro", k or "station", True
    if k == "underpass":
        return "underpass", "underpass", True
    if t == "укриття" or "пру" in t:
        return "shelter", ("pru" if "пру" in t else k if k not in ("", "building") else ""), True
    if "подвійного призначення" in t:
        return "dual", k, True
    if t.startswith("первинне") or "мобільн" in t:
        return "mobile", "", True
    if re.match(r"найпрос\w*т\w*\s+укрит", t):        # "Найпростіше укриття", "Найпростіші …", "Найпросітіше …"
        return "simple", k, True
    if t == "підвал":                     # "Підвал, Багатоквартирний будинок": the kind is the building's
        return "simple", "basement", True
    return "simple", k, False


def _ramp(kind, invalid):
    """A ramp: the kind says "з пандусом", or the city's field "В наявності" / "Наявний" (not "Відсутній")."""
    return 1 if ("пандус" in (kind or "").lower() or re.search(r"(?i)наявн", invalid or "")) else 0


# Who may come in, and when — the city writes it in words, in "Режим роботи" or in the note. A school's shelter is for
# its pupils and staff during the school day (about 570), or for them only (about 510): those words are what the pages
# show, in the reader's language, and a shelter for the school only is never offered as "the nearest".
SCHOOL = re.compile(r"(?i)освітнього\s+процесу")
SCHOOL_DAY = re.compile(r"(?i)навчальн\w*\s+дн|під\s+час\s+здійснення\s+освітнього")
REPAIR = re.compile(r"(?i)ремонт")


def _access(hours, note):
    """(code, hours text, note left): "" round the clock, "?" not stated, "s" for the school's pupils and staff during
    the school day, "S" for them only, "r" under repair (may be closed), or the hours as written ("10:00–18:00")."""
    h = " ".join(re.sub(r"<br\s*/?>", " ", hours or "").split())
    n = " ".join((note or "").split())
    both = h + " " + n
    if REPAIR.search(both):
        return "r", n if n and not REPAIR.search(n) and not SCHOOL.search(n) else ""
    if SCHOOL.search(both):
        return ("s" if SCHOOL_DAY.search(both) else "S"), n if n and not SCHOOL.search(n) else ""
    m = re.search(r"(\d{1,2}[:.]\d{2})\s*(?:[-–—]|до)\s*(\d{1,2}[:.]\d{2})", both)
    if m:                                  # "Цілодобово" and, in the note, "в робочий час з 10:00 до 18:00": the hours
        return f"{m.group(1)}–{m.group(2)}", "" if m.group(0) in n else n
    if not h or h in ("-", "—"):
        return "?", n
    return ("" if re.fullmatch(r"(?i)цілодобово\.?|24/7|24 год(ини)?", h) else h[:60]), n


def _text(v, n):
    v = " ".join(str(v or "").split())
    return "" if v in ("-", "—", "None") else v[:n]


def _rank(h):
    """Who may come in, best first: round the clock, hours, not stated, school day, under repair, the school only."""
    return {"": 0, "?": 2, "s": 3, "r": 4, "S": 5}.get(h, 1)


def records(doc):
    """(attributes, lon, lat) of every feature: the ArcGIS JSON the city's query returns, or GeoJSON."""
    for f in doc.get("features") or []:
        a = f.get("attributes") or f.get("properties") or {}
        g = f.get("geometry") or {}
        if "x" in g:
            lon, lat = g.get("x"), g.get("y")
        elif g.get("type") == "Point":
            lon, lat = (g.get("coordinates") or [None, None])[:2]
        else:
            lon, lat = a.get("long"), a.get("lat")
        yield a, lon, lat


def _name_entrances(out):
    """85 metro entrances are "Вхід в станцію метро" and 25 have no address: name the station whose point is within
    350 m, saying it is the nearest ("біля ст. …"), never as if the city had written it."""
    import math
    m, e = CATS.index("metro"), KINDS.index("entrance")
    st = [(r[0], r[1], q.group(0)) for r in out
          if r[2] == m and r[3] == KINDS.index("station") and (q := re.search(r"[«\"].{2,}", r[5]))]
    for r in out:
        if r[2] != m or r[3] != e or re.search(r"[«\"]", r[5]):
            continue
        k = math.cos(math.radians(r[1])) * 111.32
        best = min(((math.hypot((x - r[0]) * k, (y - r[1]) * 110.57), n) for x, y, n in st), default=None)
        r[5] = f"Вхід у метро — біля ст. {best[1]}" if best and best[0] <= 0.35 else "Вхід у метро"


def build(doc, asof):
    out, seen, unknown, dropped = [], {}, {}, 0
    for a, lon, lat in records(doc):
        if a.get("actual") not in (None, 1, "1"):
            continue
        try:
            lon, lat = float(lon), float(lat)
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            dropped += 1
            continue
        cat, kind, known = classify(a.get("type"), a.get("kind"))
        if not known:
            unknown[(a.get("type"), a.get("kind"))] = unknown.get((a.get("type"), a.get("kind")), 0) + 1
        hours, note = _access(a.get("working_time"), a.get("description"))
        rec = [round(lon, 5), round(lat, 5), CATS.index(cat), KINDS.index(kind), _ramp(a.get("kind"), a.get("invalid")),
               _text(a.get("address"), 80), hours, _text(re.split(r"[,;]", str(a.get("tel") or ""))[0], 24), _text(note, 120)]
        # several shelters of one kind in one building, at one point (374 points in Oct 2026): one point on the map, the
        # one anybody may enter if there is one
        key = (rec[0], rec[1], cat, rec[5])
        if key in seen:
            j = seen[key]
            if _rank(hours) < _rank(out[j][6]):
                out[j] = rec
            continue
        seen[key] = len(out)
        out.append(rec)
    _name_entrances(out)
    out.sort(key=lambda r: (r[2], r[1], r[0]))
    data = {"v": FORMAT, "asof": asof, "src": SRC, "url": URL, "n": len(out), "cat": CATS, "kind": KINDS, "s": out}
    return data, unknown, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", help="the city's query result, saved from a browser")
    ap.add_argument("--asof", help="the day it was saved (default: the file's date)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    with open(a.src, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("error"):
        sys.exit(f"the city's service answered an error: {doc['error']}")
    asof = a.asof or datetime.fromtimestamp(os.path.getmtime(a.src)).date().isoformat()
    date.fromisoformat(asof)
    data, unknown, dropped = build(doc, asof)
    if data["n"] < 1000:
        sys.exit(f"only {data['n']} shelters — not the whole city (a page of the answer?); nothing written")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    by = {c: sum(1 for r in data["s"] if r[2] == i) for i, c in enumerate(CATS)}
    print(f"{data['n']} shelters ({', '.join(f'{c} {n}' for c, n in by.items())}); {dropped} without a usable point; "
          f"{os.path.getsize(a.out):,} bytes → {os.path.relpath(a.out, ROOT)}")
    for (t, k), n in sorted(unknown.items(), key=lambda x: -x[1]):
        print(f"  not known to the rules, kept as a simplest shelter: {t!r}, {k!r} × {n}")


if __name__ == "__main__":
    main()
