"""The manual (docs/manual.html) is rebuilt with every change to the documentation.

The owner (10 Oct 2026): "the manual must be updated systematically, if needed, with every commit / change in the app".
scripts/build_manual.py writes it from docs/*.md and stamps it with their hash and the documented version; this fails
when a document changed and the manual was not rebuilt, and when the system map no longer counts what the code has.
"""
import importlib.util
import os
import re

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def _builder():
    spec = importlib.util.spec_from_file_location("build_manual", os.path.join(ROOT, "scripts", "build_manual.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_manual_is_built_from_the_current_documents():
    page = _read("docs", "manual.html")
    stamp = re.search(r'<meta name="heimdall-docs" content="([0-9a-f]+)">', page).group(1)
    assert stamp == _builder().docs_hash(), "the documents changed: run python scripts/build_manual.py"
    ver = re.search(r'<meta name="heimdall-version" content="([\d.]+)">', page).group(1)
    assert f"({ver})" in _read("docs", "TECHNICAL.md").split("\n", 3)[2]


def test_the_system_map_counts_what_the_code_has():
    svg = _read("scripts", "manual", "map-svg.html")
    n = len(server.AUTHORITATIVE_CHANNELS)
    api = {c for c, v in server.CHANNEL_VIA_DEFAULT.items() if v == "api"} | set(server.DEFAULT_CONFIG.get("telegram_api_channels") or [])
    assert f">{n} public channels<" in svg and f">t.me/s/ previews, {n - len(api)} channels<" in svg
    assert f">{len(api)} channels (previews off)<" in svg
    assert ">≤ 350 km/h, a jet ≤ 650<" in svg and server.VMAX_KMH == {False: 350, True: 650}


def test_every_patch_rebuilds_it():
    assert "python scripts/build_manual.py" in _read("CLAUDE.md")
    assert "scripts/build_manual.py" in _read("docs", "TECHNICAL.md")
    assert "markdown-it-py" in _read("requirements-dev.txt")
