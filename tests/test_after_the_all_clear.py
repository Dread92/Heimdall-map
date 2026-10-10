"""1.38: 5 October 2026, 20:14–20:38 Kyiv time, replayed from the posts the app read (tests/fixtures/
kyiv_2026_10_05_evening.json). A jet drone crossed Kyiv to Vydubychi and the Southern bridge; kyiv_airdef posted
"Вибух" (an explosion — the interception), then that it fell and Kyiv was clear; the official all-clear for the city
came at 20:27. The app then kept a "target" at Vydubychi, "1 min ago", until 20:37 — carried there by chyste_nebo's
lines about another target 100 km south ("На Таращу", "Йде 8000 курсом на Кагарлик") — lit the Darnytskyi and Southern
bridges with it, and for half an hour said "Darnytskyi Bridge: hit reported", "Southern Bridge: hit reported". Nobody
had reported a hit. These tests hold what the app may conclude, and when what it was told ends."""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "kyiv_2026_10_05_evening.json"), encoding="utf-8"))
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()


def _replay(at):
    """The app as it stood at Kyiv time `at` ("20:36"): the posts up to then, the official alerts as they were."""
    at_utc = f"2026-10-05T{int(at[:2]) - 3:02d}:{at[3:5]}:{at[6:8] if len(at) > 5 else '00'}+00:00"
    shift = datetime.now(timezone.utc) - datetime.fromisoformat(at_utc)

    def sh(s):
        return (datetime.fromisoformat(s) + shift).isoformat()
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "marker_ttl_minutes": 45})
    st.store.add_feed([dict(p, ts=sh(p["ts"])) for p in FX["posts"] if p["ts"] <= at_utc])
    k = FX["kyiv_city_alert"]
    a = {"key": "kyiv31", "source": "alerts_in_ua", "location_uid": "31", "location_title": "м. Київ", "location_type": "city",
         "oblast_uid": "31", "alert_type": "air_raid", "alert_level": "yellow", "started_at": sh(k["started_at"])}
    ended = k["finished_at"] <= at_utc
    st.store.upsert_alert(dict(a, finished_at=sh(k["finished_at"]) if ended else None))
    if not ended:
        st.active["kyiv31"] = a
    st.active["kharkiv"] = {"key": "kharkiv", "source": "alerts_in_ua", "location_uid": "22", "location_title": "Харківська область",
                            "location_type": "oblast", "oblast_uid": "22", "alert_type": "air_raid", "started_at": sh("2026-10-05T16:00:00+00:00")}
    if FX["bila_tserkva_alert"]["started_at"] <= at_utc:
        st.active["bc"] = {"key": "bc", "source": "alerts_in_ua", "location_uid": "bc", "location_title": "Білоцерківський район",
                           "location_type": "raion", "oblast_uid": "14", "alert_type": "air_raid", "started_at": sh(FX["bila_tserkva_alert"]["started_at"])}
    ms = st.markers()
    st.markers_now = lambda: ms
    return st, ms


def _live_in_kyiv(ms):
    return [(m["place"], m["channel"]) for m in ms if m.get("oblast_uid") == "31" and not m.get("status")]


def test_while_it_flew_the_bridges_lit_up():
    st, ms = _replay("20:25:20")
    B = st.bridges_now()
    assert B["pivdennyi"]["lvl"] == "at" and B["darnytskyi"]["lvl"] == "at"
    assert ("Видубичі", "chyste_nebo") in _live_in_kyiv(ms)


def test_after_the_official_all_clear_nothing_is_left_in_kyiv_and_no_bridge_is_lit():
    for at in ("20:27:30", "20:30", "20:33", "20:36", "20:38:30", "20:41"):
        st, ms = _replay(at)
        assert _live_in_kyiv(ms) == [], at
        assert not any(st.bridges_now().values()), (at, st.bridges_now())


def test_a_line_about_where_it_goes_does_not_restart_the_clock_of_where_it_was():
    # chyste_nebo's next target was at Lysianka (Cherkasy oblast), going north: it is drawn there, not at Vydubychi
    st, ms = _replay("20:30")
    mine = [m for m in ms if m["channel"] == "chyste_nebo" and not m.get("status")]
    assert [m["place"] for m in mine] == ["Лисянка"] and mine[0]["target"] == "Тараща" and mine[0]["pos_ts"] < mine[0]["ts"]
    # five lines later ("На Таращу", "На Богуслав", "Йде 8000 курсом на Кагарлик") it has had no new position for six
    # minutes. An unspecified target older than five minutes is not drawn at all — never "1 min ago" at an old place
    st, ms = _replay("20:35:30")
    assert [m for m in ms if m["channel"] == "chyste_nebo" and not m.get("status")] == []
    # "Не спостерігається": the channel lost it — the next bare line is placed nowhere
    st, ms = _replay("20:38:30")
    assert not [m for m in ms if m["channel"] == "chyste_nebo" and m.get("status") == "clear" and m.get("place") == "Видубичі"]


def test_an_explosion_is_never_a_hit_on_a_bridge():
    st, ms = _replay("20:26")
    vyd = [m for m in ms if m.get("status") == "impact"]
    assert vyd and vyd[0]["place"] == "Видубичі"                                  # the explosion stays on the map, as an explosion
    for at in ("20:26", "20:41", "20:50"):
        assert not any(e.get("lvl") == "hit" for e in _replay(at)[0].bridges_now().values()), at


def _post(text, minutes, ch="kyiv_airdef"):
    now = datetime.now(timezone.utc)
    return {"post_id": f"{ch}/{abs(hash(text)) % 10**6}", "channel": ch, "ts": (now - timedelta(minutes=minutes)).isoformat(), "text": text, "tags": []}


def _state(posts, all_clear_min=None):
    st = server.State(server.Store(":memory:"), {})
    st.markers_now = lambda: []
    st.store.add_feed(posts)
    if all_clear_min is not None:
        now = datetime.now(timezone.utc)
        st.store.upsert_alert({"key": "k", "source": "alerts_in_ua", "location_uid": "31", "location_title": "м. Київ", "location_type": "city",
                               "oblast_uid": "31", "alert_type": "air_raid", "started_at": (now - timedelta(minutes=40)).isoformat(),
                               "finished_at": (now - timedelta(minutes=all_clear_min)).isoformat()})
    return st


def test_hit_reported_only_when_a_post_says_the_bridge_was_hit():
    B = _state([_post("Влучання в Південний міст", 12)]).bridges_now()
    assert B["pivdennyi"]["lvl"] == "hit" and B["pivdennyi"]["how"] == "named"
    for text in ("Вибух біля Південного мосту", "Південний міст падає", "Над Південним мостом збито", "Південний міст — уражено ціль"):
        B = _state([_post(text, 12)]).bridges_now()
        assert B["pivdennyi"] == {}, text                                      # 12 minutes: too old for "at", and no hit said
    assert _state([_post("Південний міст увага", 2)]).bridges_now()["pivdennyi"]["lvl"] == "at"
    assert _state([_post("Над Південним мостом збито", 2)]).bridges_now()["pivdennyi"] == {}   # shot down: no target on it
    assert _state([_post("Петрівський міст увага", 1)]).bridges_now()["petrivskyi"]["lvl"] == "at"


def test_nothing_posted_before_the_official_all_clear_counts_after_it():
    assert _state([_post("Південний міст увага", 3)], all_clear_min=1).bridges_now()["pivdennyi"] == {}
    assert _state([_post("Південний міст увага", 1)], all_clear_min=3).bridges_now()["pivdennyi"]["lvl"] == "at"   # after it: a new one
    assert _state([_post("Влучання в Південний міст", 20)], all_clear_min=10).bridges_now()["pivdennyi"] == {}


def test_the_rules_are_in_the_code_where_they_belong():
    i = SRC.index("    def markers(self):")
    body = SRC[i:SRC.index("    def _chain_and_prune", i)]
    assert "kyiv_ends = self.kyiv_city_all_clears(ttl)" in body
    assert 'last_by_channel[p["channel"]] = ctx if (m.get("pos_ts") and ctx) else (pts, m, p["ts"], n_here)' in body   # 1.56.3: and how many targets that post reported
    assert 'm.get("status") in ("down", "lost", "clear")' in body
    assert 'tp = parse_iso(m.get("pos_ts") or m["ts"])' in SRC
    assert "Лисянка" in geo.PLACES and geo.PLACES["Лисянка"][2] == "24"


def test_the_bar_is_one_line_and_the_map_names_only_what_matters():
    assert 'class="brn" aria-expanded=' in TAC and "BRG_OPEN" in TAC
    assert "svg:not(.vclose) .brgl:not(.at):not(.near):not(.hit){display:none}" in TAC
    assert "function placeBrgLabels()" in TAC and "if(typeof placeBrgLabels==='function')placeBrgLabels();" in TAC
    assert "a.slice(0,1).map(" in LIGHT and "' · +'+(a.length-1)" in LIGHT
