"""1.58.4 — an alert's history is read from its start and end, not from the alerts table's one row per region.

Found reading the dashboard for the owner's pattern analysis: every oblast "under alert 168 hours a week", Kyiv city
1,440 minutes a day since mid-September, and on the app's own statistics "the longest alert: 20,131 minutes, from
24 September to 12 October". The alerts table keeps ONE row per region and alert type (key "ua:<region>:<type>"):
a new alert of the region only rewrote its end, and its start stayed the region's FIRST — read as a history, every
alert ran from that first start to the last end. The stats, the dashboard's analytics, the lead times, the nights' and
the bulletins' records (what the AI writes from) all read it so.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import server  # noqa: E402

TZ = server.kyiv_tz()


def kyiv(days_ago, h, m=0):
    d = (datetime.now(TZ) - timedelta(days=days_ago)).date()
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ).astimezone(timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def city_alert(st, s, e):
    """As the server records one (State.apply): the row upserted, a start event; the row finished, an end event."""
    a = {"key": "ua:31:air_raid", "source": "ukrainealarm_proxy", "location_uid": "ua-31", "location_title": "м. Київ",
         "location_title_en": "Kyiv", "location_type": "city", "oblast_uid": "31", "alert_type": "air_raid", "alert_level": "red",
         "started_at": iso(s), "finished_at": None, "notes": None, "threats": []}
    ev = {"key": a["key"], "location_uid": a["location_uid"], "location_title": a["location_title"], "alert_type": "air_raid",
          "oblast_uid": "31"}
    st.store.upsert_alert(a)
    st.store.add_event(dict(ev, ts=iso(s), kind="start"))
    st.store.finish_alert(a["key"], iso(e))
    st.store.add_event(dict(ev, ts=iso(e), kind="end"))


def two_alerts():
    st = server.State(server.Store(":memory:"), {})
    city_alert(st, kyiv(5, 10), kyiv(5, 11))                 # 60 min, five days ago
    city_alert(st, kyiv(2, 20), kyiv(2, 20, 30))             # 30 min, two days ago
    return st


def test_a_new_alert_of_a_region_starts_its_row_again():
    st = two_alerts()
    row = st.store.history(24 * 30, ["31"])[0]
    assert row["started_at"] == iso(kyiv(2, 20)) and row["finished_at"] == iso(kyiv(2, 20, 30))


def test_each_alert_is_its_own_row_in_the_history():
    st = two_alerts()
    rows = [a for a in st.alert_rows(kyiv(7, 0)) if a["oblast_uid"] == "31"]
    assert [(r["started_at"][:16], r["finished_at"][:16]) for r in rows] == [
        (kyiv(2, 20).isoformat()[:16], kyiv(2, 20, 30).isoformat()[:16]), (kyiv(5, 10).isoformat()[:16], kyiv(5, 11).isoformat()[:16])]


def test_the_stats_count_minutes_alert_by_alert():
    st = two_alerts()
    d = st.stats(14)
    mins = {r["day"]: round(r["minutes"]) for r in d["series"] if r["minutes"]}
    assert sorted(mins.values()) == [30, 60]
    assert round(d["longest"][0]) == 60 and round(d["kyiv_minutes"]) == 90


def test_the_dashboards_minutes_and_lead_times_too():
    st = two_alerts()
    A = st.analytics(14)
    k = {r["date"]: (round(r["city_min"]), r["city_alerts"]) for r in A["kyiv"] if r["city_min"]}
    assert sorted(k.values()) == [(30, 1), (60, 1)]
    assert sum(map(sum, A["starts"])) == 2
    assert st.lead_times(14)["waves"] == 2


def test_a_flicker_of_seconds_is_not_an_alert():
    st = two_alerts()
    city_alert(st, kyiv(3, 12), kyiv(3, 12) + timedelta(seconds=17))
    assert len([a for a in st.alert_rows(kyiv(7, 0)) if a["oblast_uid"] == "31"]) == 2


def test_nothing_reads_the_alerts_table_as_a_history_any_more():
    src = open(os.path.join(os.path.dirname(__file__), "..", "app", "server.py"), encoding="utf-8").read()
    body = src.split("class State", 1)[1]
    assert "self.store.history(days" not in body and "FROM alerts \"\n                                 \"WHERE alert_type='air_raid' AND started_at<?" not in body
    assert body.count("self.alert_rows(") >= 6
