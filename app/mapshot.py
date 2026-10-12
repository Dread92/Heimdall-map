"""1.58: a picture of the map around one target — for the private Telegram channel (app/chanpost.py).

The owner: "a small private Telegram channel that posts alerts like the channels we read, with a 'screenshot' of the
app where the drone is (Kyiv and Kyiv oblast only)" — and, of the two ways asked, "the app's style, drawn on the server".
It is drawn here with the map data the pages use (static/kyiv-map.json, kyiv-districts.json, map-ua.json, the towns and
the raion names of kyiv.html, the silhouettes of glyphs.js), in the Tactical page's colours, in a fraction of a
second; no browser runs on the server. Needs Pillow and a font with Cyrillic (the image installs DejaVu); without
Pillow the channel posts its text alone.

It shows what the post said and nothing more (docs/SAFETY.md): where it was reported, the places it was reported at
before, a course only when a post gave one, the official alerts of the moment by raion. No outcome (a shot-down, an
explosion) is ever drawn — the channel is for what flies, and where a strike landed is not published live.
"""
import io
import json
import math
import os
import re

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:            # optional: without it the channel sends text only
    Image = ImageDraw = ImageFont = None

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans.ttf")
FONTS_B = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf")

W = 1080                       # the picture's side, in pixels (Telegram shows a square photo whole)
SS = 2                         # drawn twice as large, then scaled down: smooth edges
HEAD, FOOT = 74, 86            # the title band and the foot band (two lines: the warning, the credits)

BG, NB, NB_LINE = (11, 13, 17), (14, 17, 22), (26, 31, 40)
RN, RN_LINE, CITY_LINE = (20, 25, 32), (43, 51, 64), (143, 180, 255)
KD_LINE, RIVER = (51, 65, 92), (42, 74, 115)
INK, INK2, INK3 = (232, 230, 223), (181, 179, 171), (143, 141, 134)
RED_T, YEL_T = (229, 72, 77, 72), (245, 185, 64, 60)
ORANGE, AMBER, MSL = (255, 138, 61), (255, 177, 92), (255, 90, 90)
STROKE = (8, 11, 16)

# The silhouettes of static/glyphs.js — the same shapes (tests/test_chanpost_158.py checks each against the file),
# nose up, centred on 0,0, about 24 units tall. ("R", x, y, w, h) is a rectangle; anything else a polygon.
_SHAHED = [[(0, -11.6), (2, -6.8), (2, 6.2), (-2, 6.2), (-2, -6.8)], [(-2, -3.6), (-10.4, 6.2), (-2, 6.2)],
           [(2, -3.6), (10.4, 6.2), (2, 6.2)], ("R", -10.9, 5.2, 2.4, 4.8), ("R", 8.5, 5.2, 2.4, 4.8)]
GLYPHS = {
    "drone": _SHAHED + [("R", -2.8, 6, 5.6, 4.4)],
    "jetdrone": _SHAHED + [("R", -3.3, -6.6, 6.6, 4.4), ("R", -3.2, 6, 6.4, 4.6)],
    "missile": [[(0, -12), (1.3, -9), (1.3, 9), (-1.3, 9), (-1.3, -9)], [(1.3, -0.6), (5.4, 1.8), (5.4, 2.8), (1.3, 1.9)],
                [(-1.3, -0.6), (-5.4, 1.8), (-5.4, 2.8), (-1.3, 1.9)], [(1.3, 6), (3.5, 10.2), (1.3, 9)],
                [(-1.3, 6), (-3.5, 10.2), (-1.3, 9)]],
    "ballistic": [[(0, -12), (1.6, -7.6), (2.1, -4), (2.1, 8), (-2.1, 8), (-2.1, -4), (-1.6, -7.6)],
                  [(2.1, 4.2), (4.6, 9.6), (2.1, 8)], [(-2.1, 4.2), (-4.6, 9.6), (-2.1, 8)], ("R", -1.3, 8, 2.6, 1.8)],
    "banderol": [("R", -9.8, -1.4, 19.6, 2.8), ("R", -5, 7, 10, 2.4), [(0, -11), (2.3, -5), (2.3, 10), (-2.3, 10), (-2.3, -5)],
                 ("R", -4.3, -8.4, 8.6, 3.9)],
    "supersonic": [[(0, -12.5), (2.6, -5), (2.6, 1), (8.4, 7), (8.4, 9), (2.6, 6.4), (2.6, 9.2), (4.4, 12), (-4.4, 12),
                    (-2.6, 9.2), (-2.6, 6.4), (-8.4, 9), (-8.4, 7), (-2.6, 1), (-2.6, -5)]],
    "unknown": [[(0, -9), (9, 7), (-9, 7)]],
}
MSL_TYPES = ("ballistic_missiles", "cruise_missiles", "supersonic_missiles", "unspecified_missiles")
FLAME = [(-3, 10.6), (0, 19.5), (3, 10.6)]
HALO = 52                      # the ring around the target, in pixels


def as_drone(m, missiles=()):
    """kyiv.html's asDrone: a target of no stated type is drawn, turned and named as a probable drone, unless a missile
    is on the map within MSL_NEAR_KM (150 km) of it — then "a drone or a missile". `missiles`: their (lon, lat)."""
    if m.get("type") != "unknown" or m.get("status"):
        return False
    return not any(math.hypot((lo - m["lon"]) * 70.68, (la - m["lat"]) * 111.0) <= 150 for lo, la in missiles)


def glyph_of(m, drone_like=False):
    """kyiv.html's GLYPH_BY_TYPE, with its jet and probable-drone cases."""
    t = m.get("type")
    if t == "drones" or drone_like:
        return "jetdrone" if m.get("jet") else "drone"
    return {"ballistic_missiles": "ballistic", "supersonic_missiles": "supersonic", "banderol_missiles": "banderol",
            "unknown": "unknown"}.get(t, "missile")


def colour_of(m, drone_like=False):
    """(fill, outline) as the Tactical page's map colours them (.mk.<type> .glyph)."""
    t = m.get("type")
    if t == "drones" or drone_like:
        return (AMBER if m.get("jet") else ORANGE), STROKE
    if t == "ballistic_missiles":
        return (255, 255, 255), (255, 23, 68)
    if t == "supersonic_missiles":
        return (255, 220, 168), (255, 106, 0)
    if t in ("cruise_missiles", "unspecified_missiles"):
        return (255, 32, 32), (255, 255, 255)
    if t == "banderol_missiles":
        return AMBER, STROKE
    return (255, 32, 32), (255, 255, 255)               # a warning sign: a target of no stated type near missiles


def orient(m, drone_like=False):
    """kyiv.html's orientOf: the silhouette turns to a course a post reported (any heading whose evidence has a
    confidence); with none, to the server's `face` (along the reported track, or into Ukraine), else north. A warning
    sign and an outcome stay upright."""
    if m.get("status") or (m.get("type") == "unknown" and not drone_like):
        return 0
    fc = m.get("face") or 0
    ev = (m.get("evidence") or {}).get("heading") or {}
    if m.get("heading") is None or ev.get("confidence") in (None, "", "none"):
        return fc
    return m["heading"]


def _font(paths, size):
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _rings(path):
    """"M x,y x,y … Z M …" (the pages' outlines, in the map's kilometres) → [[(x, y), …], …]."""
    out = []
    for part in re.split(r"[Mm]", path):
        part = part.replace("Z", " ").replace("z", " ").replace("L", " ")
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", part)]
        pts = list(zip(nums[0::2], nums[1::2]))
        if len(pts) >= 2:
            out.append(pts)
    return out


def _js_list(src, name):
    m = re.search(r"const " + name + r"=(\[.*?\]);", src, re.S)
    return json.loads(m.group(1).replace("'", '"')) if m else []


def _js_dict(src, name):
    m = re.search(r"const " + name + r"=\{(.*?)\};", src, re.S)
    return dict(re.findall(r"'?([\w\- ]+?)'?\s*:\s*'([^']*)'", m.group(1))) if m else {}


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


class MapShot:
    def __init__(self, static=STATIC):
        base = json.load(open(os.path.join(static, "kyiv-map.json"), encoding="utf-8"))
        self.c0, self.c1 = base["center"]
        self.kx, self.ky = base["kx"], base["ky"]
        self.features = [(f.get("raion"), f.get("obl"), f.get("key"), _rings(f["path"])) for f in base["features"]]
        self.districts = []
        try:
            kd = json.load(open(os.path.join(static, "kyiv-districts.json"), encoding="utf-8"))
            self.districts = [(d.get("uk") or d["name"], d.get("cx"), d.get("cy"), _rings(d["path"])) for d in kd["districts"]]
        except (OSError, ValueError, KeyError):
            pass
        self.rivers = []
        try:
            ua = json.load(open(os.path.join(static, "map-ua.json"), encoding="utf-8"))
            for r in ua.get("rivers", []):
                w = {"wide": 7, "mid": 5}.get(r.get("c"), 3)
                self.rivers += [(w, list(zip(ln[0::2], ln[1::2]))) for ln in r.get("l", [])]
        except (OSError, ValueError):
            pass
        page = open(os.path.join(static, "kyiv.html"), encoding="utf-8").read()
        i18n = open(os.path.join(static, "i18n.js"), encoding="utf-8").read()
        uk = _js_dict(i18n, "TOWN_UK")
        self.towns = [(uk.get(t[0], t[0]), self.proj(t[1], t[2]), len(t) > 3 and t[3] == 1) for t in _js_list(page, "TOWNS")
                      if len(t) < 4 or t[3] in (1, None)]
        adj = _js_dict(page, "RAION_ADJ")
        lbl = re.search(r"const RAION_LBL=\{(.*?)\};", page, re.S)
        self.raion_lbl = []
        if lbl:
            for k, x, y in re.findall(r"'?([\w-]+)'?:\[(-?[\d.]+),(-?[\d.]+)\]", lbl.group(1)):
                if k in adj:
                    self.raion_lbl.append(((adj[k] + " р-н").upper(), (float(x), float(y))))
        self.f = {s: _font(FONTS, s * SS) for s in (17, 19, 22, 26, 30)}
        self.fb = {s: _font(FONTS_B, s * SS) for s in (19, 22, 26, 30, 34)}

    def proj(self, lon, lat):
        return ((lon - self.c0) * self.kx, -(lat - self.c1) * self.ky)

    # ---- the view ------------------------------------------------------------------------------------------------
    def view(self, m):
        """A square of the map around the target: where it is, where it was reported before, Kyiv when it is near."""
        pts = [self.proj(m["lon"], m["lat"])]
        for h in (m.get("history") or [])[-6:]:
            if h.get("lon") is not None and h.get("lat") is not None:
                pts.append(self.proj(h["lon"], h["lat"]))
        kyiv = self.proj(30.52, 50.45)
        if math.dist(pts[0], kyiv) < 70:          # most of the oblast: the city is the reader's landmark
            pts.append(kyiv)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.5
        span = min(max(span, 30.0 if m.get("oblast_uid") == "31" else 50.0), 150.0)
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        if span >= 150.0:                         # a long track: the target stays in view, centred
            cx, cy = pts[0]
        return cx - span / 2, cy - span / 2, span

    # ---- the picture ---------------------------------------------------------------------------------------------
    def render(self, m, active=(), when="", ray=True, missiles=()):
        """JPEG bytes of the map around mark `m` (as /api/markers gives it), with the official alerts `active`.
        `ray`: draw its course — the caller says False when no post stated one (app/chanpost.py: stated_course).
        `missiles`: (lon, lat) of the missiles on the map, for a target of no stated type (as_drone)."""
        if Image is None:
            return None
        x0, y0, span = self.view(m)
        S = W * SS
        top, bottom = HEAD * SS, (W - FOOT) * SS
        k = (bottom - top) / span                       # pixels per km, the map between the two bands
        x0 -= ((S / k) - span) / 2                      # the map is wider than tall: widen the view to fill it

        def px(p):
            return ((p[0] - x0) * k, top + (p[1] - y0) * k)

        img = Image.new("RGB", (S, S), BG)
        d = ImageDraw.Draw(img, "RGBA")
        fills = alert_fill(active)
        # outlines: the oblasts around, Kyiv oblast's raions, the city — tinted by the official alerts
        for raion, obl, key, rings in self.features:
            if raion:
                continue
            lvl = fills.get("nb:" + (key or "")) or fills.get("obl:" + (obl or ""))
            for r in rings:
                d.polygon([px(p) for p in r], fill=NB)
                if lvl:
                    d.polygon([px(p) for p in r], fill=(RED_T if lvl == "R" else YEL_T)[:3] + (40,))
                d.line([px(p) for p in r] + [px(r[0])], fill=NB_LINE, width=SS)
        for raion, obl, key, rings in self.features:
            if not raion:
                continue
            for r in rings:
                d.polygon([px(p) for p in r], fill=RN)
                lvl = fills.get(raion)
                if lvl:
                    d.polygon([px(p) for p in r], fill=RED_T if lvl == "R" else YEL_T)
                d.line([px(p) for p in r] + [px(r[0])], fill=CITY_LINE if raion == "kyiv-city" else RN_LINE,
                       width=(3 if raion == "kyiv-city" else 2) * SS)
        if span <= 60:
            for name, cx, cy, rings in self.districts:
                for r in rings:
                    d.line([px(p) for p in r] + [px(r[0])], fill=KD_LINE, width=SS)
        for w, ln in self.rivers:
            d.line([px(p) for p in ln], fill=RIVER, width=w * SS, joint="curve")
        # the target's own room and the scale's are kept first: no name is written over them
        here = px(self.proj(m["lon"], m["lat"]))
        boxes = [(here[0] - HALO * SS, here[1] - HALO * SS, here[0] + HALO * SS, here[1] + HALO * SS),
                 (0, bottom - 52 * SS, 300 * SS, bottom)]
        bounds = (0, top, S, bottom)
        tag = self._tag(d, m, here, boxes, bounds)
        if span > 60:
            for text, p in self.raion_lbl:
                q = px(p)
                self._label(d, q, text, self.f[17], (138, 150, 170), boxes, bounds, anchor="mm")
        # the towns, the big ones first; a name that would cover another is left out
        for name, p, big in sorted(self.towns, key=lambda t: not t[2]):
            q = px(p)
            if not (0 <= q[0] <= S and top <= q[1] <= bottom):
                continue
            r = (5 if big else 3.5) * SS
            under = boxes[0][0] <= q[0] <= boxes[0][2] and boxes[0][1] <= q[1] <= boxes[0][3]   # under the target
            if self._label(d, (q[0] + r + 5 * SS, q[1]), name, self.fb[26] if big else self.f[19], INK if big else INK2,
                           boxes, bounds) or (big and not under):
                d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=INK if big else INK2, outline=STROKE, width=SS)
        if span <= 60:                            # the city's districts, quietly, where there is room
            for name, cx, cy, _rings_ in self.districts:
                if cx is not None:
                    self._label(d, px((cx, cy)), name.replace(" район", ""), self.f[17], (120, 132, 152), boxes, bounds,
                                anchor="mm")
        self._target(d, m, px, here, ray, as_drone(m, missiles), k, boxes, bounds)
        if tag:
            self._pill(d, *tag)
        self._bands(d, when, k)
        out = img.resize((W, W), Image.LANCZOS)
        buf = io.BytesIO()
        # JPEG, full colour resolution so the names stay sharp: Telegram re-encodes every photo as JPEG anyway, and
        # a PNG of this map took half the drawing time to compress
        out.save(buf, "JPEG", quality=90, subsampling=0)
        return buf.getvalue()

    @staticmethod
    def _free(box, boxes, bounds):
        if box[0] < bounds[0] or box[1] < bounds[1] or box[2] > bounds[2] or box[3] > bounds[3]:
            return False
        return not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in boxes)

    def _label(self, d, q, text, font, colour, boxes, bounds, anchor="lm"):
        bb = d.textbbox(q, text, font=font, anchor=anchor)
        pad = 3 * SS
        box = (bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad)
        if not self._free(box, boxes, bounds):
            return False
        boxes.append(box)
        d.text(q, text, font=font, fill=colour, anchor=anchor, stroke_width=3 * SS // 2, stroke_fill=STROKE)
        return True

    def _tag(self, d, m, here, boxes, bounds):
        """The place the post named, in a pill beside the target: right of it, else left, above, below."""
        text = (m.get("place") or "").strip()
        if not text:
            return None
        if len(text) > 34:
            text = text[:33] + "…"
        font = self.fb[30]
        w = d.textlength(text, font=font) + 28 * SS
        h = 50 * SS
        g = (HALO + 8) * SS
        for x, y in ((here[0] + g, here[1] - h / 2), (here[0] - g - w, here[1] - h / 2),
                     (here[0] - w / 2, here[1] - g - h), (here[0] - w / 2, here[1] + g)):
            box = (x, y, x + w, y + h)
            if self._free(box, boxes[1:], bounds):
                boxes.append(box)
                return box, text, font
        return None

    def _pill(self, d, box, text, font):
        d.rounded_rectangle(box, radius=12 * SS, fill=(18, 21, 27, 235), outline=(70, 78, 92), width=SS)
        d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=font, fill=INK, anchor="mm")

    def _target(self, d, m, px, here, ray=True, drone_like=False, k=1.0, boxes=None, bounds=None):
        fill, edge = colour_of(m, drone_like)
        alpha = 255
        if m.get("approach") or m.get("dest_only") or (m.get("place") or "").startswith("→"):
            # only where it is heading was said: drawn at that town as the app draws it — fainter, and from the side
            # a post named (its course) set off the town by a little, never more than 12 km (kyiv.html, apOff)
            alpha = 205
            if m.get("heading") is not None:
                a = math.radians(m["heading"])
                dd = min(60 * SS, 12 * k)
                here = (here[0] - dd * math.sin(a), here[1] + dd * math.cos(a))
        # the course ray's colour (.mk.<type> .hdg): a drone's own, red for a missile and for a Banderol
        col = (AMBER if m.get("jet") else ORANGE) if (m.get("type") == "drones" or drone_like) else MSL
        # where it was reported before, oldest first: a dotted line and a dot at each report
        hist = sorted((h for h in (m.get("history") or []) if h.get("lon") is not None and h.get("lat") is not None),
                      key=lambda h: h.get("ts") or 0)[-6:]
        trail = [px(self.proj(h["lon"], h["lat"])) for h in hist]
        if trail:
            path = trail + [here]
            for a, b in zip(path, path[1:]):
                n = max(1, int(math.dist(a, b) / (14 * SS)))
                for i in range(0, n, 2):
                    d.line([(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n),
                            (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)],
                           fill=col + (200,), width=4 * SS)
            for h, q in zip(hist, trail):
                r = 6 * SS
                d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=col + (150,), outline=STROKE, width=SS)
                if h.get("place") and boxes is not None:          # where it was reported, if there is room
                    self._label(d, (q[0] + r + 4 * SS, q[1]), str(h["place"])[:28], self.f[17], INK2, boxes, bounds)
        # a course, only when a post gave one: the ray and its chevron
        hd = m.get("heading")
        if hd is not None and ray:
            L = 110 * SS
            rad = math.radians(hd)
            tip = (here[0] + math.sin(rad) * L, here[1] - math.cos(rad) * L)
            d.line([here, tip], fill=col + (230,), width=5 * SS)
            a1, a2 = math.radians(hd + 150), math.radians(hd - 150)
            hl = 22 * SS
            d.polygon([tip, (tip[0] + math.sin(a1) * hl, tip[1] - math.cos(a1) * hl),
                       (tip[0] + math.sin(a2) * hl, tip[1] - math.cos(a2) * hl)], fill=col, outline=STROKE)
        # the halo, then the silhouette
        R = HALO * SS
        d.ellipse([here[0] - R, here[1] - R, here[0] + R, here[1] + R], outline=col + (120,), width=3 * SS)
        if m.get("type") == "ballistic_missiles":
            d.ellipse([here[0] - R * 1.4, here[1] - R * 1.4, here[0] + R * 1.4, here[1] + R * 1.4], outline=(255, 23, 68, 170), width=4 * SS)
        g = glyph_of(m, drone_like)
        sc = 3.9 * SS
        rot = math.radians(orient(m, drone_like))

        def tr(x, y):
            return (here[0] + (x * math.cos(rot) - y * math.sin(rot)) * sc, here[1] + (x * math.sin(rot) + y * math.cos(rot)) * sc)
        if g == "jetdrone":
            d.polygon([tr(*p) for p in FLAME], fill=(255, 179, 71))
        for part in GLYPHS[g]:
            if isinstance(part, tuple):
                _, x, y, w, h = part
                part = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            d.polygon([tr(*p) for p in part], fill=fill + (alpha,), outline=edge, width=2 * SS)
        if g == "unknown":                        # the warning sign's "!"
            d.line([tr(0, -4), tr(0, 1)], fill=STROKE, width=2 * SS)
            c = tr(0, 4)
            d.ellipse([c[0] - 1.2 * sc, c[1] - 1.2 * sc, c[0] + 1.2 * sc, c[1] + 1.2 * sc], fill=STROKE)

    def _bands(self, d, when, k):
        S = W * SS
        d.rectangle([0, 0, S, HEAD * SS], fill=(18, 21, 27))
        d.line([0, HEAD * SS, S, HEAD * SS], fill=(36, 40, 48), width=SS)
        d.text((26 * SS, HEAD * SS / 2), "HEIMDALL", font=self.fb[34], fill=INK, anchor="lm")
        d.text((250 * SS, HEAD * SS / 2), "Київ · Київщина", font=self.f[26], fill=INK2, anchor="lm")
        if when:
            d.text((S - 26 * SS, HEAD * SS / 2), when, font=self.fb[34], fill=INK, anchor="rm")
        y = (W - FOOT) * SS
        d.rectangle([0, y, S, S], fill=(18, 21, 27))
        d.line([0, y, S, y], fill=(36, 40, 48), width=SS)
        d.text((26 * SS, y + 30 * SS), "З дописів каналів, не радар · сирена й офіційна тривога — головне",
               font=self.f[19], fill=INK2, anchor="lm")
        d.text((26 * SS, y + 62 * SS), "Межі: OCHA · geoBoundaries (CC BY) · райони Києва © OpenStreetMap",
               font=self.f[17], fill=INK3, anchor="lm")
        # the scale: a round number of kilometres about a sixth of the picture
        km = next((v for v in (1, 2, 5, 10, 20, 50) if v * k >= S / 9), 50)
        bx, by = 26 * SS, y - 26 * SS
        d.line([bx, by, bx + km * k, by], fill=INK2, width=3 * SS)
        d.line([bx, by - 7 * SS, bx, by + 7 * SS], fill=INK2, width=2 * SS)
        d.line([bx + km * k, by - 7 * SS, bx + km * k, by + 7 * SS], fill=INK2, width=2 * SS)
        d.text((bx + km * k + 10 * SS, by), f"{km} км", font=self.f[19], fill=INK2, anchor="lm", stroke_width=SS, stroke_fill=STROKE)
