"""Build static/map-ua.json — the rivers, main roads and landmarks the map draws outside Kyiv oblast (1.45).

    python scripts/build_mapdata.py NE_DIR

Until 1.45 the map's "rivers", "roads" and "airports & power plants" layers were drawn by hand for Kyiv oblast
and nothing else, so on an Odesa or Lviv view they did nothing at all. This file carries the same three layers
for the whole country, in the map's own projected kilometres (static/kyiv-map.json: centre, kx, ky):

- rivers: Natural Earth 1:10m river and lake centrelines (public domain), cut to Ukraine's oblast outlines;
- roads:  Natural Earth 1:10m roads of the first ranks, cut to Ukraine outside Kyiv oblast and the city (whose
          highways stay the hand-drawn, labelled ones);
- pois:   the civil airports of the oblast capitals and the large power plants, from GeoNames (CC BY 4.0),
          listed by hand below — no military airfield is added.

NE_DIR holds ne_10m_rivers_lake_centerlines.geojson and roads/ne_10m_roads.shp (needs pyshp). Rebuild only when
one of those changes; the output is committed.
"""
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Natural Earth name → (class, English, Ukrainian, French)
RIVERS = {
    "Dnipro": ("mid", "Dnipro", "Дніпро", "Dniepr"),
    "Dniester": ("mid", "Dniester", "Дністер", "Dniestr"),
    "Southern Bug": ("thin", "Southern Bug", "Південний Буг", "Boug méridional"),
    "Donets": ("thin", "Siverskyi Donets", "Сіверський Донець", "Donets"),
    "Desna": ("thin", "Desna", "Десна", "Desna"),
    "Pripyat": ("thin", "Prypiat", "Прип'ять", "Pripiat"),
    "Prut": ("thin", "Prut", "Прут", "Prout"),
    "Bug": ("thin", "Western Bug", "Західний Буг", "Boug occidental"),
    "Seym": ("thin", "Seim", "Сейм", "Seïm"),
    "Danube": ("mid", "Danube", "Дунай", "Danube"),
    "Bratul Chillia": ("mid", "Danube", "Дунай", "Danube"),
}
# the Dnipro's reservoirs are its "lake centrelines": drawn wider, as the hand-drawn Kyiv Reservoir was
WIDE = {("Dnipro", "Lake Centerline")}

# (kind, English, Ukrainian, French, lon, lat) — GeoNames coordinates
POIS = [
    ("air", "Odesa airport", "аеропорт Одеса", "aéroport d'Odessa", 30.6765, 46.4268),
    ("air", "Lviv airport", "аеропорт Львів", "aéroport de Lviv", 23.9561, 49.8125),
    ("air", "Kharkiv airport", "аеропорт Харків", "aéroport de Kharkiv", 36.2900, 49.9248),
    ("air", "Dnipro airport", "аеропорт Дніпро", "aéroport de Dnipro", 35.1006, 48.3572),
    ("air", "Zaporizhzhia airport", "аеропорт Запоріжжя", "aéroport de Zaporijjia", 35.3164, 47.8672),
    ("air", "Kryvyi Rih airport", "аеропорт Кривий Ріг", "aéroport de Kryvyï Rih", 33.2100, 48.0433),
    ("air", "Ivano-Frankivsk airport", "аеропорт Івано-Франківськ", "aéroport d'Ivano-Frankivsk", 24.6861, 48.8842),
    ("air", "Chernivtsi airport", "аеропорт Чернівці", "aéroport de Tchernivtsi", 25.9817, 48.2600),
    ("air", "Rivne airport", "аеропорт Рівне", "aéroport de Rivne", 26.1416, 50.6071),
    ("air", "Uzhhorod airport", "аеропорт Ужгород", "aéroport d'Oujhorod", 22.2634, 48.6343),
    ("air", "Mykolaiv airport", "аеропорт Миколаїв", "aéroport de Mykolaïv", 31.9187, 47.0556),
    ("air", "Kherson airport", "аеропорт Херсон", "aéroport de Kherson", 32.5064, 46.6758),
    ("air", "Poltava airport", "аеропорт Полтава", "aéroport de Poltava", 34.3972, 49.5686),
    ("air", "Sumy airport", "аеропорт Суми", "aéroport de Soumy", 34.7625, 50.8583),
    ("air", "Lutsk airport", "аеропорт Луцьк", "aéroport de Loutsk", 25.4872, 50.6784),
    ("air", "Ternopil airport", "аеропорт Тернопіль", "aéroport de Ternopil", 25.7001, 49.5242),
    ("air", "Khmelnytskyi airport", "аеропорт Хмельницький", "aéroport de Khmelnytskyï", 26.9334, 49.3597),
    ("air", "Kropyvnytskyi airport", "аеропорт Кропивницький", "aéroport de Kropyvnytskyï", 32.2850, 48.5428),
    ("air", "Vinnytsia airport", "аеропорт Вінниця", "aéroport de Vinnytsia", 28.6140, 49.2399),
    ("air", "Zhytomyr airport", "аеропорт Житомир", "aéroport de Jytomyr", 28.7389, 50.2707),
    ("air", "Cherkasy airport", "аеропорт Черкаси", "aéroport de Tcherkassy", 32.0042, 49.4062),
    ("nuc", "Rivne NPP", "Рівненська АЕС", "centrale nucléaire de Rivne", 25.8917, 51.3278),
    ("nuc", "Khmelnytskyi NPP", "Хмельницька АЕС", "centrale nucléaire de Khmelnytskyï", 26.6498, 50.3014),
    ("nuc", "South Ukraine NPP", "Південноукраїнська АЕС", "centrale nucléaire d'Ukraine du Sud", 31.2167, 47.8167),
    ("nuc", "Zaporizhzhia NPP", "Запорізька АЕС", "centrale nucléaire de Zaporijjia", 34.5858, 47.5122),
    ("pow", "Burshtyn TPP", "Бурштинська ТЕС", "centrale thermique de Bourchtyn", 24.6676, 49.2087),
    ("pow", "Dniester HPP", "Дністровська ГЕС", "centrale hydro du Dniestr", 27.4530, 48.5934),
    ("pow", "Kaniv HPP", "Канівська ГЕС", "centrale hydro de Kaniv", 31.4728, 49.7672),
    ("pow", "Kremenchuk HPP", "Кременчуцька ГЕС", "centrale hydro de Krementchouk", 33.2510, 49.0750),
    ("pow", "Middle Dnipro HPP", "Середньодніпровська ГЕС", "centrale hydro du Dniepr moyen", 34.5410, 48.5485),
    ("pow", "Dnipro HPP", "Дніпровська ГЕС", "centrale hydro du Dniepr", 35.0864, 47.8691),
]


def load_base():
    with open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8") as f:
        base = json.load(f)
    c0, c1 = base["center"]
    kx, ky = base["kx"], base["ky"]

    def proj(lon, lat):
        return ((lon - c0) * kx, -(lat - c1) * ky)

    def rings(path):
        out = []
        for part in re.findall(r"M([^MZ]+)Z?", path):
            pts = [tuple(map(float, p.split(","))) for p in part.split()]
            if len(pts) >= 3:
                out.append(pts)
        return out

    ua, kyiv = [], []
    for o in base["oblasts"]:
        rs = rings(o["path"])
        ua.extend(rs)
        if o["uid"] in ("14", "31"):
            kyiv.extend(rs)
    return proj, ua, kyiv


def _inside(pt, polys):
    """Even-odd over all rings: the union of the oblasts (they do not overlap)."""
    x, y = pt
    n = 0
    for ring in polys:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                n += 1
            j = i
    return n % 2 == 1


def _bbox(polys):
    xs = [p[0] for r in polys for p in r]
    ys = [p[1] for r in polys for p in r]
    return min(xs), min(ys), max(xs), max(ys)


def cut(line, keep):
    """The runs of `line` whose points pass `keep`, each at least two points long."""
    runs, cur = [], []
    for p in line:
        if keep(p):
            cur.append(p)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def simplify(pts, tol):
    """Douglas–Peucker, in km."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-9
    best, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / L
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def flat(pts):
    return [round(v, 1) for p in pts for v in p]


def length(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))


def main(ne_dir):
    proj, ua, kyiv = load_base()
    bx = _bbox(ua)
    in_ua = lambda p: bx[0] <= p[0] <= bx[2] and bx[1] <= p[1] <= bx[3] and _inside(p, ua)  # noqa: E731
    out_kyiv = lambda p: in_ua(p) and not _inside(p, kyiv)  # noqa: E731

    rivers = {}
    with open(os.path.join(ne_dir, "ne_10m_rivers_lake_centerlines.geojson"), encoding="utf-8") as f:
        for ft in json.load(f)["features"]:
            pr = ft["properties"]
            name = pr.get("name")
            if name not in RIVERS:
                continue
            g = ft["geometry"]
            lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            cls = "wide" if (name, pr.get("featurecla")) in WIDE else RIVERS[name][0]
            for ln in lines:
                pts = [proj(x, y) for x, y in ln]
                for run in cut(pts, in_ua):
                    run = simplify(run, 0.6)
                    if length(run) >= 4:
                        rivers.setdefault((RIVERS[name][1], cls), []).append(run)
    riv_out, placed = [], []
    for (en, cls), runs in sorted(rivers.items(), key=lambda kv: -sum(length(r) for r in kv[1])):
        names = next(v for v in RIVERS.values() if v[1] == en)
        # a label every ~350 km of river at most, at the middle of its longest pieces, never within 120 km of Kyiv
        # (the map's own Kyiv-oblast labels are there) nor within 80 km of another label
        total = sum(length(r) for r in runs)
        labels = []
        for r in sorted(runs, key=length, reverse=True)[:max(1, min(3, round(total / 350)))]:
            if cls == "wide" or length(r) < 40:
                continue
            m = r[len(r) // 2]
            if math.hypot(*m) < 120 or any(math.hypot(m[0] - q[0], m[1] - q[1]) < 80 for q in placed):
                continue
            placed.append(m)
            labels.append([round(m[0], 1), round(m[1], 1)])
        riv_out.append({"en": en, "uk": names[2], "fr": names[3], "c": cls, "l": [flat(r) for r in runs], "lb": labels})

    import shapefile  # pyshp, only needed to rebuild

    rd = shapefile.Reader(os.path.join(ne_dir, "roads", "ne_10m_roads"))
    roads = []
    for i, sh in enumerate(rd.iterShapes()):
        b = sh.bbox
        if b[2] < 22 or b[0] > 40.3 or b[3] < 44.3 or b[1] > 52.4:
            continue
        rec = rd.record(i).as_dict()
        if rec["type"] not in ("Major Highway", "Secondary Highway", "Road") or rec["scalerank"] > 5:
            continue
        parts = list(sh.parts) + [len(sh.points)]
        for a, z in zip(parts[:-1], parts[1:]):
            pts = [proj(x, y) for x, y in sh.points[a:z]]
            for run in cut(pts, out_kyiv):
                run = simplify(run, 0.8)
                if length(run) >= 5:
                    roads.append(flat(run))

    pois = []
    for kind, en, uk, fr, lon, lat in POIS:
        x, y = proj(lon, lat)
        pois.append({"k": kind, "en": en, "uk": uk, "fr": fr, "x": round(x, 2), "y": round(y, 2)})

    doc = {"license": "Rivers and roads: Natural Earth (public domain). Landmarks: GeoNames (CC BY 4.0).",
           "rivers": riv_out, "roads": roads, "pois": pois}
    path = os.path.join(ROOT, "static", "map-ua.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(path, os.path.getsize(path), "bytes;", len(riv_out), "rivers,", len(roads), "road pieces,", len(pois), "landmarks")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
