"""1.58.47 — the donation jar in 3D. The owner: "make the jar better looking, in three.js for example — right now it's not
really standing out".

The jar is models3d.js's (`BUILD.jar`, not a threat: never in KEYS, never on the map), photographed once into
static/jar3d.webp by scripts/render_jar.js, and played by CSS — no three.js is loaded for it. A gold rim, a warm light, a
glow now and then; the drawing until the strip is in; nothing with "save data" or in the blackout look.
"""
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, M3D = _read("static", "kyiv.html"), _read("static", "models3d.js")


def _webp_size(path):
    with open(path, "rb") as f:
        b = f.read(64)
    assert b[:4] == b"RIFF" and b[8:12] == b"WEBP"
    if b[12:16] == b"VP8X":                                   # extended (alpha): 24-bit width-1 and height-1
        return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
    if b[12:16] == b"VP8L":
        v = struct.unpack("<I", b[21:25])[0]
        return 1 + (v & 0x3FFF), 1 + ((v >> 14) & 0x3FFF)
    return struct.unpack("<HH", b[26:30])


def test_the_strip():
    p = os.path.join(ROOT, "static", "jar3d.webp")
    w, h = _webp_size(p)
    assert (w, h) == (36 * 112, 112) and os.path.getsize(p) < 90_000          # 36 frames; light enough for a phone
    assert "VIEWS.jar = {n: 36, dur: 4.0};" in M3D and "\n  jar() {" in M3D
    keys = re.search(r"export const KEYS = \[(.*?)\];", M3D).group(1)
    assert "jar" not in keys                                                  # never a threat, never on the map
    js = _read("scripts", "render_jar.js")
    assert "M.sheet('jar', 'jar'" in js and "'image/webp'" in js and "const PX = 112;" in js


def test_the_button():
    assert '<span class="jar3d" aria-hidden="true"></span></button>' in PAGE
    assert ".jarbtn .jar3d{display:none;width:48px;height:48px;background:url(/static/jar3d.webp) 0 0/3600% 100% no-repeat;animation:jarturn 4s steps(36,jump-none) infinite}" in PAGE
    assert ".jarbtn.j3 .jar3d{display:block}.jarbtn.j3 svg{display:none}" in PAGE
    assert "@media (prefers-reduced-motion:no-preference){.jarbtn{animation:jarglow" in PAGE
    assert "@media (prefers-reduced-motion:reduce){.jarbtn .jar3d{animation:none}}" in PAGE
    load = PAGE[PAGE.index("// 1.58.47: the 3D jar's strip"):PAGE.index("$('jarbtn').onclick")]
    assert "navigator.connection.saveData" in load and "document.body.classList.contains('lite')" in load
    assert "im.onload=()=>$('jarbtn').classList.add('j3'); im.src='/static/jar3d.webp';" in load
    assert "#modetag{display:none;position:absolute;right:8px;top:8px;" in PAGE      # the look's tag moved off the jar
