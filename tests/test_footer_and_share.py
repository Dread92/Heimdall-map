"""1.39: the owner's notice, one footer for every screen, a "Share the app" button, a header switch that is never
cut, and the app's own pictograms where the phone's emoji were."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE = _read("static/kyiv.html")
LIGHT = _read("static/light.html")
I18N = _read("static/i18n.js")
EMOJI = re.compile("[☀-➿⭐\U0001f000-\U0001faff]")


def _block(start, end):
    i = I18N.index(start)
    return I18N[i:I18N.index(end, i)]


EN, UK, FR = _block("\nen:{", "\nuk:{"), _block("\nuk:{", "\nfr:{"), _block("\nfr:{", "\nconst ")


def _val(block, key):
    m = re.search(r"\b" + key + r":'((?:[^'\\]|\\.)*)'", block)
    assert m, key
    return m.group(1)


def test_the_notice_has_the_owners_title_and_opening():
    for block, title in ((UK, "ВАЖЛИВА ІНФОРМАЦІЯ"), (EN, "IMPORTANT INFORMATION"), (FR, "INFORMATION IMPORTANTE")):
        assert _val(block, "d_title") == title
        assert _val(block, "d_p1").startswith("<b>HEIMDALL</b>")
    assert _val(UK, "d_p1").startswith("<b>HEIMDALL</b> — це <b>неофіційний волонтерський сервіс</b>")
    assert "Це НЕ дані безпосередньо з радарів." in _val(UK, "d_p1")
    notice = PAGE[PAGE.index('<div class="modal" id="disc"'):PAGE.index('<div id="discfoot"></div>')]
    assert 'class="type dtitle" data-t="d_title"' in notice and 'class="dlangrow"' in notice
    assert "sup_free" not in notice                                   # the footer says it, once
    assert ".mbox .type.dtitle{text-align:center" in PAGE


def test_one_footer_for_every_screen():
    assert I18N.count("function footerHTML(") == 1
    assert "function footerHTML(" not in PAGE and "function footerHTML(" not in LIGHT
    assert "const CONTACT=" in I18N and "const CONTACT=" not in PAGE
    i = PAGE.index("function paintFooters(){")
    body = PAGE[i:PAGE.index("\n}", i)]
    assert "footerHTML({support:true,build:MYBUILD})" in body and "'discfoot','panelfoot'" in body
    assert PAGE.count("${footerHTML(") == 1                         # the help sheet (1.58.52: the support sheet is the cards alone)
    assert "footerHTML({logos:false})" in LIGHT and 'id="hfoot"' in LIGHT
    # what it says, in order: free service + support, share, ©, built by · version · build, community on its own line
    f = I18N[I18N.index("function footerHTML("):I18N.index("function shareURL(")]
    order = [f.index(k) for k in ("hf-free", "hf-share", "hf-cr", "hf-ver", "hf-com")]
    assert order == sorted(order)
    assert "bf-logo.png" in f and "logo-64.png" in f and "credits_dev" in f and "sup_community" in f
    # the old sentence under Near is gone, in every language
    assert "вдячно прийнята" not in I18N
    assert _val(UK, "sup_free").startswith("Сервіс є повністю безоплатним.") and "07300" in _val(UK, "sup_free")


def test_share_the_app_sends_the_address_and_nothing_else():
    i = I18N.index("function shareURL(){")
    body = I18N[i:I18N.index("\nif(typeof document", i)]
    assert "navigator.share(" in body and "navigator.clipboard.writeText(url)" in body and "execCommand('copy')" in body
    assert "AbortError" in body                                       # cancelled by the reader: nothing copied
    for word in ("HOME", "SLOTS", "slots", "lat", "lon", "localStorage", "location.href", "location.search", "hash"):
        assert word not in body, word
    assert "+'/'" in body
    assert 'data-hf="share"' in PAGE[PAGE.index('<div class="panel" id="menu"'):]   # More → About
    assert "if(typeof document!=='undefined') document.addEventListener('click'" in I18N   # CI evaluates i18n.js in Node
    for block in (EN, UK, FR):
        assert _val(block, "share_app") and _val(block, "share_ok")
    assert _val(UK, "share_app") == "Поділитися застосунком"


def test_the_header_switch_scales_and_is_centred():
    m = re.search(r"#top \.vsw\{([^}]*)\}", PAGE)
    assert m and "flex:1 1 auto" in m.group(1) and "margin:0 auto" in m.group(1) and "min-width:0" in m.group(1)
    m = re.search(r"#top \.vsw>\*\{([^}]*)\}", PAGE)
    assert m and "clamp(" in m.group(1) and "flex:1 1 0" in m.group(1)
    assert "#top .sp{display:none}" in PAGE


def test_pictograms_not_emoji_in_stats_and_on_the_map():
    i = PAGE.index("const TYPES=[['drones'")
    types = PAGE[i:PAGE.index("];", i)]
    assert not EMOJI.search(types), EMOJI.findall(types)
    assert "gIco(g,c,x)" in PAGE and "const gIco=" in PAGE and "const thrIco=" in PAGE
    i = PAGE.index("const POIS=[")
    pois = PAGE[i:PAGE.index("];", i)]
    assert not EMOJI.search(pois), EMOJI.findall(pois)
    assert "const POI_G={air:" in PAGE and '<circle class="rr" r="10"/>' in PAGE     # 1.58.34: a pin is a reticle in ink
    assert 'id="impbtn"' not in PAGE           # 1.54: the explosions layer and its button are gone (the owner)


def test_the_stats_key_is_one_sample_per_line():
    assert "af_legend" not in I18N and "af_legend" not in PAGE
    assert '<div class="aflg">' in PAGE and ".aflg{display:grid;grid-template-columns:auto 1fr" in PAGE
    for block in (EN, UK, FR):
        for k in ("af_lg_l", "af_lg_d", "af_lg_u", "af_lg_p"):
            assert _val(block, k)


def test_the_card_column_never_squeezes_a_block():
    assert "#mycard>*{flex-shrink:0}" in PAGE


def test_the_bells_lines_in_the_owners_words_and_true_to_the_code():
    assert _val(UK, "bl_push_b") == "цілі у вашому радіусі, загроза балістики, зліт МіГ-31К"
    assert _val(UK, "geo_title") == "Сповіщення за геопозицією"
    assert _val(UK, "bl_geo_b") == "у вибраному радіусі навколо поточного місцезнаходження"
    assert _val(UK, "m_brg") == "Мости Києва (сповіщення та push)"
    assert _val(UK, "bl_vib_b") == "тривала — при балістиці та зльоті МіГ-31К"
    # the distances the server uses (BRIDGE_NEAR_KM, BRIDGE_NEAR_FAST_KM)
    src = _read("app/server.py")
    assert "BRIDGE_AT_KM, BRIDGE_NEAR_KM, BRIDGE_NEAR_FAST_KM = 1.2, 3.5, 6.0" in src
    assert "3,5 км" in _val(UK, "bl_brg_b") and "6 км" in _val(UK, "bl_brg_b")
    # tones follow the escalation level, not the weapon
    assert "рівня загрози" in _val(UK, "bl_snd_b")
