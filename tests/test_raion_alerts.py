"""Official alerts by raion, not by oblast.

On 24 Sep 2026 at 22:07 the government app lifted the alert over Boryspil raion. At 22:21 Heimdall still
showed the whole of Kyiv oblast red, and a person in Vyshenky (Boryspil raion) read "AIR RAID ALERT … since
22:17". Both halves were wrong: the only official source running was the ubilling mirror, which says one thing
per oblast — "something in Kyiv oblast is under alert" (Brovary and Vyshhorod raions, on the yellow drone level)
— and has no start time, so "22:17" was the moment the server rebooted.

The fixture is the real official answer from that evening (a few regions of it)."""
import json
import os
import time

import server

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "ukrainealarm_alerts_2026-09-24.json")


def _src(**cfg):
    st = server.State(server.Store(":memory:"), cfg)
    return st, server.UkraineAlarm(st, cfg)


def _alerts():
    _, ua = _src()
    with open(FIX, encoding="utf-8") as f:
        return {a["location_uid"]: a for a in ua.normalise(json.load(f))}


def test_a_raion_alert_is_a_raion_alert_in_its_oblast():
    a = _alerts()["ua-79"]
    assert a["location_type"] == "raion" and a["oblast_uid"] == "14"
    assert a["location_title"] == "Броварський район"
    assert a["raion_key"] == "brovary"          # the shape on the map it colours, and no other
    assert a["alert_type"] == "air_raid"


def test_the_official_level_and_its_reason_are_kept_word_for_word():
    al = _alerts()
    assert al["ua-79"]["alert_level"] == "yellow"
    assert al["ua-79"]["notes"] == "Дронова загроза (жовтий рівень)"
    assert al["ua-51"]["alert_level"] == "red"   # red and yellow at once: red
    assert al["ua-51"]["notes"].startswith("Ракетна загроза")


def test_the_start_is_the_official_one_not_the_moment_it_was_seen():
    al = _alerts()
    assert al["ua-79"]["started_at"] == "2026-09-24T14:11:44Z"
    # yellow at 16:43, red from 17:08: the alert began at 16:43
    assert al["ua-51"]["started_at"] == "2026-09-24T16:43:03Z"


def test_a_parent_alert_listed_under_a_hromada_stays_with_its_own_region():
    al = _alerts()
    assert al["ua-122"]["location_type"] == "raion" and al["ua-122"]["oblast_uid"] == "22"
    assert al["ua-1313"]["location_type"] == "hromada" and al["ua-1313"]["raion_uid"] == "122"


def test_crimea_and_luhansk_are_oblasts():
    al = _alerts()
    assert al["ua-9999"]["oblast_uid"] == "29" and al["ua-9999"]["location_type"] == "oblast"
    assert al["ua-16"]["oblast_uid"] == "16"


def test_kyiv_oblast_with_two_raions_under_alert_is_partial_not_whole():
    st, ua = _src()
    with open(FIX, encoding="utf-8") as f:
        st.apply_snapshot(ua.NAME, ua.normalise(json.load(f)), {"oblast", "raion", "hromada", "city", "unknown"})
    ob = st.snapshot()["oblasts"]
    assert ob["14"]["status"] == "P"
    assert ob["31"]["status"] == "N"


def test_the_raion_source_takes_back_what_the_mirror_painted():
    """When the raion-level source comes back after standing down, the mirror's whole-oblast alert goes."""
    st, ua = _src()
    mirror = {"key": "ub:14", "source": "ubilling_mirror", "location_uid": "14", "location_title": "Київська область",
              "location_title_en": "Kyiv oblast", "location_type": "oblast", "oblast_uid": "14", "alert_type": "air_raid",
              "alert_level": None, "started_at": server.now_iso(), "finished_at": None, "notes": "", "threats": [], "since_known": False}
    st.apply_snapshot("ubilling_mirror", [mirror], {"oblast"})
    assert st.snapshot()["oblasts"]["14"]["status"] == "A"
    with open(FIX, encoding="utf-8") as f:
        st.apply_snapshot(ua.NAME, ua.normalise(json.load(f)), {"oblast", "raion", "hromada", "city", "unknown"})
    assert st.snapshot()["oblasts"]["14"]["status"] == "P"


def test_a_mirror_alert_with_no_start_time_has_no_since():
    st, _ = _src()
    mirror = {"key": "ub:10", "source": "ubilling_mirror", "location_uid": "10", "location_title": "Житомирська область",
              "location_title_en": "Zhytomyr", "location_type": "oblast", "oblast_uid": "10", "alert_type": "air_raid",
              "alert_level": None, "started_at": server.now_iso(), "finished_at": None, "notes": "", "threats": [], "since_known": False}
    st.apply_snapshot("ubilling_mirror", [mirror], {"oblast"})
    o = st.snapshot()["oblasts"]["10"]
    assert o["status"] == "A" and o["since"] is None


def test_the_mirror_only_stands_in_when_the_raion_source_is_down():
    _, ua = _src()
    assert ua.healthy()                       # just started: the mirror waits instead of painting whole oblasts
    ua.born -= 600
    assert not ua.healthy()                   # never answered in ten minutes: the mirror stands in
    ua.last_ok = time.time()
    assert ua.healthy()


def test_without_a_key_it_reads_the_keyless_proxy_and_with_one_the_api():
    _, ua = _src()
    assert ua.NAME == "ukrainealarm_proxy" and "siren.pp.ua" in ua.base
    _, ua = _src(ukrainealarm_key="k")
    assert ua.NAME == "ukrainealarm" and "api.ukrainealarm.com" in ua.base


def test_an_unknown_region_id_is_kept_not_dropped():
    _, ua = _src()
    out = ua.normalise([{"regionId": "987654", "regionType": "District", "regionName": "Новий район",
                         "activeAlerts": [{"regionId": "987654", "regionType": "District", "type": "AIR",
                                           "lastUpdate": "2026-09-24T19:00:00Z", "activeAlertLevels": []}]}])
    assert len(out) == 1 and out[0]["location_type"] == "raion"


def test_the_test_region_is_ignored():
    _, ua = _src()
    out = ua.normalise([{"regionId": "0", "regionType": "State", "regionName": "Тестовий регіон",
                         "activeAlerts": [{"regionId": "0", "regionType": "State", "type": "AIR", "lastUpdate": "2026-09-24T19:00:00Z"}]}])
    assert out == []


def test_every_raion_around_kyiv_has_an_official_id_and_a_shape():
    uar = server.ua_regions()
    for obl in ("14", "10", "25", "20", "19", "24", "4"):
        ds = [d for d in uar["districts"].values() if d["obl"] == obl]
        assert ds and all(d["key"] for d in ds), obl
    kyiv = {d["key"] for d in uar["districts"].values() if d["obl"] == "14"}
    assert kyiv == {"bila-tserkva", "boryspil", "brovary", "bucha", "vyshhorod", "obukhiv", "fastiv"}


def test_drones_over_an_oblast_with_raion_alerts_only_are_not_pruned():
    st, ua = _src(track_stale_minutes=5)
    with open(FIX, encoding="utf-8") as f:
        st.apply_snapshot(ua.NAME, ua.normalise(json.load(f)), {"oblast", "raion", "hromada", "city", "unknown"})
    from datetime import datetime, timedelta, timezone
    ts = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
    m = {"id": "c#1", "type": "drones", "lon": 31.3, "lat": 51.5, "ts": ts, "channel": "war_monitor", "place": "Чернігів",
         "heading": None, "count": 1, "oblast_uid": "25"}
    assert len(st._chain_and_prune([m], 45)) == 1


def test_yellow_turning_red_on_an_alert_already_on_is_applied_at_once():
    """25 Sep 2026: "we are in red now and it is still yellow here". The level changes on an alert that is
    already running; the snapshot must carry it over, and the source must re-read the full list soon even when
    the change index did not move."""
    st, ua = _src()
    raw = [{"regionId": "31", "regionType": "State", "regionName": "м. Київ", "activeAlerts": [
        {"regionId": "31", "regionType": "State", "type": "AIR", "lastUpdate": "2026-09-25T15:37:39Z",
         "activeAlertLevels": [{"alertLevel": "Yellow", "reason": "Дронова загроза (жовтий рівень)", "createdAt": "2026-09-25T15:37:40Z"}]}]}]
    st.apply_snapshot(ua.NAME, ua.normalise(raw), {"oblast", "raion", "hromada", "city", "unknown"})
    assert st.snapshot()["oblasts"]["31"]["level"] == "yellow"
    raw[0]["activeAlerts"][0]["activeAlertLevels"].append(
        {"alertLevel": "Red", "reason": "Ракетна загроза (червоний рівень)", "createdAt": "2026-09-25T18:30:00Z"})
    st.apply_snapshot(ua.NAME, ua.normalise(raw), {"oblast", "raion", "hromada", "city", "unknown"})
    snap = st.snapshot()
    assert snap["oblasts"]["31"]["level"] == "red"
    assert [a["alert_level"] for a in snap["active"] if a["oblast_uid"] == "31"] == ["red"]
    body = open(server.__file__, encoding="utf-8").read()
    assert "time.time() - self.last_full < 30" in body, "a level change could wait two minutes for the full list"
