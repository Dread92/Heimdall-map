"""1.57.4: a way back from everything — the owner: "there is currently no way to quit this popup", "in the what to do
section we need a back button", "overall we need clear return-to-home buttons, simple and accessible"."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, GUIDE, MOD = _read("static/kyiv.html"), _read("static/guide.html"), _read("static/shelters.js")
X = '<button type="button" class="shx" data-t-aria="btn_close" aria-label="Close">✕</button>'


def test_every_sheet_has_its_close_button_in_view():
    for sid in ("sheet", "homesheet"):
        assert f'id="{sid}"><div class="grab"></div>{X}' in PAGE, sid
    assert ".sheet .shx{position:sticky;top:0;float:right;z-index:3;width:44px;height:44px;" in PAGE
    assert PAGE.count("+SH_CLOSE()") == 2                                        # the shelter sheets end with Close too


def test_the_phone_s_back_button_closes_what_is_open():
    assert "history.pushState({hdo:1},'')" in PAGE and "window.addEventListener('popstate',()=>{ if(!BACK_ON) return;" in PAGE
    assert "function closeAll(){ closeSheet(); $('homesheet').classList.remove('show'); closePanels(); }" in PAGE
    assert "document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeAll(); });" in PAGE


def test_light_s_shelter_list_has_its_close():
    assert '`<button type="button" class="shx" aria-label="${esc(L(lang).close)}">✕</button>`+SH.listHTML' in MOD
    assert MOD.count("close:'") == 3


def test_the_guide_has_a_back_button_in_every_language():
    assert '<a class="back" id="back" href="/m">← <span id="backt">Back</span></a>' in GUIDE
    gd = json.loads(re.search(r'<script type="application/json" id="gd">(.*?)</script>', GUIDE, re.S).group(1))
    assert [gd[lang]["back"] for lang in ("uk", "en", "fr")] == ["Назад", "Back", "Retour"]
    assert "header{display:flex;align-items:center;gap:8px;padding:12px 0 6px;position:sticky;top:0;" in GUIDE
    assert "b.href='/light'" in GUIDE and "history.back();" in GUIDE
