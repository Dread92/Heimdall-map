"""1.43.1: the regional trackers' reports stay on the map.

On 7 October 2026, the evening after 1.43 went out, the Odesa, Kharkiv and Chernihiv trackers were read and parsed, and
almost nothing they reported was drawn. Replayed from the production feed:

- the Kyiv channels, a report a minute, "continued" every regional report within half an hour: bare place names
  ("Васильків увага") are an unspecified threat, chained at missile speed — 15 km a minute, 475 km in 30 minutes — so
  "Перший район Ніжина" became the history of a target at Vasylkiv, and an Odesa village one of Kyiv's;
- a report naming no town ("БпЛА на Харківщині", drawn at the oblast centre) swallowed "Реактивный Шахед на Змиев"
  and took over "Акустика … над Харьковом";
- a regional tracker posts every five to twenty minutes, and a report was gone after five (unspecified) or fifteen.

And three misreadings: "Акустика нашего БпЛА над Харьковом" (our own drone) as a Shahed over Kharkiv, "По этому отбой
будет" as the village Будеї, "З брянської новий буде" as Нова Буда.
"""
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8") as f:
    PAGE = f.read()


def _run(posts):
    """posts: (channel, minutes ago, text). The marks the map gets now."""
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    rows = [{"post_id": f"{ch}/{9000 + i}", "channel": ch, "ts": (now - timedelta(minutes=ago)).isoformat(timespec="seconds"),
             "text": text, "tags": server.tag_feed_text(text, ch), "text_en": text, "en_fallback": True}
            for i, (ch, ago, text) in enumerate(posts)]
    st.store.add_feed(rows)
    return st.markers()


def _by(ms, ch):
    return [m for m in ms if m["channel"] == ch]


def test_kyivs_bare_place_names_do_not_take_over_an_odesa_or_chernihiv_report():
    ms = _run([("monitoringodesa", 6, "Демидово"), ("chernihiv_nebo", 6, "Перший район Ніжина"),
               ("chyste_nebo", 4, "Ірпінь увага"), ("kyiv_airdef", 3, "Буча"), ("chyste_nebo", 1, "Васильків")])
    assert [m["place"] for m in _by(ms, "monitoringodesa")] == ["Демидове"]
    assert [m["place"] for m in _by(ms, "chernihiv_nebo")] == ["Ніжин"]
    for m in ms:                                                 # no Kyiv track carries them in its history
        assert all(h["channel"] in ("chyste_nebo", "kyiv_airdef") for h in m.get("history") or [])


def test_another_channel_continues_a_track_only_within_fifteen_minutes():
    ms = _run([("chernihiv_nebo", 22, "1 реакт біля Бобровиці"), ("kyiv_airdef", 5, "1 реакт біля Бобровиці")])
    # 17 minutes apart: two reports, the older one kept by its own (regional) clock
    assert {m["channel"] for m in ms} == {"chernihiv_nebo", "kyiv_airdef"}
    same = _run([("chernihiv_nebo", 10, "1 реакт біля Бобровиці"), ("kyiv_airdef", 2, "1 реакт біля Бобровиці")])
    assert len(same) == 1 and same[0]["channel"] == "kyiv_airdef" and same[0]["history"][0]["channel"] == "chernihiv_nebo"


def test_a_report_naming_only_the_oblast_never_takes_over_or_swallows_a_place():
    ms = _run([("kpszsu", 6, "БпЛА на Харківщині"), ("radar_kharkov", 4, "Реактивный Шахед на Змиев")])
    kh = _by(ms, "radar_kharkov")
    assert [m["place"] for m in kh] == ["→ Зміїв"]
    ms = _run([("radar_kharkov", 6, "БпЛА через Пятихатки на Жуковский"), ("kpszsu", 2, "БпЛА на Харківщині")])
    assert [m["place"] for m in _by(ms, "radar_kharkov")] == ["П'ятихатки (Харківський р-н)"]
    for m in ms:
        assert all(h.get("place") != "область" for h in m.get("history") or [])


def test_a_regional_trackers_report_keeps_longer_than_a_kyiv_channels():
    ms = _run([("radar_kharkov", 12, "БпЛА через Пятихатки на Жуковский"), ("chyste_nebo", 12, "2 шахеди Бровари")])
    kh = _by(ms, "radar_kharkov")
    assert len(kh) == 1 and kh[0]["stale"] == 12 and kh[0]["slow"] is True
    assert _by(ms, "chyste_nebo")[0]["stale"] == 12 and not _by(ms, "chyste_nebo")[0].get("slow")
    ms = _run([("radar_kharkov", 20, "БпЛА через Пятихатки на Жуковский"), ("chyste_nebo", 20, "2 шахеди Бровари")])
    assert [m["channel"] for m in ms] == ["radar_kharkov"]         # Kyiv's: gone after 15 min; the tracker's: 25
    assert not _run([("radar_kharkov", 30, "БпЛА через Пятихатки на Жуковский")])
    # an unspecified threat from a tracker: until its stale time, then gone
    assert [m["place"] for m in _run([("monitoringodesa", 8, "Демидово")])] == ["Демидове"]
    assert not _run([("monitoringodesa", 12, "Демидово")])
    assert server.REGIONAL_STALE_MIN == 10 and server.REGIONAL_GONE_MIN == 25
    # the page fades it on the same clock
    assert "m.stale >= (m.slow?20:" in PAGE and "m.stale>=(m.slow?15:8)" in PAGE and "m.stale>=(m.slow?20:11)" in PAGE


def test_our_own_drone_is_no_target():
    for ch, text in (("radar_kharkov", "Акустика нашего БпЛА над Харьковом"),
                     ("monitoringodesa", "Если вы слышите звук реактивного в городе\nТо наш!!!"),
                     ("kyiv_airdef", "Над Броварами працює наш дрон")):
        assert geo.parse_for_channel(ch, text) == [], text
        assert server.tag_feed_text(text, ch) == [] and not server.is_relevant(text, [], ch), text
    # the rest of a post stays, and "наші ППО" is still a report
    ms = geo.parse_for_channel("radar_kharkov", "Акустика нашего БпЛА над Харьковом. Шахед на Змиев")
    assert [m["place"] for m in ms] == ["→ Зміїв"]
    assert geo.parse_for_channel("kyiv_airdef", "Вибухи — це наші ППО працюють")


def test_the_kharkiv_tracker_losing_a_target_ends_its_track():
    for text in ("Без фиксации", "Больше не фиксируется", "Більше не фіксується"):
        ms = geo.parse_for_channel("radar_kharkov", text)
        assert [m["status"] for m in ms] == ["lost"], text


def test_everyday_words_are_not_villages():
    for ch, text in (("monitoringodesa", "По этому отбой будет"), ("chernihiv_nebo", "З брянської новий буде."),
                     ("monitoringodesa", "Жовтий рівень"), ("chernihiv_nebo", "Червоний рівень загрози")):
        assert geo.parse_for_channel(ch, text) == [], text
    # an oblast's adjective is not the village named after the oblast
    assert all(m["place"] != "Київське" for m in geo.parse_for_channel("RadarDnepr", "Київська область, 2 шахеди"))
    assert [m["place"] for m in geo.parse_for_channel("RadarDnepr", "1 шахед на Київське")] == ["→ Київське (Синельниківський р-н)"]


def test_a_town_of_the_next_oblast_over_a_hamlet_of_the_same_name():
    m = geo.parse_for_channel("chyste_nebocherkasy", "На Таращу")[0]
    assert m["place"] == "→ Тараща" and m["oblast_uid"] == "14"
    assert [c[0] for c in m["candidates"]] == ["Тараща", "Тараща (Звенигородський р-н)"] and not m["ambiguous"]
    m = geo.parse_for_channel("chernihiv_nebo", "Київська область, 1 реакт на Оболонь")[0]
    assert m["place"] == "→ Оболонь" and m["oblast_uid"] == "31"


def test_the_kharkiv_trackers_short_name_for_velyka_danylivka():
    m = geo.parse_for_channel("radar_kharkov", "БпЛА от Даниловки на 524 район")[0]
    assert m["place"] == "Велика Данилівка" and m["oblast_uid"] == "22"
