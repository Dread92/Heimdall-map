"""1.58.28 — a target that came into the oblast is at its edge, and a height it could not have reached is not its own.

The owner (15 Oct 2026, 03:19, @chyste_nebo): "there must be an error here" — a Shahed drawn at Lukyanivka, 3 km from
the centre of Kyiv, "300 m → 6.7 km". The channel had written "На Яготин", then "Лукʼянівка зайшов звичайний" (a regular
one came in at Lukyanivka), "300", "6700". It came in — crossed the oblast's edge — so it was the village of Brovary raion,
36 km from Yahotyn, not the Kyiv district; "звичайний" is a Shahed; and no target climbs 6.4 km in ten seconds: "6700" was
another target's height. And "Реактивний на Годунівку", read as a village of Sumy oblast, drew a jet drone at Musiiky —
the channel's last report, 300 km from it.
"""
from datetime import datetime, timedelta, timezone

import geo
import server

NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def _night(posts):
    st = server.State(server.Store(":memory:"), {})
    server.Telegram(st, {}).ingest("chyste_nebo", posts, "tg:chyste_nebo")
    st.markers()
    return {m["id"]: m for m in st.markers()}


NIGHT = [("chyste_nebo/a1", ago(8.0), "Від Пирятина реактивний на Яготин"), ("chyste_nebo/a3", ago(6.2), "На Мусійки"),
         ("chyste_nebo/a5", ago(2.3), "Мусійки"), ("chyste_nebo/a6", ago(2.0), "На Варівськ"),
         ("chyste_nebo/a7", ago(1.4), "Реактивний на Годунівку"), ("chyste_nebo/a8", ago(1.25), "На Яготин"),
         ("chyste_nebo/a9", ago(1.0), "Лукʼянівка зайшов звичайний"), ("chyste_nebo/b1", ago(0.6), "300"),
         ("chyste_nebo/b2", ago(0.45), "6700")]


def test_a_target_that_came_in_is_on_the_oblasts_edge_not_in_kyiv():
    (m,) = geo.parse_for_channel("chyste_nebo", "Лукʼянівка зайшов звичайний")
    keys = [c[0] for c in m["candidates"]]
    assert "Лук'янівка" not in keys and "Лук'янівка (Броварський р-н)" in keys and m["ambiguous"]   # the villages, undecided
    assert m["type"] == "drones" and not m["jet"]                                                # "звичайний": a Shahed
    # the district stays the district for a post that does not say it crossed anything, or says it came into the city
    (d,) = geo.parse_for_channel("chyste_nebo", "лук'янівка")
    assert d["place"] == "Лук'янівка" and not d["ambiguous"]
    (c,) = geo.parse_for_channel("chyste_nebo", "Лукʼянівка зайшов у місто")
    assert c["place"] == "Лук'янівка"
    ms = _night(NIGHT)
    lk = [x for x in ms.values() if str(x.get("place", "")).startswith("Лук'янівка")]
    assert len(lk) == 1 and lk[0]["place"] == "Лук'янівка (Броварський р-н)" and lk[0]["oblast_uid"] == "14"   # by "На Яготин"
    assert not any(x.get("place") == "Лук'янівка" for x in ms.values())


def test_a_height_it_could_not_have_reached_is_not_its_own():
    assert server.alt_reachable(300, 700, 10) and not server.alt_reachable(300, 6700, 10)       # 6.4 km in ten seconds
    assert server.alt_reachable(2200, 800, 15) and not server.alt_reachable(4400, 700, 15)      # a dive, but not 250 m/s
    assert server.alt_reachable(1700, 5400, 120) and not server.alt_reachable(1700, 5400, 41)
    ms = _night(NIGHT)
    (m,) = [x for x in ms.values() if str(x.get("place", "")).startswith("Лук'янівка")]
    assert m["alt"]["m"] == 300 and all(h.get("alt_m") != 6700 for h in m["history"])
    # a new place starts again: its own height is compared with nothing before it
    ms = _night([("chyste_nebo/c1", ago(3), "Бровари"), ("chyste_nebo/c2", ago(2.9), "300"),
                 ("chyste_nebo/c3", ago(2.5), "Калинівка"), ("chyste_nebo/c4", ago(2.4), "6700")])
    assert ms["chyste_nebo/c4#0"]["alt"]["m"] == 6700


def test_a_destination_300_km_away_is_not_the_last_reports_target():
    assert server.DEST_LINK_KM == 150
    ms = _night(NIGHT)
    a7 = ms.get("chyste_nebo/a7#0")
    assert a7 is None or not str(a7.get("place", "")).startswith("Мусійки")
