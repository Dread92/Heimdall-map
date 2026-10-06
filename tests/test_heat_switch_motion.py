"""1.40: the heat map's colour is the number of reports (yellow → red), Light ⇄ Tactical is a toggle rather than a
reload, and the menus move — briefly, and never in blackout mode or with "reduce motion"."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE = _read("static/kyiv.html")
LIGHT = _read("static/light.html")
GUIDE = _read("static/guide.html")
I18N = _read("static/i18n.js")
SRC = _read("app/server.py")
SAFETY = _read("docs/SAFETY.md")


def _ramp(name):
    m = re.search(r"const " + name + r"=\[(.*?)\];", PAGE)
    assert m, name
    return [tuple(map(int, t)) for t in re.findall(r"\[(\d+),(\d+),(\d+)\]", m.group(1))]


def test_the_heat_ramp_runs_from_yellow_to_red():
    for name in ("HEAT_DARK", "HEAT_DAY"):
        r = _ramp(name)
        (r0, g0, b0), (r1, g1, b1) = r[0], r[-1]
        assert r0 > 200 and g0 > 180 and b0 < 160, name                 # yellow: red and green high, little blue
        assert r1 > 150 and g1 < 40 and b1 < 60, name                   # red: little green, little blue
        assert all(r[i][1] >= r[i + 1][1] for i in range(len(r) - 1)), name   # green only falls: yellow → orange → red
    assert "drawn as a violet" not in _read("docs/TECHNICAL.md") and "red for the most" in _read("docs/TECHNICAL.md")


def test_the_colour_is_the_number_of_reports_on_a_scale_that_never_shrinks_below_the_busiest_place():
    i = PAGE.index("function heatGrid(")
    body = PAGE[i:PAGE.index("return {GW,GH,I,C,mx}; }", i)]
    assert "I[j]+=p.n*k" in body                                        # each place adds its own count
    assert "const top=Math.max(1,...(v.points||[]).map(p=>p[2]||0)), G=heatGrid(pts,W,H,rad,q), scale=Math.max(top,G.mx);" in PAGE
    assert "Math.sqrt(G.I[j]/scale)" in PAGE
    assert "<span>${Math.round(scale)}+</span>" in PAGE                  # the legend says what red means


def test_while_the_heat_map_is_on_the_alerts_are_outlined_and_the_legend_says_so():
    assert "svg:not(.no-heat) :is(.nb,.rn,.kd):is(.R,.oR){fill-opacity:.3!important;stroke:" in PAGE
    assert "svg:not(.no-heat) :is(.nb,.rn,.kd):is(.Y,.oY,.P){fill-opacity:.3!important;stroke:" in PAGE
    assert 'data-t="hm_alerts"' in PAGE and len(re.findall(r"\bhm_alerts:'", I18N)) == 3
    for word in ("not alerts", "не тривоги", "ni des alertes"):
        assert word in I18N, word
    assert "not live, not alerts" in SAFETY and "never a filled raion" in SAFETY
    assert "LAYERS.heat=false;" in PAGE                                  # still off at every opening


def test_the_switch_slides_then_opens_the_other_version():
    assert '<a href="/light" data-sw data-t="sw_light">' in PAGE and '<a href="/m" data-sw>' in LIGHT
    assert "#top .vsw.go::before{transform:translateX(-100%)}" in PAGE and ".sw.go::before{transform:translateX(100%)}" in LIGHT
    i = I18N.index("function swGo(a)")
    body = I18N[i:I18N.index("function whenShown", i)]
    assert "location.assign(a.href)" in body and "prefers-reduced-motion: reduce" in body
    assert "if(typeof document!=='undefined'){" in body                 # CI evaluates i18n.js in Node
    assert "window.addEventListener('pageshow'" in body                  # back to a page kept in memory


def test_the_pages_fade_into_each_other_and_the_other_one_is_ready():
    for page in (PAGE, LIGHT, GUIDE):
        assert "@view-transition{navigation:auto}" in page
    assert '{"prerender":[{"where":{"href_matches":"/light"},"eagerness":"moderate"}]}' in PAGE
    assert '{"prerender":[{"where":{"href_matches":"/m"},"eagerness":"conservative"}]}' in LIGHT   # 2G: only on the press


def test_a_page_loaded_ahead_is_not_a_visit_until_it_is_shown():
    assert "document.prerendering" in I18N and "'prerenderingchange'" in I18N
    assert "whenShown(connect);" in PAGE and "whenShown(schedulePulse);" in PAGE
    assert "whenShown(connectLive)" in LIGHT
    assert 'ahead = "prefetch" in (self.headers.get("Sec-Purpose")' in SRC
    assert SRC.count("if usage and not ahead:") == 2                     # neither /m nor /light counts it


def test_motion_is_short_and_never_in_blackout_or_with_reduce_motion():
    assert "const CALM=()=>document.body.classList.contains('lite')||" in PAGE
    i = PAGE.index("function hidePanel(p){")
    assert "if(CALM()){ p.hidden=true; return; }" in PAGE[i:i + 200]
    assert "@media (prefers-reduced-motion:reduce){.panel,.panel>*,.sec,.tabs.ind::after,#top .vsw::before{animation:none!important;transition:none!important}}" in PAGE
    assert "body.lite .panel,body.lite .panel>*,body.lite .sec,body.lite .tabs.ind::after{animation:none!important;transition:none!important}" in PAGE
    for d in re.findall(r"\.panel:not\(\[hidden\]\)\{animation:pin \.(\d+)s", PAGE):
        assert int(d) <= 30                                              # under a third of a second
    assert "function tabInd()" in PAGE and "tabInd(); }" in PAGE
