"""1.56: every settlement and street of Ukraine, from OpenStreetMap, searched on the phone.

The owner (10 Oct 2026): "for the district / village etc. it would be good to have a complete registry of the streets
within the city / oblast, so the user can set the pin accurately" — "all the towns and the streets of Ukraine".
"""
import gzip
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "static", "streets")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_streets as B  # noqa: E402
import server  # noqa: E402

NODE = shutil.which("node")


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, JS, DOC, SAFETY = (_read("static/kyiv.html"), _read("static/light.html"), _read("static/i18n.js"),
                                      _read("static/streets.js"), _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md"))


def _file(uid):
    with open(os.path.join(DIR, f"{uid}.json"), encoding="utf-8") as f:
        return json.load(f)


# ---- the files ------------------------------------------------------------------------------------------------------
def test_one_file_for_each_oblast_of_the_app():
    uids = {u for u, _, _ in server.OBLASTS}
    assert set(B.EXTRACTS.values()) == uids and len(B.EXTRACTS) == 27
    assert set(B.OBLAST_NAMES.values()) == uids
    have = {f[:-5] for f in os.listdir(DIR) if f.endswith(".json")}
    assert have == uids, uids ^ have
    raw = gz = 0
    for u in uids:
        d = _file(u)
        assert d["v"] == B.FORMAT == 1 and d["uid"] == u and "OpenStreetMap" in d["lic"] and d["src"].endswith(".osm.pbf")
        assert d["t"] and d["s"], u
        for x in d["t"][:50]:
            assert isinstance(x[0], str) and 220000 < x[1] < 410000 and 440000 < x[2] < 530000 and x[3] in (0, 1, 2, 3)
            assert -1 <= x[4] < len(d["r"])
        for s in d["s"][:200]:
            assert isinstance(s[0], str) and 0 <= s[1] < len(d["t"]) and s[4] >= 0
            assert len(s) in (5, 6, 7) and (len(s) < 6 or s[5] == 0 or isinstance(s[5], str))
            assert len(s) < 6 or not (isinstance(s[5], str) and re.search(r"[A-Za-z]", s[5]))     # a Latin spelling is no name
        with open(os.path.join(DIR, f"{u}.json"), "rb") as f:
            b = f.read()
        raw += len(b)
        gz += len(gzip.compress(b, 6))
        assert len(gzip.compress(b, 6)) < 400_000, u          # an oblast on a phone: a few seconds on 3G, once
    # the whole country: ~16 MB in the repository, ~4 MB on the wire if every oblast were opened
    assert raw < 20_000_000 and gz < 5_000_000
    lic = _read("static/streets/LICENSE.md")
    assert "Open Database License" in lic and "© OpenStreetMap contributors" in lic


def test_the_places_the_owner_named():
    k = _file("31")
    assert [t[0] for t in k["t"]] == ["Київ"] and len(k["s"]) > 2500 and len(k["r"]) == 10
    hre = [s for s in k["s"] if s[0] == "вулиця Хрещатик"]
    assert hre and len(hre[0]) == 7 and k["r"][hre[0][6]].endswith("район")              # a Kyiv street has its district
    o = _file("14")
    t = {}
    for i, x in enumerate(o["t"]):
        t.setdefault(x[0], []).append((i, o["r"][x[4]] if x[4] >= 0 else None))
    assert t["Кулажинці"] == [(t["Кулажинці"][0][0], "Броварський район")]               # @chyste_nebo's village, 1.54.7
    assert {r for _, r in t["Лук’янівка"]} == {"Білоцерківський район", "Броварський район"}
    assert [r for _, r in t["Вишеньки"]] == ["Бориспільський район"]
    bro = t["Бровари"][0][0]
    assert sum(1 for s in o["s"] if s[1] == bro) > 200 and len(o["t"]) > 1000


def test_what_a_street_is():
    assert B._name({"name": "вулиця Шевченка"}) == ("вулиця Шевченка", None)
    assert B._name({"name": "улица Гагарина", "name:uk": "вулиця Гагаріна"}) == ("вулиця Гагаріна", "улица Гагарина")
    assert B._name({"name": "проспект Степана Бандери", "old_name": "Московський проспект"}) == ("проспект Степана Бандери", "Московський проспект")
    assert B._name({"name": "вулиця Хрещатик", "old_name": "Kreschatic"}) == ("вулиця Хрещатик", None)
    for road in ("Київ — Чоп", "М-06", "Н-07", "траса Київ-Одеса"):
        assert B.ROAD_NAME.search(road), road
    for street in ("вулиця Шевченка", "Велика Васильківська вулиця", "1-й провулок Дружби", "Кільцева дорога"):
        assert not B.ROAD_NAME.search(street), street
    assert B.STREET_WORD.search("провулок Тихий") and not B.STREET_WORD.search("АЗС")
    assert B.REACH_KM == {0: 10.0, 1: 4.0, 2: 2.0, 3: 1.0}


# ---- the search, on the phone -----------------------------------------------------------------------------------------
def _find(cases):
    prog = r"""
const fs=require('fs'); global.window={}; global.document={}; global.t=k=>k; global.LANG='uk';
eval(fs.readFileSync(process.argv[1],'utf8'));
const dir=process.argv[2], cases=JSON.parse(fs.readFileSync(0,'utf8')), out=[];
const F={}; const get=u=>F[u]||(F[u]=(()=>{ const d=JSON.parse(fs.readFileSync(dir+'/'+u+'.json','utf8')); return d; })());
for(const [q,uids] of cases){
  const ds=uids.map(u=>{ const d=get(u); if(!d.S){ window.HS._prep(d,u); } return d; });
  const r=window.HS.find(q,ds,[]);
  out.push(r&&{S:r.S.slice(0,5).map(o=>[o.s.n,o.d.T[o.s.ti].n,o.d.uid]),T:r.T.slice(0,5).map(o=>[o.t.n,o.t.r]),Sn:r.Sn});
}
process.stdout.write(JSON.stringify(out));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "streets.js"), DIR], input=json.dumps(cases),
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_search():
    K = ["31", "14"]
    r = _find([["Хрещатик", K], ["шевченка бровари", K], ["khreshchatyk", K], ["лукянівка", K], ["Бандери", K],
               ["городоцька львів", ["27"]], ["х", K], ["Московський проспект", K]])
    hre, shev, lat, luk, ban, lviv, short, old = r
    assert hre["S"][0][:2] == ["вулиця Хрещатик", "Київ"]                      # Kyiv first: the oblast chosen first
    assert shev["S"][0] == ["вулиця Шевченка", "Бровари", "14"] and all(s[1] == "Бровари" for s in shev["S"])
    assert lat["S"][0][:2] == ["вулиця Хрещатик", "Київ"]                       # Latin typed: the same street
    assert [x[0] for x in luk["T"]] == ["Лук’янівка", "Лук’янівка"]              # an apostrophe or none
    assert ban["S"][0] == ["проспект Степана Бандери", "Київ", "31"]
    assert lviv["S"][0][1] == "Львів" and "Городоцька" in lviv["S"][0][0]
    assert short is None                                                         # one letter: nothing yet
    assert old["S"][0] == ["проспект Степана Бандери", "Київ", "31"]            # its old name finds it


def test_what_is_typed_never_leaves_the_phone():
    fetches = re.findall(r"fetch\(([^)]*)\)", JS)
    assert fetches == ["`/static/streets/${uid}.json?v=${V}`"]                   # one download: the oblast's file
    assert "XMLHttpRequest" not in JS and "sendBeacon" not in JS and "localStorage.setItem('hs_obl'" in JS
    for page in (PAGE, LIGHT):
        assert "s.src='/static/streets.js?v=" in page and "HS.mount({q:" in page
    assert "<script src=\"/static/streets.js" not in PAGE + LIGHT                 # loaded only when a picker opens
    assert "the server sees only which" in JS and "which oblast's list" in DOC and "OpenStreetMap" in SAFETY


def test_the_pages():
    assert "function hsPick(p){" in PAGE and "PIN_KEEP={name:p.name,uk:p.uk,obl:p.obl}; armPin(true,slot,true);" in PAGE   # 1.58.34: on save
    assert "setSlot(id,keep?Object.assign({lon,lat},keep):{lon,lat,dropped:true});" in PAGE      # moved: still the street
    assert "t(st?'sl_arm_st':'sl_arm_n',slotName(PIN_FOR))" in PAGE
    assert "pick:p=>setPlace({name:p.uk,uk:p.uk,lon:p.lon,lat:p.lat,obl:p.obl})" in LIGHT
    for k in ("hs_in", "hs_kyiv2", "hs_loading", "hs_fail", "hs_none", "hs_streets", "hs_towns", "hs_was", "hs_more", "hs_osm",
              "hs_k0", "hs_k1", "hs_k2", "hs_k3", "sl_arm_st"):
        assert len(re.findall(r"(?<![\w])" + k + ":", I18N)) == 3, k
    assert "© OpenStreetMap" in JS and "https://www.openstreetmap.org/copyright" in JS
