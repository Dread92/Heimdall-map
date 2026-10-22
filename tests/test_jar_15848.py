"""1.58.48 — the jar says what it is for. The owner: "make it more obvious that the jar of coins is for supporting the app".
Its word under it in the reader's language, a heart on the jar, and once, on a first visit, a line pointing at it — never
during an alert, in the blackout look, or for a reader who asked not to be reminded."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, M3D = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "models3d.js")


def test_its_word_and_its_heart():
    assert '<span class="jarcap" data-t="jar_cap" aria-hidden="true">Support</span></button>' in PAGE
    assert ".jarbtn{width:72px;height:68px;flex-direction:column;" in PAGE
    for k in ("jar_cap", "jar_hint"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k
    assert "jar_cap:'Підтримати'" in I18N and "jar_cap:'Support'" in I18N and "jar_cap:'Soutenir'" in I18N
    jar = M3D[M3D.index("\n  jar() {"):M3D.index("g.userData.anim = f =>")]
    assert "heart.bezierCurveTo(" in jar and "color: '#e8333a'" in jar          # a red heart on the band


def test_the_line_pointing_at_it_once():
    assert '<div class="jarhint" id="jarhint" hidden role="note"><span data-t="jar_hint">' in PAGE
    hint = PAGE[PAGE.index("// 1.58.48: once, on a first visit"):PAGE.index("// 1.58.47: the 3D jar's strip")]
    assert "if(ls('jar_hint')==='1'||ls('sup_never')==='1'||document.body.classList.contains('lite')) return;" in hint
    assert "if(S&&S.active&&S.active.length) return;" in hint                  # never while an alert is on
    assert "ls('jar_hint','1'); h.hidden=false;" in hint and "setTimeout(off,8000); },20000);" in hint
    assert "body.lite .jarhint{display:none}" in PAGE
