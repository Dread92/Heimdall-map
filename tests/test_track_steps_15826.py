"""1.58.26 — a track lists each place once in a row.

The owner (15 Oct 2026, 02:03, two Shaheds tracked by @chyste_nebo near Makariv and Fastiv): "there are often duplicates
of the height like this". The channel posts a height on its own — "700", "4400" — and each is a report of its own at
the target's last place: the card read "Макарів 02:00 (700 m) → Макарів 02:00 (600 m) → Небелиця 02:03 → Небелиця 02:03
(700 m)", the tooltip "Таборів 01:50 → Таборів 01:50 → Таборів 01:51 → … → Фастів 01:58 → Фастів 01:58". Reports at one
place in a row are one step now — its first time, its last when later, the heights said there in order; a height said
twice in a row is said once, and "700" then "700" is no trend. The count of posts is still the count of posts.
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


PAGE, LIGHT, I18N = _read("static/kyiv.html"), _read("static/light.html"), _read("static/i18n.js")


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_one_step_a_place_and_its_heights_in_order():
    prog = r"""
global.localStorage={getItem(){return null}}; global.navigator={language:'en'};
eval(require('fs').readFileSync(process.argv[1],'utf8'));
const T=s=>'2026-10-14T'+s+':00Z', fmt=iso=>iso.slice(11,16), out={};
// @chyste_nebo, 14 Oct 2026, 22:59-23:04 UTC: "Увага Макарів та сусіди", "4400", "700 висота", "600", "Небелиця", "700"
const mak=[{pl:'Макарів',ts:T('22:59'),alt:null},{pl:'Макарів',ts:T('22:59'),alt:4400},{pl:'Макарів',ts:T('23:00'),alt:700},
           {pl:'Макарів',ts:T('23:00'),alt:600},{pl:'Небелиця',ts:T('23:03'),alt:null},{pl:'Небелиця',ts:T('23:03'),alt:700}];
out.mak=trackSteps(mak).map(s=>stepTxt(s,p=>p,fmt));
// "Таборів", "1700", "5400", "Рогізна 2000", …, "Фастів" ×3 then "4400"
const fas=[{pl:'Таборів',ts:T('22:50')},{pl:'Таборів',ts:T('22:50'),alt:1700},{pl:'Таборів',ts:T('22:51'),alt:5400},
           {pl:'Рогізна',ts:T('22:52'),alt:2000},{pl:'Фастів',ts:T('22:56')},{pl:'Фастів',ts:T('22:57')},{pl:'Фастів',ts:T('22:58')},
           {pl:'Фастів',ts:T('22:58'),alt:4400}];
out.fas=trackSteps(fas).map(s=>stepTxt(s,p=>p,fmt));
out.repeat=trackSteps([{pl:'A',ts:T('22:00'),alt:700},{pl:'A',ts:T('22:01'),alt:700}]).map(s=>stepTxt(s,p=>p,fmt));
out.apart=trackSteps([{pl:'A',ts:T('22:00')},{pl:'A',ts:T('22:15')}]).length;            // the same place 15 min later
out.between=trackSteps([{pl:'A',ts:T('22:00')},{pl:'B',ts:T('22:01')},{pl:'A',ts:T('22:02')}]).length;
const ago=m=>new Date(Date.now()-m*60000).toISOString();
out.same=altTrend({ts:ago(1),alt:{m:700},history:[{ts:ago(2),alt_m:700}]});
out.trend=altTrend({ts:ago(1),alt:{m:700},history:[{ts:ago(3),alt_m:4400},{ts:ago(3),alt_m:4400},{ts:ago(2),alt_m:600}]});
process.stdout.write(JSON.stringify(out));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "i18n.js")], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["mak"] == ["Макарів 22:59–23:00 (4.4 km → 700 m → 600 m)", "Небелиця 23:03 (700 m)"]
    assert r["fas"] == ["Таборів 22:50–22:51 (1.7 km → 5.4 km)", "Рогізна 22:52 (2 km)", "Фастів 22:56–22:58 (4.4 km)"]
    assert r["repeat"] == ["A 22:00–22:01 (700 m)"]           # a height said twice in a row, once
    assert r["apart"] == 2 and r["between"] == 3                 # only one after another, and within 10 minutes
    assert r["same"] is None                                      # "700", "700": one height, no trend
    assert r["trend"]["text"] == "↓ 4.4 km → 600 m → 700 m"


def test_every_track_list_goes_through_it():
    assert PAGE.count("trackSteps(") >= 3         # the card, the tooltip, the night's trail
    assert "trackSteps((m.history||[])" in LIGHT  # the Light page's row
    assert "t('sh_track',m.history.length+1)" in PAGE and "t('tp_reports',cur.history.length+1)" in PAGE   # posts, counted
    assert "function trackSteps(list)" in I18N and "function stepTxt(s,name,fmt)" in I18N
