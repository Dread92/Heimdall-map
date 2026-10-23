"""A filter that a weapon outruns is not a filter.

Somebody sets "alert me about things within 10 km". For a Shahed that is a real setting: three minutes of
warning, and a dozen irrelevant alerts a night spared. For an Iskander-M it is a trap — the missile crosses
that ring in under four seconds, so the condition "within 10 km of you" is only ever true after it has
arrived. The filter does not filter; it silently deletes the one warning there was, and the person never
learns the setting did that.

So these types ignore every radius and concern the whole region, and they say so in those words — never with
a distance or an ETA, both of which would invite the reader to believe there is time.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402
import server  # noqa: E402

SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()


def test_the_list_is_the_weapons_that_actually_outrun_a_radius():
    assert geo.is_immediate("ballistic_missiles")
    assert geo.is_immediate("mig31k_departure")
    assert geo.is_immediate("supersonic_missiles"), "Kh-22/32 cross a 10 km ring in seven seconds"


def test_it_does_not_quietly_grow_to_mean_anything_fast():
    """A cruise missile inside a 10 km ring still gives ~45 seconds — a real warning worth filtering by.
    Widening this list would put the entire map into every alert and make the setting meaningless. Kh-59/69
    stay out on the same test: fast for a guided missile, but the same order as a Kalibr, not ten times it."""
    for t in ("drones", "cruise_missiles", "banderol_missiles", "guided_aerial_bombs",
              "unspecified_missiles", "tactic_aircraft_activity", "strategic_aircraft_activity"):
        assert not geo.is_immediate(t), f"{t} was added to the bypass list"
    assert len(geo.IMMEDIATE_TYPES) == 3


def test_the_region_span_is_about_an_oblast():
    assert 100 <= geo.REGION_ALERT_KM <= 200


# ── the push path ──────────────────────────────────────────────────────────────────────────────────────
def _watch_body():
    b = SRC[SRC.index("def proximity_watch("):]
    return b[:b.index("\nTHREAT_EN")]


def test_the_chosen_radius_is_not_applied_to_them():
    body = _watch_body()
    assert "is_immediate" in body, "the proximity watcher still filters ballistic by the chosen radius"
    assert "REGION_ALERT_KM" in body


def test_they_are_not_held_behind_the_two_minute_throttle():
    """The throttle exists so a busy night is not a stream of buzzes. A ballistic warning delayed by two
    minutes is a ballistic warning delivered after the impact."""
    body = _watch_body()
    i = body.index("PROX_LAST.get(ep, 0) < 120")
    assert "not urgent and" in body[max(0, i - 40):i], "the ballistic path still waits on the throttle"


def test_the_ballistic_push_claims_no_distance_and_no_direction():
    """The stored home is a ~10 km cell, and at Mach 5 a bearing is not something anyone can act on."""
    body = _watch_body()
    urgent = body[body.index("if urgent:"):body.index("near.sort(")]
    assert "in your region" in urgent
    for banned in ("km of you", "km from you", "heading", "compass_en", "round(radius)"):
        assert banned not in urgent, f"the ballistic push leaks {banned!r}"


def test_nothing_else_goes_out_in_the_same_breath():
    body = _watch_body()
    urgent = body[body.index("if urgent:"):body.index("near.sort(")]
    assert urgent.rstrip().endswith("continue"), (
        "a lesser proximity push still fires in the same cycle as the ballistic one")


# ── the map ────────────────────────────────────────────────────────────────────────────────────────────
def test_the_page_bypasses_its_own_radius_for_the_same_types():
    m = re.search(r"const IMMEDIATE=new Set\(\[(.*?)\]\)", PAGE)
    assert m, "the page has no bypass list"
    on_page = {x.strip().strip("'\"") for x in m.group(1).split(",")}
    assert on_page == set(geo.IMMEDIATE_TYPES), (
        f"page and server disagree about which weapons outrun a radius: {on_page} vs {set(geo.IMMEDIATE_TYPES)}")


def test_the_pages_region_span_matches_the_servers():
    m = re.search(r"const REGION_R=(\d+)", PAGE)
    assert m and float(m.group(1)) == geo.REGION_ALERT_KM


def test_the_in_app_alert_for_them_names_no_distance_and_no_eta():
    # 1.42.1: two lines (the unconfirmed ballistic variant); 1.58.44: the region-wide sound (sndFor) — missiles and KABs too
    i = PAGE.index("if(sf.why==='imm'||sf.why==='region'){ const uo=")
    line = PAGE[i:PAGE.index("}", PAGE.index("notify(", i))]
    assert "n_imm" in line
    for banned in ("hi.dist", "eta", "n_hway"):
        assert banned not in line, f"the ballistic toast leaks {banned!r} — that reads as 'there is time'"


def test_every_language_can_say_it():
    i18n = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
    for k in ("n_imm", "n_imm_b"):
        assert i18n.count(f"{k}:") == 3, f"{k} is not translated in all three languages"


def test_a_ballistic_marker_still_carries_a_position_when_the_post_gave_one():
    """The bypass is about the filter, not about the reading: nothing here invents a position."""
    ms = geo.parse_post("🚀 Швидкісна ціль на Дніпропетровщині курсом на Павлоград!")
    assert ms and ms[0]["type"] == "ballistic_missiles"
    assert geo.is_immediate(ms[0]["type"])


def test_the_span_covers_a_home_oblast_and_not_the_next_country_over():
    """Kyiv → Bila Tserkva (~80 km) is the same region and must alert. Kyiv → Kharkiv (~410 km) is four
    minutes of ballistic flight away and somebody else's warning."""
    assert server.haversine_km(50.45, 30.52, 49.80, 30.11) <= geo.REGION_ALERT_KM
    assert server.haversine_km(50.45, 30.52, 49.99, 36.23) > geo.REGION_ALERT_KM


def test_the_bypass_survives_the_branch_for_markers_with_no_speed_model():
    """The page has no speed for a ballistic missile (SPEED() returns 0), so every ballistic marker takes
    homeInfo's no-speed early return. That branch once hardcoded immediate:false, which meant the exemption
    was computed, discarded, and did nothing at all — with every test above still passing."""
    i = PAGE.index("function homeInfo(")
    body = PAGE[i:PAGE.index("function drawHome(", i)]
    early = body[body.index("if(m.status||m.endedBy||!v)"):]
    early = early[:early.index("\n")]
    assert "immediate:imm" in early.replace(" ", ""), (
        "homeInfo's no-speed branch drops the bypass — ballistic markers go back to being filtered by radius")
    assert "dist<NEAR_R||imm" in early.replace(" ", "")              # 1.58.56: the reader's near zone (it was 10 km)


def test_the_page_has_no_speed_for_ballistic_which_is_why_that_branch_matters():
    m = re.search(r"const SPEED=(.*)", PAGE)
    assert m and "ballistic" not in m.group(1), (
        "SPEED() now models ballistic — re-check that homeInfo still routes it through the right branch")


def test_a_mig31k_takeoff_is_not_a_kyiv_event():
    """The Air Force declares an alert over the whole country for it — the aircraft can turn toward anywhere
    before it fires. Gated on the Kyiv oblast uid, a subscriber in Kharkiv got nothing for the one warning
    that arrives an hour before the missile does."""
    body = SRC[SRC.index("    def on_event(self, ev):"):]
    body = body[:body.index("    def _queue(")]
    mig = body[body.index('tt == "mig31k_departure"'):]
    mig = mig[:mig.index("elif")]
    assert 'ou in ("31", "14")' not in mig, "the MiG-31K push is still gated on the Kyiv oblast"
    assert "country-wide" in mig


def test_a_supersonic_missile_is_read_as_its_own_weapon():
    """Х-22 used to match the cruise pattern. As a "cruise missile" it was drawn at a fifth of its speed and
    filtered by a radius it crosses in seven seconds — the exact failure this whole file is about."""
    for text in ("Х-22 по Одещині", "Ракета Х-32 курсом на Миколаїв", "х22 на Одесу"):
        ms = geo.parse_post(text)
        assert ms and ms[0]["type"] == "supersonic_missiles", f"{text!r} → {ms[0]['type'] if ms else None}"


def test_the_ordinary_cruise_missiles_did_not_follow_it_across():
    for text, want in (("Х-59 по Харківщині", "cruise_missiles"),
                       ("Крилаті ракети Х-101 на Полтавщині", "cruise_missiles"),
                       ("Калібри на Київщині", "cruise_missiles")):
        ms = geo.parse_post(text)
        assert ms and ms[0]["type"] == want, f"{text!r} → {ms[0]['type'] if ms else None}"


def test_it_is_never_extrapolated_along_a_course():
    """At Mach 4 one minute of drift is 93 km of invented position. No SPEED entry means no extrapolation —
    the marker stays where the post put it, like ballistic."""
    m = re.search(r"const SPEED=(.*)", PAGE)
    assert m and "supersonic" not in m.group(1)
    css = PAGE[PAGE.index(".mk.supersonic_missiles .glyph"):]
    assert ".mk.supersonic_missiles .ahead,.mk.supersonic_missiles .cone{display:none}" in css, (
        "the projection cone is still drawn for a weapon whose position cannot be projected")


def test_it_does_not_look_like_a_ballistic_missile():
    """Two different warnings. Drawn identically, the one that means "shelter now, it is already here"
    stops being distinguishable from the one that means it too — and both stop meaning anything."""
    a = PAGE[PAGE.index(".mk.ballistic_missiles .glyph"):].split("}")[0]
    b = PAGE[PAGE.index(".mk.supersonic_missiles .glyph"):].split("}")[0]
    assert a != b
