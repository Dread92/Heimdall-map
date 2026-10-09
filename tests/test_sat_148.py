"""1.48: the satellite layer, closer and sharper.

Sentinel at its full 10 m (zoom 13, built by scripts/build_imagery.py), and closer than that — a street, a building —
Esri World Imagery, asked of Esri by this server with the owner's key (ESRI_KEY): the key never reaches a browser,
nothing is kept here (Esri's terms), and the month's tiles are counted and capped under the free tier. The map zooms
in to 1 km across. Over the pictures the oblast and raion names are light on a dark halo.
"""
import os
import sqlite3
import threading
import urllib.error
import urllib.request
from unittest import mock

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, ADMIN = _read("static/kyiv.html"), _read("static/admin.html")
KYIV = (16, 38324, 22098)          # a zoom-16 tile over the centre of Kyiv
PARIS = (16, 33195, 22548)


class _Resp:
    def __init__(self, body=b"\xff\xd8\xff\xe0JFIF tile", ctype="image/jpeg", cc="max-age=86400"):
        self.body, self.headers = body, {"Content-Type": ctype, "Cache-Control": cc}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def _esri(cap=1800000, key="test-esri-key-0000"):
    store = server.Store(":memory:")
    return server.EsriTiles({"esri_key": key, "esri_monthly_tiles": cap}, store), store


def test_the_server_asks_esri_with_its_own_key_and_keeps_nothing():
    e, _ = _esri()
    seen = []

    def fake(req, timeout=None, context=None):
        seen.append((req.full_url, context))
        return _Resp()
    with mock.patch.object(server.urllib.request, "urlopen", fake):
        code, body, ctype, cc = e.fetch(*KYIV, ip="203.0.113.7")
    assert code == 200 and body.startswith(b"\xff\xd8") and ctype == "image/jpeg"
    url, ctx = seen[0]
    assert url.startswith("https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/16/22098/38324?")
    assert "token=test-esri-key-0000" in url and ctx is server._SSL_CTX      # z/y/x, the key on the server's request only
    assert cc == "private, max-age=86400"                                    # the reader's browser may keep it; no one else
    assert e.n_month == 1 and e.n_day == 1


def test_only_close_tiles_over_ukraine_are_ever_asked_for():
    e, _ = _esri()
    with mock.patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("asked Esri")):
        for z, x, y in (PARIS, (13, 4789, 2772), (19, 76636, 44356), (16, 1 << 16, 1)):
            assert e.fetch(z, x, y)[0] == 404, (z, x, y)
    assert e.n_month == 0
    no_key = server.EsriTiles({}, server.Store(":memory:"))
    assert not no_key.enabled() and no_key.fetch(*KYIV)[0] == 404


def test_the_month_and_the_day_are_capped_and_one_reader_cannot_spend_them():
    e, store = _esri(cap=40)
    with mock.patch.object(server.urllib.request, "urlopen", lambda req, timeout=None, context=None: _Resp()):
        codes = [e.fetch(*KYIV, ip=f"198.51.100.{i}")[0] for i in range(6)]
        assert codes == [200] * 4 + [429] * 2                                # a tenth of the month a day: 4
        assert not e.enabled()                                               # the page is told: Sentinel alone
        e.n_day, e.day = 0, "2000-01-01"
        e._roll()
        assert e.n_day == 0 and e.enabled()
        e.n_month = 40
        assert e.fetch(*KYIV)[0] == 429 and not e.enabled()                  # the month is spent
    e2, _ = _esri()
    e2.PER_IP_HOUR = 3
    with mock.patch.object(server.urllib.request, "urlopen", lambda req, timeout=None, context=None: _Resp()):
        assert [e2.fetch(*KYIV, ip="192.0.2.1")[0] for _ in range(4)] == [200, 200, 200, 429]
        assert e2.fetch(*KYIV, ip="192.0.2.2")[0] == 200
    assert not any("192.0.2" in k for k in e2.by_ip)                         # salted hashes, in memory only


def test_the_count_survives_a_restart():
    e, store = _esri()
    e.SAVE_EVERY = 2
    with mock.patch.object(server.urllib.request, "urlopen", lambda req, timeout=None, context=None: _Resp()):
        for _ in range(4):
            e.fetch(*KYIV)
    again = server.EsriTiles(e.cfg, store)
    assert again.stats()["tiles_month"] == 4 and again.stats()["tiles_today"] == 4


def test_a_refused_key_pauses_and_is_never_written_to_the_log():
    e, _ = _esri()
    logged = []
    err = b'{"error":{"code":498,"message":"Invalid token."}}'
    with mock.patch.object(server, "log", lambda *a: logged.append(" ".join(map(str, a)))):
        with mock.patch.object(server.urllib.request, "urlopen", lambda req, timeout=None, context=None: _Resp(err, "application/json")):
            assert e.fetch(*KYIV)[0] == 503
        st = e.stats()
        assert not e.enabled() and st["refused"]["img"] == "error 498: Invalid token." and st["paused"]["img"]   # Esri's own words
        with mock.patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("asked again")):
            assert e.fetch(*KYIV)[0] == 503                                  # paused: not asked again on every tile
        e.down["img"] = 0

        def http_err(req, timeout=None, context=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        with mock.patch.object(server.urllib.request, "urlopen", http_err):
            assert e.fetch(*KYIV)[0] == 503
    assert logged and not any("test-esri-key" in m or "token=" in m for m in logged)   # Esri's words, never the address


def test_the_route_and_the_page_flag():
    st = server.State(server.Store(":memory:"), {"esri_key": "test-esri-key-0000"})
    assert st.snapshot()["config"]["esri"] is True
    assert server.State(server.Store(":memory:"), {}).snapshot()["config"]["esri"] is False
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    real = urllib.request.urlopen
    try:
        with mock.patch.object(server.urllib.request, "urlopen",
                               lambda req, timeout=None, context=None: _Resp() if "arcgis" in getattr(req, "full_url", "") else real(req, timeout=timeout)):
            r = real(base + "/tiles/esri/16/38324/22098.jpg", timeout=10)
            assert r.status == 200 and r.headers["Content-Type"] == "image/jpeg" and r.read().startswith(b"\xff\xd8")
            for bad in ("/tiles/esri/16/33195/22548.jpg", "/tiles/esri/16/38324/22098.png", "/tiles/esri/../config.json"):
                try:
                    real(base + bad, timeout=10)
                    raise AssertionError(bad)
                except urllib.error.HTTPError as e:
                    assert e.code == 404, bad
    finally:
        srv.shutdown()
        server.Handler.state = old
    h = st.health()["imagery"]["esri"]
    assert h["key"] is True and h["tiles_month"] == 1 and h["cap_month"] == 1800000 and h["cap_day"] == 180000


def test_the_page_is_told_the_imagery_files_own_version_and_zoom(tmp_path, monkeypatch):
    p = str(tmp_path / "sat-ua.mbtiles")
    db = sqlite3.connect(p)
    db.executescript("CREATE TABLE metadata (name TEXT, value TEXT); CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER,"
                     " tile_row INTEGER, tile_data BLOB); INSERT INTO tiles VALUES (13,4790,5419,x'00');"
                     " INSERT INTO metadata VALUES ('version','2'),('maxzoom','13');")
    db.commit()
    db.close()
    monkeypatch.setattr(server, "SAT", server.SatTiles(p))
    c = server.State(server.Store(":memory:"), {}).snapshot()["config"]
    assert (c["sat"], c["sat_v"], c["sat_z"]) == (True, "2", 13)
    monkeypatch.setattr(server, "SAT", server.SatTiles(str(tmp_path / "none.mbtiles")))
    c = server.State(server.Store(":memory:"), {}).snapshot()["config"]
    assert (c["sat"], c["sat_v"], c["sat_z"]) == (False, None, None)
    # the page asks under that version, to that zoom — never a version written in the page that could run ahead of the file
    assert "var SAT_V='1', SAT_MAX=12," in PAGE and "const ok=!!c.sat, v=String(c.sat_v||'1'), z=Math.max(5,Math.min(16,+c.sat_z||12))" in PAGE
    assert "if(v!==SAT_V){ const g=$('sat'); if(g) g.innerHTML=''; }" in PAGE
    src = _read("scripts/build_imagery.py")
    assert 'ap.add_argument("--maxzoom", type=int, default=13)' in src and '"version": a.version' in src


def test_the_page_draws_esri_over_sentinel_from_zoom_14_and_zooms_to_a_kilometre():
    assert ('<g id="sat" clip-path="url(#uaclip)"></g>\n    <g id="esri" clip-path="url(#uaclip)"></g>\n'
            '    <g id="tiles" clip-path="url(#uaclip)"></g>') in PAGE
    assert "const z=ESRI_OK&&svg.classList.contains('satd')?tileZoom():0; const on=z>=14;" in PAGE
    assert "placeTiles(g,Math.max(14,Math.min(18,z)),(z,x,y)=>`/tiles/esri/${z}/${x}/${y}.jpg`,140,14);" in PAGE
    assert "if(zmin!=null&&z>zmin) return placeTiles(g,z-1,url,max,zmin);" in PAGE     # a large screen: one zoom out, not nothing
    assert "Powered by Esri" in PAGE and "Esri, Maxar, Earthstar Geographics, and the GIS User Community" in PAGE
    assert "if(c.contains('esrid')) e.push(ESRI_IMG);" in PAGE and "if(e.length) p.push('Powered by Esri · '+e.join(' · '));" in PAGE
    assert "a.classList.toggle('long',p.length>1||e.length>1);" in PAGE and ".attrib.long{max-width:calc(100vw - 72px);bottom:34px}" in PAGE
    assert "function setView(cx,cy,w){VB.w=Math.max(1,Math.min(1500,w));" in PAGE
    assert "function zoomAt(f,cx,cy,fast){const nw=Math.max(1,Math.min(1500,VB.w/f))" in PAGE
    assert "#sat,#esri{filter:" in PAGE and "svg.no-sat #sat,svg.no-sat #esri,svg.no-sat #lbl{display:none}" in PAGE
    assert "token" not in PAGE.split("function updateEsri", 1)[1][:600]      # the page never holds the key


def test_oblast_names_read_over_the_pictures():
    assert "svg.tiled .oblbl,svg.tiled .rnlbl{fill:#dfe6ef;paint-order:stroke;stroke:rgba(5,8,12,.85);" in PAGE
    assert "body.m-day svg.tiled .oblbl,body.m-day svg.tiled .rnlbl{fill:#1c222b;stroke:rgba(255,255,255,.86)}" in PAGE


def test_the_layer_choice_is_saved_again():
    # 1.47.1 had put the save inside the end of a comment: no layer choice was remembered
    assert "const saveLayers=()=>{try{localStorage.setItem('layers'," in PAGE
    i = PAGE.index("document.querySelectorAll('#layerbox input[data-l]').forEach(cb=>cb.onchange=")
    body = PAGE[i:PAGE.index("applyLayers();});", i)]
    line = next(ln for ln in body.split("\n") if "saveLayers()" in ln)
    assert line.lstrip().startswith("saveLayers();")


def test_the_key_is_set_by_the_owner_and_the_count_is_on_the_dashboard():
    bat = open(os.path.join(ROOT, "scripts", "set-esri-key.bat"), "rb").read()
    assert b"\r\n" in bat and b"(echo ESRI_KEY=%KEY%)| fly secrets import -a %APP%" in bat and b'set "KEY="' in bat
    assert server.DEFAULT_CONFIG["esri_key"] == "" and server.DEFAULT_CONFIG["esri_monthly_tiles"] < 2000000
    assert '("ESRI_KEY", "esri_key")' in _read("app/server.py")
    assert "${imagery(H.imagery||{})}" in ADMIN and "img_esri:'Esri close zoom: {0} tiles this month (cap {1})" in ADMIN
