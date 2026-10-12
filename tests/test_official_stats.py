"""Stats hold the Air Force's official figures and nothing else; the dashboard holds what matters on a live night.

1.19: "we remove everything and keep only the official statistics of the Ukrainian Air Force". The explosion and
shoot-down counts the app read from channels were never totals, and next to official numbers they were read
as if they were. And the dashboard stopped being a review queue: it says whether every source is alive, which
channels went quiet, and how early the map was compared with the official alert.
"""
import os
from datetime import datetime, timedelta, timezone

import server
from alert_events import events_from_table  # 1.58.4: the alerts' start / end events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()


def _iso(dt):
    return dt.isoformat()


MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def _summary(d, m, down, when):
    k = when.astimezone(server.kyiv_tz())
    return (f"В ніч на {k.day} {MONTHS[k.month - 1]} (з 18:00) противник атакував {d} ударними БпЛА типу Shahed та дронами-імітаторами"
            + (f" та {m} ракетами" if m else "") + f".\n\nСтаном на 08:30 збито/подавлено {down} ворожих цілей.")


def _state():
    return server.State(server.Store(":memory:"), {})


def test_each_summary_is_listed_with_the_post_it_was_read_from():
    st = _state()
    now = datetime.now(timezone.utc)
    t1, t2 = now - timedelta(hours=3), now - timedelta(days=2)
    st.store.add_feed([
        {"post_id": "kpszsu/101", "channel": "kpszsu", "ts": _iso(t1), "text": _summary(87, 4, 71, t1), "tags": []},
        # the same night re-posted by a monitoring channel, a minute later: the Air Force's own post is the one linked
        {"post_id": "war_monitor/9", "channel": "war_monitor", "ts": _iso(t1 + timedelta(minutes=1)), "text": _summary(87, 4, 71, t1), "tags": []},
        {"post_id": "kpszsu/90", "channel": "kpszsu", "ts": _iso(t2), "text": _summary(64, 12, 60, t2), "tags": []},
    ])
    server.AFBackfill(st).from_feed()                # 1.32: summaries are kept in af_reports, read from there
    d = st.stats(14)
    days = d["af_days"]
    assert [x["post"] for x in days] == ["kpszsu/101", "kpszsu/90"]           # newest first, one per day
    assert (days[0]["drones"], days[0]["missiles"], days[0]["down"]) == (87, 4, 71)
    assert d["windows"]["7"]["launched_drones"] == 87 + 64                    # the re-post is not counted twice


def test_the_stats_tab_shows_only_the_air_force_figures():
    body = PAGE[PAGE.index("function renderStats(){"):PAGE.index("// Update notice")]
    # the app's own counts of explosion reports are gone; "impacts" now means the Air Force's own figure
    # ("влучання … на N локаціях"), read from its summary like the rest (1.32)
    for gone in ("imp_windows", "st_expl", "st_downs", "sbars", "impacts_total"):
        assert gone not in body, f"the Stats tab still shows {gone}"
    assert "af_days" in body and "st_af_src" in body
    assert "https://t.me/" in body                                           # every figure links to its summary


def test_the_live_tally_moved_to_the_alerts_tab():
    i = PAGE.index("$('alerts').innerHTML=")
    assert 'id="livecounts"' in PAGE[i:i + 120]
    assert "id=\"livecounts\"" not in PAGE[PAGE.index("function renderHist(){"):PAGE.index("async function loadState()")]


def test_the_dashboard_no_longer_reviews_posts():
    for gone in ("drawReview", "loadReview", "/api/corpus", "drawFlags", "/api/flags", "h_review", "h_flags"):
        assert gone not in ADMIN, f"the dashboard still has {gone}"
    assert "/api/health" in ADMIN


def test_the_health_view_is_the_owners_alone():
    i = SRC.index('if u.path == "/api/health":')
    assert "_admin_ok(q)" in SRC[i:i + 200]


def test_the_health_view_lists_every_channel_read_and_every_official_source():
    st = _state()
    st.set_source("ukrainealarm_proxy", True, count=3)
    st.set_source("tg:kyiv_airdef", True, count=10)
    st.set_source("tga:chyste_nebo", False, via="Telegram API", error="session expired")
    h = st.health()
    names = [c["channel"] for c in h["channels"]]
    assert names[:len(server.AUTHORITATIVE_CHANNELS)] == list(server.AUTHORITATIVE_CHANNELS)
    ch = {c["channel"]: c for c in h["channels"]}
    assert ch["chyste_nebo"]["via"] == "api" and ch["chyste_nebo"]["ok"] is False
    assert ch["kyiv_airdef"]["via"] == "preview"
    assert [o["name"] for o in h["official"]] == ["ukrainealarm_proxy"]      # channels are not listed as official


def test_lead_time_counts_a_wave_once_and_no_warning_as_no_warning():
    st = _state()
    now = datetime.now(timezone.utc)
    t1, t2 = now - timedelta(hours=5), now - timedelta(hours=2)

    def alert(key, t):
        st.store.upsert_alert({"key": key, "source": "ukrainealarm_proxy", "location_uid": key, "location_title": key,
                               "location_title_en": None, "location_type": "raion", "oblast_uid": "14", "alert_type": "air_raid",
                               "alert_level": "yellow", "started_at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "finished_at": None,
                               "notes": None, "threats": []})
    alert("a", t1)
    alert("b", t1 + timedelta(minutes=5))       # the same wave, one raion after another
    alert("c", t2)                              # a second wave, with nothing on the map before it
    events_from_table(st, active=("a", "b", "c"))
    st.store.log_markers([{"id": "kyiv_airdef/1#0", "ts": _iso(t1 - timedelta(minutes=14)), "channel": "kyiv_airdef",
                           "type": "drones", "status": None, "place": "Бровари", "oblast_uid": "14", "lon": 30.8, "lat": 50.5}])
    ld = st.lead_times(30)
    assert ld["waves"] == 2 and ld["warned"] == 1
    assert ld["median_min"] == 14
