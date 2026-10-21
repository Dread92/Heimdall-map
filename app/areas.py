"""1.58.7: which official alert area a point is in — Kyiv city, a raion of Kyiv oblast, a raion of an oblast around —, and
whether that area is under an official alert now. From static/kyiv-map.json, the shapes the Tactical page paints the
alerts on, so that a point is "under alert" exactly when the page shows it so (alertMap). No Pillow, no network.
1.58.16: and the hromadas' (static/hromadas/<oblast uid>.json, scripts/build_hromadas.py): an alert the official data
gives for a hromada is that hromada's, no longer its whole raion's — as the pages now paint it.

Used for the owner's rule (said of 1.58.6): "alarm ALWAYS is better, you see Kyiv isn't under alarm yet so why put a drone icon
here, it's dangerous" — a target whose post gave only where it is heading is not drawn at that place while the place has
no official alert (server.State.markers → `held`), and the private channel marks the official all-clear of a target's
area (app/chanpost.py)."""
import json
import math
import os

RAION_STEM = (("бровар", "brovary"), ("бориспіл", "boryspil"), ("бучан", "bucha"), ("вишгород", "vyshhorod"),
              ("обухів", "obukhiv"), ("білоцерків", "bila-tserkva"), ("фастів", "fastiv"))


def alert_fill(active):
    """The official alerts of the moment → {key: 'R' | 'Y'}, as the Tactical page paints them (alertMap): Kyiv city
    ("kyiv-city"), the raions of Kyiv oblast by key — an oblast-wide alert fills all of them, a raion's or a hromada's
    its raion —, and for the oblasts around, "obl:<uid>" for an oblast-wide alert and "nb:<raion key>" for a raion's.
    1.58.16: a hromada with a known outline is "hr:<oblast uid>:<id>" instead of its raion."""
    out = {}

    def put(k, lvl):
        if k and out.get(k) != "R":
            out[k] = lvl
    for a in active or ():
        uid, lt, title = a.get("oblast_uid"), a.get("location_type"), (a.get("location_title") or "").lower()
        lvl = "Y" if a.get("alert_level") == "yellow" else "R"        # no level reported (a mirror) = a full alert
        h = hromada_of(a)
        if h:
            put("hr:%s:%s" % h, lvl)
        elif uid == "31":
            put("kyiv-city", lvl)
        elif uid == "14":
            if lt == "oblast":
                for _, k in RAION_STEM:
                    put(k, lvl)
            else:
                put(a.get("raion_key") or next((k for s, k in RAION_STEM if s in title), None), lvl)
        elif uid:
            if lt == "oblast":
                put("obl:" + uid, lvl)
            elif a.get("raion_key"):
                put("nb:" + a["raion_key"], lvl)
    return out


STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
_FEATURES = None
_BASE = None
_HROM = {}
BORDER_KM = 1.5     # the outlines are right to a few hundred metres: this close to a hromada's line counts as in it


def _hromadas(obl):
    """1.58.16: the hromada outlines of one oblast → {official id: (rings, bbox, parent raion key)}, read once; {} when
    there are none."""
    if obl not in _HROM:
        out = {}
        if str(obl).isdigit():
            try:
                with open(os.path.join(STATIC, "hromadas", "%d.json" % int(obl)), encoding="utf-8") as f:
                    for i, h in json.load(f)["h"].items():
                        rings = [list(zip(r[0::2], r[1::2])) for r in h["p"]]
                        xs = [p[0] for r in rings for p in r]
                        ys = [p[1] for r in rings for p in r]
                        if xs:
                            out[i] = (rings, (min(xs), min(ys), max(xs), max(ys)), h.get("r"))
            except (OSError, ValueError, KeyError, TypeError):
                pass
        _HROM[obl] = out
    return _HROM[obl]


def hromada_of(a):
    """(oblast uid, official id) of the hromada an official alert names, when its outline is known — else None."""
    if not a or a.get("location_type") != "hromada":
        return None
    uid, obl = a.get("location_uid") or "", str(a.get("oblast_uid") or "")
    rid = uid[3:] if uid.startswith("ua-") else ""
    return (obl, rid) if rid.isdigit() and rid in _hromadas(obl) else None


def hromada_rings(obl, rid):
    """The rings of a hromada's outline, in the map's km (static/kyiv-map.json's grid) — [] when unknown."""
    h = _hromadas(obl).get(rid)
    return h[0] if h else []


def hromada_raion(obl, rid):
    """The key of a hromada's parent raion ("bucha", "nikopolskyi") — None when unknown."""
    h = _hromadas(obl).get(rid)
    return h[2] if h else None


def _load():
    global _FEATURES, _BASE
    if _FEATURES is None:
        import re
        try:
            base = json.load(open(os.path.join(STATIC, "kyiv-map.json"), encoding="utf-8"))
        except (OSError, ValueError):
            _FEATURES, _BASE = [], None
            return _FEATURES
        _BASE = base
        feats = []
        for f in base["features"]:
            rings = []
            for part in re.split(r"[Mm]", f.get("path") or ""):
                nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", part.replace("Z", " ").replace("z", " "))]
                pts = list(zip(nums[0::2], nums[1::2]))
                if len(pts) >= 3:
                    rings.append(pts)
            if rings:
                xs = [p[0] for r in rings for p in r]
                ys = [p[1] for r in rings for p in r]
                feats.append((f.get("raion"), f.get("obl"), f.get("key"), rings, (min(xs), min(ys), max(xs), max(ys))))
        # Kyiv oblast's raions and the city first: they lie over the oblasts' outlines
        feats.sort(key=lambda t: 0 if t[0] else 1)
        _FEATURES = feats
    return _FEATURES


def _inside(x, y, ring):
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            hit = not hit
        j = i
    return hit


def area_at(lon, lat):
    """(oblast uid, area key) of a point: ("31", "kyiv-city"), ("14", "brovary"), ("25", "<raion key>") — or None."""
    feats = _load()
    if not feats or _BASE is None or lon is None or lat is None:
        return None
    x, y = (lon - _BASE["center"][0]) * _BASE["kx"], -(lat - _BASE["center"][1]) * _BASE["ky"]
    for raion, obl, key, rings, (x0, y0, x1, y1) in feats:
        if x0 <= x <= x1 and y0 <= y <= y1 and sum(_inside(x, y, r) for r in rings) % 2 == 1:
            return (obl, raion or key)
    return None


def edge_km(lon, lat, bearing, raion="kyiv-city"):
    """1.58.41: how far from this point, going toward `bearing` (0 = north), the outline of `raion` ends — the last time
    the line crosses it, so the point found is outside — in km; None when the point is not inside that outline. The
    owner, of a jet drone "курсом на Київ з півночі" drawn over Podil: "it says heading to Kyiv, from the north, and yet
    the icon is placed right inside the city" — an approach to Kyiv stands off the city, not off its centre."""
    feats = _load()
    if not feats or _BASE is None or lon is None or lat is None or bearing is None:
        return None
    x, y = (lon - _BASE["center"][0]) * _BASE["kx"], -(lat - _BASE["center"][1]) * _BASE["ky"]
    rings = next((f[3] for f in feats if f[0] == raion), None)
    if not rings or sum(_inside(x, y, r) for r in rings) % 2 == 0:
        return None
    a = math.radians(bearing)
    dx, dy = math.sin(a), -math.cos(a)              # the map's km run east and south
    best = None
    for r in rings:
        for i in range(len(r)):
            (ax, ay), (bx, by) = r[i - 1], r[i]
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            t = ((ax - x) * ey - (ay - y) * ex) / den
            u = ((ax - x) * dy - (ay - y) * dx) / den
            if t > 0 and 0 <= u <= 1 and (best is None or t > best):
                best = t
    return best


def _edge_km(x, y, ring):
    best = 1e9
    for i in range(len(ring)):
        (ax, ay), (bx, by) = ring[i - 1], ring[i]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy or 1e-9
        u = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L))
        best = min(best, ((ax + u * dx - x) ** 2 + (ay + u * dy - y) ** 2) ** 0.5)
    return best


def in_hromada(lon, lat, fills):
    """1.58.16: is this point in a hromada the official alerts of the moment name ("hr:" in `fills`), or within
    BORDER_KM of one?"""
    keys = [k for k in fills if k.startswith("hr:")]
    if not keys or lon is None or lat is None or not _load() or _BASE is None:
        return False
    x, y = (lon - _BASE["center"][0]) * _BASE["kx"], -(lat - _BASE["center"][1]) * _BASE["ky"]
    for k in keys:
        _, obl, rid = k.split(":", 2)
        h = _hromadas(obl).get(rid)
        if not h:
            continue
        rings, (x0, y0, x1, y1), _r = h
        m = BORDER_KM
        if not (x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m):
            continue
        if sum(_inside(x, y, r) for r in rings) % 2 == 1 or min(_edge_km(x, y, r) for r in rings) <= m:
            return True
    return False


def under_alert(lon, lat, fills):
    """Is the area of this point painted by the official alerts of the moment? `fills`: mapshot.alert_fill(active).
    A point in no known area is taken to be under alert: nothing is held back on a guess."""
    if in_hromada(lon, lat, fills):
        return True
    a = area_at(lon, lat)
    if not a:
        return True
    obl, key = a
    if obl == "31":
        return "kyiv-city" in fills
    if obl == "14":
        return key in fills
    return ("obl:" + str(obl)) in fills or ("nb:" + str(key)) in fills
