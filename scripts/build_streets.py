"""Build `static/streets/<uid>.json`: every settlement and named street of each oblast, from OpenStreetMap.

1.56, the owner: "a complete registry of the streets within the city / the oblast, so the user can set the pin
accurately — all the towns and streets of Ukraine". The phone downloads an oblast's file and searches it itself: what
is typed never leaves the phone (static/streets.js).

Build time only — pyosmium and shapely are not the server's dependencies:

    pip install osmium shapely
    python scripts/build_streets.py DIR [NAME ...]

DIR holds the 27 regional extracts of https://download.openstreetmap.fr/extracts/europe/ukraine/ (`kiev.osm.pbf`,
`kiev_oblast.osm.pbf`, … — `EXTRACTS` below). Data © OpenStreetMap contributors, Open Database License 1.0
(static/streets/LICENSE.md).

What a file holds (compact JSON, version `FORMAT`):
- `t`, the settlements of the oblast — every place=city / town / village / hamlet named in OSM inside the oblast's
  boundary, streets or not: `[name, lon×1e4, lat×1e4, kind (0 city, 1 town, 2 village, 3 hamlet), raion index]`;
- `r`, the raions (admin_level 6) — and for Kyiv the city's districts (admin_level 10);
- `s`, the streets: `[name, settlement index, dx, dy, reach, alias?, district?]` — the street's point (the vertex of its
  ways nearest their centre) as an offset from its settlement in 1e-5 degrees, how far its ways go from that point
  (1e-5 degrees, the larger of the four directions: the map is zoomed to show it), another name it is known by (`old_name`; or the `name` when `name:uk` was used — the Russian one in
  Crimea), and for Kyiv the district its point is in. A street is every named way of a street's kind whose middle is in
  the settlement's boundary (admin_level 9 or a place area), or else nearest its settlement node within that kind's
  reach (`REACH_KM`); ways of one name in one settlement are one street.
"""
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "streets")
FORMAT = 1

EXTRACTS = {"kiev": "31", "kiev_oblast": "14", "cherkasy_oblast": "24", "chernihiv_oblast": "25", "chernivtsi_oblast": "26",
            "crimea": "29", "dnipropetrovsk_oblast": "9", "donetsk_oblast": "28", "ivano-frankivsk_oblast": "13",
            "kharkiv_oblast": "22", "kherson_oblast": "23", "khmelnytskyi_oblast": "3", "kirovohrad_oblast": "15",
            "luhansk_oblast": "16", "lviv_oblast": "27", "mykolaiv_oblast": "17", "odessa_oblast": "18", "poltava_oblast": "19",
            "rivne_oblast": "5", "sevastopol": "30", "sumy_oblast": "20", "ternopil_oblast": "21", "vinnytsia_oblast": "4",
            "volyn_oblast": "8", "zakarpattia_oblast": "11", "zaporizhia_oblast": "12", "zhytomyr_oblast": "10"}
# the oblasts' names as OSM has them (admin_level 4) → the app's uids; the Russian-claimed units are not here
OBLAST_NAMES = {"Автономна Республіка Крим": "29", "Волинська область": "8", "Вінницька область": "4",
                "Дніпропетровська область": "9", "Донецька область": "28", "Житомирська область": "10",
                "Закарпатська область": "11", "Запорізька область": "12", "Івано-Франківська область": "13", "Київ": "31",
                "Київська область": "14", "Кіровоградська область": "15", "Луганська область": "16", "Львівська область": "27",
                "Миколаївська область": "17", "Одеська область": "18", "Полтавська область": "19", "Рівненська область": "5",
                "Севастополь": "30", "Сумська область": "20", "Тернопільська область": "21", "Харківська область": "22",
                "Херсонська область": "23", "Хмельницька область": "3", "Черкаська область": "24", "Чернівецька область": "26",
                "Чернігівська область": "25"}
KINDS = {"city": 0, "town": 1, "village": 2, "hamlet": 3}
REACH_KM = {0: 10.0, 1: 4.0, 2: 2.0, 3: 1.0}      # a street outside any boundary: this near its settlement's node
# the ways a street is: these kinds, named; a track, a path, a service road only when its name is a street's
HIGHWAYS = {"residential", "living_street", "tertiary", "secondary", "primary", "trunk", "unclassified", "pedestrian",
            "road", "tertiary_link", "secondary_link", "primary_link"}
STREET_WORD = re.compile(r"(?i)\b(вулиц|вул\.|провулок|пров\.|проспект|просп\.|бульвар|площа|майдан|узвіз|набережна|шосе|"
                         r"проїзд|тупик|алея|спуск|в['’ʼ]їзд|завулок|лінія|квартал|мікрорайон|улица|переулок|площадь|шоссе|"
                         r"проезд|набережная|тупик)")
ROAD_NAME = re.compile(r"\S\s*[—–]\s*\S|^\s*[MНРТHPTМ]-?\d|\bтраса\b|\bобхід\b|\bобъезд", re.I)


def _name(tags):
    """The Ukrainian name, and another it is known by (or None)."""
    uk, nm, old = tags.get("name:uk"), tags.get("name"), tags.get("old_name")
    name = (uk or nm or "").strip()
    alias = None
    if uk and nm and nm.strip() != uk.strip():
        alias = nm.strip()
    elif old and old.strip() != name:
        alias = old.strip().split(";")[0]
    if alias and re.search(r"[A-Za-z]", alias):        # "Kreschatic": a spelling, not a name people search by
        alias = None
    return name, alias


def build(path, uid):
    import osmium
    import shapely.wkb
    from shapely.geometry import Point
    from shapely.prepared import prep
    from shapely.strtree import STRtree

    wkb = osmium.geom.WKBFactory()

    class H(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.obl, self.raion, self.dist, self.spoly, self.nodes, self.ways = [], [], [], [], [], []

        def node(self, n):
            k = KINDS.get(n.tags.get("place"))
            if k is None:
                return
            name, _ = _name(n.tags)
            if name and n.location.valid():
                self.nodes.append((name, k, n.location.lon, n.location.lat))

        def way(self, w):
            hw = w.tags.get("highway")
            if not hw and w.tags.get("place") != "square":
                return
            name, alias = _name(w.tags)
            if not name or ROAD_NAME.search(name) or name.isdigit():
                return
            if hw not in HIGHWAYS and not STREET_WORD.search(name):
                return
            if hw in ("track", "path", "footway", "cycleway", "construction", "proposed", "motorway", "motorway_link", "bus_stop", "platform"):
                return
            pts = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
            if pts:
                self.ways.append((name, alias, pts))

        def area(self, a):
            t = a.tags
            lv = t.get("admin_level") if t.get("boundary") == "administrative" else None
            pk = KINDS.get(t.get("place"))
            if lv not in ("4", "6", "9", "10") and pk is None:
                return
            name, _ = _name(t)
            if not name:
                return
            try:
                g = shapely.wkb.loads(wkb.create_multipolygon(a), hex=True)
            except Exception:
                return
            if lv == "4":
                if t.get("name") in OBLAST_NAMES or name in OBLAST_NAMES:
                    self.obl.append((OBLAST_NAMES.get(t.get("name")) or OBLAST_NAMES[name], g))
            elif lv == "6":
                self.raion.append((name, g))
            elif lv == "10":
                self.dist.append((name, g))
            else:
                self.spoly.append((name, pk if pk is not None else KINDS.get(t.get("place"), 2), g))

    h = H()
    h.apply_file(path, locations=True, idx="flex_mem")
    own = [g for u, g in h.obl if u == uid]
    if own:
        o = own[0]
        for g in own[1:]:
            o = o.union(g)
        inside = prep(o.buffer(0.002))
    else:
        print(f"  {uid}: its own boundary did not assemble — keeping every settlement of the extract", file=sys.stderr)
        inside = None
    isin = (lambda x, y: inside.contains(Point(x, y))) if inside else (lambda x, y: True)    # noqa: E731

    # the settlements: the nodes, and a boundary with no node of its name inside it
    norm = lambda s: re.sub(r"[’ʼ`´]", "'", s.lower()).replace("ё", "е")                      # noqa: E731
    setl = []
    if uid == "31":
        setl.append(["Київ", 30.5234, 50.4501, 0])
    else:
        seen = set()
        for name, k, lon, lat in h.nodes:
            key = (norm(name), round(lon, 3), round(lat, 3))
            if key in seen or not isin(lon, lat):
                continue
            seen.add(key)
            setl.append([name, lon, lat, k])
    spt = STRtree([Point(s[1], s[2]) for s in setl]) if setl else None
    polys = []                                   # (settlement index, area, prepared polygon, polygon)
    for name, k, g in h.spoly:
        if uid == "31":
            continue
        idx = None
        if spt is not None:
            for i in spt.query(g):
                s = setl[int(i)]
                if norm(s[0]) == norm(name) and g.contains(Point(s[1], s[2])):
                    idx = int(i)
                    break
        if idx is None:
            c = g.representative_point()
            if not isin(c.x, c.y):
                continue
            setl.append([name, c.x, c.y, k])
            idx = len(setl) - 1
        polys.append((idx, g.area, prep(g), g))
    ptree = STRtree([p[3] for p in polys]) if polys else None
    # each settlement's raion (Kyiv's districts are its streets')
    rnames, rtree = [r[0] for r in h.raion], STRtree([r[1] for r in h.raion]) if h.raion else None
    dnames, dtree = [d[0] for d in h.dist], STRtree([d[1] for d in h.dist]) if h.dist else None
    names_r = []

    def rix(name):
        if name not in names_r:
            names_r.append(name)
        return names_r.index(name)

    def within(tree, geoms, x, y, near=0.02):
        """The polygon the point is in — or, on a border or just outside (the extract's edge), the nearest one."""
        if tree is None:
            return None
        p = Point(x, y)
        for i in tree.query(p):
            if geoms[int(i)].covers(p):
                return int(i)
        best = min(((geoms[int(i)].distance(p), int(i)) for i in tree.query(p.buffer(near))), default=None)
        return best[1] if best else None
    for s in setl:
        i = within(rtree, [r[1] for r in h.raion], s[1], s[2]) if uid != "31" else None
        s.append(rix(rnames[i]) if i is not None else -1)
    # a grid of the settlements' nodes for the nearest one
    grid = defaultdict(list)
    for i, s in enumerate(setl):
        grid[(int(s[1] * 10), int(s[2] * 10))].append(i)

    def nearest(x, y):
        best, bd = None, None
        gx, gy = int(x * 10), int(y * 10)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in grid.get((gx + dx, gy + dy), ()):
                    s = setl[i]
                    d = math.hypot((s[1] - x) * 71.5, (s[2] - y) * 111.2)
                    r = d / REACH_KM[s[3]]
                    if r <= 1 and (bd is None or r < bd):
                        best, bd = i, r
        return best

    def settlement_of(x, y):
        if uid == "31":
            return 0 if isin(x, y) else None
        if not isin(x, y):
            return None
        if ptree is not None:
            p = Point(x, y)
            hit = [polys[int(i)] for i in ptree.query(p)]
            hit = [q for q in hit if q[2].contains(p)]
            if hit:
                return min(hit, key=lambda q: q[1])[0]
        return nearest(x, y)

    groups = {}
    for name, alias, pts in h.ways:
        mx, my = pts[len(pts) // 2]
        si = settlement_of(mx, my)
        if si is None:
            continue
        key = (si, norm(name))
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"name": name, "alias": alias, "pts": [], "x0": 1e9, "y0": 1e9, "x1": -1e9, "y1": -1e9}
        if alias and not g["alias"]:
            g["alias"] = alias
        step = max(1, len(pts) // 24)
        g["pts"].extend(pts[::step])
        for x, y in pts:
            g["x0"], g["y0"], g["x1"], g["y1"] = min(g["x0"], x), min(g["y0"], y), max(g["x1"], x), max(g["y1"], y)
    streets = []
    for (si, _), g in groups.items():
        cx = sum(p[0] for p in g["pts"]) / len(g["pts"])
        cy = sum(p[1] for p in g["pts"]) / len(g["pts"])
        rx, ry = min(g["pts"], key=lambda p: (p[0] - cx) ** 2 * .51 + (p[1] - cy) ** 2)
        s = setl[si]
        X, Y = round(s[1] * 1e4) * 10, round(s[2] * 1e4) * 10
        px, py = round(rx * 1e5), round(ry * 1e5)
        reach = max(px - round(g["x0"] * 1e5), round(g["x1"] * 1e5) - px, py - round(g["y0"] * 1e5), round(g["y1"] * 1e5) - py)
        row = [g["name"], si, px - X, py - Y, max(0, reach)]
        d = within(dtree, [q[1] for q in h.dist], rx, ry) if uid == "31" else None
        if g["alias"] or d is not None:
            row.append(g["alias"] or 0)
        if d is not None:
            row.append(rix(dnames[d]))
        streets.append(row)
    # the settlements that are kept: every one of the oblast; renumbered by name
    order = sorted(range(len(setl)), key=lambda i: (norm(setl[i][0]), setl[i][3]))
    new = {o: n for n, o in enumerate(order)}
    t = [[setl[o][0], round(setl[o][1] * 1e4), round(setl[o][2] * 1e4), setl[o][3], setl[o][4]] for o in order]
    for r in streets:
        r[1] = new[r[1]]
    streets.sort(key=lambda r: (r[1], norm(r[0])))
    return {"v": FORMAT, "uid": uid, "built": date.today().isoformat(), "src": os.path.basename(path),
            "lic": "© OpenStreetMap contributors — ODbL 1.0", "r": names_r, "t": t, "s": streets}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    src, only = argv[0], set(argv[1:])
    os.makedirs(OUT, exist_ok=True)
    for name, uid in EXTRACTS.items():
        if only and name not in only and uid not in only:
            continue
        path = os.path.join(src, name + ".osm.pbf")
        if not os.path.exists(path):
            print(f"{name}: not in {src}", file=sys.stderr)
            continue
        d = build(path, uid)
        out = os.path.join(OUT, f"{uid}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{name} → {uid}.json: {len(d['t'])} settlements, {len(d['s'])} streets, {os.path.getsize(out):,} B")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
