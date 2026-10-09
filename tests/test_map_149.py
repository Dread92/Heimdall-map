"""1.49: the map — zooming that keeps up on a phone, no stall zoomed in, a background of three, the towns of every
oblast, and Kyiv named without a place in it marked as the city, not a point at its centre.
"""
import json
import os
import re
import threading
import urllib.error
import urllib.request
from unittest import mock

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, REPLAY, SW = _read("static/kyiv.html"), _read("static/i18n.js"), _read("static/replay.js"), _read("static/sw.js")
KYIV = (12, 2395, 1381)


class _Resp:
    def __init__(self, body=b"\x89PNG tile", ctype="image/png"):
        self.body, self.headers = body, {"Content-Type": ctype, "Cache-Control": "max-age=3600"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def _esri():
    return server.EsriTiles({"esri_key": "test-esri-key-0000"}, server.Store(":memory:"))


# ---- the streets from Esri: over the imagery, and the Map ----------------------------------------------------------
def test_the_roads_and_names_and_the_map_come_from_the_static_basemap_tiles_in_the_readers_language():
    e, seen = _esri(), []
    with mock.patch.object(server.urllib.request, "urlopen", lambda req, timeout=None, context=None: seen.append(req.full_url) or _Resp()):
        assert e.fetch(*KYIV, kind="lbl", lang="uk")[0] == 200
        assert e.fetch(10, 598, 345, kind="mapn", lang="fr")[0] == 200
        assert e.fetch(10, 598, 345, kind="map", lang="xx")[0] == 200
    base = "https://static-map-tiles-api.arcgis.com/arcgis/rest/services/static-basemap-tiles-service/v1/"
    assert seen[0].startswith(base + "arcgis/imagery/labels/static/tile/12/1381/2395?language=uk&worldview=unitedStatesOfAmerica&token=")
    assert seen[1].startswith(base + "arcgis/streets-night/static/tile/10/345/598?language=fr&worldview=")
    assert "language=" not in seen[2] and "worldview=unitedStatesOfAmerica" in seen[2]   # an unknown language: none asked
    assert e.n_month == 3                                                    # one cap for every kind
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("asked Esri")):
        assert e.fetch(8, 149, 86, kind="lbl")[0] == 404                     # the names only from zoom 9
        assert e.fetch(3, 4, 2, kind="map")[0] == 404 and e.fetch(*KYIV, kind="nope")[0] == 404
        assert e.fetch(10, 5, 5, kind="map")[0] == 404                       # far from Ukraine


def test_style_preferences_esri_refuses_are_dropped_once_and_remembered():
    e, seen = _esri(), []

    def first_refuses(req, timeout=None, context=None):
        seen.append(req.full_url)
        if "worldview" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
        return _Resp()
    with mock.patch.object(server, "log", lambda *a: None), mock.patch.object(server.urllib.request, "urlopen", first_refuses):
        assert e.fetch(*KYIV, kind="lbl", lang="en")[0] == 200
        assert e.fetch(*KYIV, kind="lbl", lang="en")[0] == 200
    assert "worldview" in seen[0] and "worldview" not in seen[1] and len(seen) == 3 and "lbl" in e.no_prefs


def test_the_routes():
    st = server.State(server.Store(":memory:"), {"esri_key": "test-esri-key-0000"})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    real, seen = urllib.request.urlopen, []
    try:
        with mock.patch.object(server.urllib.request, "urlopen",
                               lambda req, timeout=None, context=None: seen.append(req.full_url) or _Resp()
                               if "arcgis" in getattr(req, "full_url", "") else real(req, timeout=timeout)):
            r = real(base + "/tiles/esri/lbl/12/2395/1381.png?lang=uk", timeout=10)
            assert r.status == 200 and r.headers["Content-Type"] == "image/png" and "private" in r.headers["Cache-Control"]
            assert real(base + "/tiles/esri/mapn/10/598/345.png?lang=en", timeout=10).status == 200
            assert real(base + "/tiles/esri/img/16/38324/22098.jpg", timeout=10).status == 200
            for bad in ("/tiles/esri/lbl/12/2395/1381.gif", "/tiles/esri/sat/12/2395/1381.png", "/tiles/esri/lbl/x/1/1.png"):
                try:
                    real(base + bad, timeout=10)
                    raise AssertionError(bad)
                except urllib.error.HTTPError as e:
                    assert e.code == 404, bad
    finally:
        srv.shutdown()
        server.Handler.state = old
    assert "language=uk" in seen[0] and "arcgis/streets-night" in seen[1] and "World_Imagery" in seen[2]


# ---- the page: Satellite, Map or Plain ------------------------------------------------------------------------------
def test_the_background_is_one_choice_of_three():
    assert ('<div class="lbase" id="lbase" role="radiogroup"><span class="lbh" data-t="l_base">Background</span><div class="lbopts">'
            '<label data-b="sat" hidden><input type="radio" name="lbase" value="sat">') in PAGE
    assert '<input type="radio" name="lbase" value="map">' in PAGE and '<input type="radio" name="lbase" value="none">' in PAGE
    assert "LAYERS.sat=rb.value==='sat'; LAYERS.tiles=rb.value==='map'; saveLayers(); applyLayers();" in PAGE
    assert "const b=LAYERS.sat?'sat':LAYERS.tiles?'map':'none';" in PAGE
    assert ".layermenu label[hidden]{display:none}" in PAGE            # the satellite stays hidden until the server has it
    for s in ("l_base:'Background',l_sat:'Satellite',l_map:'Map',l_plain:'Plain'", "l_base:'Підкладка',l_sat:'Супутник',l_map:'Карта'",
              "l_base:'Fond de carte',l_sat:'Satellite',l_map:'Plan',l_plain:'Sans fond'"):
        assert s in I18N
    assert "l_tiles" not in I18N


def test_the_streets_over_the_imagery_and_the_map_with_esri_and_osm_without():
    i = PAGE.index('<g id="sat"')
    order = [PAGE.index(f'<g id="{g}" clip-path="url(#uaclip)"></g>') for g in ("sat", "esri", "tiles", "emap", "lbl")]
    assert order == sorted(order) and order[0] == i
    assert "placeTiles(g,Math.min(18,z),(z,x,y)=>`/tiles/esri/lbl/${z}/${x}/${y}.png?lang=${LANG}`,60,9);" in PAGE
    assert "const kind=MODE==='day'?'map':'mapn';" in PAGE
    assert "placeTiles(g,Math.max(4,Math.min(18,tileZoom()-1)),(z,x,y)=>`/tiles/esri/${kind}/${z}/${x}/${y}.png?lang=${LANG}`,60,4);" in PAGE
    assert "const on=LAYERS.tiles&&ESRI_OK&&MAP&&!CITY&&!LITE_ON();" in PAGE
    # our own names step aside where Esri's are drawn
    assert "svg.lbld #towns,svg.mapd #towns,svg.lbld #minorg,svg.lbld #villg,svg.mapd #minorg,svg.mapd #villg{display:none}" in PAGE
    assert "var ESRI_SRC='Esri, TomTom, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors, and the GIS User Community';" in PAGE
    assert "if(c.contains('lbld')||c.contains('mapd')) e.push(ESRI_SRC);" in PAGE


# ---- zooming --------------------------------------------------------------------------------------------------------
def test_a_pinch_or_the_wheel_scales_the_last_picture_and_draws_once_at_rest():
    assert "function applyVB(fast){ if(fast){ fastVB(); return; }" in PAGE
    assert "svg.style.transform=`translate(${(bx1-k*bx0).toFixed(2)}px,${(by1-k*by0).toFixed(2)}px) scale(${k.toPrecision(6)})`;" in PAGE
    assert "clearTimeout(VBT); VBT=setTimeout(()=>applyVB(),150);" in PAGE
    assert "zoomAt(e.deltaY<0?1.2:1/1.2,cx,cy,true);},{passive:false});" in PAGE               # the wheel
    assert "zoomAt(d/lastDist,cx,cy,true); if(lastMid){VB.x-=(mid[0]-lastMid[0])*k;VB.y-=(mid[1]-lastMid[1])*k;applyVB(true);}" in PAGE
    assert "const dx=(e.clientX-prev[0])*k, dy=(e.clientY-prev[1])*k; VB.x-=dx;VB.y-=dy;applyVB(); }" in PAGE   # a drag redraws
    assert "svg#map{transform-origin:0 0;will-change:transform}" in PAGE and "svg.zoomg :not(.mk)>text{display:none}" in PAGE
    # the view's arithmetic uses the map's box without the transform
    assert "const SR=()=>(VBC&&SVGR)?SVGR:(SVGR=svg.getBoundingClientRect());" in PAGE
    assert PAGE.count("svg.getBoundingClientRect()") == 1 and "function toSvg(px,py){const r=SR();" in PAGE


def test_tiles_of_the_zoom_before_stay_until_the_new_ones_have_come():
    assert "if(inView&&+im.dataset.z!==z) im.classList.add('old'); else im.remove(); }" in PAGE
    assert "im.addEventListener('load',tileDone); im.addEventListener('error',tileDone);" in PAGE
    assert "g._sw=setTimeout(()=>g.querySelectorAll('image.old').forEach(i=>i.remove()),4000); return; }" in PAGE


def test_lengths_sized_by_the_zoom_keep_their_digits():
    # 1.48: at 1 km across a drone was drawn scale(0.00) — the mark vanished
    assert "let KDIG=2; const kx=v=>v.toFixed(KDIG);" in PAGE and "KDIG=Math.max(2,Math.ceil(-Math.log10(KPX||1))+3);" in PAGE
    for src in (PAGE, REPLAY):
        assert not re.search(r"KPX[^`;]{0,40}\)\.toFixed\(", src), re.search(r".{60}KPX[^`;]{0,40}\)\.toFixed\(.{20}", src)
        assert "KPX.toFixed(" not in src
    assert "`rotate(${orientOf(m)}) scale(${kx(gs*(m.stale&&!m.status&&!m.endedBy?0.8:1))})`" in PAGE


def test_zoomed_in_nothing_large_is_dashed_or_animated():
    assert "svg.classList.toggle('deep',KPX<0.011);" in PAGE
    rule = PAGE[PAGE.index("svg.deep .ring,"):]
    rule = rule[:rule.index("}") + 1]
    for sel in (".ring", ".zone", ".ob.occ", "#oblevt .obring", ".mk .reach", ".mk .ahead", ".trail", ".homemk .ring"):
        assert f"svg.deep {sel}" in rule
    assert rule.endswith("{stroke-dasharray:none!important;animation:none!important}")


# ---- the towns of every oblast --------------------------------------------------------------------------------------
def test_the_towns_of_every_oblast():
    d = json.loads(_read("static/towns-ua.json"))
    names = {t[0] for t in d["towns"]}
    assert len(d["towns"]) >= 300 and all(t[4] in (1, 2) for t in d["towns"])
    assert {"Чугуїв", "Балаклія", "Берестин", "Гадяч", "Карлівка", "Калуш", "Хрустальний", "Миколаївка"} <= names
    assert not names & {"Красний Луч", "Черемушки", "Харків", "Полтава", "Бровари"}   # renamed / city section / in TOWNS
    for n, lon, lat, pop, tier in d["towns"]:
        assert 22 < lon < 40.3 and 44.3 < lat < 52.4, n
    assert "async function loadTownsUA(){ const g0=$('twng'); if(!g0||g0.childElementCount||loadTownsUA.busy) return;" in PAGE
    assert "try{ const d=await(await fetch('/static/towns-ua.json')).json();" in PAGE
    assert "+'<g id=\"twng\"></g><g id=\"minorg\"></g><g id=\"villg\"></g>';\n  if(LAYERS.towns) loadTownsUA();" in PAGE
    # 1.49.1: a layer of its own — on by default on a computer, off on a phone, where it was unreadable
    assert "towns:window.innerWidth>=1000," in PAGE and '<input type="checkbox" data-l="towns">' in PAGE
    assert "if(cb.dataset.l==='towns'&&cb.checked)loadTownsUA();" in PAGE and "svg.no-towns #twng{display:none}" in PAGE
    assert "@media (max-width:999px){svg.veryfar #twng,svg.far .tw1{display:none}}" in PAGE
    assert "if(it.pr>=3||it.e.classList.contains('tw')){" in PAGE                 # no nameless dots
    for s_ in ("l_towns:'Main towns of every oblast'", "l_towns:'Основні міста кожної області'", "l_towns:'Villes principales de chaque oblast'"):
        assert s_ in I18N
    assert "e.classList.contains('rg')||e.classList.contains('tw2')?2:" in PAGE      # the collision pass ranks them
    assert "svg.wide #twng,svg.veryfar .tw1,svg.no-towns #twng{display:none}" in PAGE and "svg.classList.toggle('wide',VB.w>520);" in PAGE
    assert "svg.veryfar.no-minor .town:not(.big):not(.rg):not(.uac):not(.tw2){display:none}" in PAGE
    assert "'/static/towns-ua.json'" in SW
    src = _read("scripts/build_towns.py")
    assert "MIN_POP = 10000" in src and 'CENTRES = {"PPLA", "PPLA2"}' in src and "geonames" in src.lower()


# ---- Kyiv named without a place in it -------------------------------------------------------------------------------
def _one(ch, text):
    ms = geo.parse_for_channel(ch, text)
    assert len(ms) == 1, (text, ms)
    return ms[0], (ms[0].get("evidence") or {}).get("position") or {}


def test_kyiv_without_a_place_in_it_is_the_city_not_a_point_at_its_centre():
    for ch, text, bank in (("monitor_ukr", "1 реактивний БпЛА Шахед на околицях правого берега Києва", "right"),
                           ("kyiv_airdef", "Дрон над лівим берегом Києва", "left"),
                           ("kyiv_airdef", "Шахед над Києвом", None), ("kyiv_airdef", "Дрон біля Києва", None)):
        m, pos = _one(ch, text)
        assert (m["place"], m["oblast_uid"], pos["confidence"]) == ("область", "31", "low"), text
        assert pos.get("bank") == bank and "the city is marked" in pos["method"]
    m, pos = _one("kyiv_airdef", "Шахед над Оболонню")                       # a district keeps its point
    assert m["place"] == "Оболонь" and pos["confidence"] == "high"
    m, pos = _one("kpszsu", "БпЛА на півночі від Києва")                       # a side of Kyiv: the oblast (1.45.1)
    assert (m["place"], m["oblast_uid"]) == ("область", "14")
    m, _ = _one("kpszsu", "Ударні БпЛА з півночі на Київ")                    # a course to Kyiv stays an approach
    assert m["place"] == "→ Київ" and m["approach"]
    # the page says where in the city it is not
    assert "if(ps.bank) return t('bank_'+ps.bank)+(o?' · '+o:'');" in PAGE
    for s in ("bank_right:'right bank'", "bank_left:'лівий берег'", "city_somewhere:'quelque part dans la ville'"):
        assert s in I18N
