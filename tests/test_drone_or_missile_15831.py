"""1.58.31 — a drone is a drone until a missile is reported; and the mirror standing in says only what it knows.

The owner (15 Oct 2026, 08:57–09:02, four screenshots): "Ракети ×2" over Obolon, then "Ракети ↓ знижується" over
Troieshchyna, from @kievinfo_kyiv's "останній троя, тец-6🚀 знижує висоту" — while the state's own level for Kyiv was
yellow, a drone threat. "Even propeller drones, jet drones or super high-speed UAVs are still DRONES, not missiles … if the
parser hasn't found any messages in the channels about missile launches, ballistics, or MiG-31K takeoffs, the system
shouldn't have the right to put up a «Missile» marker at all … any disputed or high-speed target should default to a drone.
When they write «останній» in the masculine, it's always a drone (Shahed); «остання» in the feminine is a missile."

Then (10:17): "everything is still red while the official app has lifted the alert in several raions". siren.pp.ua, the
raion-level source, did not answer from 09:39 to 10:17; the oblast-only mirror stood in and painted Kyiv, Cherkasy and
Chernihiv oblasts whole, red, while the government app showed four raions of Kyiv oblast, yellow.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, DOC = _read("static", "kyiv.html"), _read("static", "light.html"), _read("static", "i18n.js"), _read("docs", "TECHNICAL.md")


def _parse(channel, text):
    return geo.parse_for_channel(channel, server._clean_post(text))


def _marks(posts, air=()):
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "marker_ttl_minutes": 45})
    for ch, pid, minutes, text in posts:
        server.Telegram(st, {}).ingest(ch, [(f"{ch}/{pid}", (NOW - timedelta(minutes=minutes)).isoformat(), text)], "tg:" + ch)
    for kind, phase, minutes in air:
        st.store.conn.execute("INSERT INTO air_reports(post_id,kind,phase,channel,ts,h) VALUES(?,?,?,?,?,?)",
                              (f"a/{kind}{minutes}", kind, phase, "kpszsu", (NOW - timedelta(minutes=minutes)).isoformat(), "h"))
    st.store.conn.commit()
    return st, {m["id"].split("#")[0]: m for m in st.markers()}


# ---- the words ---------------------------------------------------------------------------------------------------------
def test_the_masculine_last_one_is_a_drone_the_feminine_only_suggests_a_missile():
    (m,) = _parse("kievinfo_kyiv", "останній троя, тец-6🚀 знижує висоту")          # the post of 08:58
    assert m["type"] == "drones" and not m.get("msl_weak")
    (m,) = _parse("kievinfo_kyiv", "Останній залишився на Нивки")
    assert m["type"] == "drones"
    (m,) = _parse("kievinfo_kyiv", "остання троя, тец-6 знижує висоту")
    assert m["type"] == "unspecified_missiles" and m["msl_weak"]
    (m,) = _parse("kievinfo_kyiv", "остання група на Бровари")                        # a group: not a missile
    assert m["type"] == "unknown"
    assert not any(x["type"] == "drones" for x in _parse("kievinfo_kyiv", "останній раз вибух на Оболоні"))


def test_what_names_a_missile_and_what_only_suggests_one():
    assert geo.missile_said("🚀🚀Оболонь, Труханів", "kievinfo_kyiv") == "weak"
    assert geo.missile_said("швидкісна ціль на Київ", "kyiv_airdef") == "weak"
    assert geo.missile_said("🚀 Швидкісна ціль на Київщині курсом на Київ", "kpszsu") == "named"      # the Air Force's word
    assert geo.missile_said("🚀КАБи на Харківщину.", "kpszsu") == "weak"                                # its 🚀 is no proof
    for t in ("Ракета на Оболонь", "2 КР на Київ", "Балістика з Брянська", "Калібри з Чорного моря", "Зліт МіГ-31К",
              "Ту-95 у повітрі", "х-101 курсом на Київ", "кинджал"):
        assert geo.missile_said(t) == "named", t
    assert geo.missile_said("Реактивна ракета з Оріона на Херсон") is None                             # a Banderol: a jet drone
    assert geo.missile_said("Кр.Ріг : Загрозу зняли") is None and geo.missile_said("Кр Ріг чисто") is None
    (m,) = _parse("kyiv_airdef", "2 КР на Київ")
    assert m["type"] == "cruise_missiles" and m["count"] == 2


# ---- the rule ----------------------------------------------------------------------------------------------------------
def test_no_missile_reported_no_missile_on_the_map():
    st, ms = _marks([("kievinfo_kyiv", "1", 3, "🚀🚀Оболонь, Труханів")])
    m = ms["kievinfo_kyiv/1"]
    assert m["type"] == "unknown" and m["likely"] == "drones"                      # "probably a drone" on the pages
    assert "no missile was reported" in m["evidence"]["type"]["method"] and m["evidence"]["type"]["confidence"] == "low"
    assert st.missile_active() == 0
    st, ms = _marks([("kyiv_airdef", "1", 3, "швидкісна ціль на Київ")])
    assert ms["kyiv_airdef/1"]["type"] == "unknown" and st.missile_active() == 0   # no ballistic banner for it alone
    # the tag says so too: no missile chip, no missile in the feed's tags
    assert server.tag_feed_text("🚀🚀Оболонь, Труханів", "kievinfo_kyiv")[:1] == ["msl_weak"]


def test_a_missile_reported_and_it_may_be_one():
    # a launch reported by the Air Force an hour before
    st, ms = _marks([("kpszsu", "9", 60, "Ракетна небезпека! Пуски крилатих ракет з Каспію"), ("kievinfo_kyiv", "1", 3, "🚀🚀Оболонь, Труханів")])
    m = ms["kievinfo_kyiv/1"]
    assert m["type"] == "unspecified_missiles" and "a missile reported at" in m["evidence"]["type"]["method"]
    # ... but not three hours before
    st, ms = _marks([("kpszsu", "9", 200, "Ракетна небезпека! Пуски крилатих ракет з Каспію"), ("kievinfo_kyiv", "1", 3, "🚀🚀Оболонь, Труханів")])
    assert ms["kievinfo_kyiv/1"]["type"] == "unknown"
    # a carrier in the air: a Tu-95 launching two hours ago, a MiG-31K up
    st, ms = _marks([("kievinfo_kyiv", "1", 3, "🚀🚀Оболонь, Труханів")], air=[("strategic", "launch", 120)])
    assert ms["kievinfo_kyiv/1"]["type"] == "unspecified_missiles"
    st, ms = _marks([("kyiv_airdef", "1", 3, "швидкісна ціль на Київ")], air=[("mig31k", "up", 20)])
    assert ms["kyiv_airdef/1"]["type"] == "ballistic_missiles"
    # the Air Force's own "швидкісна ціль" a minute later makes the tracker's one a minute before a missile too
    st, ms = _marks([("kyiv_airdef", "1", 3, "швидкісна ціль на Київ"), ("kpszsu", "2", 2, "🚀 Швидкісна ціль на Київщині курсом на Київ")])
    assert ms["kyiv_airdef/1"]["type"] == "ballistic_missiles" and st.missile_active() == 2
    # a channel taking it back: what was reported before no longer counts
    st, ms = _marks([("kpszsu", "9", 30, "Балістика на Київ"), ("kyiv_airdef", "8", 20, "балістика — ймовірно лаг системи"),
                     ("kievinfo_kyiv", "1", 3, "🚀🚀Оболонь, Труханів")])
    assert ms["kievinfo_kyiv/1"]["type"] == "unknown"
    # a post that names a missile is one, reported or not
    st, ms = _marks([("kudy_letyt", "1", 3, "Київ: ракета на Оболонь")])
    assert ms["kudy_letyt/1"]["type"] == "cruise_missiles"


# ---- the mirror standing in ---------------------------------------------------------------------------------------------
def _alert(key, uid, title, lt, level="yellow", source="ukrainealarm_proxy", raion_key=None):
    return {"key": key, "source": source, "location_uid": key, "location_title": title, "location_title_en": None, "location_type": lt,
            "oblast_uid": uid, "alert_type": "air_raid", "alert_level": level, "started_at": (NOW - timedelta(hours=2)).isoformat(),
            "finished_at": None, "notes": None, "threats": [], "raion_key": raion_key}


class _Detail:
    def __init__(self, last_ok):
        self.last_ok = last_ok

    def healthy(self):
        return False


def test_the_mirror_standing_in_says_only_what_it_knows():
    st = server.State(server.Store(":memory:"), {})
    proxy = [_alert("ua:77", "14", "Вишгородський район", "raion", raion_key="vyshhorodskyi"),
             _alert("ua:78", "14", "Бориспільський район", "raion", raion_key="boryspilskyi"),
             _alert("ua:152", "24", "Черкаський район", "raion"), _alert("ua:31", "31", "м. Київ", "oblast")]
    st.apply_snapshot("ukrainealarm_proxy", proxy, {"oblast", "raion", "hromada", "city", "unknown"})
    ub = server.Ubilling(st, {}, primary=True, detail=_Detail((NOW - timedelta(minutes=38)).timestamp()))
    mirror = [{"key": f"ub:{u}", "source": "ubilling_mirror", "location_uid": u, "location_title": t, "location_title_en": None,
               "location_type": "oblast", "oblast_uid": u, "alert_type": "air_raid", "alert_level": None,
               "started_at": NOW.isoformat(), "finished_at": None, "notes": "keyless mirror — oblast level only", "threats": []}
              for u, t in (("14", "Київська область"), ("31", "м. Київ"))]
    ub.stand_in(mirror, off={"24"})                                     # Cherkasy oblast: clear, says the mirror
    act = st.snapshot()["active"]
    keys = {a["key"] for a in act}
    assert "ua:152" not in keys                                          # its raion alert ends with it
    assert {"ua:77", "ua:78", "ub:14", "ub:31"} <= keys                  # Kyiv oblast's raions as last shown, kept
    k14 = next(a for a in act if a["key"] == "ub:14")
    assert k14["unsure"] and k14["raions_as_of"] and "as the official data last showed them" in k14["notes"]
    assert not next(a for a in act if a["key"] == "ub:31").get("unsure")        # the city is one unit: exact
    ob = st.snapshot()["oblasts"]
    assert ob["14"]["status"] == "P" and ob["31"]["status"] == "A"      # Kyiv oblast in part, not whole
    # with no raion source ever heard (a boot with it down), the old way: the whole oblast
    st2 = server.State(server.Store(":memory:"), {})
    server.Ubilling(st2, {}, primary=True, detail=_Detail(0)).stand_in([dict(mirror[0], unsure=None, raions_as_of=None)], off=set())
    assert not st2.snapshot()["active"][0].get("unsure") and st2.snapshot()["oblasts"]["14"]["status"] == "A"


def test_the_pages_show_unknown_raions_hatched_never_red_never_clear():
    assert "(a.location_type==='oblast'&&!a.unsure)" in PAGE and "if(uq) return {k:'P',u,q:uq};" in PAGE
    assert "cls.set(p,`rn ${l||(kQ?'Q':'')}`)" in PAGE and "oQ?'oQ':''" in PAGE and 'id="hatchQ"' in PAGE
    assert "svg .rn.Q,svg .nb.oQ{fill:url(#hatchQ)!important" in PAGE
    assert "(a.location_type==='oblast'&&!a.unsure)" in LIGHT and "if(air.some(a=>a.unsure&&a.oblast_uid===uid)) return {k:'P',part:[],mirror:true,others};" in LIGHT
    assert I18N.count("b_unsure:") == 3


def test_the_docs_tell_it():
    for s in ("1.58.31", "missile_said", "MSL_CTX_POST_MIN", "stand_in", "raions_as_of"):
        assert s in DOC, s
    json.dumps(server.State.MSL_OFFICIAL and sorted(server.State.MSL_OFFICIAL))
