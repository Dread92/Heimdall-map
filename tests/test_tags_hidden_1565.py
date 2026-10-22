"""1.56.5: the target numbers are off in the app, for now.

The owner (11 Oct 2026): "let's also disable the target IDs for now — it doesn't work and it's very unreliable".
The server still works them out (the patterns, the record); the pages show none.
"""
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, REPLAY, LIGHT = _read("static/kyiv.html"), _read("static/i18n.js"), _read("static/replay.js"), _read("static/light.html")


def test_off_everywhere_a_number_was_shown():
    assert "const TAGS_SHOWN=false;" in I18N
    for s in ("tg=(TAGS_SHOWN&&!m.status&&!m.endedBy)?m.tag:null", "tid=TAGS_SHOWN&&en[k]===1&&m.tag?m.tag.id:''",
              "${TAGS_SHOWN&&cur.tag?`<span class=\"tagid\">", "return `${TAGS_SHOWN?`<div class=\"kv1 tagl\">",
              "${TAGS_SHOWN&&m.tag?`<div style=\"font-size:11px;color:var(--muted);margin-top:6px\">${esc(t('tg_what'))}",
              "if(!TAGS_SHOWN||!tg||!tg.night||m.status) return;"):
        assert s in PAGE, s
    assert "tr.tg&&typeof TAGS_SHOWN!=='undefined'&&TAGS_SHOWN?tr.tg+' ':''" in REPLAY
    # every other use of a tag's number in the page goes through the switch
    uses = [m.start() for m in re.finditer(r"\.tag\.id|tg\.id", PAGE)]
    # 1.58.44: and one key that is never shown — a target sounds once per track (trackKey)
    assert uses and all("TAGS_SHOWN" in PAGE[max(0, u - 900):u] or "sig=" in PAGE[max(0, u - 200):u]
                        or "const trackKey=m=>" in PAGE[max(0, u - 90):u] for u in uses)
    assert "tag.id" not in LIGHT


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_switch_is_false_in_the_browser():
    prog = r"""global.localStorage={getItem(){return null}}; global.navigator={language:'en'};
const vm=require('vm'); vm.runInThisContext(require('fs').readFileSync(process.argv[1],'utf8')); process.stdout.write(String(TAGS_SHOWN));"""
    p = subprocess.run([NODE, "-e", prog, os.path.join(ROOT, "static", "i18n.js")], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout == "false", p.stderr


def test_the_docs():
    assert "TAGS_SHOWN" in _read("docs/TECHNICAL.md") and "1.56.5" in _read("docs/SAFETY.md")
