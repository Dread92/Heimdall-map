"""1.36: the Tactical page redesigned around the reader's own place. The card at the top is the first thing read on
a bad night, so these tests hold what it may say and where it sits; docs/SAFETY.md ("The card says what is known
about your place, and nothing more") says why."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE = _read("static/kyiv.html")
LIGHT = _read("static/light.html")
I18N = _read("static/i18n.js")
HEAD = PAGE[PAGE.index('<header id="top">'):PAGE.index("</header>")]
CARD_JS = PAGE[PAGE.index("// ---- 1.36: the card"):PAGE.index("// Kyiv city (31) and Kyiv oblast (14)")]


def _rule(sel):
    m = re.search(r"(?:^|[}\n])" + re.escape(sel) + r"\{([^}]*)\}", PAGE)
    assert m, sel
    return m.group(1)


def _panel(i):
    a = PAGE.index('<div class="panel" id="' + i + '"')
    return PAGE[a:PAGE.index("\n</div>", a)]


def _keys(lang_start, lang_end):
    return I18N[I18N.index(lang_start):I18N.index(lang_end) if lang_end else len(I18N)]


def test_the_card_is_in_the_header_and_never_over_the_map():
    assert '<section id="mycard"' in HEAD
    for part in ('id="slotrow"', 'id="kyiv"', 'id="tstrip"', 'id="mych"', 'id="brgbar"', 'id="mcfoot"', 'id="mcmini"'):
        assert part in HEAD, part
    phone = _rule("#mycard")
    assert "position" not in phone                                  # in the flow: syncTop() measures it
    assert "syncTop()" in CARD_JS
    # screen readers hear the official status change, not a clock ticking every second
    assert "aria-live" not in HEAD[:HEAD.index('id="slotrow"')]


def test_each_place_chip_carries_its_own_official_status_and_only_that():
    i = PAGE.index("function placeLevel(p){")
    body = PAGE[i:PAGE.index("\n}", i)]
    assert "S.active" in body and "raion_key===u.key" in body and "'hromada'" in body
    for k in ("'R'", "'Y'", "'H'", "'G'", "'U'"):
        assert k in body, k
    assert "MK" not in body and "proximity" not in body              # never from a channel's post
    assert "placeLevel(p).k" in PAGE                                 # the chips
    assert "placeStatus(" in LIGHT and "raionsOf(p)" in LIGHT        # the same on Light


def test_the_target_on_the_card_is_one_the_post_placed_and_no_time_is_promised():
    assert "live.find(r=>r.hi.inbound)||live.find(r=>r.d<=30)" in CARD_JS
    assert "Math.hypot(x-ref[0],y-ref[1])" in CARD_JS                 # a distance between two reported points
    for word in ("etaBand", "ETA", "speed", "t('eta"):
        assert word not in CARD_JS, word
    # nothing near: said, and said not to be safe
    assert "t('lt_none')" in CARD_JS and "t('lt_none_b')" in CARD_JS


def test_the_one_instruction_is_the_guides_own_and_links_to_it():
    assert "<a class=\"tsbtn\" href=\"/guide#w-ballistic\">" in PAGE
    assert "tt.ty==='ballistic_missiles'||tt.ty==='mig31k_departure'" in PAGE
    guide = _read("static/guide.html")
    assert "Не чекайте: одразу в найближче укриття" in guide          # what mc_go_now says, in the guide's words
    assert "mc_go_now:'Часу мало — в укриття зараз, не чекайте сирени.'" in I18N


def test_the_escalation_level_comes_from_facts_and_picks_the_tone():
    i = PAGE.index("function escLevel(rows){")
    body = PAGE[i:PAGE.index("return lv; }", i)]
    assert "placeLevel(HOME)" in body and "r.d<=30||r.hi.inbound" in body and "r.d<=10" in body
    assert "lvl==='at'" in body and "'mig31k_departure'" in body
    assert "const VIB_L={2:" in PAGE
    assert "now-TONE.t<10000&&level<=TONE.l" in PAGE                 # one tone in 10 s unless it rises
    for k in ("kind==='l1'", "kind==='l2'", "kind==='l3'", "kind==='l4'"):
        assert k in PAGE, k


def test_the_menu_is_split_by_where_each_control_is_looked_for():
    assert "const PANELS=['bell','menu','lay'];" in PAGE
    bell, more, lay = _panel("bell"), _panel("menu"), _panel("lay")
    for i in ("pushbtn", "geobtn", "brgbtn", "snd", "sndvol", "sndtest", "vib"):
        assert 'id="' + i + '"' in bell, i
    for i in ("homebtn", "oblbtn", "langsel", "mdstd", "mdday", "mdnight", "litebtn", "helpbtn", "supbtn", "aboutbtn", "buildtag"):
        assert 'id="' + i + '"' in more, i
    assert 'href="/guide" data-t="m_guide"' in more
    for i in ("layerbox", "zcity2", "est", "zobl", "zreg", "zua"):
        assert 'id="' + i + '"' in lay, i
    assert 'data-close="bell"' in bell and 'data-close="menu"' in more and 'data-close="lay"' in lay
    for b in ('id="bellbtn"', 'id="menubtn"'):
        assert b in HEAD, b
    assert 'id="laybtn"' in PAGE[PAGE.index('class="mapctl"'):]
    assert "const TABS=['near','feedwrap','alerts','hist'];" in PAGE  # the Map tab became the Layers panel


def test_targets_are_large_enough_for_a_thumb():
    assert "height:44px" in _rule(".slotrow button") and "width:44px;height:44px" in _rule(".hb")
    assert "width:44px;height:44px" in _rule(".mapctl button")
    assert "min-height:48px" in _rule(".panel .mi") and "width:44px;height:44px" in _rule(".px")
    assert "min-height:44px" in _rule(".tstrip .tsbtn") and "width:44px;height:44px" in _rule(".mcfold")
    assert "inset:-10px -2px" in _rule(".mcwhat::before")                # "What to do": 24 px of text, 44 px to hit
    assert "min-height:44px" in _rule("#top .vsw>*") and "min-height:44px" in _rule(".card .mo")
    assert "inset:-10px -4px" in PAGE                                 # the "unofficial" line's hit area
    assert "--ink2:#b5b3ab" in PAGE and "--ink3:#8f8d86" in PAGE


def test_the_new_words_never_call_anything_safe():
    for start, end, pat in (("\nen:{", "\nuk:{", r"\bsafe\b"), ("\nuk:{", "\nfr:{", r"безпечн"), ("\nfr:{", "\nconst ", r"\bsûr")):
        block = _keys(start, end)
        for key in re.findall(r"\b((?:mc|nr|bl|tab)_[a-z_0-9]+):'([^']*)'", block):
            for m in re.finditer(pat, key[1], re.I):
                around = key[1][max(0, m.start() - 30):m.end() + 30]
                assert re.search(r"not the same|не те саме|pas la même", around, re.I), key


def test_what_the_ticker_said_still_has_a_place():
    assert 'id="ticker"' not in PAGE and "tkr:" not in I18N
    assert 'data-t="mc_unoff"' in HEAD and "$('disc').hidden=false" in PAGE.replace("document.getElementById('disc')", "$('disc')")
    assert '<p class="fnote" data-t="fd_opsec">' in PAGE
    assert len(re.findall(r"\bfd_opsec:", I18N)) == 3


def test_the_opening_notice_is_unchanged_but_its_button_stays_in_reach():
    assert "sessionStorage.getItem('disc_seen')==='1'" in PAGE
    dok = _rule(".dok")
    assert "position:sticky" in dok and "bottom:" in dok


def test_the_card_asks_the_server_for_nothing():
    for call in ("fetch(", "jget(", "sendBeacon", "XMLHttpRequest", "/api/"):
        assert call not in CARD_JS, call


def test_the_reader_can_fold_the_card_and_it_opens_itself_when_something_matters():
    """1.37: on a phone the card took a third of the screen on a quiet night. It folds to one line that keeps the
    official status; it opens by itself when the level rises or a new warning appears, and folds back after."""
    assert 'id="mcfold"' in HEAD and ".mcfold{display:none}" in PAGE          # a phone thing; a computer has room
    assert "localStorage.getItem('card_fold')==='1'" in PAGE
    i = PAGE.index("function foldShut(){")
    body = PAGE[i:PAGE.index("\n", i)]
    assert "LEVEL<=FOLD.at" in body and "k===FOLD.key" in body
    assert "FOLD.at=Math.max(1,LEVEL||0)" in PAGE and "FOLD.key=warnKey()" in PAGE
    assert "window.innerWidth<1000&&(drawerState()!==''||foldShut())" in PAGE
    # the folded line: the official status and the place, or the live warning in its own colour
    assert "t('lt_'+dk)" in CARD_JS and "' w '+tw.className" in CARD_JS
    assert "!/\\b(calm|old)\\b/.test(ts.className)" in PAGE
