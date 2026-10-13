"""1.58.7: which official alert area a point is in — Kyiv city, a raion of Kyiv oblast, a raion of an oblast around —, and
whether that area is under an official alert now. From static/kyiv-map.json, the shapes the Tactical page paints the
alerts on, so that a point is "under alert" exactly when the page shows it so (alertMap). No Pillow, no network.

Used for the owner's rule (said of 1.58.6): "alarm ALWAYS is better, you see Kyiv isn't under alarm yet so why put a drone icon
here, it's dangerous" — a target whose post gave only where it is heading is not drawn at that place while the place has
no official alert (server.State.markers → `held`), and the private channel marks the official all-clear of a target's
area (app/chanpost.py)."""
import json
import os

RAION_STEM = (("бровар", "brovary"), ("бориспіл", "boryspil"), ("бучан", "bucha"), ("вишгород", "vyshhorod"),
              ("обухів", "obukhiv"), ("білоцерків", "bila-tserkva"), ("фастів", "fastiv"))


def alert_fill(active):
    """The official alerts of the moment → {key: 'R' | 'Y'}, as the Tactical page paints them (alertMap): Kyiv city
    ("kyiv-city"), the raions of Kyiv oblast by key — an oblast-wide alert fills all of them, a raion's or a hromada's
    its raion —, and for the oblasts around, "obl:<uid>" for an oblast-wide alert and "nb:<raion key>" for a raion's."""
    out = {}

    def put(k, lvl):
        if k and out.get(k) != "R":
            out[k] = lvl
    for a in active or ():
        uid, lt, title = a.get("oblast_uid"), a.get("location_type"), (a.get("location_title") or "").lower()
        lvl = "Y" if a.get("alert_level") == "yellow" else "R"        # no level reported (a mirror) = a full alert
        if uid == "31":
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


def under_alert(lon, lat, fills):
    """Is the area of this point painted by the official alerts of the moment? `fills`: mapshot.alert_fill(active).
    A point in no known area is taken to be under alert: nothing is held back on a guess."""
    a = area_at(lon, lat)
    if not a:
        return True
    obl, key = a
    if obl == "31":
        return "kyiv-city" in fills
    if obl == "14":
        return key in fills
    return ("obl:" + str(obl)) in fills or ("nb:" + str(key)) in fills
