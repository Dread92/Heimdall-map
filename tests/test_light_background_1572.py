"""1.57.2: the Light radar's background — plain, satellite or map, as on the Tactical map.

The owner: "it'd be good if the light version of the app was showing satellite / map version too of the map". Plain by
default, the choice kept on the phone; the code is loaded only when asked for (static/lightmap.js), so the page stays
light. A pin never leaves the phone: the tiles asked for are those of the ~10 km cell the place is in, never its own.
"""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


LIGHT, MOD = _read("static/light.html"), _read("static/lightmap.js")


def test_the_page_loads_it_only_when_asked():
    assert 'id="zbg"' in LIGHT and "$('zbg').onclick=()=>ldLT(()=>LT.menu());" in LIGHT
    assert "try{ if(localStorage.getItem('lbg')) ldLT(); }catch(e){}" in LIGHT        # a choice kept: at the next opening
    assert "$('radar').innerHTML=g; if(window.LT) LT.draw(p);" in LIGHT
    assert "lightmap.js" not in _read("static/sw.js").split("FAST")[0]                # never downloaded ahead


def test_what_it_says():
    for s in ("© ESA WorldCover 2021", "Powered by Esri", "uses more data", "більше даних", "plus de données"):
        assert s in MOD, s
    assert "tr('l_base')" in MOD and "'l_plain'" in MOD and "'l_sat'" in MOD and "'l_map'" in MOD   # the Tactical words
    assert "/tiles/esri/mapn/" in MOD and "/tiles/sat/" in MOD


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_tiles_say_the_cell_not_the_place():
    prog = r"""global.window={devicePixelRatio:2}; global.document={createElement:()=>({}),head:{appendChild(){}}};
global.S=2; global.localStorage={getItem(){return null},setItem(){},removeItem(){}};
require(process.argv[1]); const LT=window.LT; const a={sat:true,v:'3',zmax:13,map:true};
const T=(p,b,rz)=>LT.tiles(p,b,a,rz||{z:1,cx:0,cy:0},400,2);
const p1={lon:30.5390,lat:50.4270}, p2={lon:30.5420,lat:50.4290}, far={lon:30.80,lat:50.45};
const k=ts=>ts.map(t=>t.k).sort().join(',');
const s=T(p1,'sat'), m=T(p1,'map'), zin=T(p1,'sat',{z:4,cx:10,cy:-6});
// the place itself, (0,0) on the radar, is inside one of the tiles; every view corner is covered
const inside=(ts,x,y)=>ts.some(t=>x>=t.x&&x<=t.x+t.w&&y>=t.y&&y<=t.y+t.h);
const cov=[[-60,-60],[60,-60],[-60,60],[60,60],[0,0]].every(([x,y])=>inside(s,x,y));
const covz=[[10-16,-6-16],[10+16,-6+16]].every(([x,y])=>inside(zin,x,y));
process.stdout.write(JSON.stringify({same:k(T(p1,'sat').map(t=>({k:t.k})))===k(T(p2,'sat').map(t=>({k:t.k}))),
  other:k(s)!==k(T(far,'sat')), n:[s.length,m.length,zin.length], z:[s[0].k.split('/')[1],m[0].k.split('/')[1],zin[0].k.split('/')[1]],
  cov, covz, href:[s[0].href,m[0].href]}));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "lightmap.js")], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    o = json.loads(p.stdout)
    assert o["same"] and o["other"]                       # two places of one cell ask for the same tiles; another cell not
    assert all(n <= 49 for n in o["n"]) and o["cov"] and o["covz"]
    assert int(o["z"][0]) >= 10 and int(o["z"][2]) > int(o["z"][0]) and int(o["z"][2]) <= 13
    assert o["href"][0].startswith("/tiles/sat/") and o["href"][0].endswith(".webp?v=3")
    assert o["href"][1].startswith("/tiles/esri/mapn/") and "lang=" in o["href"][1]
