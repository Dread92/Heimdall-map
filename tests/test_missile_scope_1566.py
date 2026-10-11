"""1.56.6: a missile warning for another oblast neither raises the shelter banner nor changes the targets here.

The owner (11 Oct 2026, a phone in Vyshenky at 15:34): "a ballistic alert for I don't know which oblast, and the banner
alarms the user for nothing — it must be fixed at all costs, all the more because it changes how the targets are marked".
The Air Force, 15:32: "🚀Швидкісна ціль на заході Донеччини, курс на північ." The Voronkiv target became "drone or missile".
"""
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
NOW = datetime.now(timezone.utc)
DONETSK = "🚀Швидкісна ціль на заході Донеччини, курс на північ."


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N = _read("static/kyiv.html"), _read("static/light.html"), _read("static/i18n.js")


def test_a_missile_post_says_which_oblasts():
    bal = ["ballistic_missiles"]
    assert server.missile_obls("a/1", "kpszsu", DONETSK, bal) == ["28"]
    assert server.missile_obls("a/2", "kpszsu", "🚀Швидкісна ціль на Київ!", bal) == ["14"]       # the city is its oblast
    assert server.missile_obls("a/3", "kpszsu", "🚀Швидкісна ціль на Кривий Ріг", bal) == ["9"]    # a town's oblast
    assert server.missile_obls("a/4", "kpszsu", "Загроза застосування балістичного озброєння з північного сходу", bal) == []
    assert server.missile_obls("a/5", "kpszsu", DONETSK, ["drones"]) == []                          # missile posts only


def _state_with(text):
    st = server.State(server.Store(":memory:"), {})
    st.store.conn.execute("INSERT INTO feed(post_id, channel, ts, text, tags) VALUES(?,?,?,?,?)",
                          ("kpszsu/1", "kpszsu", (NOW - timedelta(minutes=2)).isoformat(), text, json.dumps(["ballistic_missiles"])))
    st.store.conn.commit()
    return st


def test_the_server_does_not_raise_the_missile_level_for_another_oblast():
    assert server.State._missile_active(_state_with(DONETSK)) == server.State.MSL_NONE
    assert server.State._missile_active(_state_with("🚀Швидкісна ціль на Київ!")) == server.State.MSL_BALLISTIC
    assert server.State._missile_active(_state_with("Загроза застосування балістичного озброєння з північного сходу")) == server.State.MSL_BALLISTIC
    # the level sets every reader's cadence: an oblast on the map still raises it (Kharkiv), one off it does not
    assert server.State._missile_active(_state_with("🚀Швидкісна ціль на Харківщину")) == server.State.MSL_BALLISTIC
    assert server.State._missile_active(_state_with("🚀Швидкісна ціль на Запоріжжя")) == server.State.MSL_NONE
    # an edited post keeps its id: its new text is read again
    assert server.missile_obls("e/1", "kpszsu", DONETSK, ["ballistic_missiles"]) == ["28"]
    assert server.missile_obls("e/1", "kpszsu", "🚀Швидкісна ціль на Київ!", ["ballistic_missiles"]) == ["14"]
    st = _state_with(DONETSK)
    assert st.store.feed(10)[0]["obl"] == ["28"]                                   # the pages are told which oblast


def test_the_strip_keeps_a_missile_post_to_the_oblasts_it_names():
    assert "if(p.obl&&p.obl.length&&!tg.includes('mig31k_departure')&&!p.obl.some(ours)) continue;" in PAGE
    assert "const ours=u=>mine.has(u)||(u==='14'&&mine.has('31'));" in PAGE


def test_the_missile_context_is_local():
    assert "const MSL_NEAR_KM=150;" in PAGE and "const asDrone=m=>m.type==='unknown'&&!m.status&&!mslCtx(m);" in PAGE
    assert "MSLX" not in PAGE.split("// late). The missile context")[1][:4000] and "mslPaint();" in PAGE
    assert "const lMsl=m=>MKS.some(x=>!x.status&&/^(mig31|strat)/.test(x.type))||mslNear(m,MKS);" in LIGHT
    assert "const lDr=m=>m.type==='unknown'&&!m.status&&!lMsl(m);" in LIGHT


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_mslnear():
    prog = r"""global.localStorage={getItem(){return null}}; global.navigator={language:'en'};
const vm=require('vm'); vm.runInThisContext(require('fs').readFileSync(process.argv[1],'utf8'));
const vor={lon:31.05,lat:50.06}, don={type:'ballistic_missiles',lon:37.2,lat:48.3}, near={type:'cruise_missiles',lon:30.9,lat:50.4};
process.stdout.write(JSON.stringify([mslNear(vor,[don]), mslNear(vor,[near]), mslNear(vor,[Object.assign({},near,{status:'down'})])]));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "i18n.js")], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == [False, True, False]


def test_the_docs():
    assert "missile_obls" in _read("docs/TECHNICAL.md") and "Донеччини" in _read("docs/SAFETY.md")
