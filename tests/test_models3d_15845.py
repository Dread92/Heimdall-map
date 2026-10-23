"""1.58.45 — the threats in 3D, on the Tactical map, in the card and in the sheet.

The owner: "could you make some little animated threejs icon for every threat that we have" (where: "card and sheet + the
map marker"); and of a Banderol drawn as the "?" disc although its post named it: "if the target is correctly identified
like here, then display a real logo … it needs to be a 3D model".

What must hold: one model per silhouette; three.js from this server only, loaded only when it can be used; a model with a
course turned by orientOf and nothing else, one with no course turning without stopping (never a heading); the mark's
colours (read from the silhouette underneath) kept; outcomes, night, blackout, Light and the channel's picture in 2D.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import server  # noqa: E402


def _read(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


M3D = _read("static", "models3d.js")
PAGE = _read("static", "kyiv.html")
GLY = _read("static", "glyphs.js")
LIGHT = _read("static", "light.html")
ENTRY = _read("scripts", "three-m3d.entry.js")
SRV = _read("app", "server.py")


def test_a_model_for_every_silhouette():
    keys = re.search(r"export const KEYS = \[(.*?)\];", M3D).group(1)
    keys = set(re.findall(r"'(\w+)'", keys))
    by_type = set(re.findall(r":'(\w+)'", GLY[GLY.index("const GLYPH_BY_TYPE="):GLY.index("};", GLY.index("const GLYPH_BY_TYPE="))]))
    assert by_type <= keys and "jetdrone" in keys                    # every weapon's silhouette, the jet drone's too
    build = M3D[M3D.index("const BUILD = {"):M3D.index("// ---- posing")]
    for k in keys:
        assert re.search(r"\n  " + k + r"\(\) \{", build), k
    assert "export const VIEWS = {top: {n: 8, dur: 0.8}, spin: {n: 24, dur: 3.2}};" in M3D
    m3k = re.search(r"const M3_KEYS=new Set\(\[(.*?)\]\);", PAGE).group(1)
    assert set(re.findall(r"'(\w+)'", m3k)) == keys


def test_three_js_from_this_server_only_and_only_the_parts_used():
    assert re.findall(r"^import .*$", M3D, re.M) == ["import * as T from './vendor/three-m3d.min.js';"]
    used = set(re.findall(r"\bT\.([A-Z]\w+)", M3D))
    exported = set(re.findall(r"\b([A-Z]\w+)\b", ENTRY[ENTRY.index("export {"):]))
    assert used <= exported, used - exported
    lib = _read("static", "vendor", "three-m3d.min.js")
    assert lib.startswith("/**\n * @license\n * Copyright 2010-2026 Three.js Authors\n * SPDX-License-Identifier: MIT")
    assert "MIT License" in _read("static", "vendor", "three.LICENSE")
    assert 'THREE=0.185.1' in _read("scripts", "build_three.sh")
    assert "script-src 'self' 'unsafe-inline'" in SRV and "img-src 'self' data: blob:" in SRV     # the module, the blob: strips
    assert '"static/models3d.js", "static/vendor/three-m3d.min.js"' in SRV and "static/models3d.js" in server.BUILD_FILES
    assert "models3d" not in LIGHT and "three" not in LIGHT.lower().replace("threat", "")       # Light stays light


def test_loaded_only_when_it_can_be_used():
    assert PAGE.count("import('/static/models3d.js')") == 1
    start = PAGE[PAGE.index("function m3Start(){"):PAGE.index("const m3Ok=")]
    assert "navigator.connection.saveData" in start and "!window.WebGLRenderingContext" in start
    assert "if(!M3.state&&MK.length&&MODE!=='night'&&!document.body.classList.contains('lite')) m3Start();" in PAGE[PAGE.index("function tick(){"):PAGE.index("function tick(){") + 250]
    assert "const m3Ok=()=>M3.state===2&&MODE!=='night'&&!document.body.classList.contains('lite');" in PAGE
    pump = PAGE[PAGE.index("async function m3Pump(){"):PAGE.index("const m3Key=")]
    assert "requestAnimationFrame" in pump and "M3.mod.release();" in pump           # one at a time; the context let go


def test_a_course_turns_it_and_nothing_else_no_course_never_holds_a_heading():
    mark = PAGE[PAGE.index("function m3Mark(b,m,gk){"):PAGE.index("function m3Ico(")]
    assert "if(m3Ok()&&!m.status&&(gk==='nofront'?!M3.rm.matches:M3_KEYS.has(gk))){" in mark      # no outcome; less motion: the disc
    assert "s=m3Sheet(gk==='nofront'?m3Key(m):gk,gk==='nofront'?'spin':'top',b.m3col,M3PX,b.m3line);" in mark
    assert "rot.insertAdjacentHTML('beforeend'" in mark and "transform" not in mark.replace("style=", "")   # turned by .rot only
    # the .rot it sits in is turned by orientOf, as the silhouette was
    assert "b.g.querySelector('.rot').setAttribute('transform',\n      `rotate(${orientOf(m)}) scale(" in PAGE
    pose = M3D[M3D.index("function pose("):M3D.index("// ---- the camera")]
    assert "model.userData.sign ? 0.55 * Math.sin(f * 2 * Math.PI) : f * 2 * Math.PI" in pose      # spin: a full turn a loop
    assert "const turn = view !== 'spin' ? 0" in pose                                             # top: never turned here
    assert "@media (prefers-reduced-motion:reduce){.mk .m3i,.m3ico{animation:none}}" in PAGE


def test_the_marks_colours_are_kept():
    mark = PAGE[PAGE.index("function m3Mark(b,m,gk){"):PAGE.index("function m3Ico(")]
    assert "const el=rot.querySelector('.glyph:not(.m3)');" in mark
    assert "el.style.animation='none'; const cs=getComputedStyle(el); b.m3col=cs.fill;" in mark
    assert ".mk.m3on .rot>:not(.m3){visibility:hidden}" in PAGE                # the silhouette stays, hidden, underneath
    assert '<g class="m3 glyph"><svg class="m3v"' in mark and ".mk .m3v{overflow:hidden}" in PAGE   # no filter on the window
    assert ".mk.m3on.ballistic_missiles .m3{animation:m3bl .55s steps(2) infinite}" in PAGE
    assert "sc.fillStyle = line;" in M3D                                      # the outline in the silhouette's stroke
    # the aircraft marks have a colour now (they were black)
    assert ".mk.strategic_aircraft_activity .glyph,.mk.mig31k_departure .glyph{fill:#b07cff}" in PAGE


def test_the_card_and_the_sheets():
    assert "${m3Ico(cur,28)||thrIco(cur.type)}" in PAGE                        # the card: the model, else the silhouette
    assert "(m3Ico(evs[0],34)||silSvg(evs[0])" in PAGE                         # an oblast's targets
    assert '<div class="type">${m3Ico(m,34)}${kind}' in PAGE                   # a target's sheet
    ico = PAGE[PAGE.index("function m3Ico(m,sz,col){"):PAGE.index("function m3Ico(m,sz,col){") + 600]   # 1.58.55: a colour
    assert "if(!m3Ok()||!m||m.status) return '';" in ico and "'spin'" in ico and "steps(${s.n},jump-none)" in ico


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = _read("docs", doc)
        assert "1.58.45" in s and "spin" in s, doc
    assert "## 1.58.45" in _read("CHANGELOG.md")
