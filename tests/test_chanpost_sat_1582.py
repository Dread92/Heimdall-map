"""1.58.2 — the channel's picture over the satellite view.

The owner: "il faudrait idéalement la vision map satellite". The picture is drawn over the app's own Sentinel-2 tiles
(server.SAT, the file on the volume — no map provider is asked), dimmed as the Tactical page dims its satellite layer,
the alerts' tint in one layer of its own; without the file, the plain map as before.
"""
import io
import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import chanpost  # noqa: E402
import mapshot  # noqa: E402

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
GREEN = (40, 160, 60)


class FakeSat:
    """server.SAT's two calls: the file's (version, deepest zoom), and a tile's WebP bytes."""

    def __init__(self, zmax=13, colour=GREEN):
        self.zmax, self.asked = zmax, []
        buf = io.BytesIO()
        Image.new("RGB", (256, 256), colour).save(buf, "WEBP")
        self.webp = buf.getvalue()

    def info(self):
        return ("2", self.zmax) if self.zmax else (None, None)

    def tile(self, z, x, y):
        self.asked.append((z, x, y))
        return self.webp


def drone(**kw):
    m = {"type": "drones", "place": "Бровари", "lon": 30.79, "lat": 50.51, "oblast_uid": "14", "history": []}
    m.update(kw)
    return m


def pixel(jpg, xy):
    return Image.open(io.BytesIO(jpg)).convert("RGB").getpixel(xy)


def test_the_picture_is_drawn_over_the_apps_satellite_tiles_dimmed_as_the_page_dims_them():
    assert "#sat,#esri{filter:brightness(.62) saturate(.82) contrast(1.04)}" in TAC
    assert mapshot.SAT_LOOK == (0.62, 0.82, 1.04)
    sat = FakeSat()
    shot = mapshot.MapShot(sat=sat)
    jpg = shot.render(drone(), [], "21:40")
    r, g, b = pixel(jpg, tuple(map(int, shot.to_pixel(31.12, 50.70, drone()))))   # inside the oblast, away from names
    assert g > r + 30 and g > b + 30 and g < GREEN[1]    # the ground, darker than the tile itself
    # the tiles of the view only, at a zoom as sharp as the picture and no sharper
    zs = {z for z, x, y in sat.asked}
    assert len(zs) == 1 and 9 <= zs.pop() <= 13 and 4 <= len(sat.asked) <= 120     # 1.58.13: ~90 at 110 km


def test_without_the_file_it_is_the_plain_map():
    shot = mapshot.MapShot(sat=FakeSat(zmax=None))
    plain = shot.render(drone(), [], "21:40")
    r, g, b = pixel(plain, tuple(map(int, shot.to_pixel(31.12, 50.70, drone()))))
    assert abs(r - g) < 12 and abs(g - b) < 12          # the dark map's grey, no picture under it
    assert mapshot.MapShot().render(drone(), [], "21:40")[:3] == b"\xff\xd8\xff"


def test_tiles_are_kept_once_decoded_and_never_a_failed_one():
    sat = FakeSat()
    shot = mapshot.MapShot(sat=sat)
    shot.render(drone(), [], "21:40")
    n = len(sat.asked)
    shot.render(drone(), [], "21:41")
    assert len(sat.asked) == n                          # the same view: nothing read again
    assert len(shot._tiles) <= 200

    class Broken(FakeSat):
        def tile(self, z, x, y):
            self.asked.append((z, x, y))
            return b"not a picture"
    b = Broken()
    s2 = mapshot.MapShot(sat=b)
    s2.render(drone(), [], "21:40")
    assert not s2._tiles                                 # a bad tile is not kept: asked again next time


def test_an_alert_is_tinted_once_where_two_shapes_meet():
    shot = mapshot.MapShot(sat=FakeSat(colour=(90, 90, 90)))
    shot.towns, shot.raion_lbl = [], []      # the tint alone: no name over the pixels read
    act = [{"oblast_uid": "14", "location_type": "oblast"}, {"oblast_uid": "31", "location_type": "city"}]
    bc = drone(place="Біла Церква", lon=30.11, lat=49.80)
    jpg = shot.render(bc, act, "21:40")
    im = Image.open(io.BytesIO(jpg)).convert("RGB")
    # every tinted pixel of Kyiv oblast is the same red over the same grey: one layer, not one per shape
    pts = [shot.to_pixel(29.4 + i * 0.1, 49.62, bc) for i in range(22)]
    reds = {im.getpixel((int(x), int(y))) for x, y in pts if 0 <= x < mapshot.W and 0 <= y < mapshot.H}
    reds = {p for p in reds if p[0] > p[1] + 25}
    assert len(reds) >= 1 and max(p[0] for p in reds) - min(p[0] for p in reds) <= 30


def test_the_credits_follow_the_picture():
    assert "ESA WorldCover 2021" in mapshot.SAT_CREDIT and "Copernicus Sentinel" in mapshot.SAT_CREDIT
    assert "OCHA" in mapshot.SAT_CREDIT and "OpenStreetMap" in mapshot.SAT_CREDIT
    assert "self._bands(d, when, k, SAT_CREDIT if on_sat else MAP_CREDIT)" in open(
        os.path.join(ROOT, "app", "mapshot.py"), encoding="utf-8").read()


def test_the_server_gives_the_channel_its_satellite_file():
    assert "tgbot.start(state, log=log, ssl_ctx=_SSL_CTX, sat=SAT, oblasts=NAME_BY_UID)" in SRV      # 1.58.38: the bot's picture
    sat = FakeSat()
    p = chanpost.ChannelPoster(object(), "x", "-1", "https://h", api=object(), log=lambda *a: None, kv=False, sat=sat)
    assert p.shot.sat is sat
    assert re.search(r"def start\(state, log=print, ssl_ctx=None, env=None, sat=None\)", open(
        os.path.join(ROOT, "app", "chanpost.py"), encoding="utf-8").read())
