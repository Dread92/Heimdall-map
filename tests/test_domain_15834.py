"""1.58.34 — the app's own address, heimdall.com.ua: the channel's link follows CANONICAL_HOST, and the places that named
the first address name the new one. The first address is not closed (an installed app, its push subscription and its
pins belong to the address they were made on): the move banner (1.29) does that work."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import chanpost  # noqa: E402

HOST = "heimdall.com.ua"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_the_channel_links_to_the_canonical_host():
    assert chanpost.PUBLIC_URL == f"https://{HOST}"
    assert chanpost.public_url({}) == f"https://{HOST}"
    assert chanpost.public_url({"CANONICAL_HOST": HOST}) == f"https://{HOST}"
    assert chanpost.public_url({"CANONICAL_HOST": " Heimdall.com.ua/ "}) == f"https://{HOST}"
    assert chanpost.public_url({"CANONICAL_HOST": HOST, "PUBLIC_URL": "https://x.example/"}) == "https://x.example"
    assert chanpost.public_url({"PUBLIC_URL": "  "}) == f"https://{HOST}"


def test_the_channel_is_off_without_its_secrets_whatever_the_host():
    assert chanpost.start(None, env={"CANONICAL_HOST": HOST}) is None


def test_the_first_address_is_named_nowhere_a_reader_reads():
    readme, tpl = _read("README.md"), _read("scripts", "manual", "template.html")
    assert f"<https://{HOST}/m>" in readme and f"<https://{HOST}/light>" in readme and f"<https://{HOST}/guide>" in readme
    assert "kyiv-air-watch-gb.fly.dev/m>" not in readme and "keeps working" in readme
    assert f"Heimdall · {HOST}" in tpl and "kyiv-air-watch-gb" not in tpl
    for page in ("kyiv.html", "light.html", "index.html", "guide.html", "i18n.js", "sw.js"):
        p = os.path.join(ROOT, "static", page)
        if os.path.exists(p):
            assert "fly.dev" not in _read("static", page), page


def test_the_scripts_check_the_new_address_and_keep_an_override():
    rel, dia = _read("scripts", "release.bat"), _read("scripts", "diagnose.bat")
    for s in (rel, dia):
        assert f"set SITE=https://{HOST}" in s and "if exist .site set /p SITE=<.site" in s
    assert "curl -s %SITE%/api/version" in rel and "https://%APP%.fly.dev/api/version" not in rel.split("set SITE")[0]
    assert "%SITE%/api/version" in dia and "https://%APP%.fly.dev/api/version" in dia          # both, to tell them apart
    assert ".site" in _read(".gitignore")


def test_the_docs_tell_it():
    doc, dep, log = _read("docs", "TECHNICAL.md"), _read("docs", "DEPLOY.md"), _read("CHANGELOG.md")
    assert "1.58.34" in doc[:4000] and "heimdall.com.ua" in doc[:4000]
    for s in (f"https://{HOST}", "chanpost.public_url", "1.58.34 — done", "two doors"):
        assert s in doc, s
    assert "Done, 18 October 2026 (1.58.34)" in dep and "Extend nameservers" in dep
    assert log.index("## 1.58.34") < log.index("## 1.58.33") and HOST in log.split("## 1.58.33")[0]
