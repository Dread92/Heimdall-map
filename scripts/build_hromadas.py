"""Build static/hromadas/<oblast uid>.json — the outline of every hromada the official alerts can name (1.58.16).

    python scripts/build_hromadas.py PATH/ukr_admin_boundaries.gdb

The official «Повітряна тривога» data names some alerts by hromada ("м. Нікополь та Нікопольська територіальна
громада", "Червоногригорівська територіальна громада"). Until 1.58.16 the map had no hromada shapes, so such an
alert coloured its whole raion and a place in that raion read "alert in part of your raion". With these outlines the
alert is painted on the hromada itself, and a place inside it reads the alert as its own.

Source: OCHA COD-AB Ukraine, admin level 3 (`ukr_admin3` of ukr_admin_boundaries.gdb, HDX), CC BY 3.0 IGO — the same
data set as the raion outlines (geoBoundaries gbHumanitarian), in a newer edition. Each outline is matched to the
official hromada id of data/ua_regions.json (`communities`) by its raion's and its own Ukrainian name; an id with no
outline keeps the old rule (the parent raion is coloured). Outlines are in the map's own kilometres (static/kyiv-map.json:
centre, kx, ky), simplified as one coverage so neighbours keep a shared border, to 0.1 km.

Needs pyogrio and shapely (build only — the app does not import them). Administrative boundaries change rarely;
rebuild after a reform, after data/ua_regions.json is rebuilt.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "hromadas")   # one file per oblast: a page fetches only the oblast it needs
TOL_KM = 0.25          # simplification tolerance; the raion outlines are accurate to a few hundred metres too
MIN_KM2 = 0.3          # islands and holes smaller than this are dropped
LICENSE = "OCHA COD-AB Ukraine (HDX), admin level 3, edition v05 valid 2025-09-01 — CC BY 3.0 IGO"

# renamed since the official list was made: its name → the GDB's
RENAMED = {"новоград-волинська": "звягельська"}

APOS = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "ʹ": "'", "‘": "'"})


def norm(s):
    """'м. Нікополь та Нікопольська територіальна громада' → 'нікопольська'; 'Білоцерківський район' → 'білоцерківський'."""
    s = (s or "").translate(APOS).lower().strip()
    s = re.sub(r"^м\.\s*[^,]*?\s+та\s+", "", s)
    s = re.sub(r"\s*(територіальна\s+)?громада\s*$", "", s)
    s = re.sub(r"\s*(сільська|селищна|міська)\s*$", "", s)
    s = re.sub(r"\s*район\s*$", "", s)
    return re.sub(r"[\s\-]+", "-", s).replace("'", "")


def read_layer(path, layer, geometry=True):
    import shapely
    from pyogrio.raw import read
    meta, _fids, geom, fields = read(path, layer=layer, read_geometry=geometry)
    cols = meta["fields"].tolist()
    rows = []
    for i in range(len(fields[0])):
        r = {c: fields[j][i] for j, c in enumerate(cols)}
        if geometry:
            r["geom"] = shapely.from_wkb(geom[i])
        rows.append(r)
    return rows


def _fuzzy(name, cands):
    """The one candidate whose name is this one with a typo or cut short ("Гостомелська", "Слобідсько-Кульчієвецьк",
    "Монастрищенська", "Русько-Полянська") — or None when two come as close."""
    from difflib import SequenceMatcher
    a = name.replace("-", "")
    sc = []
    for r in cands:
        b = norm(r.get("adm3_name1")).replace("-", "")
        x = SequenceMatcher(None, a, b).ratio()
        if len(a) >= 8 and b.startswith(a):
            x = max(x, 0.95)
        sc.append((x, r))
    sc.sort(key=lambda t: -t[0])
    if sc and sc[0][0] >= 0.85 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.06):
        return sc[0][1]
    return None


def match(rows, uar, cities):
    """official hromada id → (GDB row, oblast uid, parent raion key); and the ids left without an outline.

    By the Ukrainian names of the hromada and of its raion, in its oblast. Two hromadas of one raion can share a name
    (Нікопольський: Покровська міська and Покровська сільська): the official list names the city's "м. Покров та
    Покровська …", so the one whose centre is a city (`cities`, from ukr_admin4) is the city's and the other the rest's.
    A renamed hromada keeps its old name in the GDB (adm3_name1_old); a typo or a cut-short name matches its one
    close neighbour. Anything still ambiguous is left out — that alert keeps colouring its raion."""
    dist = uar["districts"]
    by_name = {}
    for r in rows:
        for n in {r.get("adm3_name1"), r.get("adm3_name1_old")} - {None}:
            by_name.setdefault(norm(n), []).append(r)
    votes = {}
    for c in uar["communities"].values():
        d = dist.get(c.get("d") or "") or {}
        cands = [r for r in by_name.get(norm(c["name"]), []) if d and norm(r.get("adm2_name1")) == norm(d["name"])]
        if len(cands) == 1 and d.get("obl"):
            v = votes.setdefault(cands[0]["adm1_pcode"], {})
            v[d["obl"]] = v.get(d["obl"], 0) + 1
    uid_of = {p: max(v, key=v.get) for p, v in votes.items()}
    out, miss = {}, []
    for cid, c in uar["communities"].items():
        d = dist.get(c.get("d") or "") or {}
        obl = d.get("obl") or c.get("obl")
        n = norm(c["name"])
        n = RENAMED.get(n, n)
        in_obl = [r for r in rows if uid_of.get(r["adm1_pcode"]) == obl]
        in_raion = [r for r in in_obl if d and norm(r.get("adm2_name1")) == norm(d["name"])] or in_obl
        cands = [r for r in by_name.get(n, []) if r in in_raion] or [r for r in by_name.get(n, []) if r in in_obl]
        if len(cands) > 1:
            city = c["name"].strip().startswith("м.")
            cands = [r for r in cands if (r["adm3_pcode"] in cities) == city]
        if not cands:
            f = _fuzzy(n, in_raion)
            cands = [f] if f else []
            if f:
                print(f"close name: {c['name']} → {f['adm3_name1']} ({f['adm2_name1']})")
        if len(cands) == 1:
            out[cid] = (cands[0], obl, d.get("key"))
        else:
            miss.append((cid, c["name"], obl, len(cands)))
    return out, miss


def project(geom, center, kx, ky):
    import shapely
    return shapely.transform(geom, lambda xy: [[(x - center[0]) * kx, (center[1] - y) * ky] for x, y in xy])


def rings_of(g):
    """A (Multi)Polygon → flat [x, y, …] rings at 0.1 km, the outer ring first in each part; tiny parts dropped."""
    from shapely.geometry import Polygon
    parts = [g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))
    out = []
    for p in sorted(parts, key=lambda p: -p.area):
        if p.area < MIN_KM2 or not isinstance(p, Polygon):
            continue
        for ring in [p.exterior] + [h for h in p.interiors if Polygon(h).area >= MIN_KM2]:
            xs = []
            for x, y in list(ring.coords)[:-1]:
                q = [round(x, 1), round(y, 1)]
                if len(xs) < 2 or xs[-2:] != q:
                    xs += q
            if len(xs) >= 6:
                out.append(xs)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    import shapely
    with open(os.path.join(ROOT, "data", "ua_regions.json"), encoding="utf-8") as f:
        uar = json.load(f)
    with open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8") as f:
        kmap = json.load(f)
    rows = read_layer(sys.argv[1], "ukr_admin3")
    # the hromadas whose centre (its first settlement, …001) is a city
    cities = {r["adm3_pcode"] for r in read_layer(sys.argv[1], "ukr_admin4", geometry=False)
              if str(r.get("adm4_pcode") or "").endswith("001") and r.get("adm4_type") == "City"}
    found, miss = match(rows, uar, cities)
    ids = sorted(found, key=int)
    geoms = [project(found[i][0]["geom"], kmap["center"], kmap["kx"], kmap["ky"]) for i in ids]
    geoms = shapely.coverage_simplify(shapely.make_valid(geoms), TOL_KM)
    h = {}
    for cid, g in zip(ids, geoms):
        r, obl, rkey = found[cid]
        p = rings_of(shapely.make_valid(g))
        if not p:
            miss.append((cid, uar["communities"][cid]["name"], obl, "empty"))
            continue
        h[cid] = {"o": obl, "r": rkey, "uk": uar["communities"][cid]["name"], "en": r.get("adm3_name"), "p": p}
    by_obl = {}
    for cid, v in h.items():
        by_obl.setdefault(v.pop("o"), {})[cid] = v
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".json"):
            os.remove(os.path.join(OUT, f))
    size = 0
    for obl, hs in sorted(by_obl.items(), key=lambda t: int(t[0])):
        data = {"_about": "built by scripts/build_hromadas.py — official hromada id → its outline in the map's kilometres "
                          "(r: parent raion's shape key, p: rings [x, y, …], outer ring first)",
                "license": LICENSE, "obl": obl, "center": kmap["center"], "kx": kmap["kx"], "ky": kmap["ky"], "h": hs}
        path = os.path.join(OUT, f"{obl}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        size += os.path.getsize(path)
    print(f"static/hromadas/: {len(h)} of {len(uar['communities'])} official hromadas in {len(by_obl)} oblasts, "
          f"{size // 1024} KB")
    for m in miss:
        print("no outline:", *m)


if __name__ == "__main__":
    main()
