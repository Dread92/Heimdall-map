"""1.32: the Air Force's summaries, type by type, kept for good. Read on the real summaries of 21–28 Sep 2026
(tests/fixtures/af_summaries_2026_09.json, @kpszsu). From 25 Sep they were read as news and dropped, so the
statistics lost them; and missiles were never counted, because the Air Force names most of them without a number
("балістичними ракетами Іскандер-М …") and gives the number only for the ones shot down."""
import json
import os
from datetime import datetime, timedelta, timezone

import server

FIX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "af_summaries_2026_09.json"), encoding="utf-8"))


def rep(pid):
    ts, text = FIX[pid]
    return server.parse_af_report(text, ts)


def test_every_weapon_type_launched_and_shot_down():
    r = rep("79455")                                   # night of 22 Sep: a list, missiles with and without numbers
    assert (r["period"], r["date"]) == ("night", "2026-09-22")
    assert r["launched"] == {"cruise": 4, "banderol": 8, "drones": 212}
    assert {"ballistic", "antiship"} <= set(r["used"])          # used, no number given — never counted as 0
    assert r["down"] == {"cruise": 1, "banderol": 8, "drones": 177, "total": 186}
    assert r["impacts"] == 22 and r["debris"] == 4
    assert r["directions"] == ["Дніпропетровщина", "Кіровоградщина", "Полтавщина"]
    assert "Калібр" in r["models"] and "Онікс" in r["models"]
    r = rep("79861")                                   # 24 Sep: the missiles only in the shot-down list
    assert r["down"]["ballistic"] == 3 and r["down"]["antiship"] == 4 and r["down"]["total"] == 227
    assert "ballistic" in r["used"] and "Циркон" in r["models"]


def test_jet_drones_night_and_day_areas():
    r = rep("80852")
    assert (r["period"], r["date"], r["launched"], r["down"]["total"]) == ("night", "2026-09-28", {"drones": 165, "jet": 79}, 112)
    assert r["areas"] == ["Орел", "Міллерово", "Приморсько-Ахтарськ", "Шаталово", "Донецьк", "Гвардійське"]
    r = rep("81127")
    assert (r["period"], r["date"]) == ("day", "2026-09-28")
    assert r["launched"] == {"drones": 124, "jet": 86} and r["down"] == {"drones": 86, "jet": 49, "total": 86}
    assert rep("81106") is None                        # "продовжує атакувати": an update, not a summary


def test_a_summary_is_kept_never_read_as_news_nor_as_a_live_threat():
    for pid in FIX:
        if pid == "81106":
            continue
        tags = server.tag_feed_text(FIX[pid][1], "kpszsu")
        assert tags == ["af_summary"], (pid, tags)     # not "news" (dropped), not "ballistic_missiles" (a banner)
        assert server.is_relevant(FIX[pid][1], tags, "kpszsu")


def test_one_report_per_night_the_statistics_and_the_backfill():
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    # the same night's summary from the Air Force and a re-post: the Air Force's own is the one kept
    t = FIX["80852"][1]
    ts = (now - timedelta(hours=10)).isoformat()
    st.store.af_save("war_monitor/1", "war_monitor", ts, server.parse_af_report(t, ts))
    st.store.af_save("kpszsu/80852", "kpszsu", ts, server.parse_af_report(t, ts))
    reps = st.store.af_reports()
    assert len(reps) == 1 and reps[0]["post"] == "kpszsu/80852"
    ts2 = (now - timedelta(hours=3)).isoformat()
    st.store.af_save("kpszsu/79455", "kpszsu", ts2, server.parse_af_report(FIX["79455"][1], ts2))
    w = st.stats(14)["windows"]["1"]
    assert w["summaries"] == 2 and w["launched_drones"] == 165 + 212 and w["launched_missiles"] == 4
    assert w["af"]["down"]["cruise"] == 1 and "ballistic" in w["af"]["used"]
    # a type counted in one summary and named without a number in another is a floor, not a total
    ts3 = (now - timedelta(hours=2)).isoformat()
    st.store.af_save("kpszsu/x", "kpszsu", ts3, {"period": "day", "date": "2099-01-01", "launched": {"ballistic": 2}, "down": {}, "used": []})
    st._stats_res.clear()
    w = st.stats(14)["windows"]["1"]
    assert w["af"]["launched"]["ballistic"] == 2 and "ballistic" in w["af"]["partial"] and "ballistic" not in w["af"]["used"]
    # the history backfill: pages of t.me/s/kpszsu, summaries only
    page = "".join(f'<div class="tgme_widget_message_wrap"><div data-post="kpszsu/{pid}"><div class="tgme_widget_message_text js">'
                   f'{FIX[pid][1].replace(chr(10), "<br>")}</div><time datetime="{FIX[pid][0]}"></time></div>'
                   for pid in ("80051", "80253", "81106"))
    calls = []
    old = server.http_get
    server.http_get = lambda url, h=None, timeout=20: (calls.append(url), (200, {}, page.encode()))[1]
    try:
        b = server.AFBackfill(st)
        b.MAX_PAGES = 2
        # the fixture's posts are from late September 2026: the window reaches back to them whatever today is (1.57.8 —
        # with the default 14 days the test stopped after one page from 12 October on)
        b.DAYS = (datetime.now(timezone.utc) - datetime(2026, 9, 20, tzinfo=timezone.utc)).days + 1
        assert b.from_history() == 2                   # two summaries; the update (81106) is not one
    finally:
        server.http_get = old
    assert calls[0] == "https://t.me/s/kpszsu" and "before=80051" in calls[1]
