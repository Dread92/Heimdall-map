"""1.58.59 — the privacy policy (/privacy) and the Google Play listing (docs/PLAY.md).

The owner: the app goes to Google Play's beta — the listing, the data-safety form and the privacy page Google asks for.
The page is held to the code: each figure it gives is the code's own, and the three languages give the same facts.
"""
import os
import re

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PRIV, PAGE, I18N, SRC, PLAY = (_read("static", "privacy.html"), _read("static", "kyiv.html"), _read("static", "i18n.js"),
                               _read("app", "server.py"), _read("docs", "PLAY.md"))
ARTS = dict(re.findall(r'<article lang="(uk|en|fr)">(.*?)</article>', PRIV, re.S))


def test_served_and_linked_from_every_footer():
    i = SRC.index('if u.path == "/privacy":')
    assert 'self._file("privacy.html", "text/html; charset=utf-8")' in SRC[i:i + 220]
    assert ' · <a href="/privacy">${_hx(t(\'priv_link\'))}</a></div>`' in I18N
    assert len(re.findall(r"(?<![A-Za-z_])priv_link:'", I18N)) == 3
    # self-contained: no script or stylesheet from elsewhere, no request made
    assert not re.findall(r"<script[^>]*\bsrc=", PRIV) and "<link rel=\"stylesheet\"" not in PRIV and "fetch(" not in PRIV


def test_three_languages_the_same_facts():
    assert set(ARTS) == {"uk", "en", "fr"}
    shape = {l: (a.count("<h2>"), a.count("<li>"), a.count("<b>")) for l, a in ARTS.items()}
    assert len(set(shape.values())) == 1, shape
    for a in ARTS.values():
        for fig in ("180", "300", "10 к" if "км" in a else "10 km", "nomakievip@gmail.com", "tile.openstreetmap.org", "Fly.io",
                    "Google Fonts", "/stop", "26"):
            assert fig.replace("10 к", "10 км") in a, fig


def test_its_figures_are_the_codes():
    assert server.HOME_CELL_KM == 10.0                                          # "~10 km"
    assert "FB_PER_DEVICE, FB_PER_DAY, FB_KEEP_DAYS = 6, 300, 180" in SRC         # feedback kept 180 days
    assert 'body = text if len(text) <= 300 else text[:300] + "…"' in SRC          # 300 characters to Telegram
    assert 'DELETE FROM push_subs WHERE endpoint=? AND fails>=3' in SRC            # three failed deliveries
    assert "hosting:'nomakievip@gmail.com'" in I18N                                # the contact it gives
    assert "fonts.googleapis.com" in PAGE and "https://tile.openstreetmap.org/" in PAGE   # the services it names
    assert "def log_message(self, fmt, *args):  # quiet" in SRC                    # no access log: no address written
    assert 'primary_region = "ams"' in _read("fly.toml")                           # "servers in Europe"


def test_the_play_listing_fits_and_names_the_apps_package():
    uk_t, en_t = re.findall(r"^(?:Назва|Name): `([^`]+)`", PLAY, re.M)
    uk_s, en_s = re.findall(r"^(?:Короткий опис|Short description): `([^`]+)`", PLAY, re.M)
    assert len(uk_t) <= 30 and len(en_t) <= 30 and len(uk_s) <= 80 and len(en_s) <= 80
    full = re.findall(r"Повний опис:\n\n```\n(.*?)```|Full description:\n\n```\n(.*?)```", PLAY, re.S)
    assert len(full) == 2 and all(0 < len("".join(f).strip()) <= 4000 for f in full)
    assert f"`{server.ANDROID_PACKAGE_DEFAULT}`" in PLAY and "https://heimdall.com.ua/privacy" in PLAY
    assert "No donation buttons in the Play build" in PLAY
    # the key to the Play account is never meant for the repository
    assert "never in git" in PLAY
