"""1.42.1, from the night of 7 Oct 2026 (01:14–01:20).

- The map comes first on a phone: a ballistic warning, the admin's message and a mark's sheet left the map 260 px of an
  860 px screen, and 7 px with the sheet open.
- "Балістика курсом на Київ" names where it is going: the sheet said "Kyiv · 0 km from Kyiv · near zone, up to 10 km".
- A ballistic report while no official alert covers the reader's place said "shelter now, do not wait for the siren"
  for eight minutes; Kyiv city was never under alert.
- єРадар's "реактивний повз Пісківку курсом на Київщину, Макарів / Наливайківку" pointed at the oblast's centre, and
  "від Боромлі на Полтавщину" stood at the centre of Sumy oblast: the towns the post named were not used."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402
import server  # noqa: E402

PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
ERADAR = ("🛵Житомирщина: реактивний повз Пісківку курсом на Київщину, Макарів / Наливайківку\n\n"
          "🛵Сумщина: реактивний від Боромлі на Полтавщину")


def test_the_towns_after_the_oblast_are_the_destination_and_a_named_village_is_a_position():
    a, b = geo.parse_for_channel("eRadarrua", ERADAR)
    assert (a["place"], a["target"]) == ("Пісківка", "Макарів") and 140 <= a["heading"] <= 165
    assert b["place"] == "Боромля" and b["oblast_uid"] == "20"                # was the centre of Sumy oblast
    assert [m["place"] for m in geo.parse_for_channel("kievinfo_kyiv", "✈️Реактивний БпЛА на Наливайківку")] == ["→ Наливайківка"]


def test_an_oblast_alone_is_still_the_oblast():
    m = geo.parse_for_channel("eRadarrua", "🛵Житомирщина: реактивний повз Пісківку курсом на Київщину")[0]
    assert m["target"] == "область" and m["place"] == "Пісківка"


def test_a_destination_is_never_shown_as_a_position_with_a_distance():
    assert "const appr=!!m.approach&&!m.status&&!m.endedBy;" in PAGE
    assert "const where=appr?`<b>${esc(t('sh_appr',pn(m.place)))}</b>`" in PAGE
    assert "if(!HOME||m.status||m.endedBy||appr) return '';" in PAGE          # no "near zone, up to 10 km"
    assert len(re.findall(r"\bsh_appr:'", I18N)) == 3 and len(re.findall(r"\bn_rep_to:'", I18N)) == 3


def test_a_ballistic_report_without_an_official_alert_says_so_and_fades_sooner():
    assert "TS_FRESH_BAL_UNOFF=4" in PAGE
    assert "const unoff=x=>x.ty==='ballistic_missiles'&&!lvl&&!x.official;" in PAGE
    assert "unoff(tt)?t('ts_bal_ready'):t('mc_go_now')" in PAGE
    assert "const uo=m.type==='ballistic_missiles'&&!officialLevel();" in PAGE
    for k in ("ts_bal_unoff", "ts_bal_ready"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k
    for w in ("no official alert here yet", "офіційної тривоги тут ще немає", "pas encore d’alerte officielle ici"):
        assert w in I18N, w


def test_on_a_phone_the_map_keeps_its_room():
    i = PAGE.index("@media (max-width:999px){\n  #mycard{gap:4px;padding:4px}")
    css = PAGE[i:PAGE.index("\n}\n", i)]
    for rule in (".sheet.mark{max-height:52vh", "body.shmk #notice,body.shmk #moved{display:none!important}",
                 ".notice:not(.open) .ntx{display:-webkit-box;-webkit-line-clamp:2",
                 "#mycard:has(.tstrip:not([hidden]):not(.calm):not(.old)) .mych.calm small{display:none}"):
        assert rule in css, rule
    assert "b.contains('shmk')" in PAGE and "$('sheet').classList.add('show','mark'); document.body.classList.add('shmk'); syncMini();" in PAGE
    assert "el.onclick=()=>el.classList.remove('show');" in PAGE                 # a tap puts the toast away


# --- a channel taking a missile report back (the 01:14 launch was the military system's glitch) ---------------------


def test_a_glitch_or_an_unconfirmed_launch_is_a_retraction_and_nothing_else():
    for t in ("швидкість 6000 була, ймовірно лаг системи", "Лаг системи", "Збій системи — балістики немає",
              "хибне спрацювання", "Інформація про пуск балістики не підтвердилась", "Пуск не підтверджено"):
        assert server.tag_feed_text(t, "kyiv_airdef")[:1] == ["retract"], t
        assert server.is_relevant(t, server.tag_feed_text(t, "kyiv_airdef"), "kyiv_airdef"), t   # kept, so it can act
    # a decoy is a "хибна ціль" and it flies; a ballistic report is one; an unconfirmed explosion is no mark at all
    assert "retract" not in server.tag_feed_text("Хибна ціль на Київ", "kyiv_airdef")
    assert "ballistic_missiles" in server.tag_feed_text("Балістика курсом на Київ", "monitor_ukr")
    assert server.tag_feed_text("Вибух у Броварах не підтвердився", "kyiv_airdef") == ["news"]


def test_a_retraction_ends_the_channels_ballistic_mark_and_warning_but_never_an_official_alert():
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    posts = [("monitor_ukr/1", "monitor_ukr", 6, "Балістика курсом на Київ"), ("kyiv_airdef/2", "kyiv_airdef", 2, "швидкість 6000 була, ймовірно лаг системи")]
    st.store.add_feed([{"post_id": i, "channel": c, "ts": (now - timedelta(minutes=m)).isoformat(), "text": t, "tags": server.tag_feed_text(t, c)}
                       for i, c, m, t in posts])
    assert not [m for m in st.markers() if m["type"] == "ballistic_missiles"]
    assert st._missile_active() != st.MSL_BALLISTIC
    assert "const retracted=ts=>recent.some(p=>p.ts>ts&&(p.tags||[]).includes('retract'));" in PAGE
    i = PAGE.index("const retracted=ts=>")
    assert "for(const a of S.active)" not in PAGE[i:i + 600]          # the official threats are read above, untouched
