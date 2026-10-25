"""1.58.57 — the bank's and PayPal's own logos on the support page's buttons.

The owner, with the two files (PUMB's red tile, PayPal's logo): "it's for the app and the sites — instead of just the
names". Taken as given: PUMB's tile cropped around its wordmark, PayPal's wordmark (its baked-in checkerboard keyed out),
colours untouched; nothing of either is drawn by the app.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE = _read("static", "kyiv.html")
SUP = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]


def _img(name):
    return Image.open(os.path.join(ROOT, "static", name)).convert("RGBA")


def _px(im):
    return [im.getpixel((x, y)) for y in range(im.size[1]) for x in range(im.size[0])]


def test_the_two_files_are_small_and_the_brands_own():
    p, pp = _img("pumb-logo.png"), _img("paypal-logo.png")
    assert p.size == (144, 72) and pp.size == (179, 48)                      # 3x of 48x24 and 60x16
    for n in ("pumb-logo.png", "paypal-logo.png"):
        assert os.path.getsize(os.path.join(ROOT, "static", n)) < 4000, n
    reds = sum(1 for c in _px(p) if abs(c[0] - 231) < 12 and c[1] < 40 and abs(c[2] - 42) < 15)
    assert reds > p.size[0] * p.size[1] * 0.6                               # PUMB's red, its tile
    cols = [c for c in _px(pp) if c[3] > 250]
    dark = sum(1 for c in cols if abs(c[0] - 37) < 14 and abs(c[1] - 59) < 14 and abs(c[2] - 128) < 14)
    light = sum(1 for c in cols if abs(c[0] - 23) < 14 and abs(c[1] - 155) < 14 and abs(c[2] - 215) < 14)
    assert dark > 300 and light > 300                                          # "Pay" and "Pal", PayPal's two blues
    assert pp.getpixel((0, 0))[3] == 0 and pp.getpixel((pp.size[0] - 1, pp.size[1] - 1))[3] == 0   # no checkerboard left


def test_on_the_buttons_with_their_names_as_alt_and_not_in_blackout():
    assert "const lite=document.body.classList.contains('lite');" in SUP
    assert "const lgP=lite?'':`<img class=\"payl\" src=\"/static/pumb-logo.png\" width=\"48\" height=\"24\" alt=\"${esc(t('sup_pumb'))}\">`;" in SUP
    assert "const lgPP=lite?'':'<span class=\"payl pp\"><img src=\"/static/paypal-logo.png\" width=\"60\" height=\"16\" alt=\"PayPal\"></span>';" in SUP
    assert SUP.count("${lgP}") == 2 and SUP.count("${lgPP}") == 1               # Heimdall's and the NGO's PUMB, PayPal
    assert ".payl.pp{display:flex;align-items:center;width:auto;padding:0 7px;background:#fff;" in PAGE   # dark blue needs white
    assert "body.lite .payl{display:none}" in PAGE
    assert '<i class="payl">' not in PAGE                                    # the plain names of 1.58.52 are gone
