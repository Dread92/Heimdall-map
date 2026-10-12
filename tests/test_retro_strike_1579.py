"""1.57.9 — a strike told after it happened is no threat; the Air Force's flash report is no total.

The owner (a screenshot: ballistic missiles over Kyiv, "launch completed", 23:48): "encore une news détectée comme une
menace". The Air Force at 23:48: "❗️О 22.10 ворог завдав удару по столиці попередньо 6-ма балістичними ракетами … Інформації
щодо пусків з території противника не поступало … Крім того, противник атакував Харків 9-ма баражуючими боєприпасами
S-8000 «Бандероль»". The feed had tagged it the Air Force's summary; the marks had not listened, and every Kyiv channel
that relayed it drew the same missiles. Its figures were stored as 8,000 Banderols launched.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import geo  # noqa: E402
import server  # noqa: E402

FIX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "af_flash_2026_10_12.json"), encoding="utf-8"))
TEXT = FIX["text"]


def test_the_flash_report_draws_nothing_whoever_posts_it():
    for ch in ("kpszsu", "kievinfo_kyiv", "kyiv_airdef", "chyste_nebo", "vseok450", "povitryanatrivogaaa", "war_monitor"):
        assert geo.parse_for_channel(ch, TEXT) == [], ch
    assert server.tag_feed_text(TEXT, "kpszsu") == ["af_summary"]
    assert server.tag_feed_text(TEXT, "kievinfo_kyiv") == ["news"]
    # the live map's own reading of the posts, the Air Force's guard included
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    assert st._marks_from_posts([dict(FIX)], [], {}) == []


def test_a_strike_told_after_it_happened():
    for t in ("О 22.10 ворог завдав удару по столиці балістичними ракетами",
              "Ворог завдав масованого удару по Харкову ракетами",
              "Об 01:40 противник атакував Київ балістикою"):
        assert geo.looks_like_summary(t), t
    # what flies now is still read
    assert [m["type"] for m in geo.parse_for_channel("kpszsu", "🚀 Швидкісна ціль на Київ")] == ["ballistic_missiles"]
    assert geo.parse_for_channel("kpszsu", "Балістика з Брянщини! Загроза для Києва")
    assert geo.parse_for_channel("kyiv_airdef", "Шахед курсом на Бровари")


def test_its_figures_are_its_own_and_kept_apart():
    rep = server.parse_af_report(TEXT, FIX["ts"])
    assert rep["period"] == "flash" and rep["launched"] == {"ballistic": 6, "banderol": 9}
    # a model's number is no count: "S-8000 «Бандероль»", "Х-101"
    assert server._af_counts("9-ма баражуючими боєприпасами S-8000 «Бандероль»")[0] == {"banderol": 9}
    assert "flash" not in server.AF_TOTAL_PERIODS
    # never added to a week's totals — the night's summary counts the same missiles in the morning
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    now = datetime.now(timezone.utc)
    st.store.af_save("kpszsu/flash", "kpszsu", (now - timedelta(hours=1)).isoformat(), rep)
    st.store.af_save("kpszsu/night", "kpszsu", (now - timedelta(hours=2)).isoformat(),
                     {"period": "night", "date": rep["date"], "launched": {"drones": 100, "ballistic": 2}, "down": {}, "used": []})
    w = st.stats(14)["windows"]["1"]
    assert w["summaries"] == 1 and w["launched_drones"] == 100 and w["af"]["launched"].get("ballistic") == 2
    a = st.analytics(7)
    assert not any((d.get("launched") or {}).get("banderol") for d in a.get("af", a.get("af_days", [])) if isinstance(d, dict))


def test_a_stored_report_is_read_again_once():
    s = server.Store(":memory:")
    s.add_feed([{"post_id": FIX["post_id"], "channel": "kpszsu", "ts": FIX["ts"], "text": TEXT, "tags": ["af_summary"]}])
    s.af_save(FIX["post_id"], "kpszsu", FIX["ts"], {"period": "other", "date": "2026-10-12", "launched": {"banderol": 8000}, "down": {}, "used": []})
    assert s.af_reparse() == 1
    r = [x for x in s.af_reports("2026-10-01") if x["post"] == FIX["post_id"]][0]
    assert r["period"] == "flash" and r["launched"] == {"ballistic": 6, "banderol": 9}
    assert s.af_reparse() == 0                                       # once per AF_PARSE_V


def test_no_word_of_a_launch_is_no_launch_and_the_capital_is_kyiv():
    assert geo.detect_phase("Інформації щодо пусків з території противника не поступало", "ballistic_missiles") is None
    assert geo.detect_phase("пусків не зафіксовано", "cruise_missiles") is None
    assert geo.detect_phase("Пуск балістики з Брянщини!", "ballistic_missiles") == "launch"
    # "столиця" is Kyiv named and no place in it: the city is marked, not a point; a course to it is a course to Kyiv
    assert [(m["place"], m["oblast_uid"]) for m in geo.parse_for_channel("kyiv_airdef", "Шахед над столицею")] == [("область", "31")]
    assert [m["place"] for m in geo.parse_for_channel("kyiv_airdef", "Балістика на столицю!")] == ["→ Київ"]
