"""1.58.55 — the 3D models in the Near list, the card and the guide; a pin put on the map keeps its view.

The owner: "update the 3D models in the threats nearby and in the cheat sheet". A reader (on a phone): "after zooming in
on the tactical map to precisely position the marker, the map reverted to its original scale".
"""
import os
import re

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, GUIDE, SW = _read("static", "kyiv.html"), _read("static", "guide.html"), _read("static", "sw.js")
MOD, REN = _read("static", "models3d.js"), _read("scripts", "render_models.js")


def test_the_near_rows_and_the_card_show_the_model_turning():
    assert "const rowIco=(m,col,sz)=>m3Ico(m,sz,col)||silSvg(m,col);" in PAGE
    assert "function m3Ico(m,sz,col){ if(!m3Ok()||!m||m.status) return ''; const s=m3Sheet(m3Key(m),'spin',col||m3IcoCol(m),M3IPX);" in PAGE
    near = PAGE[PAGE.index("function nearHTML(rows){"):PAGE.index("// The escalation level")]
    assert "${rowIco(m,here?'#ff2d55':null,38)}" in near and "silSvg(" not in near
    assert "ch.innerHTML=`${rowIco(m,here?'#ff2d55':null,36)}" in PAGE
    # the strips are made after the list is drawn: it is drawn again when they are there
    assert "if(sh){ M3.cache.set(id,sh); M3.gen++; }" in PAGE and "if(typeof paintCard==='function') paintCard(true); }" in PAGE
    assert "$('kyiv').querySelector('.dur')?.textContent||'',M3.gen].join('#');" in PAGE
    assert ".nrow>.m3ico{margin:0;" in PAGE


def test_a_pin_put_on_the_map_keeps_the_view_it_was_put_in():
    save = PAGE[PAGE.index("$('homesave').onclick="):PAGE.index("$('homeclear').onclick=")]
    assert "same=p===SLOTS[slot]" in save
    assert "if(!same){ const [x,y]=proj(p.lon,p.lat); setView(x,y,Math.max(p.street?1.6:4,(p.km||8)*2.6)); }" in save
    assert save.index("same=p===SLOTS[slot]") < save.index("setSlot(slot,p)")      # read before the slot takes it


def test_the_guide_plays_the_models_from_one_picture():
    rows = re.search(r"const ROWS = (\[\[.*?\]\]);", REN, re.S).group(1)
    keys = re.findall(r"\['(\w+)', '#", rows)
    assert keys == ["drone", "jetdrone", "missile", "ballistic", "bomb"]
    assert "var M3G=['drone','jetdrone','missile','ballistic','bomb']" in GUIDE
    px = int(re.search(r"const PX = (\d+);", REN).group(1))
    n, dur = re.search(r"spin: \{n: (\d+), dur: ([\d.]+)\}", MOD).groups()
    im = Image.open(os.path.join(ROOT, "static", "threats3d.webp"))
    assert im.size == (int(n) * px, len(keys) * px) and im.mode == "RGBA"
    assert os.path.getsize(os.path.join(ROOT, "static", "threats3d.webp")) < 200_000
    assert f"background-size:{int(n) * 100}% {len(keys) * 100}%" in GUIDE
    assert f"animation:m3g {dur}s steps({n},jump-none) infinite" in GUIDE
    # every model the guide names is one models3d.js builds, and each card's silhouette key is the row's
    for k in keys:
        assert f"'{k}'" in MOD.split("export const KEYS")[1].split("\n")[0]
    assert "shahed:['drone'," in GUIDE and "jet:['jetdrone'," in GUIDE and "cruise:['missile'," in GUIDE
    assert "ballistic:['ballistic'," in GUIDE and "kab:['bomb'," in GUIDE


def test_the_guide_stays_light_and_offline():
    # after the page, as an image, never with "save data"; nothing fetched, no script but the silhouettes'
    assert re.findall(r"<script[^>]*\bsrc=\"([^\"]+)\"", GUIDE) == ["/static/glyphs.js"] and "fetch(" not in GUIDE
    go = GUIDE[GUIDE.index("// 1.58.55: the picture of the models once the page is up"):]
    assert "navigator.connection.saveData" in go and "if(sd) return;" in go
    assert "im.onload=function(){ M3_ON=true; render(); }; im.src='/static/threats3d.webp';" in go
    assert "window.addEventListener('load'" in go
    # the silhouette stays under it (until it is here, in print) and reduced motion stops it on its first frame
    assert ".ic.m3~.ic{display:none}" in GUIDE and ".ic.m3{display:none}.ic.m3~.ic{display:block}" in GUIDE
    assert "@media (prefers-reduced-motion:reduce){.ic.m3{animation:none}}" in GUIDE
    assert "const KEEP = GUIDE.concat(SHELL, ['/static/threats3d.webp'," in SW
