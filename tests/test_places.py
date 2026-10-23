"""The four places somebody watches, and the promise that they stay on the phone.

One of the four is a school. A row in a database saying "this person's child is at these coordinates on
weekday mornings" is not a thing this app gets to create, whatever it would buy — and the way that row gets
created is never a decision, it is a `name` field quietly riding along in a request body that somebody added
for debugging. So the test is not "does the server store it": it is "does it ever leave the phone at all".

The rest is the filtering around that place. Two rules run through all of it: a course the app inferred is
never treated as a course the source reported, and "we do not know" is never rendered as "not coming".
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _values(key, src):
    """Every translation of one key. Written to survive escaped apostrophes — "s\'il garde le cap" is the
    French for the most safety-critical caveat in the app, and a naive quote regex truncates it to "s\\"."""
    out = []
    for m in re.finditer(rf"\b{key}:'((?:[^'\\]|\\.)*)'", src):
        # unescape the JS quote escapes, or "n\'est pas" never matches "n'est pas"
        out.append(m.group(1).replace("\\'", "'").replace('\\"', '"'))
    return out
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def _fn(name, page=None):
    src = page or PAGE
    i = src.index(f"function {name}(")
    return src[i:src.index("\n}", i)]


# ── the promise ────────────────────────────────────────────────────────────────────────────────────────
def test_the_four_places_are_written_only_to_this_browser():
    body = _fn("saveSlots")
    assert "localStorage.setItem('slots'" in body
    assert "fetch(" not in body and "XMLHttpRequest" not in body


def test_no_place_name_is_ever_put_in_the_push_request():
    """It used to send the name of the watched place. The server threw it away, but the request could still
    say "School 217" — and a request that can say it is one configuration change from a request that keeps
    it. Only the browser's own coarse geolocation goes now."""
    body = _fn("pushSync")
    assert "name:" not in body, "a place name is back in the push payload"
    assert "homeRaion()" not in body, "the raion is back in the push payload"
    assert "home:cellOf(GEO)" in body.replace(" ", "")      # 1.58.35: and only the ~10 km cell of it


def test_the_slots_are_never_read_into_anything_that_leaves_the_page():
    """A direct check that no network call anywhere on the page references the slot store."""
    for m in re.finditer(r"fetch\([^)]*\)", PAGE):
        assert "SLOTS" not in m.group(0), f"a slot reached a fetch call: {m.group(0)[:90]}"
    assert "SLOTS" not in SRV, "the server has gained a concept of the user's named places"


def test_the_server_still_has_exactly_one_door_for_writing_a_home():
    writes = re.findall(r"(?:INSERT|REPLACE)[^\"']*push_subs", SRV)
    assert len(writes) == 1


def test_the_school_is_not_left_sitting_on_the_screen():
    """The chips show the pin, not the place. Somebody standing behind you on the metro reads "Pin 3" — or the name
    the owner chose (1.54.9) — not the name of the school."""
    body = _fn("paintSlots")
    assert '<span class="sl">${esc(nm)}</span>' in body and "p.dropped||p.street||!(p.name||p.uk)?t('sl_n'" in PAGE, "the chip prints an address"   # 1.58.34: a town, never a street


# ── switching and dropping ─────────────────────────────────────────────────────────────────────────────
def test_switching_place_does_not_replay_old_alerts():
    """Alerts already raised for the old place would fire again against the new one the moment it changes."""
    body = _fn("useSlot")
    assert "homeAlerted.clear()" in body


def test_a_dropped_pin_carries_no_frozen_name():
    """Stored with t('...') baked in, its label stayed in whichever language was active when it was dropped."""
    # 1.56: a pin moved along the street it was put on keeps the street's name (`keep`, a proper name in Ukrainian and
    # its transliteration — no t()); one dropped anywhere else has none
    i = PAGE.index("setSlot(id,keep?")
    line = PAGE[i:PAGE.index("\n", i)]
    assert "name:" not in line and line.endswith(":{lon,lat,dropped:true});")
    assert "PIN_KEEP={name:p.name,uk:p.uk,obl:p.obl};" in PAGE and "t(" not in PAGE[PAGE.index("PIN_KEEP={"):PAGE.index("PIN_KEEP={") + 60]


def test_a_dropped_pin_can_never_be_named_by_a_post():
    """homeNamed() matches a post's place against the watched place's name. A pin has none, so it can never
    match — which is correct: a point on a map is not somewhere a channel can name."""
    body = _fn("homeNamed")
    assert "HOME.name" in body and "HOME.uk" in body
    assert "filter(Boolean)" in body, "an undefined name would join the match set and match loosely"


# ── the zones ──────────────────────────────────────────────────────────────────────────────────────────
def test_the_three_zones_are_the_ones_that_were_asked_for():
    m = re.search(r"const ZONES=\[(.*?)\];", PAGE)
    assert m
    # 1.58.56: the first is the reader's near zone — 10, 15 or 20 km (a reader: "15 km minimum, eventually 20"), 15 unless chosen
    assert m.group(1) == "[NEAR_R,'near'],[30,'approach'],[60,'observe']"
    assert "const NEAR_RS=[10,15,20]; let NEAR_R=15;" in PAGE


def test_the_eta_is_a_band_and_never_a_number():
    body = _fn("etaBand")
    assert "lo:" in body and "hi:" in body
    assert "eta_band" in PAGE
    for lang_count in [I18N.count("eta_band:"), I18N.count("eta_if:")]:
        assert lang_count == 3


def test_the_eta_states_its_own_condition_in_every_language():
    """A number with the condition dropped is a promise. Each translation has to carry "if it holds course"."""
    vals = _values("eta_if", I18N)
    assert len(vals) == 3
    for v in vals:
        assert len(v) > 20, f"the ETA condition was shortened away: {v!r}"


def test_no_eta_without_a_course_the_post_actually_reported():
    body = _fn("etaBand")
    assert "m.heading==null" in body.replace(" ", "")
    assert "confidence==='none'" in body.replace(" ", ""), (
        "an ETA can be built on a heading the app inferred rather than one the post gave")


def test_no_eta_for_the_weapons_that_outrun_a_filter():
    """Their whole point is that there is no time to plan around. A countdown for one is a cruelty."""
    body = _fn("etaBand")
    assert "IMMEDIATE.has(m.type)" in body


def test_the_eta_is_not_offered_for_a_target_flying_elsewhere():
    body = _fn("etaBand")
    assert re.search(r"off\s*>\s*\d+", body), "there is no bearing test at all"


# ── focus (removed 2026-09-24) ─────────────────────────────────────────────────────────────────────────
def test_the_towards_me_toggle_is_gone_and_nothing_is_dimmed_by_course():
    """Removed on request. What must not survive it is a half-removed filter still dimming targets."""
    assert "focusbtn" not in PAGE and "towardsMe" not in PAGE and "FOCUS" not in PAGE
    assert ".mk.defocus" not in PAGE and "'defocus'" not in PAGE


# ── contact lost ───────────────────────────────────────────────────────────────────────────────────────
def test_contact_lost_says_what_it_means_and_what_it_does_not():
    """A mark that just vanishes reads as "shot down", and people conclude the sky is clear."""
    vals = _values("lost_b", I18N)
    assert len(vals) == 3
    for v in vals:
        assert "NOT" in v or "НЕ " in v or "PAS" in v, f"the wording does not rule out 'shot down': {v!r}"
    assert I18N.count("lost_t:") == 3 and I18N.count("lost_b:") == 3


def test_a_confirmed_outcome_is_not_contact_lost():
    """Shot down is a known ending. Calling it "contact lost" would throw away the one certain thing."""
    body = _fn("contactLost")
    assert "m.status||m.endedBy" in body.replace(" ", "")


def test_the_faded_state_lasts_about_two_minutes():
    assert re.search(r"const LOST_FADE_MIN=2\b", PAGE)


# ── telemetry ──────────────────────────────────────────────────────────────────────────────────────────
def test_ground_speed_comes_from_two_reports_or_not_at_all():
    """No post states a speed. The only honest source is the distance between two consecutive reports."""
    body = _fn("groundSpeed")
    assert "m.history" in body
    assert "return null" in body
    assert re.search(r"Math\.round\(d/dt\*60/10\)\*10", body), (
        "the derived speed is reported to a precision its inputs do not carry")


def test_ground_speed_says_where_it_came_from():
    assert I18N.count("tel_gs_src:") == 3
    vals = _values("tel_gs_src", I18N)
    assert len(vals) == 3
    for v in vals:
        assert "radar" in v.lower() or "радар" in v.lower(), f"it does not disclaim radar: {v!r}"


# ── audio ──────────────────────────────────────────────────────────────────────────────────────────────
def test_the_alert_volume_follows_what_the_reader_can_still_do():
    body = _fn("alertVol")
    assert "IMMEDIATE.has(m.type)" in body
    m = re.search(r"const ZONE_VOL=\{(.*?)\};", PAGE)
    assert m
    vals = dict(re.findall(r"(\w+):([\d.]+)", m.group(1)))
    assert float(vals["near"]) > float(vals["approach"]) > float(vals["observe"])


def test_every_new_string_exists_in_all_three_languages():
    for k in ("sl_home", "sl_work", "sl_kids", "sl_pin", "sl_pin_set", "sl_pin_how", "sl_pin_dropped",
              "z_near", "z_approach", "z_observe",
              "eta_band", "eta_if", "tel_gs", "tel_gs_src", "lost_t", "lost_b"):
        n = len(re.findall(rf"(?<![A-Za-z_]){k}:", I18N))      # whole key: lt_z_near must not count as z_near
        assert n == 3, f"{k} appears {n} times — expected once per language"


# ── closing the loop on a warning ───────────────────────────────────────────────────────────────────────
def test_a_warning_is_closed_when_the_target_it_named_comes_down():
    """Somebody was told a Shahed was coming at their place and is now sitting in a corridor with a phone.
    When a later post says it was shot down, nothing used to tell them."""
    i = PAGE.index("if(m.endedBy&&m.endedBy.status==='down'")
    body = PAGE[i:i + 900]
    assert "homeAlerted.has(m.id)" in body, (
        "it fires for interceptions anywhere in the country, not only for what this reader was warned about")
    assert "homeClosed" in body, "the same shoot-down would be announced on every render"
    assert "'down'" in body, "it fires on outcomes other than a confirmed shoot-down"


def test_the_shoot_down_notice_can_never_be_read_as_an_all_clear():
    """One target down is one target. A person who reads it as "the raid is over" walks outside."""
    for k in ("n_down_note", "n_down_left"):
        vals = _values(k, I18N)
        assert len(vals) == 3, f"{k} is missing from a language"
    for v in _values("n_down_note", I18N):
        assert any(w in v.lower() for w in ("not mean", "не відбій", "n'est pas")), (
            f"the wording does not rule out an all-clear: {v!r}")
    i = PAGE.index("if(m.endedBy&&m.endedBy.status==='down'")
    body = PAGE[i:i + 900]
    assert "n_down_left" in body and "n_down_note" in body, (
        "it never says whether anything else is still in the air")


def test_the_shoot_down_notice_is_quieter_than_a_warning():
    """It is good news. It does not need the volume that "take cover" needs."""
    i = PAGE.index("if(m.endedBy&&m.endedBy.status==='down'")
    body = PAGE[i:i + 900]
    assert "'end'" in body, "it uses an alarm tone for good news"


def test_switching_watched_place_forgets_the_closed_ones_too():
    body = _fn("useSlot")
    assert "homeClosed.clear()" in body.replace(" ", "") or "homeClosed.clear()" in PAGE[
        PAGE.index("homeAlerted.clear()"):PAGE.index("homeAlerted.clear()") + 120]
