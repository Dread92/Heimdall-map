"""1.58.32 — the side panels fold on a computer.

Oleksandr Tymoshenko (15 Oct 2026): "Makes sense as an option to collapse or hide the side panels and to give users maximum
map visibility together with full screen mode … a subtle vertical button with an arrow right on the inner border of each
panel … Alternatively, panels can collapse into a narrow ~50px strip instead of hiding completely. On the left side, it
retains only the color status dot (green/yellow/red) and total target count. On the right side, it keeps only the three
tab icons (Feed, Alerts, Stats)."
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, DOC = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("docs", "TECHNICAL.md")


def test_a_chevron_on_each_inner_edge_folds_its_panel_into_a_strip():
    assert 'id="lcolb" aria-controls="mycard" aria-expanded="true"' in PAGE and 'id="rcolb" aria-controls="drawer" aria-expanded="true"' in PAGE
    assert ":root{--lw:360px;--rw:380px}" in PAGE and "body.lcol{--lw:52px}body.rcol{--rw:52px}" in PAGE
    assert "body.lcol #mycard,body.rcol #drawer{display:none}" in PAGE
    # the map and everything placed beside the panels follow their widths — no width written out any more
    for rule in ("#stage{left:var(--lw)}", "#stage{right:var(--rw)}", "#sheet{left:calc(var(--lw) + 12px)", "#netbar{left:calc(var(--lw) + 16px);right:calc(var(--rw) + 16px)}",
                 "right:calc(var(--rw) + 16px);width:360px;bottom:16px", ".toast{left:calc(var(--lw) + 16px)}"):
        assert rule in PAGE, rule
    assert not re.search(r"left:37[26]px|right:396px|#stage\{left:360px\}|#stage\{right:380px\}", PAGE)


def test_the_strips_keep_the_status_the_count_and_the_tabs():
    assert 'id="lrdot"' in PAGE and 'id="lrn"' in PAGE
    assert "n=(MK||[]).filter(m=>!m.status&&!m.endedBy&&!m.stale).length" in PAGE and "d.className='rdot '+lv" in PAGE
    for tab in ("feedwrap", "alerts", "hist"):
        assert f'data-rt="{tab}"' in PAGE
    assert "showTab(x.dataset.rt); setCol('r',false);" in PAGE
    assert "localStorage.setItem(side+'col',on?'1':'0')" in PAGE                                # remembered on this device
    for k in ("pc_hide:", "pc_show:", "rl_tgts:", "rl_feed:", "rl_alerts:", "rl_stats:"):
        assert I18N.count(k) == 3, k


def test_the_full_screen_map_is_the_map_alone():
    assert "body.fullmap .rail,body.fullmap .pcol{display:none!important}body.fullmap #stage{left:0!important}" in PAGE


def test_the_docs_tell_it():
    assert "Side panels that fold (1.58.32" in DOC and "`--lw` / `--rw`" in DOC
