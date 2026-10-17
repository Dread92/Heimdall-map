"""The small things a live night found (1.19): each of these was reported from a phone."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()


def _rule(src, sel):
    m = re.search(re.escape(sel) + r"\{([^}]*)\}", src)
    assert m, sel
    return m.group(1)


def test_the_zone_label_is_sized_in_screen_pixels():
    """"10 km" was 2.2 km tall: zoomed in, it filled the screen."""
    r = _rule(PAGE, ".zlbl")
    assert "var(--k" in r and "2.2px" not in r


def test_the_tile_credit_sits_in_a_bottom_corner():
    r = _rule(PAGE, ".attrib")
    assert "bottom:" in r and "top:" not in r


def test_the_crimea_cossack_is_drawn_above_the_raion_outlines_in_one_path_per_colour():
    body = PAGE[PAGE.index("function cossack(){"):PAGE.index("// ---- the background under the map")]
    assert "<rect x=\"${x-6}\"" not in body                     # no longer 200 separate squares
    i = PAGE.index("$('obllbl').innerHTML=")
    assert "cossack()" in PAGE[i:PAGE.index("\n", PAGE.index("\n", i) + 1)]
    assert "cossack()" not in PAGE[PAGE.index("$('oblastsg').innerHTML="):i]


def test_press_and_hold_survives_a_trembling_finger():
    """The drag test was 0.2 km — less than a pixel at oblast zoom — so the hold was always cancelled."""
    assert "HOLD_SLOP_PX" in PAGE and "Math.abs(dx)+Math.abs(dy)>0.2" not in PAGE
    assert "addEventListener('contextmenu',e=>e.preventDefault())" in PAGE
    assert "-webkit-touch-callout:none" in _rule(PAGE, ".mapwrap")


def test_the_empty_pin_chip_arms_the_map_instead_of_only_explaining():
    # 1.54.9: every pin opens its sheet; "on the map" there arms the map for that pin
    assert "if(a){ openPinSheet(a.dataset.add,'new'); return; }" in PAGE                 # 1.58.34: "+" opens the sheet
    assert "$('homemap').onclick=()=>{ const id=HS_PEND?HS_PEND.slot:ACTIVE; $('homesheet').classList.remove('show'); PIN_NAME=true; armPin(true,id); };" in PAGE   # 1.58.34
    assert "if(PIN_ARM&&tap){ dropPin(" in PAGE
    assert I18N.count("sl_pin_arm:") == 3 and I18N.count("sl_pin_cancel:") == 3


def test_the_language_is_a_drop_down_on_both_pages():
    assert 'id="langsel"' in PAGE and 'id="langsel"' in LIGHT
    assert "<select" in PAGE[PAGE.index('id="disc"'):PAGE.index('id="discok"')]
    assert "function langSelect(" in I18N and "function pickLang(" in I18N


def test_changing_the_language_in_the_notice_shows_the_notice_again():
    """Tapping a language in the opening notice reloaded the page — and the notice, already marked as seen,
    did not come back: it closed before anyone had read it."""
    body = I18N[I18N.index("function pickLang("):I18N.index("function langSelect(")]
    assert "removeItem('disc_seen')" in body
    assert "langSelect(document.getElementById('dlang'),true)" in PAGE
    assert "langSelect($('dmlang'),true)" in LIGHT


def test_i_understand_is_big_and_centred():
    for src, sel in ((PAGE, ".dok"), (LIGHT, "#dm #dmok")):
        r = _rule(src, sel)
        assert "width:100%" in r and "margin:18px auto" in r


def test_light_zooms_the_map_not_the_page():
    r = _rule(LIGHT, "#radar")
    assert "touch-action:pan-y" in r and "user-select:none" in r      # a tap no longer selects a place name
    assert "touch-action:none" in _rule(LIGHT, "#radar.zoomed")
    assert "function zoomAt(" in LIGHT and "gesturestart" in LIGHT and "e.preventDefault(); const [a,b]=e.touches" in LIGHT


def test_light_opens_a_mark_on_a_tap():
    assert "function tapAt(" in LIGHT and "RT.push({id:m.id,x,y})" in LIGHT
    assert 'id="rcard"' in LIGHT and "row(selR,true)" in LIGHT


def test_the_new_logo_is_the_app_icon_and_the_partner_logos_stay():
    """1.29: Heimdall's radar is the app icon everywhere; 07300 and Black Flame stay (the old name: test_old_name_15824)."""
    for man in ("manifest.json", "light.webmanifest"):
        m = json.load(open(os.path.join(ROOT, "static", man), encoding="utf-8"))
        assert m["short_name"].startswith("Heimdall")
        for ic in m["icons"]:
            assert ic["src"].startswith("/static/heimdall-"), ic
            assert os.path.isfile(os.path.join(ROOT, ic["src"].lstrip("/")))
        assert any(ic["purpose"] == "maskable" for ic in m["icons"])
    # the installed Tactical app keeps its identity: an update of the same app, not a second one beside it
    assert json.load(open(os.path.join(ROOT, "static", "manifest.json"), encoding="utf-8"))["id"] == "/m"
    for page in (PAGE, LIGHT):
        assert 'rel="apple-touch-icon" href="/static/heimdall-apple-180.png"' in page     # an iPhone's home screen
    assert 'src="/static/logo-64.png" alt="07300"' in PAGE          # NGO 07300 stays in the header
    assert "/static/bf-logo.png" in I18N and "footerHTML(" in PAGE  # Black Flame stays in the credits (1.39: the shared footer)
    assert '"heimdall-64.png"' in SRC                                 # the favicon


def test_mark_labels_are_spaced_from_what_is_drawn_not_from_a_copy_of_the_css():
    """25 Sep 2026: "⚠ likely a drone" and "↓ DESCENDING · updated 21:46" written over each other. The spacing
    code had its own copy of the rules saying which label lines show, and that copy did not know "descending"."""
    i = PAGE.index("  // Label de-collision (screen px).")
    body = PAGE[i:PAGE.index("  // edge indicators", i)]
    assert "getComputedStyle(el).display" in body
    assert "classList.contains('inbound')?true" not in body          # the hand-kept copy is gone
    assert "glyphs.filter(" in body and "out(r)" in body             # clear of other marks and of the map's edge
    assert "'nolbl2'" in body and "'nolbl'" in body                  # a label that fits nowhere is shortened, then left out
    assert ".mk.nolbl .lbl,.mk.nolbl .lbl2,.mk.nolbl2 .lbl2{display:none!important}" in PAGE


def test_a_town_name_under_a_threat_label_is_hidden():
    i = PAGE.index("function layoutTownLabels(){")
    assert "const placed=[...LBLBOX.boxes]" in PAGE[i:i + 1500]


def test_no_map_text_has_a_halo_measured_in_kilometres():
    """27 Sep 2026: in daylight mode the white halo of the town names was 2.4px — 2.4 km in the map's units —
    and zoomed in on Kyiv every name became a white cloud over the map. Every stroke on map text is in screen
    pixels (--k)."""
    text = ("town", "roadlbl", "rvlbl", "zlbl", "kdist", "rnlbl", "oblbl", "nblbl", "ringlbl", "poilbl", "lbl", "lbl2",
            "etxt", "obtxt", "hl", "qm", "dn", "it", "kozak")
    bad = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", PAGE[:PAGE.index("</style>")]):
        classes = set(re.findall(r"\.([a-z0-9]+)\b", sel))
        m = re.search(r"stroke-width:\s*([^;}]+)", body)
        if m and classes & set(text) and "var(--k" not in m.group(1) and m.group(1).strip() not in ("0", "0px"):
            bad.append(f"{sel.strip()[:80]} -> {m.group(1)}")
    assert not bad, bad


def test_the_disclaimer_button_is_reachable_on_an_iphone():
    """1.27: on an iPhone 14 in Safari "I understand" sprang back under the bottom bar. The box was sized with vh,
    which Safari measures with its bars hidden; the overlay now scrolls and is sized by inset:0 only."""
    for src, overlay, box in ((PAGE, ".modal", ".mbox"), (LIGHT, "#dm", "#dm .dbox")):
        o, b = _rule(src, overlay), _rule(src, box)
        assert "inset:0" in o and "overflow-y:auto" in o and "align-items:center" not in o, overlay
        assert "vh" not in b and "margin:auto" in b, box
        a = _rule(src, overlay + "::after")
        assert "safe-area-inset-bottom" in a or "--sab" in a, overlay


def test_the_sound_has_a_volume_that_an_iphone_obeys():
    """1.28: on an iPhone the tones blasted at the phone's media volume. The level is a Web Audio gain (iOS ignores
    an <audio> element's volume), every tone goes through it, and the slider is in the menu in every language."""
    assert re.search(r'<input type="range" id="sndvol" min="0" max="100"', PAGE)
    assert "g.connect(master)" in PAGE and "g.connect(actx.destination)" not in PAGE
    assert "master.connect(actx.destination)" in PAGE and "master.gain.value=volGain()" in PAGE
    assert "localStorage.setItem('sndvol'" in PAGE and "let sndVol=50" in PAGE
    assert ".volume" not in PAGE  # no <audio>.volume: it does nothing on an iPhone
    for k in ("m_vol", "m_vol_test", "m_vol_test_t", "m_vol_off"):
        assert I18N.count(k + ":") == 3, k


def test_a_move_to_a_new_address_carries_settings_but_never_a_watched_place():
    """1.29: CANONICAL_HOST shows the move banner; the link carries settings in its #fragment, and neither the
    sender nor the receiver lets a watched place through (they never leave the phone)."""
    for page in (PAGE, LIGHT):
        carry_in = page[page.index('<script id="carry">'):page.index("</script>", page.index('<script id="carry">'))]
        assert page.index('<script id="carry">') < page.index('<script src="/static/i18n.js">')   # before anything reads
        send = page[page.index("const CARRY=["):page.index("];", page.index("const CARRY=["))]
        for place_key in ("'slots'", "'slot_active'", "'home'", "'geo'"):
            assert place_key not in carry_in and place_key not in send, place_key
        assert "function shape(k,v)" in carry_in and "history.replaceState" in carry_in   # 1.58.35: shaped, not listed
        assert "location.host===c" in page
    assert 'os.environ.get("CANONICAL_HOST")' in SRC and '"canonical": canonical_host(self.cfg)' in SRC


def test_the_team_message_is_escaped_and_admin_only():
    for page in (PAGE, LIGHT):
        assert "el.querySelector('.ntx').textContent=tx" in page       # text, never HTML
    i = SRC.index('if u.path == "/api/admin/notice":')
    assert "if not self._admin_ok(q):" in SRC[i:i + 300]
    i = SRC.index('if u.path == "/api/online":')
    assert "if not self._admin_ok(q):" in SRC[i:i + 400]

