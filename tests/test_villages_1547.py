"""1.54.7: the villages of Kyiv oblast, a height alone, the physical check, tiles that come back, a replay that says it loads.

The owner (10 Oct 2026, 01:12–01:21, @chyste_nebo): "лук'янівка" was drawn on Lukyanivka in Kyiv — "that's another
Lukyanivka, not a district but a village" — and "Куладинці", "500", "400", "Кулажинці" drew nothing: "this is critical data
and was not displayed on the map". Since 1.54 the AI reads no post, and the villages of Kyiv oblast were the AI's alone.
Then: "a basic physical check — if attaching a new report to a target implies 1,000 km/h, reject the match: 350 km/h for a
Shahed, 650 for jets". And: "one of my users has glitched tiles"; "an obvious loading spinner — people think the feature
simply does not work".
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, SW, REPLAY, DOC, LIGHT = (_read("static/kyiv.html"), _read("static/i18n.js"), _read("static/sw.js"),
                                      _read("static/replay.js"), _read("docs/TECHNICAL.md"), _read("static/light.html"))
NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _state():
    st = server.State(server.Store(":memory:"), {})
    return st, server.Telegram(st, {})


def _places(ch, text):
    return [m.get("place") for m in geo.parse_for_channel(ch, text)]


# ---- the villages of Kyiv oblast ---------------------------------------------------------------------------------------
def test_a_kyiv_tracker_reads_the_villages_of_kyiv_oblast():
    (m,) = geo.parse_for_channel("chyste_nebo", "Кулажинці")
    assert m["place"].startswith("Кулажинці") and m["oblast_uid"] == "14" and abs(m["lon"] - 31.21) < 0.02
    assert _places("kyiv_airdef", "Мощун") == ["Мощун"] and _places("chyste_nebo", "Біля Кулажинців")[0].startswith("Кулажинці")
    # never a word that is also some village's name, and a town of the gazetteer keeps its name
    for w in ("Озеро", "Ферма", "Селище", "Кулі", "Увага", "Виходить", "Знову ? В Чернігівську"):
        assert _places("chyste_nebo", w) == [], w
    assert _places("chyste_nebo", "Калинівка") == ["Калинівка"] and _places("chyste_nebo", "Бровари") == ["Бровари"]


def test_a_kyiv_district_and_a_village_of_its_name_are_candidates():
    (m,) = geo.parse_for_channel("chyste_nebo", "лук'янівка")
    keys = [c[0] for c in m["candidates"]]
    assert m["place"] == "Лук'янівка" and not m["ambiguous"]                         # the district, until something says
    assert keys[0] == "Лук'янівка" and "Лук'янівка (Броварський р-н)" in keys


def _night(st, tg, posts):
    tg.ingest("chyste_nebo", posts, "tg:chyste_nebo")
    st.markers()
    return {m["id"]: m for m in st.markers()}


def test_the_night_of_10_october_is_one_drone_north_east_of_brovary_with_its_height():
    st, tg = _state()
    ms = _night(st, tg, [("chyste_nebo/t1", ago(10), "лук'янівка"), ("chyste_nebo/t2", ago(1.5), "Знову ? В Чернігівську"),
                         ("chyste_nebo/t3", ago(1.4), "Куладинці ❗❗❗"), ("chyste_nebo/t4", ago(1.3), "500"),
                         ("chyste_nebo/t5", ago(1.2), "400"), ("chyste_nebo/t6", ago(1.1), "Увага"), ("chyste_nebo/t7", ago(1.0), "500"),
                         ("chyste_nebo/t8", ago(0.9), "Кулажинці"), ("chyste_nebo/t9", ago(0.8), "Виходить")])
    m = ms["chyste_nebo/t8#0"]
    # the next report (Kulazhyntsi, 9 minutes later) put "лук'янівка" on the village 14 km away, not the Kyiv district 52 km
    assert [h["place"] for h in m["history"]][0] == "Лук'янівка (Броварський р-н)"
    assert m["tag"]["alt"]["m"] == 500 and not m["tag"]["alt"]["cur"]          # the latest stated height, with its age
    assert not any(x.get("place") == "Лук'янівка" for x in ms.values())


def test_a_district_stays_the_district_when_the_channel_was_in_kyiv():
    st, tg = _state()
    ms = _night(st, tg, [("chyste_nebo/u1", ago(4), "Шулявка"), ("chyste_nebo/u2", ago(2), "лук'янівка")])
    m = ms["chyste_nebo/u2#0"]
    assert m["place"] == "Лук'янівка" and m["oblast_uid"] == "31"


def test_a_height_alone_is_the_height_of_the_last_report():
    for t, v in (("500", 500), ("400 м", 400), ("Увага 500", 500), ("500!!", 500)):
        (m,) = geo.parse_for_channel("chyste_nebo", t)
        assert m["height_only"] and m["needs_context"] and m["alt"]["m"] == v and m["lon"] is None, t
    assert geo.parse_for_channel("chyste_nebo", "500 знижується")[0]["alt"]["state"] == "descending"
    for t in ("50", "3х", "12:40", "1200 2", "Увага"):
        assert geo.parse_for_channel("chyste_nebo", t) == [], t
    # with no report of the channel in the last 15 minutes it is nothing at all — a height is never a place
    st, tg = _state()
    assert not [m for m in _night(st, tg, [("chyste_nebo/v1", ago(1), "700")]).values()]
    st, tg = _state()
    ms = _night(st, tg, [("chyste_nebo/w1", ago(20), "Бровари"), ("chyste_nebo/w2", ago(1), "700")])
    assert "chyste_nebo/w2#0" not in ms
    st, tg = _state()
    ms = _night(st, tg, [("chyste_nebo/x1", ago(3), "Бровари"), ("chyste_nebo/x2", ago(1), "700")])
    assert ms["chyste_nebo/x2#0"]["place"] == "Бровари" and ms["chyste_nebo/x2#0"]["alt"]["m"] == 700


# ---- the physical check ----------------------------------------------------------------------------------------------------
def test_two_reports_are_one_target_only_at_a_speed_it_can_fly():
    assert server.VMAX_KMH == {False: 350, True: 650} and server.POS_TOL_KM == 8.0
    assert abs(server.reach_km(10) - (350 / 6 + 8)) < 1e-9 and server.reach_km(60) == 80 and server.reach_km(60, True) == 120
    assert server.reach_km(60, True, cap=False) == 658.0                         # a Banderol: no cap
    def sh(mid, mins, place, **kw):
        lon, lat, uid = geo.PLACES[place]
        m = dict(id=mid, ts=ago(mins), type="drones", status=None, place=place, channel="kyiv_airdef", lon=lon, lat=lat,
                 heading=None, count=1, jet=False, likely=None, origin=None, oblast_uid=uid)
        m.update(kw)
        return m
    # Fastiv → Boiarka, 35 km in 8 minutes: one Shahed. Chernihiv → Kozelets, 65 km in 6 minutes: 650 km/h — not a Shahed;
    # a jet drone, yes
    assert server.State._chain([sh("a/1#0", 20, "Фастів"), sh("a/2#0", 12, "Боярка")])[0]["superseded_by"] == "a/2#0"
    assert not server.State._chain([sh("b/1#0", 8, "Чернігів"), sh("b/2#0", 2, "Козелець")])[0]["superseded_by"]
    j = server.State._chain([sh("c/1#0", 8, "Чернігів", jet=True), sh("c/2#0", 2, "Козелець", jet=True)])
    assert j[0]["superseded_by"] == "c/2#0"
    # the path drawn on the card leaves out the same lines
    assert "return d>(jet?120:80)||d>(jet?650:350)/60*dt+8; };" in PAGE


def test_a_shared_name_the_target_could_not_have_reached_is_not_it():
    # Brovary 5 minutes before: the Lukyanivka village 43 km east would need 520 km/h — the district (22 km) it is
    st, tg = _state()
    ms = _night(st, tg, [("chyste_nebo/y1", ago(7), "Бровари"), ("chyste_nebo/y2", ago(2), "лук'янівка")])
    assert ms["chyste_nebo/y2#0"]["place"] == "Лук'янівка"


# ---- tiles -----------------------------------------------------------------------------------------------------------------
def test_a_tile_that_could_not_be_read_is_never_kept_as_missing(tmp_path):
    p = str(tmp_path / "sat.mbtiles")
    sat = server.SatTiles(p)
    assert sat.lookup(12, 2395, 1386) == (None, None)                          # no file just then: a 503 nobody keeps
    db = sqlite3.connect(p)
    db.executescript("CREATE TABLE metadata (name TEXT, value TEXT); CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER,"
                     " tile_row INTEGER, tile_data BLOB);")
    db.execute("INSERT INTO tiles VALUES (12, 2395, ?, ?)", ((1 << 12) - 1 - 1386, b"RIFF"))
    db.commit()
    db.close()
    sat.checked = 0
    assert sat.lookup(12, 2395, 1386) == (True, b"RIFF") and sat.lookup(12, 2395, 1387) == (False, None)
    src = _read("app/server.py")
    assert 'self.send_response(404 if found is False else 503)' in src and '"public, max-age=86400" if found is False else "no-store"' in src


def test_a_tile_that_did_not_come_is_asked_again_and_the_page_is_never_recoloured():
    assert "if(!ok&&g&&g.id==='sat'){ const n=(+im.dataset.r||0)+1; if(n<=3) setTimeout(" in PAGE and "[2000,8000,30000][n-1]" in PAGE
    assert '<meta name="color-scheme" content="only light">' in PAGE and '<meta name="color-scheme" content="only light">' in LIGHT
    assert "const TILES = 'heimdall-tiles-2';" in SW and SW.count("/^image\\//.test(r.headers.get('content-type') || '')") == 2
    assert "localStorage.getItem('satwarm2')===SAT_V" in PAGE


# ---- the replay says it is loading ----------------------------------------------------------------------------------------
def test_the_replay_shows_a_spinner_while_it_loads():
    assert "function waiting(on){" in REPLAY and REPLAY.count("waiting(") >= 4
    assert '<span class="rpspin" aria-hidden="true"></span>' in REPLAY and "o.setAttribute('role','status')" in REPLAY
    assert ".rpspin{display:inline-block;" in PAGE and "@keyframes rpspin{to{transform:rotate(360deg)}}" in PAGE
    assert "#rpbar.loading .rpctl button,#rpbar.loading .rptrack{opacity:.35;pointer-events:none}" in PAGE
    assert I18N.count("rp_wait:'") == 3


def test_the_docs_tell_it():
    for s in ("Kyiv oblast's villages for the rules (1.54.7)", "reach_km", "A height alone", "heimdall-tiles-2", "rpwait"):
        assert s in DOC, s
