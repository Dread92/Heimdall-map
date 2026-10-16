"""Heimdall Light: one place, what concerns it, nothing else.

It inherits every promise the full app makes and adds two of its own: it has to be readable in seconds on a
phone in a corridor, and it must never learn more about where somebody is than the full app does — which is
nothing. The four places live in the browser, and the oblast a place sits in is worked out on the phone,
because asking the server would mean sending it the coordinates of a school.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def _script():
    return LIGHT[LIGHT.index("<script>"):LIGHT.index("</script>", LIGHT.index("<script>"))]


# ── it exists, separately ──────────────────────────────────────────────────────────────────────────────
def test_it_is_served_at_its_own_address():
    assert 'u.path in ("/light", "/l")' in SRC and '"light.html"' in SRC


def test_it_installs_as_its_own_app():
    man = json.load(open(os.path.join(ROOT, "static", "light.webmanifest"), encoding="utf-8"))
    assert man["id"] == "/light" and man["start_url"] == "/light" and man["scope"] == "/light"
    assert man["name"] != json.load(open(os.path.join(ROOT, "static", "manifest.json"), encoding="utf-8"))["name"]
    assert '<link rel="manifest" href="/light.webmanifest">' in LIGHT


def test_it_is_part_of_the_build_hash():
    """Otherwise a change to it never tells an open page that a new version exists."""
    assert '"static/light.html"' in SRC[SRC.index("BUILD_FILES"):SRC.index("BUILD_FILES") + 200]


def test_it_stays_light():
    """Measured as it travels: the server gzips text. Page + map outlines + Kyiv districts stay under 61 KB on
    the wire — a few seconds on 2G — and the status is painted before any of the map data arrives."""
    import gzip
    page = len(gzip.compress(LIGHT.encode("utf-8"), 6))
    extra = 0
    for f in ("light-map.json", "kyiv-districts.json"):
        with open(os.path.join(ROOT, "static", f), "rb") as fh:
            extra += len(gzip.compress(fh.read(), 6))
    # 1.19 raised both by ~2.5 KB for the map's own zoom and the tap-to-open card (about 0.2 s on 2G).
    # 1.29 raised them by ~3 KB (page + static/live.js) for the live line, the team's message and the move to a new
    # address: in exchange the page no longer downloads the alerts and the marks every 15 s (~8 KB gzipped each
    # time) while the line is up.
    # 1.32 raised them by 0.5 KB: the admin's message in loud colours (green / pulsing red) and the few lines that
    # download static/nuke.js — only while a nuclear event is on; the overlay itself is not part of the page.
    # 1.34 raised them by 0.5 KB: the Kyiv bridges — a target reported on or near one, bridge by bridge.
    # 1.36 raised them by 0.5 KB: each place's chip carries its own official status, every target is 44 px, and the
    # radar's legend sits behind a button.
    with open(os.path.join(ROOT, "static", "live.js"), "rb") as fh:
        page += len(gzip.compress(fh.read(), 6))
    # 1.54.8 raised it by 0.2 KB: a target whose weapon was not stated is "probably a drone", or "drone or missile" while
    # a missile is reported — never "type not stated" alone.
    # 1.54.9 raised it by 0.3 KB: four pins named by their owner, the picker kept above the keyboard, and an unstated
    # threat drawn as a drone outside a missile context.
    # 1.56 raised it by 0.2 KB: the streets and villages of every oblast in the picker — the few lines that load
    # static/streets.js when the picker opens (the search and the oblast's list are not part of the page)
    # 1.57 raised it by 0.2 KB: the nearest shelter Kyiv city lists, under an alert — the few lines that load
    # static/shelters.js (the list, its look and the shelters themselves are not part of the page)
    # 1.57.2 raised it by 0.2 KB: the radar's background (plain, satellite or map) — the button and the few lines that
    # load static/lightmap.js when a reader asks for it (the tiles and their code are not part of the page)
    # 1.58.16 raised it by 0.7 KB: a hromada's alert on the hromada itself — the few lines that load static/hromadas.js
    # once an alert names a hromada (the outlines and their test are not part of the page)
    # 1.58.24 raised the sum by 0.1 KB: a live line that keeps failing is asked again later and later, one at a time
    # 1.58.31 raised both by 0.1 KB: with the raion source silent, a raion the oblast-only mirror cannot see is unknown
    # 1.58.33 raised both by 0.1 KB: the official status as a flat (red, yellow) or a rule (green), the switch as two tabs
    # 1.58.34: the pins that exist and a "+"
    assert page < 26_600, f"the light page is no longer light ({page} B gzipped)"
    assert page + extra < 67_600, f"page + map data = {page + extra} B gzipped"   # 1.58.16: the same 0.6 KB
    # 1.29: the live line is allowed — the light variant only (alerts and marks, no feed, no raw events). An open
    # line costs the server nothing any more (one thread holds them all) and the phone ~100 bytes every 15 s,
    # against ~8 KB every 15 s for asking.
    assert "/api/stream?p=light&ev=0&sync=mk,st" in LIGHT
    for heavy in ("kyiv-map.json", "tile.openstreetmap", "/api/feed"):
        assert heavy not in LIGHT, f"the light page loads {heavy}"


def test_the_status_is_painted_before_the_outlines_arrive():
    i = LIGHT.index("async function usePlace()")
    body = LIGHT[i:LIGHT.index("}", LIGHT.index("paint(); }", i))]
    assert body.index("paint()") < body.index("await loadLM()")


# ── the promise about places ───────────────────────────────────────────────────────────────────────────
def test_the_places_come_from_the_same_browser_storage_as_the_full_app():
    js = _script()
    assert "localStorage.getItem('slots')" in js and "localStorage.setItem('slots'" in js


def test_no_request_ever_carries_a_place():
    js = _script()
    for call in re.findall(r"fetch\(([^)]*)\)", js):
        assert not re.search(r"lat|lon|SLOTS|place\(|\bp\.", call), f"a request carries the place: fetch({call})"


def test_the_oblast_is_worked_out_on_the_phone():
    js = _script()
    body = js[js.index("async function oblastOf"):js.index("\n}", js.index("async function oblastOf"))]
    assert "isPointInFill" in body and "/static/ukraine-map.json" in body
    assert "p.obl=found" in body.replace(" ", ""), "the answer is not cached with the place"


def test_the_city_is_tested_before_the_oblast_around_it():
    """Kyiv city sits inside Kyiv oblast. Testing the oblast first would put everyone in the city in it."""
    js = _script()
    assert "u.uid==='31'" in js.replace(" ", "")


# ── the rules it inherits ──────────────────────────────────────────────────────────────────────────────
def test_the_status_comes_only_from_the_alert_state():
    js = _script()
    body = js[js.index("function placeStatus"):js.index("\n}", js.index("function placeStatus"))]
    assert "STATE.active" in body
    for banned in ("MKS", "markers", "clear"):
        assert banned not in body, f"the status is decided by {banned!r}, not by the official alert data"


def test_empty_is_never_called_safe():
    for pat in (r"lt_none:'([^']*)'", r"lt_none_b:'((?:[^'\\]|\\.)*)'"):
        for v in re.findall(pat, I18N):
            assert not re.search(r"\bsafe\b|безпечн[оа]\b(?!\s*—)|\bsûr\b(?!\s*»)", v.replace("the same as safe", "").replace("те саме, що безпечно", "").replace("« sûr »", "")), v


def test_eta_only_on_a_stated_course_pointing_here_and_never_for_immediate_weapons():
    js = _script()
    assert "statedCourse=m=>m.heading!=null&&" in js.replace(" ", "")
    i = js.index("if(IMMEDIATE.has(m.type))")
    assert "continue" in js[i:i + 80], "an immediate weapon falls through to the ETA list"


def test_a_shot_down_target_leaves_the_list():
    js = _script()
    assert "function link(" in js and "returntr.filter(m=>!m.endedBy)" in js.replace(" ", "")


def test_every_light_string_is_in_all_three_languages():
    keys = {k for k in re.findall(r"t\('(lt_[a-zA-Z_]+)'", LIGHT) if not k.endswith("_")} | {"lt_R", "lt_Y", "lt_G", "lt_U", "lt_z_near", "lt_z_approach", "lt_z_observe"}
    for k in sorted(keys):
        n = len(re.findall(rf"(?<![A-Za-z_]){k}:", I18N))
        assert n == 3, f"{k} appears {n} times"


def test_it_watches_thirty_kilometres():
    js = _script()
    assert "R_KM=30" in js.replace(" ", "")
    assert "if(d<=R_KM) rows.push(r)" in js
    # beyond the radius, only what a post says is heading here — never "everything within 100 km"
    assert "else if(toHere&&!m.stale&&d<=FAR_KM) far.push(r)" in js
    for pat in (r"lt_none:'([^']*)'",):
        for v in re.findall(pat, I18N):
            assert "30" in v and "60" not in v, v


def test_the_notice_shows_once_per_opening_on_both_pages():
    full = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    for page in (full, LIGHT):
        assert "sessionStorage.getItem('disc_seen')" in page and "sessionStorage.setItem('disc_seen','1')" in page
    assert "shown on every open, on purpose" not in full


def test_the_switch_is_on_both_pages_and_each_half_says_what_it_is():
    full = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    assert 'href="/light"' in full[full.index('<header id="top">'):full.index('<header id="top">') + 800]
    assert '<nav class="sw" id="sw">' in LIGHT and 'href="/m"' in LIGHT[LIGHT.index('<nav class="sw"'):LIGHT.index('<nav class="sw"') + 300]
    for k in ("sw_light_b", "sw_tac_b"):
        assert I18N.count(k + ":") == 3


def test_light_draws_the_same_silhouettes_as_the_tactical_map():
    """A Shahed, a Banderol and a Kalibr each have one picture in this app. The Light page used to draw its own
    arrows and dots — a second picture of the same weapon, which is exactly what a silhouette must never be."""
    assert '<script src="/static/glyphs.js"></script>' in LIGHT
    full = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    assert '<script src="/static/glyphs.js"></script>' in full
    assert "const G=" not in full and "const GLYPH_BY_TYPE=" not in full, "the Tactical page keeps its own copy"
    js = _script()
    assert "G[silKey(m)]" in js and "GLYPH_BY_TYPE[m.type]" in js
    assert "const ico=" not in js, "the old letter icons are back"


def test_a_light_silhouette_turns_only_to_a_stated_course():
    js = _script()
    m = re.search(r"const markOrient=m=>(.*?);\n", js)
    assert m and "statedCourse(m)" in m.group(1) and "m.type!=='unknown'" in m.group(1)
