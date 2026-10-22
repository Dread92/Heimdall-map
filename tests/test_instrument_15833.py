"""1.58.33 — the "Instrument" direction: the UX audit of 16 Oct 2026, done.

The owner: "an advanced UX audit, and above all design alternatives so that it looks less like a default AI asset — the
buttons, the gradients, the pin management in particular" — then "we'll do everything the audit proposes, I approve",
and "the Banderol / Dan-T icon is really ugly, it needs reworking too". The audit's seven signs: one radius for everything,
the orange switch with its halo, every button at the same weight, tinted translucent fills, emoji as icons, a row of four
pins three of them empty, a stack of six map pebbles with the full-screen one in the alert's yellow.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, GLY, INDEX, DOC = (_read("static", "kyiv.html"), _read("static", "light.html"), _read("static", "i18n.js"),
                                      _read("static", "glyphs.js"), _read("static", "index.html"), _read("docs", "TECHNICAL.md"))
CSS = PAGE[PAGE.index("<style>"):PAGE.index("</style>")]


def _rule(sel, css=CSS):
    """The declarations of the first rule that is exactly `sel` (not a longer selector ending in it)."""
    m = re.search(r"(?<![\w.#:\- ])" + re.escape(sel) + r"\{([^}]*)\}", css)
    return m.group(1) if m else ""


# ---- 1. tokens: one radius, no halo, no tinted box ----------------------------------------------------------------------
def test_one_radius_token_and_no_pebbles():
    assert "--r:2px;--line2:#3a414c;" in PAGE
    for px in ("8px", "10px", "12px", "14px", "18px 18px 0 0", "22px", "999px"):
        assert f"border-radius:{px}" not in CSS, px
    assert "box-shadow:0 0 0 3px rgba(255,138,61" not in PAGE and "rgba(47,191,113,.14)" not in CSS
    assert "linear-gradient" not in CSS.replace("linear-gradient(90deg,transparent 0,rgba(255,138,61,.35) 50%,transparent 100%)", "")   # the ballistic sweep stays
    assert "linear-gradient" not in INDEX and "--radius:2px" in INDEX


# ---- 2. buttons: a hierarchy ----------------------------------------------------------------------------------------------
def test_the_buttons_have_a_hierarchy():
    assert "background:var(--ua-yellow);color:#0b0d11;font:800 15px/1 var(--cond)" in _rule(".b-p")
    assert "border:1px solid var(--line2);background:transparent" in _rule(".tgl,.b-s")
    assert "box-shadow:inset 3px 0 0 var(--ua-yellow)" in _rule(".tgl.on")
    assert "border:0;background:transparent;color:var(--ink2)" in _rule(".b-t")
    assert "border:1px solid #6a2a26;background:transparent" in _rule(".b-dgr")
    # the one yellow of a screen: the warning's button, "choose your place", the update, the pin's save
    assert "background:var(--ua-yellow);color:#0b0d11;font:800 15px var(--cond)" in _rule(".tstrip .tsbtn")
    assert "background:var(--ua-yellow);color:#0b0d11;border-radius:var(--r)" in _rule(".mych.set")
    assert "#mycard:has(.tsbtn) .mych.set{background:transparent" in CSS
    assert "#updGo,#pwaGo{background:var(--ua-yellow)" in CSS and 'class="b-p" id="homesave"' in PAGE
    assert '<button class="b-t" onclick="closeSheet()">' in PAGE
    assert "color:var(--ink);font:800 14px var(--cond)" in _rule(".mcwhat") and "#9cc0ff" not in _rule(".mcwhat")


# ---- 3. the switch and the map's controls --------------------------------------------------------------------------------
def test_the_switch_is_two_tabs_and_the_controls_one_bar():
    sw = _rule("#top .vsw")
    assert "border-bottom:1px solid var(--line)" in sw and "orange" not in sw and "box-shadow" not in sw
    assert "height:2px;background:var(--ua-yellow)" in _rule("#top .vsw::before")
    assert "#top .vsw a::after{content:' ›'}" not in PAGE
    assert '<small data-t="sw_light_b">' in PAGE and '<small data-t="sw_tac_b">' in PAGE
    assert ".sw{display:flex;position:relative;margin:0 14px 12px;border-bottom:1px solid var(--line)}" in LIGHT
    ctl = _rule(".mapctl")
    assert "gap:0;border:1px solid var(--line2);border-radius:var(--r)" in ctl and "overflow:hidden" in ctl
    assert "border:0;border-bottom:1px solid var(--line)" in _rule(".mapctl button") and ".mapctl button:last-child{border-bottom:0}" in CSS
    assert "box-shadow:inset 3px 0 0 var(--ua-yellow)" in _rule(".mapctl button.on")
    assert "#fsbtn{color:var(--ua-yellow)" not in CSS
    assert '<button id="zkyiv" type="button" data-t-title="t_center" data-t-aria="t_center" title="Centre on my place"><svg' in PAGE   # no ◎
    # the drawer's tabs and the layer boxes take the yellow too: one vocabulary for "chosen"
    assert "border-bottom-color:var(--ua-yellow)" in _rule(".tabs button.on") and "accent-color:var(--ua-yellow)" in _rule(".layermenu input")


# ---- 4. the band and the rows ---------------------------------------------------------------------------------------------
def test_the_band_is_a_flat_and_the_green_a_rule():
    band = _rule(".band")
    assert "border-radius:0;background:var(--panel);border:0;border-left:4px solid var(--green)" in band
    assert ".band.R,.band.A{background:#c62a22;border-left-color:#7a1611;color:#fff}" in CSS
    assert ".band.Y,.band.P{background:var(--ua-yellow);border-left-color:#b89400;color:#0b0d11}" in CSS
    assert "font:800 19px/1.05 var(--cond)" in _rule(".band .big") and "tabular-nums" in _rule(".band .dur")
    assert ".band.N .big{color:var(--green)}" in CSS
    assert "border-left:4px solid var(--ink3);background:var(--panel)" in _rule(".status", LIGHT)
    assert ".status.R{background:#c62a22;border-left-color:#7a1611;color:#fff}" in LIGHT and ".status.G{border-left-color:var(--grn)}" in LIGHT


def test_the_rows_are_a_list():
    row = _rule(".mych")
    assert "border-radius:0;background:transparent;border-top:1px solid var(--line);border-bottom:1px solid var(--line);box-shadow:inset 3px 0 0 var(--orange)" in row
    assert ".mych.near{box-shadow:inset 3px 0 0 var(--red2)}" in CSS and "rgba(224,52,44,.14)" not in CSS
    assert "font:800 24px/1 var(--cond);font-variant-numeric:tabular-nums" in _rule(".mych .km")


# ---- 5. the pins -------------------------------------------------------------------------------------------------------------
def test_the_row_shows_the_pins_that_exist_and_a_plus():
    body = PAGE[PAGE.index("function paintSlots"):PAGE.index("// a tap on another pin")]
    assert "SLOT_IDS.filter(id=>SLOTS[id])" in body and 'class="add" data-add="${free}"' in body and " empty" not in body
    assert "if(id===ACTIVE) openPinSheet(id,'edit'); else useSlot(id);" in PAGE                 # no long press
    assert "setTimeout(()=>setFor(" not in PAGE and "SLOT_PICKING" not in PAGE
    assert "border-bottom-color:var(--ua-yellow)" in _rule(".slotrow button.on")
    # Light: the same row
    assert 'class="add" data-s="${free}"' in LIGHT and "hold=setTimeout" not in LIGHT


def test_the_sheet_asks_where_then_a_name():
    for i in ("hs-where", "hs-find", "hs-name", "homemap", "homegeo", "homefind", "homefreq", "hspn", "hschg", "homesug", "homesave", "homecancel", "homeclear", "homeconf", "homedel", "homedelno"):
        assert f'id="{i}"' in PAGE, i
    assert "const HS_FREQ=['Оболонь','Троєщина','Позняки','Бровари','Буча','Бориспіль'];" in PAGE
    assert "const rows=s?PLACES_ALL.filter(" in PAGE                                           # the list once something is typed
    assert "const r=s?(PLACES||[]).filter(" in LIGHT
    assert "setSlotName(slot,$('homen').value); setSlot(slot,p);" in PAGE                         # nothing kept before "save"
    assert "$('homeclear').onclick=()=>{ $('homeconf').hidden=false; };" in PAGE                 # an inline confirmation, no confirm()
    assert "confirm(" not in PAGE[PAGE.index("$('homedel').onclick"):PAGE.index("$('homedel').onclick") + 400]
    assert "if(PIN_NAME){ PIN_NAME=false; setTimeout(()=>openPinSheet(id,'edit'),250); }" in PAGE
    assert "navigator.geolocation.getCurrentPosition(pos=>{ b.classList.remove('busy');" in PAGE
    for k in ("sl_new:", "sl_add:", "sl_c_map:", "sl_c_find:", "sl_freq:", "sl_save:", "sl_delete_q:", "sl_delete_yes:", "sl_s_home:", "sl_local_1:"):
        assert I18N.count(k) == 3, k


def test_a_pin_is_a_reticle_in_ink():
    body = PAGE[PAGE.index("function drawHome"):PAGE.index("$('homeg').addEventListener")]
    assert '<circle class="rr" r="10"/><circle class="rc" r="2.8"/>' in body and 'class="hd ${k}"' in body
    assert "SLOT_IDS.filter(id=>SLOTS[id]&&id!==ACTIVE).map(id=>one(id,SLOTS[id],false)).join('')+one(ACTIVE,HOME,true)" in body
    assert "POI_G.pin" not in body and ".homemk .ico{fill:#ffd9a8}" not in CSS
    assert ".homemk:not(.on) .rr,.homemk:not(.on) .rt{stroke:#8f8d86" in CSS


# ---- 6. icons and the Banderol ------------------------------------------------------------------------------------------------
def test_the_chrome_has_no_colour_emoji_and_the_banderol_is_an_airframe():
    emo = re.compile("[\U0001F300-\U0001FAFF\U0001F514]")
    for k in ("sup_link", "n_home", "sl_pin_set", "ts_bal", "ts_cruise", "ts_mig", "mk_fire", "lb_damage", "lt_locate", "al_none", "d_p2", "d_p3"):
        for m in re.finditer(k + r":'((?:[^'\\]|\\.)*)'", I18N):
            assert not emo.search(m.group(1)), (k, m.group(1)[:40])
    assert "${thrIco(x.ty,'currentColor')}${esc(lb)}" in PAGE and "${m3Ico(cur,28)||thrIco(cur.type)}${cur.type==='drones'" in PAGE   # 1.58.45: the 3D model first
    b = re.search(r"\bbanderol:'(.*?)',?\n", GLY).group(1)
    assert b.count('<path class="glyph"') == 5 and b.count('<rect class="glyph"') == 1 and 'class="jetfx"' in b
    assert 'x="-9.8" y="-1.4" width="19.6"' not in GLY                                           # the cross of two bars
    assert ".mk.jet .jetfx,.mk.banderol_missiles .jetfx{display:block}" in CSS


def test_the_docs_tell_it():
    for s in ("1.58.33", "Instrument", "--r", ".b-p", "openPinSheet", "pinLabel", "reticle"):
        assert s in DOC, s
