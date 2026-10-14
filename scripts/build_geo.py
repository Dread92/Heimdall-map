"""Build the two small geography files the app needs to respect raions.

    python scripts/build_geo.py [regions.json]

data/ua_regions.json — for the server. The official «Повітряна тривога» data (api.ukrainealarm.com, or the
    keyless siren.pp.ua proxy of it) names a raion or a hromada by a numeric id and nothing else: no oblast, no
    parent. This table turns that id into the oblast, the parent raion and the key of the raion's shape on the
    map, so an alert over one raion is drawn over that raion and not over the whole oblast.

static/light-map.json — for the light page. The raion outlines of Kyiv, Kyiv oblast and the oblasts around it
    (to work out, on the phone, which raion a saved place is in — the place itself is never sent), the oblast
    outlines, and the rivers, roads and towns the full map already draws, for the small map under the radar.

The regions file is https://siren.pp.ua/api/v3/regions (the same list as api.ukrainealarm.com/api/v3/regions).
Without an argument it is downloaded. Administrative boundaries change rarely; rebuild after a reform.
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

SCOPE = ["31", "14", "10", "25", "20", "19", "24", "4",   # Kyiv, Kyiv oblast and the oblasts around it
         "18", "22", "9",                                  # 1.43: Odesa, Kharkiv, Dnipro — each with a tracker of its own
         "17",                                             # 1.44: Mykolaiv
         "23", "15", "3", "21", "5", "27", "8"]            # 1.45: Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne, Lviv, Volyn

TR = {"а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y",
      "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
      "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu",
      "я": "ia", "'": "", "ʼ": "", "’": ""}


def translit(s):
    out = []
    for i, c in enumerate(s.lower()):
        if i == 0 and c in "єїйюя":
            out.append({"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}[c])
        else:
            out.append(TR.get(c, c))
    return "".join(out)


# raions renamed since the map's outlines were drawn: the official name → the outline's key
RENAMED = {"samarivskyi": "novomoskovskyi"}


def key_of(name):
    return re.sub(r"[^a-z]", "", translit(re.sub(r"\s*район\s*$", "", name.strip(), flags=re.I)))


def load_regions(path):
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request("https://siren.pp.ua/api/v3/regions", headers={"User-Agent": "heimdall-build"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def build_regions(regions, kmap):
    # the server's own oblast-name matcher, so the two can never disagree
    from server import OBLASTS, norm_uk

    feats = kmap["features"]
    by_obl = {}
    for f in feats:
        by_obl.setdefault(f["obl"], []).append(f)

    def shape_key(f):
        # Kyiv oblast raions are keyed by f.raion on the map (the Chornobyl zone shares Vyshhorod's), the rest by f.key
        return f["raion"] if f["obl"] == "14" and f.get("raion") else f["key"]

    states, districts, communities, unmatched, ignore = {}, {}, {}, [], []
    for st in regions["states"]:
        uid = norm_uk(st["regionName"])
        city = re.match(r"м\.\s*(\S+?)\s+та\s", st["regionName"])
        if city and not uid:
            # "м. Харків та Харківська територіальна громада": a city listed at the top level. It is a hromada
            # of its oblast, not the oblast — an alert over it must not paint the oblast around it.
            stem = city.group(1).lower()[:5]
            uid = next((u for u, uk, _ in OBLASTS if uk.lower().startswith(stem)), None)
            if uid:
                communities[st["regionId"]] = {"name": st["regionName"], "d": None, "obl": uid}
                continue
        if not uid:
            if "тестов" in st["regionName"].lower():
                ignore.append(st["regionId"])   # the API's own test region
            else:
                unmatched.append(("state", st["regionName"]))
            continue
        states[st["regionId"]] = uid
        for d in st.get("regionChildIds") or []:
            if d.get("regionType") == "District":
                k = key_of(d["regionName"])
                k = RENAMED.get(k, k)
                shape = None
                for f in by_obl.get(uid, []):
                    if f["key"] == k or (f.get("stem") and re.search(f["stem"], d["regionName"].lower())):
                        shape = shape_key(f)
                        break
                if shape is None and uid in SCOPE and uid != "31":
                    unmatched.append(("district", d["regionName"]))
                districts[d["regionId"]] = {"name": d["regionName"], "obl": uid, "key": shape}
                for c in d.get("regionChildIds") or []:
                    communities[c["regionId"]] = {"name": c["regionName"], "d": d["regionId"]}
            elif d.get("regionType") == "Community":   # a hromada straight under the oblast (none today)
                communities[d["regionId"]] = {"name": d["regionName"], "d": None, "obl": uid}
    return {"_about": "built by scripts/build_geo.py from the ukrainealarm region list — id → oblast / raion / map shape",
            "states": states, "districts": districts, "communities": communities, "ignore": ignore}, unmatched


def parse_path(d):
    rings = []
    for sub in re.split(r"(?=M)", d):
        pts = [tuple(map(float, p.split(","))) for p in re.findall(r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", sub)]
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def simplify(pts, tol):
    """Douglas–Peucker on one closed ring, in km."""
    if len(pts) < 5:
        return pts
    keep = [False] * len(pts)
    # a closed ring starts and ends on the same point, so the first chord has no length: anchor it on the
    # point farthest from the start as well, and simplify the two halves
    x0, y0 = pts[0]
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - x0) ** 2 + (pts[i][1] - y0) ** 2)
    keep[0] = keep[-1] = keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        L = (dx * dx + dy * dy) ** 0.5 or 1e-9
        best, bi = 0.0, -1
        for i in range(a + 1, b):
            x0, y0 = pts[i]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / L
            if d > best:
                best, bi = d, i
        if best > tol and bi > 0:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def flat(rings, tol):
    out = []
    for r in rings:
        s = simplify(r, tol)
        if len(s) >= 3:
            out.append([round(v, 1) for p in s for v in p])
    return out


def js_const(html, name):
    """The array literal assigned to `const NAME=` in the full page, as JSON."""
    i = html.index(f"const {name}=[") + len(f"const {name}=")
    depth, j = 0, i
    while True:
        c = html[j]
        depth += c == "["
        depth -= c == "]"
        j += 1
        if depth == 0:
            break
    return json.loads(html[i:j].replace("'", '"'))


def build_light_map(kmap, uar, html):
    shape_ids = {}
    for rid, d in uar["districts"].items():
        if d["key"]:
            shape_ids.setdefault((d["obl"], d["key"]), rid)
    raions, far = [], []
    for f in kmap["features"]:
        if f["obl"] not in SCOPE:
            continue
        k = f["raion"] if f["obl"] == "14" and f.get("raion") else f["key"]
        rid = shape_ids.get((f["obl"], k))
        uk = uar["districts"][rid]["name"] if rid else None
        # 1.43: the oblasts farther out go to a second file the Light page fetches only for a place there — the page
        # and its map data must stay small enough for a phone on 2G
        (raions if f["obl"] in SCOPE[:8] else far).append(
            {"k": k, "id": rid, "obl": f["obl"], "en": f["name"], "uk": uk, "p": flat(parse_path(f["path"]), 0.3)})
    build_light_map.far = {"_about": "built by scripts/build_geo.py — the raions of the oblasts farther out (1.43), "
                                     "fetched by the Light page only for a place in one of them", "raions": far}
    # oblast outlines: the scope and every oblast a 60 km circle around a place in it can reach into
    near = set(SCOPE[:8]) | {"15", "22", "5", "3", "18"}
    oblasts = [{"uid": o["uid"], "p": flat(parse_path(o["path"]), 1.0)} for o in kmap["oblasts"] if o["uid"] in near]
    towns = [t for t in js_const(html, "TOWNS") if len(t) < 4 or t[3] in (1, 2)]
    seen, tw = set(), []
    for t in towns:
        if t[0] not in seen:
            seen.add(t[0])
            tw.append(t)
    return {"_about": "built by scripts/build_geo.py — geoBoundaries raions/oblasts (CC BY), towns/rivers/roads from the full map",
            "license": kmap.get("license"), "center": kmap["center"], "kx": kmap["kx"], "ky": kmap["ky"],
            "raions": raions, "oblasts": oblasts, "rivers": js_const(html, "RIV"), "roads": [r[1] for r in js_const(html, "ROADS")],
            "ring": js_const(html, "RING"), "towns": tw}


def main():
    """`--light` rebuilds only static/light-map.json, from the data/ua_regions.json already in the repository."""
    light_only = "--light" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--light"]
    with open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8") as f:
        kmap = json.load(f)
    with open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8") as f:
        html = f.read()
    if light_only:
        with open(os.path.join(ROOT, "data", "ua_regions.json"), encoding="utf-8") as f:
            uar, unmatched = json.load(f), []
    else:
        uar, unmatched = build_regions(load_regions(args[0] if args else None), kmap)
    if unmatched:
        print("unmatched:", unmatched)
    lm = build_light_map(kmap, uar, html)
    missing = [r["en"] for r in lm["raions"] if not r["id"] and r["obl"] != "31"]
    if missing:
        print("raion shapes without an official id:", missing)
    if not light_only:
        with open(os.path.join(ROOT, "data", "ua_regions.json"), "w", encoding="utf-8") as f:
            json.dump(uar, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    with open(os.path.join(ROOT, "static", "light-map.json"), "w", encoding="utf-8") as f:
        json.dump(lm, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(ROOT, "static", "light-map-x.json"), "w", encoding="utf-8") as f:
        json.dump(build_light_map.far, f, ensure_ascii=False, separators=(",", ":"))
    print(f"ua_regions.json: {len(uar['states'])} oblasts, {len(uar['districts'])} raions, {len(uar['communities'])} hromadas")
    print(f"light-map.json: {len(lm['raions'])} raions, {len(lm['oblasts'])} oblasts, {len(lm['towns'])} towns")


if __name__ == "__main__":
    main()
