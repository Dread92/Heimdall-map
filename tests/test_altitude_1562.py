"""1.56.2: a height is never shown more than 4 minutes after the report that stated it.

The owner (10 Oct 2026): "for the altitude report we should never exceed 4 minutes — a drone at low altitude (900 m) whose
altitude was last reported 10 minutes ago is probably already down, has struck a target, has regained altitude or has
changed path". Kyiv INFO, 15:48 "900m Shahid Drone", 15:50 "Again, explosions, it's close by" — on the map the 900 m stayed
for 11 minutes.
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


PAGE, LIGHT, I18N, DOC, SAFETY = (_read("static/kyiv.html"), _read("static/light.html"), _read("static/i18n.js"),
                                  _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md"))


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_four_minutes_at_most():
    prog = r"""
global.localStorage={getItem(){return null}}; global.navigator={language:'en'};
eval(require('fs').readFileSync(process.argv[1],'utf8'));
const ago=m=>new Date(Date.now()-m*60000).toISOString(), out={};
out.fresh=altNow({ts:ago(3.5),alt:{m:900}});
out.old=altNow({ts:ago(4.5),alt:{m:900}});
out.none=altNow({ts:ago(1)});
out.trend=altTrend({ts:ago(2),alt:{m:900},history:[{ts:ago(6),alt_m:1500}]});
out.trendOld=altTrend({ts:ago(11),alt:{m:900},history:[{ts:ago(15),alt_m:1500}]});
out.trendLastInHistory=altTrend({ts:ago(1),history:[{ts:ago(9),alt_m:1500},{ts:ago(6),alt_m:900}]});
process.stdout.write(JSON.stringify(out));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "i18n.js")], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert "const ALT_MAX_MIN=4;" in I18N and r["fresh"] == {"m": 900} and r["old"] is None and r["none"] is None
    assert r["trend"]["dir"] == "down" and r["trendOld"] is None and r["trendLastInHistory"] is None


def test_every_height_on_the_maps_and_in_the_lists_goes_through_it():
    for s in ("const A0=altNow(m), tv0=", "(A0&&A0.m&&live1)?A0.m:(tgv&&tgv.alt&&tgv.alt.m&&altFresh(tgv.alt.at||m.ts)?tgv.alt.m:null)",
              "const altOld=altM&&", "tv0.vs.v==='descending'&&altFresh(m.ts)", "function oblAlt(m){ if(m.status) return ''; const tg=m.tag||{}, A=altNow(m);",
              "const descTxt=(altNow(m)&&", "altF=alt&&altNow(m)", "const altChip=!altF?'':", "t('alt_old',Math.round(agoMin(m.ts)))"):
        assert s in PAGE, s
    for s in ("const tr=altTrend(m), A=altNow(m), dsc=(A&&A.state==='descending')", "const tr=altTrend(m), A=altNow(m);",
              "else if(A&&A.m!=null) bits.push("):
        assert s in LIGHT, s
    assert "m.alt&&m.alt.state==='descending')||(tr&&tr.dir==='down')" not in LIGHT
    import re
    assert len(re.findall(r"(?<![\w])alt_old:", I18N)) == 3


def test_the_docs():
    assert "ALT_MAX_MIN" in DOC and "4 minutes" in SAFETY
