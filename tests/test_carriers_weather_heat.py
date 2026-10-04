"""1.33: the carriers (MiG-31K, Tu-95/Tu-160, Tu-22M3, the Kalibr ships), the weather of each night, the sides of
Kyiv the drones are reported on, and the time under alert oblast by oblast — on the dashboard and as a heat map on
the Tactical page. Read on real posts of @war_monitor and @kpszsu (tests/fixtures/air_posts_2026.json, each with
what it says, read by hand). And the two live bugs found on the way: a reply read as the message it answers, and a
Tu-160 airbase drawn as a town near Kyiv."""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = json.load(open(os.path.join(ROOT, "tests", "fixtures", "air_posts_2026.json"), encoding="utf-8"))
SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()


def test_what_each_real_post_reports_about_the_carriers():
    wrong = {}
    for pid, c in FIX.items():
        got = sorted(list(x) for x in server.parse_air_report(c["text"]))
        if got != sorted(c["want"]):
            wrong[pid] = (got, c["want"])
    assert not wrong, wrong


def test_a_threat_or_an_expectation_is_never_a_report():
    for text in ("Загроза пусків Х-22/32 для Одещини.", "Якщо будуть пуски КР, то у нашому повітряному просторі ближче до 06:00.",
                 "Може відбутись пуск ракет Х-101 найближчим часом", "Загроза застосування аеробалістичних ракет \"Кинджал\"!",
                 "🟩 Стратегічна авіація не активна.", "Відомо про присутність споряджених 6х бортів Ту-95мс готових до вильоту.",
                 "На вечір / ніч для Одещини загроза Ту-22м3 і відповідно пусків Х-22."):
        assert server.parse_air_report(text) == [], text


def _r(ts, kind, phase, ch="war_monitor", h=None):
    return {"ts": ts, "kind": kind, "phase": phase, "channel": ch, "h": h or f"{ch}{ts}{phase}"}


def test_sorties_one_take_off_many_posts_and_the_delay_to_the_launch():
    reps = [
        _r("2026-09-16T23:03:39Z", "mig31k", "up", "kpszsu", "A"), _r("2026-09-16T23:04:10Z", "mig31k", "up"),
        _r("2026-09-16T23:23:58Z", "mig31k", "end", "kpszsu"),
        _r("2026-09-16T23:24:30Z", "mig31k", "up", "kpszsu", "A"),     # a reply stored with the take-off's text
        _r("2026-09-17T10:22:54Z", "mig31k", "up", "kpszsu", "A"),     # the same words, the next morning: a new take-off
        _r("2026-09-17T10:42:16Z", "mig31k", "end"),
        _r("2026-09-07T17:24:20Z", "strategic", "up"), _r("2026-09-08T00:11:16Z", "strategic", "launch"),
        _r("2026-09-08T01:28:03Z", "kalibr", "launch"), _r("2026-09-08T05:00:00Z", "kalibr", "launch"),
    ]
    so = server.air_sorties(sorted(reps, key=lambda r: r["ts"]))
    mig = [s for s in so if s["kind"] == "mig31k"]
    assert len(mig) == 2 and mig[0]["up_min"] == 20 and mig[0]["reports"] == 3 and mig[0]["launch"] is None
    st = next(s for s in so if s["kind"] == "strategic")
    assert st["delay_min"] == 407 and st["start"].startswith("2026-09-07T17:24")
    assert [s["delay_min"] for s in so if s["kind"] == "kalibr"] == [None, None]    # two salvos, no take-off to count from


def test_a_reply_is_read_as_its_own_text_not_the_message_it_answers():
    block = ('<div class="tgme_widget_message_wrap"><div data-post="kpszsu/78658"><a class="tgme_widget_message_reply">'
             '<div class="tgme_widget_message_text js-message_reply_text">⚠Увага! 🛫Зафіксовано зліт МіГ-31К!</div></a>'
             '<div class="tgme_widget_message_text js-message_text" dir="auto">📢 Відбій небезпеки по МіГ-31К.</div>'
             '<time datetime="2026-09-17T10:42:00+00:00"></time></div>')
    assert server.tg_post_text(block) == "📢 Відбій небезпеки по МіГ-31К."
    assert server.tg_post_text('<div class="tgme_widget_message_text js">x</div>') == "x"
    assert "MSG_RE" not in SRC and SRC.count("tg_post_text(") >= 3            # every t.me/s/ reader uses it


def test_the_carriers_place_no_mark_and_kinzhal_is_ballistic():
    t = "⚠️ Відмічено зліт 4х бортів Ту-95мс з ае \"Оленья\". ⚠️ Також у повітрі 4х борти Ту-160 з \"Українки\"."
    assert geo.parse_for_channel("war_monitor", t) == []                     # Ukrainka, Amur region — not Obukhiv raion
    assert "geo" not in server.tag_feed_text(t, "war_monitor")
    ms = geo.parse_for_channel("war_monitor", "🚀 Кинджал вектор Житомир")
    assert ms and ms[0]["type"] == "ballistic_missiles"
    assert "ballistic_missiles" in server.tag_feed_text("🚀\"Кинджал\" на Чернігівщині в напрямку Київщини!", "kpszsu")


def test_the_nights_weather_from_open_meteo():
    times = [f"2026-09-{d:02d}T{h:02d}:00" for d in (26, 27, 28) for h in range(24)]
    one = {"hourly": {"time": times, "wind_speed_10m": [10.0] * 72, "wind_gusts_10m": [20.0] * 71 + [35.0],
                      "cloud_cover": [50] * 72, "precipitation": [0.1] * 72, "temperature_2m": [4.0] * 72}}
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    got = server.parse_open_meteo([one] * len(server.WEATHER_POINTS), now)
    assert ("2026-09-27", "kyiv") in got and ("2026-09-28", "orel") in got
    assert ("2026-09-26", "kyiv") not in got                                  # its evening is not in the series
    assert ("2026-09-29", "kyiv") not in got                                  # tonight is not over
    assert got[("2026-09-27", "kyiv")] == {"wind": 10.0, "gust": 20.0, "cloud": 50, "precip": 1.2, "tmin": 4.0}
    assert "api.open-meteo.com" in server.Weather.URL and "timezone=Europe%2FKyiv" in server.Weather.URL


def _state():
    return server.State(server.Store(":memory:"), {})


def test_analytics_weather_approach_carriers_and_oblasts():
    st = _state()
    tz = server.kyiv_tz()
    now = datetime.now(timezone.utc)
    d1 = (now.astimezone(tz) - timedelta(days=1)).date()
    st.store.weather_save({(d1.isoformat(), "kyiv"): {"wind": 12.0, "gust": 30.0, "cloud": 80, "precip": 0.0, "tmin": 5.0},
                           (d1.isoformat(), "orel"): {"wind": 20.0, "gust": 40.0, "cloud": 20, "precip": 1.0, "tmin": 2.0},
                           (d1.isoformat(), "kursk"): {"wind": 10.0, "gust": 25.0, "cloud": 40, "precip": 0.0, "tmin": 3.0}})
    a = datetime.combine(d1, datetime.min.time()).replace(hour=2, tzinfo=tz).astimezone(timezone.utc)
    with st.store.lock:
        c = st.store.conn
        # drones at Brovary (east, ~22 km), twice in one post, once at Bila Tserkva (south, ~80 km); Kyiv city is out
        c.executemany("INSERT INTO marker_log(id,ts,post_id,type,status,oblast_uid,lon,lat,pos_conf) VALUES(?,?,?,?,?,?,?,?,?)",
                      [("a", a.isoformat(), "p1", "drones", None, "14", 30.79, 50.51, "high"), ("b", a.isoformat(), "p1", "drones", None, "14", 30.80, 50.52, "high"),
                       ("c", a.isoformat(), "p2", "drones", None, "14", 30.11, 49.80, "high"), ("d", a.isoformat(), "p3", "drones", None, "31", 30.52, 50.45, "high"),
                       ("e", a.isoformat(), "p4", "drones", None, "14", 30.11, 49.80, "low")])
        # alerts: Kharkiv 3 h, closed; an open row a restart left behind (not active) must not count to now
        c.executemany("INSERT INTO alerts(key,source,location_uid,location_title,location_type,oblast_uid,alert_type,alert_level,started_at,finished_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)",
                      [("k1", "t", "ua-22", "Харківська", "oblast", "22", "air_raid", "red", (now - timedelta(hours=5)).isoformat(), (now - timedelta(hours=2)).isoformat()),
                       ("k2", "t", "ua-22-1", "район", "raion", "22", "air_raid", "red", (now - timedelta(hours=4)).isoformat(), (now - timedelta(hours=3)).isoformat()),
                       ("s1", "t", "ua-20", "Сумська", "oblast", "20", "air_raid", "red", (now - timedelta(days=20)).isoformat(), None)])
        c.commit()
    st.store.air_save("war_monitor/1", "war_monitor", (now - timedelta(hours=9)).isoformat(), [("strategic", "up")], "a")
    st.store.air_save("war_monitor/2", "war_monitor", (now - timedelta(hours=7)).isoformat(), [("strategic", "launch")], "b")
    A = st.analytics(7)
    w = next(r for r in A["weather"] if r["date"] == d1.isoformat())
    assert w["kyiv"]["cloud"] == 80 and w["launch"] == {"wind": 15.0, "gust": 40.0, "cloud": 30.0, "precip": 0.5, "tmin": 2.0, "points": 2}
    ap = {r["date"]: r["s"] for r in A["approach"]}
    day = (a.astimezone(tz) + timedelta(hours=6)).date().isoformat()
    assert ap[day][2] == 1 and ap[day][4] == 1 and sum(ap[day]) == 2           # E once (one post), S once; city and "low" out
    assert A["air"]["stats"]["strategic"]["delay_median"] == 120 and A["air"]["stats"]["strategic"]["launched"] == 1
    kh = next(r for r in A["obl"]["rows"] if r["uid"] == "22")
    assert kh["total_h"] == 3.0 and A["obl"]["by"] == "day" and len(A["obl"]["cols"]) == 7
    assert all(r["uid"] != "20" for r in A["obl"]["rows"])                     # the stale open row counts nothing
    json.dumps(A)


def test_the_analytics_cards_and_their_csv():
    assert "csvMore(k,A,tag)" in ADMIN and "an_c_obl" in ADMIN and "an_c_air" in ADMIN
