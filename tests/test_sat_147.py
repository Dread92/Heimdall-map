"""1.47: the satellite layer — Ukraine from the ESA WorldCover Sentinel-2 composite of 2021, as tiles this server
serves itself (scripts/build_imagery.py builds them once; scripts/upload-imagery.bat puts them on the volume).

No map provider is asked for anything: nobody learns which part of the country a reader looks at, and nothing is
paid per tile. The tiles are drawn inside Ukraine only, under the OSM streets, at every zoom.
"""
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N = _read("static/kyiv.html"), _read("static/i18n.js")


def _mbtiles(path, tiles):
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE metadata (name TEXT, value TEXT);"
                     "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);")
    for (z, x, y), data in tiles.items():
        db.execute("INSERT INTO tiles VALUES (?,?,?,?)", (z, x, (1 << z) - 1 - y, data))   # TMS rows, as the format wants
    db.commit()
    db.close()


def test_a_tile_is_read_by_its_map_address(tmp_path):
    p = str(tmp_path / "sat-ua.mbtiles")
    sat = server.SatTiles(p)
    assert not sat.available() and sat.tile(12, 2395, 1386) is None          # no file: no layer, no error
    _mbtiles(p, {(12, 2395, 1386): b"RIFF-kyiv", (5, 18, 10): b"RIFF-ua"})
    sat.checked = 0
    assert sat.available()
    assert sat.tile(12, 2395, 1386) == b"RIFF-kyiv" and sat.tile(5, 18, 10) == b"RIFF-ua"
    assert sat.tile(12, 2395, 1387) is None and sat.tile(12, 99999, 1) is None and sat.tile(30, 1, 1) is None
    # a new file put in place (upload-imagery.bat) is read without a restart
    os.remove(p)
    _mbtiles(p, {(12, 2395, 1386): b"RIFF-new"})
    os.utime(p, (time.time() + 5, time.time() + 5))
    sat.checked = 0
    assert sat.tile(12, 2395, 1386) == b"RIFF-new"


def test_the_server_sends_tiles_the_browser_keeps(tmp_path, monkeypatch):
    p = str(tmp_path / "sat-ua.mbtiles")
    _mbtiles(p, {(12, 2395, 1386): b"RIFF0000WEBPVP8 tile"})
    monkeypatch.setattr(server, "SAT", server.SatTiles(p))
    st = server.State(server.Store(":memory:"), {})
    assert st.snapshot()["config"]["sat"] is True                              # the page offers the layer
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        r = urllib.request.urlopen(base + "/tiles/sat/12/2395/1386.webp?v=1", timeout=10)
        assert r.status == 200 and r.headers["Content-Type"] == "image/webp"
        assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable" and r.read() == b"RIFF0000WEBPVP8 tile"
        for bad in ("/tiles/sat/12/2395/9.webp", "/tiles/sat/12/../../alerts.sqlite", "/tiles/sat/x/1/1.webp"):
            try:
                urllib.request.urlopen(base + bad, timeout=10)
                raise AssertionError(bad)
            except urllib.error.HTTPError as e:
                assert e.code == 404, bad
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_the_page_draws_it_inside_ukraine_under_the_streets():
    assert '<g id="sat" clip-path="url(#uaclip)"></g>' in PAGE and '<g id="tiles" clip-path="url(#uaclip)"></g>' in PAGE
    assert PAGE.index('<g id="sat"') < PAGE.index('<g id="tiles"') < PAGE.index('<g id="oblastsg">')
    assert "const LAYERS={sat:true,tiles:false," in PAGE                        # 1.47.1: the default on every device
    # 1.47.1: one picture or the other — zooming in no longer falls back to the OSM streets (1.49: one of three radios)
    assert "LAYERS.sat=rb.value==='sat'; LAYERS.tiles=rb.value==='map';" in PAGE
    assert "const want=(LAYERS.tiles&&SAT_KNOWN&&!stOK())||(LAYERS.sat&&SAT_KNOWN&&!SAT_OK);" in PAGE   # no imagery: the streets
    assert "if(!localStorage.getItem('layers_v3')){LAYERS.sat=true;LAYERS.tiles=false;" in PAGE   # once, for the saved choices
    assert '<label data-b="sat" hidden><input type="radio" name="lbase" value="sat">' in PAGE   # offered once the server has the tiles
    assert "satAvail(S.config);" in PAGE and "const ok=!!c.sat," in PAGE
    # 1.48: to the file's own deepest zoom, under the file's own version (tests/test_sat_148.py)
    assert "placeTiles(g,Math.max(5,Math.min(SAT_MAX,tileZoom())),(z,x,y)=>`/tiles/sat/${z}/${x}/${y}.webp?v=${SAT_V}`,160,5);" in PAGE
    assert "ESA WorldCover 2021" in PAGE and "Copernicus Sentinel data (2021)" in PAGE   # CC BY: credited whenever drawn
    assert "if(c.contains('satd')) p.push(SAT_ATTR);" in PAGE
    for lang in ("l_sat:'Satellite'", "l_sat:'Супутник'", "l_map:'Plan'"):
        assert lang in I18N


def test_the_build_and_the_upload_are_scripts_and_the_file_never_enters_git_or_the_image():
    src = _read("scripts/build_imagery.py")
    assert "esa-worldcover-s2" in src and "CC BY 4.0" in src and "Contains modified Copernicus Sentinel data (2021)" in src
    # the open sea is left out (the map's background is the sea), rivers and reservoirs are not
    assert "def sea_mask(cache):" in src and "binary_erosion" in src and "NIR_WATER" in src and "(36.5, 46.0)" in src
    bat = _read("scripts/upload-imagery.bat")
    assert "fly ssh sftp put imagery\\sat-ua.mbtiles /data/sat-ua.upload" in bat and 'mv -f /data/sat-ua.upload /data/sat-ua.mbtiles' in bat
    assert "imagery/" in _read(".gitignore") and "imagery/" in _read(".dockerignore")
    assert server.SAT_PATH.endswith("sat-ua.mbtiles")
