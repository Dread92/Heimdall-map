"""1.58.44 — "БР" is a ballistic missile; and the sounds say what concerns the reader, once per target.

The owner, of "Без подальшої фіксації 3х БР.": "Algorithm can manage messages like this?" — it could not: "БР" (балістичні
ракети) was no weapon ("3х БР на Київ" a probable drone, "Пуск БР з Брянщини" nothing) and "без подальшої фіксації" no
outcome. Now it is three ballistic missiles no longer tracked, at the channel's last report of them.

A tester: "I didn't quite understand the sound notifications. Is there a specific tracking radius from the marker? It keeps
pinging constantly. What to actually fear is unclear. Missile threats make sense — no radius there. But for UAVs, it's
confusing." The owner's spec: drones sound in a radius the reader picks (10 / 20 / 30 km / the oblast, 20 by default),
louder inside 10 km, or when a post names the place or a stated course points at it within 40 km; once per target, again
only when it gets more serious; missiles and KABs region-wide; official alerts of the reader's own area only; no place —
no target sound, a prompt; a line under the picker saying what makes a sound.
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import geo  # noqa: E402
import server  # noqa: E402

PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
NOW = datetime.now(timezone.utc)


def _read(ch, t):
    return [(m["type"], m.get("status"), m.get("place"), m.get("count")) for m in geo.parse_for_channel(ch, t)]


# ---- БР ---------------------------------------------------------------------------------------------------------------
def test_br_is_a_ballistic_missile():
    assert _read("kpszsu", "3х БР на Київ") == [("ballistic_missiles", None, "→ Київ", 3)]
    assert _read("kyiv_airdef", "БР на Київ")[0][0] == "ballistic_missiles"
    assert _read("kpszsu", "2 БР на Харків!") == [("ballistic_missiles", None, "→ Харків", 2)]
    assert "ballistic_missiles" in server.tag_feed_text("Пуск БР з Брянщини", "kpszsu")          # a launch: the strip
    assert geo.missile_said("3х БР на Київ") == "named"
    assert _read("kpszsu", "бр. Іванова") == [] and "ballistic_missiles" not in server.tag_feed_text("бр. Іванова", "kpszsu")
    assert "(?:^|[^а-яіїє])бр\\s+(?:на|по)\\s+ки[їєе]в" in PAGE                                   # "БР на Київ": the strip


def test_no_further_tracking_is_lost():
    for ch in ("kpszsu", "kyiv_airdef"):
        (m,) = geo.parse_for_channel(ch, "Без подальшої фіксації 3х БР.")
        assert (m["type"], m["status"], m["count"], m["type_stated"], m["needs_context"]) == ("ballistic_missiles", "lost", 3, True, True)
    assert _read("kpszsu", "Без дальнейшей фиксации 2х БР")[0][:2] == ("ballistic_missiles", "lost")
    assert _read("kyiv_airdef", "Ціль без подальшої фіксації")[0][:2] == ("drones", "lost")
    assert _read("kpszsu", "Мінус 2 БР") == [("ballistic_missiles", "down", None, 2)]
    assert _read("kpszsu", "Мінус") == []                       # no weapon named: the Air Force's is nobody's in particular


def test_it_closes_that_channels_ballistic_report_never_a_drone():
    def marks(ch, posts):
        st = server.State(server.Store(":memory:"), {})
        tg = server.Telegram(st, {})
        n = abs(hash((ch, tuple(posts)))) % 900000 + 100000
        tg.ingest(ch, [(f"{ch}/{n + i}", (NOW - timedelta(minutes=5 - 2 * i)).isoformat(), t) for i, t in enumerate(posts)], "tg:" + ch)
        return st, [(m["type"], m.get("status"), m.get("place")) for m in st.markers()]
    st, ms = marks("kpszsu", ["3х БР на Київ", "Без подальшої фіксації 3х БР."])
    assert ("ballistic_missiles", "lost", "→ Київ") in ms and ("ballistic_missiles", None, "→ Київ") in ms
    st, ms = marks("kyiv_airdef", ["Шахед Бровари", "Без подальшої фіксації 3х БР."])
    assert ms == [("drones", None, "Бровари")]                  # no ballistic report before it: no mark, the drone untouched
    st, ms = marks("kyiv_airdef", ["БР на Київ", "Шахед Бровари", "Без подальшої фіксації 3х БР."])
    assert ("ballistic_missiles", "lost", "→ Київ") in ms and ("drones", None, "Бровари") in ms


def test_an_ending_warns_of_nothing():
    assert geo.ended_only("Без подальшої фіксації 3х БР.") and geo.ended_only("Мінус 2 БР")
    assert not geo.ended_only("3х БР на Київ") and not geo.ended_only("Пуск БР з Брянщини")
    st = server.State(server.Store(":memory:"), {})
    tg = server.Telegram(st, {})
    tg.ingest("kpszsu", [("kpszsu/990001", (NOW - timedelta(minutes=2)).isoformat(), "Без подальшої фіксації 3х БР.")], "tg:kpszsu")
    assert st.missile_active() == 0                             # no one-second cadence, no ballistic level, for an ending


# ---- the sounds -------------------------------------------------------------------------------------------------------
def test_what_makes_a_sound():
    assert "const SND_REGION=new Set(['ballistic_missiles','mig31k_departure','supersonic_missiles','cruise_missiles','unspecified_missiles','guided_aerial_bombs']);" in PAGE
    assert "const SND_RS=[10,20,30,0]; let SND_R=20;" in PAGE
    body = PAGE[PAGE.index("function sndFor(m,hi,x,y){"):PAGE.index("// 1.58.44: the official alert of the reader's own place")]
    for s in ("if(!HOME||m.status||m.endedBy||m.stale||m.held||hi.dist==null) return null;",
              "if(SND_REGION.has(m.type)){ if(d>REGION_R) return null;",
              "if(m.place==='область') return null;",
              "if(d<=10) return {rank:3,level:3,why:'near'};",
              "if(d<=REGION_R&&(hi.named||courseAtHome(m,x,y,d))) return {rank:2,level:2,why:'course'};",
              "if(d<=(SND_R||REGION_R)) return {rank:1,level:2,why:'radius'};"):
        assert s in body, s
    course = PAGE[PAGE.index("function courseAtHome(m,x,y,d){"):PAGE.index("function sndFor(")]
    assert "if(m.approach||m.heading==null||d==null||d>40) return false;" in course          # a stated course, 40 km
    assert "ev.confidence==='none') return false;" in course and "<=20; }" in course


def test_once_per_target_again_only_when_more_serious():
    assert "const trackKey=m=>m.tag&&m.tag.id?`t:${m.tag.night||''}:${m.tag.id}`:m.id;" in PAGE
    assert "if(sf&&sf.rank>(SND.get(tk)||0)){ SND.set(tk,sf.rank); homeAlerted.add(m.id);" in PAGE
    assert "if(SND.has(tk)) homeAlerted.add(m.id);" in PAGE         # a warned track's "shot down" still follows it
    assert "if(!homeAlerted.has(m.id)){homeAlerted.add(m.id);" not in PAGE


def test_official_alerts_of_the_readers_own_area():
    assert "function render(){\n  if(!S) return; areaWatch();" in PAGE
    aw = PAGE[PAGE.index("function areaWatch(){"):PAGE.index("function coversHome(a){")]
    assert "const k=placeLevel(HOME).k, prev=AREA_K;" in aw and "if(prev===null) return;" in aw
    on = PAGE[PAGE.index("const onA=kind=>ev=>{"):PAGE.index("['start','end','threat','update'].forEach")]
    assert "kind==='start')notify(" not in on and "kind==='end')notify(" not in on
    assert "if(imm||coversHome(a)) notify(" in on


def test_no_place_no_target_sound_a_prompt():
    assert "noPlaceSaid=true;notify(t('snd_noplace'),t('snd_noplace_b'),'threat',0);" in PAGE   # vol 0: silent
    assert "notify(t('n_kyivarea'),ptxt(d.post)" not in PAGE


def test_the_picker_and_its_line_in_three_languages():
    assert '<div class="mrow z" id="sndrr">' in PAGE and 'data-sr="0" data-t="snd_r_all"' in PAGE
    assert '<div class="pnote sndw" data-t="snd_why">' in PAGE
    for k in ("snd_r", "snd_r_all", "snd_km", "snd_why", "snd_noplace", "snd_noplace_b", "n_reg_b"):
        assert len(re.findall(r"\b" + k + r":", I18N)) == 3, k
    assert "snd_km:'{0} км'" in I18N and "snd_why:'Дрон — один сигнал" in I18N


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.44" in s and "БР" in s and "SND_R" in s, doc
    assert "## 1.58.44" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
