"""1.58.16 — the hromadas on the map. The owner gave the administrative boundaries (ukr_admin_boundaries.gdb, OCHA's
COD-AB) "pour t'aider avec les districts sur la map".

The official data names some alerts by hromada ("м. Нікополь та Нікопольська територіальна громада"). Without their
outlines such an alert coloured its whole raion, and a place anywhere in that raion read "alert in part of your raion".
With static/hromadas/<oblast>.json the alert is the hromada's: painted on it, the place inside it under it, the place
in another hromada of the raion not."""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import areas  # noqa: E402

HDIR = os.path.join(ROOT, "static", "hromadas")
UAR = json.load(open(os.path.join(ROOT, "data", "ua_regions.json"), encoding="utf-8"))
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
REPLAY = open(os.path.join(ROOT, "static", "replay.js"), encoding="utf-8").read()
SW = open(os.path.join(ROOT, "static", "sw.js"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
HJS = os.path.join(ROOT, "static", "hromadas.js")
NODE = shutil.which("node")

NIKOPOL = (34.392, 47.567)       # the city of Nikopol — Нікопольська громада (351)
MARHANETS = (34.627, 47.648)     # the city of Marhanets — Марганецька громада (349), the same raion
HOSTOMEL = (30.262, 50.569)      # Гостомельська громада (704), Bucha raion, Kyiv oblast


def hal(rid, obl, raion_key, level="red", title="громада"):
    return {"location_uid": f"ua-{rid}", "location_type": "hromada", "oblast_uid": obl, "raion_key": raion_key,
            "alert_level": level, "alert_type": "air_raid", "location_title": title}


def files():
    return sorted(f for f in os.listdir(HDIR) if f.endswith(".json"))


# ---- the data -----------------------------------------------------------------------------------------------------------
def test_every_outline_is_an_official_hromada_of_its_oblast():
    n = 0
    for f in files():
        d = json.load(open(os.path.join(HDIR, f), encoding="utf-8"))
        obl = f[:-5]
        assert d["obl"] == obl and "CC BY 3.0 IGO" in d["license"]
        km = json.load(open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8"))
        assert (d["center"], d["kx"], d["ky"]) == (km["center"], km["kx"], km["ky"])   # the map's own kilometres
        for rid, h in d["h"].items():
            c = UAR["communities"][rid]
            dist = UAR["districts"].get(c.get("d") or "") or {}
            assert (dist.get("obl") or c.get("obl")) == obl
            assert h["r"] == dist.get("key")
            assert h["p"] and all(len(r) >= 6 and len(r) % 2 == 0 for r in h["p"])
            n += 1
    # all but the one the GDB has twice in one raion (Сумський: Миколаївська селищна and сільська)
    assert n >= len(UAR["communities"]) - 3


def test_the_outlines_are_where_the_hromadas_are():
    fills = areas.alert_fill([hal("351", "9", "nikopolskyi")])
    assert areas.in_hromada(*NIKOPOL, fills)
    assert not areas.in_hromada(*MARHANETS, fills)
    assert areas.in_hromada(*HOSTOMEL, areas.alert_fill([hal("704", "14", "bucha")]))


# ---- the server: the held rule and the channel picture follow the hromada ------------------------------------------------
def test_a_hromada_alert_is_the_hromadas_not_its_raions():
    f = areas.alert_fill([hal("351", "9", "nikopolskyi")])
    assert f == {"hr:9:351": "R"}                      # was {"nb:nikopolskyi": "R"}: the whole raion
    assert areas.under_alert(*NIKOPOL, f)
    assert not areas.under_alert(*MARHANETS, f)        # another hromada of the raion: no alert over it
    k = areas.alert_fill([hal("704", "14", "bucha", "yellow")])
    assert k == {"hr:14:704": "Y"} and "bucha" not in k


def test_a_hromada_with_no_outline_still_colours_its_raion():
    f = areas.alert_fill([hal("999999", "9", "nikopolskyi")])
    assert f == {"nb:nikopolskyi": "R"}
    assert areas.under_alert(*MARHANETS, f)
    assert areas.alert_fill([hal("888888", "14", "bucha")]) == {"bucha": "R"}


def test_close_to_the_line_belongs_to_both_sides():
    f = areas.alert_fill([hal("351", "9", "nikopolskyi")])
    rings = areas.hromada_rings("9", "351")
    x, y = rings[0][0]
    c0, c1 = areas._BASE["center"]
    kx, ky = areas._BASE["kx"], areas._BASE["ky"]
    # a point on the outline, then 1 km and 4 km outward (away from the hromada's middle)
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx, dy = x - mx, y - my
    L = (dx * dx + dy * dy) ** 0.5
    for d, want in ((1.0, True), (4.0, False)):
        px, py = x + dx / L * d, y + dy / L * d
        lon, lat = px / kx + c0, c1 - py / ky
        assert areas.in_hromada(lon, lat, f) is want, d


def test_the_channel_picture_tints_a_kyiv_oblast_hromada():
    mapshot = pytest.importorskip("mapshot")
    if mapshot.Image is None:
        pytest.skip("no Pillow")
    shot = mapshot.MapShot()
    m = {"id": "x/1", "type": "drones", "lon": 30.30, "lat": 50.60, "place": "Гостомель", "oblast_uid": "14",
         "ts": "2026-10-14T18:00:00Z", "channel": "chyste_nebo"}
    a = shot.render(m, [], "21:00")
    b = shot.render(m, [hal("704", "14", "bucha")], "21:00")
    c = shot.render(m, [{"oblast_uid": "14", "location_type": "raion", "raion_key": "bucha", "alert_level": "red",
                         "location_title": "Бучанський район"}], "21:00")
    assert a != b and b != c                           # tinted, and not as the whole raion


# ---- the pages ---------------------------------------------------------------------------------------------------------
def test_the_pages_fetch_and_paint_the_outlines():
    assert '<script src="/static/hromadas.js"></script>' in TAC
    assert "sc.src='/static/hromadas.js'" in LIGHT and '<script src="/static/hromadas.js">' not in LIGHT   # loaded when needed
    for page in (TAC, LIGHT):
        assert "HROMADA.need(" in page and "HROMADA.covers(" in page
    # the Tactical map: no longer the raion, the hromada's own path, under the raions' names
    assert "a.location_type!=='oblast'&&!hromOf(a)" in TAC
    assert "a.location_type==='city')&&!hromOf(a)" in TAC
    assert '<g id="hromg"></g>' in TAC and TAC.index('id="hromg"') < TAC.index('class="rnlbl"')
    assert "#hromg .hr:not(.R):not(.Y){display:none}" in TAC
    # a place: its hromada's alert is its own; H only for another hromada of its raion, or one with no outline yet
    assert "const mine=air.filter(a=>covers(a)||hIn(a))" in TAC
    assert "pl.h||unitName(pl.u)" in TAC
    assert "function placeStatus(uid, PR, pt)" in LIGHT and "placeStatus(uid,PR,ptOf(p))" in LIGHT
    assert "inPart(a,r)&&!hromOf(a)) L='H'" in LIGHT
    # the replay too
    assert "location_uid:a.k" in REPLAY and "HROMADA.need(" in REPLAY


def test_the_band_counts_hromadas_as_hromadas():
    assert "hR?tn('hrom_red',hR)" in TAC
    for k in ("hrom_red_1", "hrom_yel_1"):
        assert I18N.count(k + ":") == 3
    assert "hrom_red_n:" in I18N and "hrom_red_5:'{0} громад червоні'" in I18N


def test_kept_offline_like_the_rest_of_the_map():
    assert "'/static/hromadas.js'" in SW
    assert "/^\\/static\\/hromadas\\/\\d+\\.json$/.test(key)" in SW


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_phone_test_matches_the_servers():
    d = json.load(open(os.path.join(HDIR, "9.json"), encoding="utf-8"))
    pts = {"nikopol": NIKOPOL, "marhanets": MARHANETS}
    prog = ("const H=require(process.argv[1]);const i=JSON.parse(require('fs').readFileSync(0,'utf8'));H.load('9',i.d);"
            "const a={location_uid:'ua-351',location_type:'hromada',oblast_uid:'9'};const h=H.of(a);"
            "const pr=(lon,lat)=>[(lon-i.d.center[0])*i.d.kx,-(lat-i.d.center[1])*i.d.ky];"
            "const o={};for(const [k,[lon,lat]] of Object.entries(i.pts)){const [x,y]=pr(lon,lat);o[k]=H.covers(h,x,y);}"
            "o.none=H.of({location_uid:'ua-1',location_type:'hromada',oblast_uid:'9'});"
            "o.raion=H.id({location_uid:'ua-351',location_type:'raion'});o.path=H.path(h).slice(0,1);"
            "console.log(JSON.stringify(o));")
    out = subprocess.run([NODE, "-e", prog, HJS], input=json.dumps({"d": d, "pts": pts}), capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r == {"nikopol": True, "marhanets": False, "none": None, "raion": None, "path": "M"}
