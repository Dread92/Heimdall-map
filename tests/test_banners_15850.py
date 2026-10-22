"""1.58.50 — closing a banner, at a glance. The owner, with an official alert, a ballistic warning in the card and the
map's banner on one screen: "when there are several banners, how to close them must be obvious at once, so nobody has to
look for it". And two faults found on the way: the folded line under a warning had no words, and in the day look the
official alert was white on white."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N = _read("static", "kyiv.html"), _read("static", "i18n.js")


def test_the_maps_banner_has_its_close_button():
    fn = PAGE[PAGE.index("function toastShow("):PAGE.index("function notify(")]
    assert '<button type="button" class="tx" aria-label="${esc(t(\'btn_close\'))}">✕</button>' in fn
    assert "el.onclick=()=>el.classList.remove('show');" in fn            # a tap anywhere still closes it
    assert "el._t=setTimeout(()=>el.classList.remove('show'),ms);" in fn  # and it still goes by itself
    # one way to show it: the alert, the quiet one, the shelter one
    assert "function notify(title,body,kind,vol,level){ toastShow(" in PAGE
    assert "function toastQuiet(title,body){ toastShow('var(--yellow)',title,body,12000); }" in PAGE
    assert "toastShow('#5aa9ff','🛡 '" in PAGE
    assert PAGE.count("$('toast')") == 1 and PAGE.count("el.innerHTML=`<b>${esc(title)}</b>") == 0
    assert ".toast .tx{position:absolute;top:6px;right:6px;width:40px;height:40px;" in PAGE
    assert "#toast{padding-right:54px}" in PAGE                                # the words keep clear of the ✕
    assert "width:40px;height:40px" in re.search(r"\.notice \.nx\{([^}]*)\}", PAGE).group(1)


def test_the_card_says_collapse_in_words():
    assert ('<button type="button" class="mcfold" id="mcfold" data-t-aria="mc_fold" aria-label="Fold the card">'
            '<span data-t="mc_fold_s">Collapse</span><svg') in PAGE
    for w in ("mc_fold_s:'Згорнути'", "mc_fold_s:'Collapse'", "mc_fold_s:'Réduire'"):
        assert w in I18N
    rule = re.search(r"(?:^|\n)\.mcfold\{([^}]*)\}", PAGE).group(1)
    assert "min-width:44px;height:44px" in rule and "color:var(--ink)" in rule and "border:1px solid var(--line2)" in rule


def test_the_folded_line_says_the_warning():
    strip = PAGE[PAGE.index("const lab=x=>(tsAge(x)>fresh(x)?"):PAGE.index("// Kept outside threatStrip")]
    assert "el.dataset.line=lab(tt);" in strip and "const lb=lab(x);" in strip
    assert "<b>${esc(tw.dataset.line||'')}</b>" in PAGE
    assert "tw?tw.className+(tw.dataset.line||''):''," in PAGE
    assert "tw.firstChild" not in PAGE                    # the strip begins with an icon: its first text is nothing


def test_the_official_alert_keeps_its_colour_in_daylight():
    assert "body.m-day .band{background:#fff}" in PAGE
    i = PAGE.index("body.m-day .band{background:#fff}")
    day = PAGE[i:i + 1200]
    assert ("body.m-day:not(.lite) .band.R,body.m-day:not(.lite) .band.A{background:#c62a22;border-left-color:#7a1611;"
            "color:#fff}") in day
    assert "body.m-day:not(.lite) .band.Y,body.m-day:not(.lite) .band.P{background:var(--ua-yellow);" in day
    assert "body.m-day .tabs em{color:#fff}" in day
