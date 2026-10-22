"""1.57: the shelters Kyiv city lists — labelled as the city labels them, the nearest found on the phone.

The owner's colleague: "a layer of the official shelters — only the government's data — baked into the app so it works
offline". The owner: every shelter the city lists, each labelled with what it is (static/shelters.json, from the city's
shelter map, KMDA). A distance is a straight line, never a route, a walking time or a time to get there; nothing says a
place is safe; no pin leaves the phone.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_shelters as B  # noqa: E402

NODE = shutil.which("node")


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, SW, MOD = _read("static/kyiv.html"), _read("static/light.html"), _read("static/sw.js"), _read("static/shelters.js")
CODE = "\n".join(ln for ln in MOD.splitlines() if not ln.strip().startswith("//"))     # what a reader can be shown


def test_the_city_s_types_are_read_as_the_city_wrote_them():
    c = B.classify
    assert c("Споруди подвійного призначення", "Станція метрополітену")[:2] == ("metro", "station")
    assert c("Найпростіше укриття", "Вхід в станцію метро")[:2] == ("metro", "entrance")
    assert c("Вхід в станцію метро", "Вхід в станцію метро")[:2] == ("metro", "entrance")
    assert c("Подвійного призначення", "Підземний перехід з пандусом")[:2] == ("underpass", "underpass")
    assert c("Укриття", "Підвал з пандусом")[:2] == ("shelter", "basement")
    assert c("СПП із захисними властивостями ПРУ", "СПП із захисними властивостями ПРУ")[:2] == ("shelter", "pru")
    assert c("Споруди подвійного призначення", "Підземний паркінг")[:2] == ("dual", "parking")
    assert c("Найпростіше укриття", "Частина паркінгу прилегла до евакуаційного коридор")[:2] == ("simple", "parking")
    assert c("Найпростіші укриття", "Підвал") == ("simple", "basement", True)          # the plural, and a typo
    assert c("Найпросітіше укриття", "Підвал") == ("simple", "basement", True)
    assert c("Підвал", "Багатоквартирний будинок")[:2] == ("simple", "basement")
    assert c("Первинне (мобільне) укриття", "ПМУ")[:2] == ("mobile", "")
    # a pair the rules do not know is never ranked higher than a simplest shelter, and is reported
    assert c("Щось нове", "Підвал") == ("simple", "basement", False)


def test_who_may_come_in_is_the_city_s_words():
    a = B._access
    assert a("Цілодобово", None) == ("", "")
    assert a(None, None) == ("?", "")
    assert a("Впродовж навчального дня доступ надається тільки учасникам освітнього процесу", None)[0] == "s"
    assert a("Укриття доступне лише для учасників освітнього процесу", None)[0] == "S"
    assert a("Цілодобово", "тільки для освітнього процесу")[0] == "S"
    assert a("Проводиться капітальний ремонт.\nПротягом навчального дня укриття доступне лише для учасників освітнього процесу", None)[0] == "r"
    assert a("Цілодобово", "Доступ надається в робочий час з 10:00 до 18:00") == ("10:00–18:00", "")
    assert a("10:00–18:00", None)[0] == "10:00–18:00"
    assert B._ramp("Підвал", "В наявності") == 1 and B._ramp("Підземний перехід з пандусом", "Відсутній") == 1
    assert B._ramp("Підвал", "Відсутній") == 0 and B._ramp("Підвал", None) == 0


def _f(typ, kind, addr, x, y, hours="Цілодобово", note=None, inv="Відсутній", tel="044 000 00 00, 050 1"):
    return {"attributes": {"type": typ, "kind": kind, "address": addr, "working_time": hours, "description": note,
                           "invalid": inv, "tel": tel}, "geometry": {"x": x, "y": y}}


def test_the_file():
    doc = {"features": [
        _f("Споруди подвійного призначення", "Станція метрополітену", "Станція метро «Печерська»", 30.5390, 50.4270),
        _f("Споруди подвійного призначення", "Вхід в станцію метро", "Вхід в станцію метро", 30.5405, 50.4275),
        _f("Найпростіше укриття", "Підвал", "вул. Григорія Сковороди, 2", 30.5200, 50.4640,
           "Укриття доступне лише для учасників освітнього процесу"),
        _f("Найпростіше укриття", "Підвал", "вул. Григорія Сковороди, 2", 30.5200, 50.4640),      # the same point: kept once,
        _f("Найпростіше укриття", "Підвал", "поза містом", 31.9, 49.0),                           # the open one
    ]}
    d, unknown, dropped = B.build(doc, "2026-10-11")
    assert d["n"] == 3 and dropped == 1 and not unknown and d["asof"] == "2026-10-11" and "КМДА" in d["src"]
    met = [r for r in d["s"] if r[2] == B.CATS.index("metro")]
    assert [B.KINDS[r[3]] for r in met] == ["station", "entrance"]
    assert met[1][5] == "Вхід у метро — біля ст. «Печерська»"            # named after the station, as the nearest
    base = next(r for r in d["s"] if r[5].startswith("вул."))
    assert base[6] == "" and base[7] == "044 000 00 00"                   # the open one; the first phone number
    with pytest.raises(SystemExit):                                       # a page of the answer is never the city
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shelters_tmp.json")
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            B.main([p, "--asof", "2026-10-11", "--out", p + ".out"])
        finally:
            for q in (p, p + ".out"):
                if os.path.exists(q):
                    os.remove(q)


def test_the_bundled_list():
    d = json.loads(_read("static/shelters.json"))
    assert d["v"] == B.FORMAT and d["cat"] == B.CATS and d["kind"] == B.KINDS and d["url"] == B.URL
    assert d["n"] == len(d["s"]) > 3000 and d["asof"] >= "2026-10-11"
    for r in d["s"]:
        assert 30.1 <= r[0] <= 31.0 and 50.1 <= r[1] <= 50.7 and r[4] in (0, 1)
    by = {c: sum(1 for r in d["s"] if r[2] == i) for i, c in enumerate(B.CATS)}
    assert by["metro"] > 100 and by["underpass"] > 100 and by["simple"] > 1000


def test_the_phone_works_it_out_and_says_no_more_than_the_city():
    assert MOD.count("fetch(") == 1 and "fetch('/static/shelters.json" in MOD          # one file, the same for everyone
    for w in (r"\bsafe\b", r"(?<!не)безпечн", r"\bsûrs?\b", r"\bminutes?\b", "хвилин", r"\bwalk"):
        assert not re.search(w, CODE), w                                         # "небезпечно" (dangerous) is fine
    assert MOD.count("two walls") == 1 and MOD.count("правило двох стін") == 1 and MOD.count("deux murs") == 1
    assert MOD.count("Heimdall does not check shelters") == 1 and MOD.count("straight-line distance") == 1
    assert "closed(i){ const h=SH.D.s[i][6]; return h==='S'||h==='r'; }" in MOD
    assert "'/static/shelters.json'];" in SW and "'/light.webmanifest', '/static/shelters.js']);" in SW   # kept for no network
    # (1.58.46: the list answered from the kept copy at once; the code network first, never an old release's)


def test_the_pages():
    assert "<g id=\"shelg\"></g>" in PAGE and 'id="mysh"' in PAGE and 'data-l="shelters"' in PAGE
    assert "if(!HOME||!shIn(HOME)||!(LEVEL>=1||pk!=='G'||LAYERS.shelters)){ el.hidden=true; return; }" in PAGE
    assert "closest('g.mk,g.imp,g.shl')" in PAGE and "openShelter(+mk.dataset.i)" in PAGE
    assert "heat:false,shelters:false};" in PAGE                                    # off by default
    assert "SH.light($('lsh'),p,k,LANG,placeName(p),paint)" in LIGHT and "lShel(p,s.k);" in LIGHT
    for lang in ("Shelters around me (5 km)", "Укриття навколо мене (5 км)", "Abris autour de moi (5 km)"):
        assert lang in _read("static/i18n.js")
    # 1.57.1, the owner: "shelters around me", within 5 km of the pin — the card, the list and the layer
    assert "const RADIUS_KM=5;" in MOD and "max=o.max||RADIUS_KM" in MOD and "LIST_KM" not in MOD
    assert "if(!LAYERS.shelters||!window.SH||!SH.D||!MAP||!shIn(HOME)||VB.w>120)" in PAGE
    assert 'r="${SH.RADIUS_KM}"' in PAGE and "SH.near(HOME.lon,HOME.lat,{n:1e5,all:true})" in PAGE and "shNoPin();" in PAGE


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_nearest():
    prog = r"""global.window={}; require(process.argv[1]); const SH=window.SH; SH.D=require(process.argv[2]);
const out={}; const P=[30.5390,50.4270];   // Pechersk
out.st=SH.near(P[0],P[1],{strong:true,n:3}).map(([i,d])=>[SH.D.cat[SH.D.s[i][2]],+d.toFixed(3)]);
out.closed=SH.near(P[0],P[1],{n:4000}).filter(([i])=>SH.closed(i)).length;
out.all=SH.near(P[0],P[1],{n:4000,all:true}).filter(([i])=>SH.closed(i)).length; out.max=Math.max(...SH.near(P[0],P[1],{n:4000}).map(a=>a[1]));
out.line=SH.line(P[0],P[1],'en'); out.far=SH.line(31.5,49.5,'en'); out.irpin=SH.line(30.25,50.52,'en');
out.html=['uk','en','fr'].map(l=>SH.listHTML(P[0],P[1],l,'Дім'));
out.dist=[SH.dist(0.004,'en'),SH.dist(0.437,'uk'),SH.dist(1.26,'fr'),SH.dist(12.4,'en')];
process.stdout.write(JSON.stringify(out));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "shelters.js"), os.path.join(ROOT, "static", "shelters.json")],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    o = json.loads(p.stdout)
    assert len(o["st"]) == 3 and all(c in ("metro", "underpass", "shelter") for c, _ in o["st"])
    assert [d for _, d in o["st"]] == sorted(d for _, d in o["st"]) and o["st"][0][1] < 0.5
    assert o["closed"] == 0 and o["all"] > 0                          # a school's own, or one under repair: never offered
    assert 4.5 < o["max"] <= 5                                        # within 5 km of the pin
    assert o["line"]["st"] and o["far"] is None                      # outside Kyiv city: nothing
    assert o["dist"] == ["10 m", "440 м", "1,3 km", "12 km"]
    for h, words in zip(o["html"], (("Укриття навколо мене", "у радіусі 5 км", "по прямій", "КМДА", "двох стін"),
                                    ("Shelters around me", "within 5 km", "straight-line", "KMDA", "two walls"),
                                    ("Abris autour de moi", "dans un rayon de 5 km", "vol d&#39;oiseau", "KMDA", "deux murs"))):
        for w in words:
            assert w in h, (w, h[:200])


def test_the_docs():
    doc, safety, ch = _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md"), _read("CHANGELOG.md")
    for s in ("### 10.7 The shelters Kyiv city lists", "build_shelters.py", "Укриття_редактор", "SH.closed", "_name_entrances"):
        assert s in doc, s
    assert "a distance is a straight line" in safety.lower() or "A distance is a straight line" in safety
    assert "## 1.57.0" in ch
