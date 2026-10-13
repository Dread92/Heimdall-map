"""1.58.14 — the Map background on a phone that crashed with it.

A reader (Oppo Reno 15 Pro), through the owner: "with the Map background it crashes — solid artifacts, and it falls out
to the phone's lock screen". Not reproduced here (no such phone, no GPU); what the page does about it: a page that died
on the screen with the Map background opens next time on the satellite and says so, the older 512-pixel tiles kept
are counted by their memory, and the night mode no longer filters the whole street map as one picture.
"""
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def test_a_page_that_died_with_the_map_opens_on_the_satellite_and_says_so():
    guard = PAGE[PAGE.index("const RUN_K='run_v1'"):PAGE.index("if(RUN_FELL) setTimeout(")]
    assert "pr.bg==='map'&&pr.ok===false&&LAYERS.tiles" in guard and "LAYERS.tiles=false; LAYERS.sat=true;" in guard
    assert "runMark(document.visibilityState==='hidden');" in guard
    assert "document.addEventListener('visibilitychange',()=>runMark(document.visibilityState==='hidden'));" in guard
    assert "addEventListener('pagehide',()=>runMark(true));" in guard
    # before the first applyLayers(): no Map tile is asked for on the opening that falls back
    assert PAGE.index("const RUN_K='run_v1'") < PAGE.index("\napplyLayers();\n")
    # quietly: no tone, no vibration — it is not an alert
    toast = PAGE[PAGE.index("function toastQuiet("):PAGE.index("if(RUN_FELL) setTimeout(")]
    assert "beep(" not in toast and "vibrate" not in toast
    for k in ("map_fell_t:", "map_fell_b:"):
        assert I18N.count(k) == 3, k


def test_old_tiles_are_counted_by_their_memory_and_no_group_filter_at_night():
    assert "keep=Math.round(150*(256/(px||256))**2)" in PAGE
    assert ",60,4,512);" in PAGE and ",60,9,512);" in PAGE
    assert "body.m-night #lbl,body.m-night #emap{filter" not in PAGE
    assert "body.m-night #lbl image,body.m-night #emap image{opacity:.55}" in PAGE
