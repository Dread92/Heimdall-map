"""Build the satellite layer: data/… → sat-ua.mbtiles, Ukraine at zoom 5–12 (1.47).

    pip install rasterio numpy pillow scipy matplotlib     (only to build — the server needs none of them)
    python scripts/build_imagery.py OUT.mbtiles [--maxzoom 12] [--only N50E030,…]

The imagery is the ESA WorldCover Sentinel-2 composite for 2021: the median of a year of cloud-free Sentinel-2
pixels, 10 m, the same processing everywhere — so the tiles join without seams. It is read straight from the public
bucket (s3://esa-worldcover-s2, no account), at its 20 m overview, which is all zoom 12 needs (~25 m a pixel at
Kyiv's latitude); zoom 13 and closer are the zoom-12 tiles enlarged on the page.

Licence: CC BY 4.0. Attribution, on the map whenever the layer is drawn:
"ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium".

Only the tiles that touch Ukraine are made (its oblasts' outlines in static/kyiv-map.json, occupied land included);
the page draws them inside those outlines only (#uaclip). Output: an MBTiles file (SQLite), WebP tiles, rows in TMS
order as the format wants. The server serves it from the volume (/tiles/sat/z/x/y.webp, docs/TECHNICAL.md §10.1);
scripts/upload-imagery.bat puts it there.
"""
import argparse
import io
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "/vsicurl/https://esa-worldcover-s2.s3.eu-central-1.amazonaws.com/rgbnir/2021/N{lat:02d}/ESA_WorldCover_10m_2021_v200_N{lat:02d}E{lon:03d}_S2RGBNIR.tif"
ATTRIBUTION = ("ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) "
               "processed by ESA WorldCover consortium (CC BY 4.0)")
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", GDAL_HTTP_MAX_RETRY="5",
                GDAL_HTTP_RETRY_DELAY="3", GDAL_CACHEMAX=512)
R = 6378137.0
ORIGIN = math.pi * R                      # Web Mercator: x, y in [-ORIGIN, ORIGIN]
# the colour: reflectance × 10⁴ → 0–255, the same curve for every pixel of the country
HI, GAMMA = 2200.0, 1 / 1.7
WEBP_Q = 72


def ukraine_rings():
    with open(os.path.join(ROOT, "static", "kyiv-map.json"), encoding="utf-8") as f:
        m = json.load(f)
    c0, c1 = m["center"]
    kx, ky = m["kx"], m["ky"]
    out = []
    for o in m["oblasts"]:
        for part in re.findall(r"M([^MZ]+)Z?", o["path"]):
            pts = [tuple(map(float, p.split(","))) for p in part.split()]
            if len(pts) >= 3:
                out.append([(x / kx + c0, -y / ky + c1) for x, y in pts])
    return out


def tile_lonlat(x, y, z):
    n = 2 ** z
    return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def tiles_touching(rings, z):
    """The tiles of zoom z any part of which (a 5×5 sample) is in Ukraine."""
    from matplotlib.path import Path  # point-in-polygon for ~400,000 points at once
    paths = [Path(r) for r in rings]
    lons = [p[0] for r in rings for p in r]
    lats = [p[1] for r in rings for p in r]
    n = 2 ** z
    x0 = int((min(lons) + 180) / 360 * n)
    x1 = int((max(lons) + 180) / 360 * n)
    lat2y = lambda la: int((1 - math.log(math.tan(math.radians(la)) + 1 / math.cos(math.radians(la))) / math.pi) / 2 * n)  # noqa: E731
    y0, y1 = lat2y(max(lats)), lat2y(min(lats))
    f = np.array([0.02, 0.25, 0.5, 0.75, 0.98])
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1), indexing="ij")
    xs, ys = xs.ravel(), ys.ravel()
    fx, fy = np.meshgrid(f, f, indexing="ij")
    px = (xs[:, None] + fx.ravel()[None, :]) / n * 360 - 180
    py = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (ys[:, None] + fy.ravel()[None, :]) / n))))
    pts = np.column_stack([px.ravel(), py.ravel()])
    hit = np.zeros(len(pts), bool)
    for pa in paths:                                   # the oblasts do not overlap: inside one = inside Ukraine
        hit |= pa.contains_points(pts)
    hit = hit.reshape(len(xs), -1).any(axis=1)
    return {(int(x), int(y)) for x, y, h in zip(xs, ys, hit) if h}


def existing_cells(lats):
    """The 1° cells the product has (open sea has none), from the bucket's listing."""
    out = set()
    for la in lats:
        token = ""
        while True:
            url = (f"https://esa-worldcover-s2.s3.eu-central-1.amazonaws.com/?list-type=2&prefix=rgbnir/2021/N{la:02d}/"
                   + (f"&continuation-token={urllib.parse.quote(token)}" if token else ""))
            body = urllib.request.urlopen(url, timeout=60).read().decode()
            for m in re.finditer(r"N(\d\d)E(\d\d\d)_S2RGBNIR\.tif</Key>", body):
                out.add((int(m.group(1)), int(m.group(2))))
            nt = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
            if not nt:
                break
            token = nt.group(1)
    return out


# The open sea. The oblasts' outlines take in coastal waters (Odesa oblast reaches Zmiinyi), and the composite has sea
# pixels near the coast and none farther out: drawn as is, the Black Sea ended in a staircase of tiles. So the sea is
# made transparent and the map's own background shows there. "Sea" is water (near-infrared below NIR_WATER) that is
# connected to the open Black Sea — found once on a coarse mosaic of the whole region (1/750°, ~150 m), after an
# opening of ~1 km so that a river is never connected to it: the Dnipro and its reservoirs, the Dniester, the lakes
# stay in the picture; the sea, the Sea of Azov and the wide estuaries become the map's.
NIR_WATER = 700
SEA_RES = 750                          # pixels per degree of the coarse mosaic
SEA_BOX = (44, 53, 22, 41)             # lat0, lat1, lon0, lon1
SEEDS = ((31.5, 44.6), (36.5, 46.0))   # the open Black Sea south of Odesa; the Sea of Azov (its strait is too narrow
                                       # for the opening to keep the two joined)


def sea_mask(cache):
    """(mask uint8 1 = sea, its geotransform) for SEA_BOX, cached in `cache` (.npz)."""
    if os.path.exists(cache):
        z = np.load(cache)
        return z["sea"], Affine(*z["tr"])
    from scipy import ndimage
    la0, la1, lo0, lo1 = SEA_BOX
    have = existing_cells(range(la0, la1))
    water = np.zeros(((la1 - la0) * SEA_RES, (lo1 - lo0) * SEA_RES), bool)
    for la in range(la0, la1):
        for lo in range(lo0, lo1):
            r0, c0 = (la1 - 1 - la) * SEA_RES, (lo - lo0) * SEA_RES
            if (la, lo) not in have:
                water[r0:r0 + SEA_RES, c0:c0 + SEA_RES] = True           # no cell there: open sea
                continue
            for k in range(7):
                try:
                    with rasterio.Env(**GDAL_ENV):
                        with rasterio.open(SRC.format(lat=la, lon=lo)) as d:
                            nir = d.read(4, out_shape=(SEA_RES, SEA_RES), resampling=Resampling.average)
                    break
                except Exception as ex:
                    print(f"  sea mask retry {k + 1}: {str(ex)[:100]}", flush=True)
                    time.sleep(min(90, 5 * 2 ** k))
            else:
                raise SystemExit(f"could not read cell N{la}E{lo:03d} for the sea mask")
            water[r0:r0 + SEA_RES, c0:c0 + SEA_RES] = nir < NIR_WATER          # 0 = no pixel: water too
        print(f"  sea mask: N{la} done", flush=True)
    yy, xx = np.ogrid[-6:7, -6:7]
    disk = (xx * xx + yy * yy) <= 36
    core = ndimage.binary_erosion(water, structure=disk)
    lab, _ = ndimage.label(core, structure=np.ones((3, 3), bool))
    keep = []
    for lo, la in SEEDS:
        sr, sc = int((la1 - la) * SEA_RES), int((lo - lo0) * SEA_RES)
        if not lab[sr, sc]:
            raise SystemExit(f"the sea mask's seed {lo},{la} is not open water")
        keep.append(lab[sr, sc])
    sea = ndimage.binary_dilation(np.isin(lab, keep), structure=disk, iterations=2) & water
    tr = Affine(1 / SEA_RES, 0, lo0, 0, -1 / SEA_RES, la1)
    np.savez_compressed(cache, sea=sea.astype(np.uint8), tr=np.array(tr[:6]))
    return sea.astype(np.uint8), tr


def read_cell(url, ovr, tries=7):
    """The cell's RGB at overview `ovr`, retried: the bucket and the network between drop a long read now and then."""
    for k in range(tries):
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(url) as d:
                    h, w_ = d.height // ovr, d.width // ovr
                    src = d.read([1, 2, 3, 4], out_shape=(4, h, w_), resampling=Resampling.average).astype(np.float32)
                    return src, d.transform * Affine.scale(d.width / w_, d.height / h)
        except Exception as ex:
            wait = min(90, 5 * 2 ** k)
            print(f"  retry {k + 1} in {wait}s: {str(ex)[:160]}", flush=True)
            time.sleep(wait)
    raise SystemExit(f"could not read {url} — run again later; nothing half-made is kept")


def stretch(a):
    """float reflectance (0 = no data) → uint8, the same curve for the whole country."""
    v = np.clip(a / HI, 0, 1) ** GAMMA
    return (v * 255 + 0.5).astype(np.uint8)


def webp(px):
    """RGB, or RGBA where part of the tile has no imagery (the open sea: the oblasts' outlines take in coastal waters,
    and a black square there read as land). Transparent there, the map's own sea shows through."""
    if px.shape[2] == 4 and px[:, :, 3].min() == 255:
        px = px[:, :, :3]
    b = io.BytesIO()
    Image.fromarray(px).save(b, "WEBP", quality=WEBP_Q, method=4)
    return b.getvalue()


def open_db(path):
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""CREATE TABLE metadata (name TEXT, value TEXT);
        CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);
        CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);""")
    return db


def put(db, z, x, y, data):
    db.execute("INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)", (z, x, (2 ** z - 1) - y, data))


def build_top(db, tiles, z, rings, only=None, sea=None):
    """Zoom z from the source: each 1° cell read once at the overview that suits z, warped onto the tile grid."""
    n = 2 ** z
    res = 2 * ORIGIN / n / 256                       # metres (Mercator) per pixel
    # which 1° cells each tile needs
    need = {}
    for (x, y) in tiles:
        w, nlat = tile_lonlat(x, y, z)
        e, slat = tile_lonlat(x + 1, y + 1, z)
        cells = {(la, lo) for la in range(math.floor(slat), math.floor(nlat - 1e-9) + 1)
                 for lo in range(math.floor(w), math.floor(e - 1e-9) + 1)}
        need[(x, y)] = cells
    cells = sorted({c for v in need.values() for c in v}, key=lambda c: (-c[0], c[1]))
    have = existing_cells(sorted({c[0] for c in cells}))
    print(f"{len(cells)} cells needed, {len([c for c in cells if c in have])} exist (the others are open sea)", flush=True)
    if only:
        cells = [c for c in cells if f"N{c[0]:02d}E{c[1]:03d}" in only]
    left = {t: len(v) for t, v in need.items()}
    acc = {}
    ovr = max(1, int(res * math.cos(math.radians(48.5)) / 10 / 1.2))      # 10 m source; keep a little finer than the tile
    ovr = 1 << (ovr.bit_length() - 1)
    t0 = time.time()
    done = 0
    for i, (la, lo) in enumerate(cells):
        url = SRC.format(lat=la, lon=lo)
        src = st = None
        if (la, lo) in have:
            src, st = read_cell(url, ovr)
        mine = [t for t, v in need.items() if (la, lo) in v]
        if src is not None and mine:
            xs = [t[0] for t in mine]
            ys = [t[1] for t in mine]
            tx0, tx1, ty0, ty1 = min(xs), max(xs), min(ys), max(ys)
            W, H = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
            dst = np.zeros((4, H, W), np.float32)
            dt = Affine(res, 0, -ORIGIN + tx0 * 256 * res, 0, -res, ORIGIN - ty0 * 256 * res)
            reproject(src, dst, src_transform=st, src_crs="EPSG:4326", dst_transform=dt, dst_crs="EPSG:3857",
                      resampling=Resampling.bilinear, src_nodata=0, dst_nodata=0, num_threads=2)
            # the sea of this cell (±0.1°), onto the same grid
            dsea = np.zeros((H, W), np.uint8)
            if sea is not None:
                mask, mt = sea
                r0 = max(0, int((mt.f - (la + 1.1)) / -mt.e))
                c0 = max(0, int(((lo - 0.1) - mt.c) / mt.a))
                crop = mask[r0:r0 + int(1.2 * SEA_RES), c0:c0 + int(1.2 * SEA_RES)]
                if crop.size:
                    reproject(crop, dsea, src_transform=mt * Affine.translation(c0, r0), src_crs="EPSG:4326",
                              dst_transform=dt, dst_crs="EPSG:3857", resampling=Resampling.nearest)
            # what is kept: imagery, except water that is part of the open sea (the map's own background shows there)
            keep = (dst[:3].max(axis=0) > 0) & ~((dsea > 0) & (dst[3] < NIR_WATER))
            dst[3] = keep
            for (x, y) in mine:
                px, py = (x - tx0) * 256, (y - ty0) * 256
                part = dst[:, py:py + 256, px:px + 256]
                cur = acc.get((x, y))
                if cur is None:
                    acc[(x, y)] = part.copy()
                else:
                    m = (cur[0] == 0) & (cur[1] == 0) & (cur[2] == 0)
                    cur[:, m] = part[:, m]
        for t in mine:
            left[t] -= 1
            if left[t] == 0:
                a = acc.pop(t, None)
                if a is not None and (a[3] > 0.5).any():
                    alpha = np.where(a[3] > 0.5, 255, 0).astype(np.uint8)
                    put(db, z, t[0], t[1], webp(np.dstack([stretch(a[k]) for k in range(3)] + [alpha])))
                    done += 1
        db.commit()
        el = time.time() - t0
        print(f"z{z} cell {i + 1}/{len(cells)} N{la}E{lo:03d}: {done} tiles, {el / 60:.1f} min, "
              f"~{el / (i + 1) * (len(cells) - i - 1) / 60:.0f} min left", flush=True)
    return done


def build_lower(db, z):
    """Zoom z from the four tiles under each of its tiles."""
    rows = db.execute("SELECT tile_column, tile_row FROM tiles WHERE zoom_level=?", (z + 1,)).fetchall()
    parents = {(x // 2, ((2 ** (z + 1) - 1) - r) // 2) for x, r in rows}
    for (x, y) in sorted(parents):
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        for dx in (0, 1):
            for dy in (0, 1):
                cx, cy = 2 * x + dx, 2 * y + dy
                row = db.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                                 (z + 1, cx, (2 ** (z + 1) - 1) - cy)).fetchone()
                if row:
                    canvas.paste(Image.open(io.BytesIO(row[0])).convert("RGBA"), (dx * 256, dy * 256))
        px = np.asarray(canvas.resize((256, 256), Image.Resampling.BOX)).copy()
        px[:, :, 3] = np.where(px[:, :, 3] >= 128, 255, 0)            # an edge pixel is imagery or it is not
        put(db, z, x, y, webp(px))
    db.commit()
    return len(parents)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--maxzoom", type=int, default=12)
    ap.add_argument("--minzoom", type=int, default=5)
    ap.add_argument("--only", default="", help="cells to read, e.g. N50E030 (a test)")
    a = ap.parse_args()
    rings = ukraine_rings()
    tiles = tiles_touching(rings, a.maxzoom)
    print(f"{len(tiles)} tiles at z{a.maxzoom}", flush=True)
    db = open_db(a.out)
    sea = sea_mask(a.out + ".sea.npz")
    n = build_top(db, tiles, a.maxzoom, rings, set(a.only.split(",")) if a.only else None, sea)
    for z in range(a.maxzoom - 1, a.minzoom - 1, -1):
        k = build_lower(db, z)
        print(f"z{z}: {k} tiles", flush=True)
        n += k
    lons = [p[0] for r in rings for p in r]
    lats = [p[1] for r in rings for p in r]
    meta = {"name": "Heimdall — Ukraine, Sentinel-2 2021", "format": "webp", "type": "baselayer", "version": "1",
            "minzoom": str(a.minzoom), "maxzoom": str(a.maxzoom), "attribution": ATTRIBUTION,
            "bounds": f"{min(lons):.4f},{min(lats):.4f},{max(lons):.4f},{max(lats):.4f}",
            "description": "ESA WorldCover Sentinel-2 RGB median composite 2021, 20 m overview, built by scripts/build_imagery.py"}
    db.executemany("INSERT INTO metadata VALUES (?,?)", meta.items())
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"done: {n} tiles, {os.path.getsize(a.out) / 1048576:.0f} MB → {a.out}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
