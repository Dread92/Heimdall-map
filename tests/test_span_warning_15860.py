"""1.58.60 — a warning for the next 24 hours is no ballistic missile.

@kyiv_airdef, 27 Oct 2026, 13:15: "дали попередження на 24 години щодо застосування ворогом балістичного озброєння по м.
Київ та Київщині" — the monitoring channels' notice that ballistic missiles may be used against Kyiv some time in the next
day. It was tagged ballistic_missiles, drawn as two ballistic missiles (Kyiv, Kyiv oblast) and lit the ballistic strip; the
owner: "flagged wrongly as a ballistic threat". A warning that spans hours or days is a forecast: its sentence places
nothing and raises nothing — the post stays in the feed, as a warning. What else the post says is read as before.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import ai_reader  # noqa: E402
import geo  # noqa: E402
import server  # noqa: E402
import translate  # noqa: E402

POST = "дали попередження на 24 години щодо застосування ворогом балістичного озброєння по м. Київ та Київщині"
AHEAD = [
    POST,
    "❗️Моніторингові канали дали попередження на 24 години щодо застосування ворогом балістичного озброєння по м. Київ та Київщині.",
    "Протягом доби існує загроза застосування балістичного озброєння по Києву та області",
    "Найближчу добу можлива масована атака з застосуванням балістики по столиці",
    "Попередження на 48 годин: ймовірні удари балістикою по Київщині",
    "У найближчі дні ймовірна комбінована атака на Київ",
    "Предупреждение на 24 часа по баллистике на Киев",
]
CHANNELS = ("kyiv_airdef", "chyste_nebo", "kievinfo_kyiv", "war_monitor")


def test_the_post_places_nothing_and_raises_nothing():
    for ch in CHANNELS:
        assert geo.parse_for_channel(ch, POST) == [], ch
        tags = server.tag_feed_text(POST, ch)
        assert tags == ["alert", "forecast"], (ch, tags)                   # no ballistic_missiles: no strip, no push
        # a tracker's warning stays in the feed, as a warning; a news channel keeps live reports only, as before
        assert server.is_relevant(POST, tags, ch) is (ch not in server.NEWS_CHANNELS), ch
    assert geo.parse_post(POST) == []


def test_other_wordings_of_a_warning_for_hours_or_days():
    for t in AHEAD:
        assert geo.drop_span_warnings(t) == "", t
        for ch in CHANNELS:
            assert geo.parse_for_channel(ch, t) == [], (ch, t)
            assert "ballistic_missiles" not in server.tag_feed_text(t, ch), (ch, t)


def test_only_its_sentence_a_missile_in_the_same_post_still_warns():
    t = "Балістика на Київ! Попередження на 24 години продовжено."
    assert geo.drop_span_warnings(t) == "Балістика на Київ!"
    ms = geo.parse_for_channel("chyste_nebo", t)
    assert ms and ms[0]["type"] == "ballistic_missiles"
    assert "ballistic_missiles" in server.tag_feed_text(t, "chyste_nebo")


def test_what_is_in_the_sky_is_not_a_warning_ahead():
    live = [("chyste_nebo", "Балістика на Київ!", "ballistic_missiles"),
            ("kyiv_airdef", "Пуск балістики з Брянщини, на 24 години не прогнозуємо — летить на Київ", "ballistic_missiles"),
            ("kyiv_airdef", "Шахед на Бровари, на 3 годину ночі очікуємо ще", "drones")]
    for ch, t, kind in live:
        ms = geo.parse_for_channel(ch, t)
        assert ms and ms[0]["type"] == kind, (t, ms)
    # minutes are not hours ahead, and a time of day is no span
    for t in ("В найближчі 10 хвилин можливий пуск балістики", "Шахед на Бровари, на 3 годину ночі очікуємо ще",
              "Тривога триває вже 3 години", "Бровари. Ще 2 години можливі шахеди"):
        assert geo.drop_span_warnings(t) == t, t


def test_a_sentence_ends_where_it_ends():
    assert geo._sentences("Шахед н.п. Гребінка. Далі на м. Бровари! о 12.30 t.me/x ок") == \
        ["Шахед н.п. Гребінка.", " Далі на м. Бровари!", " о 12.30 t.me/x ок"]
    # "по м. Київ" did not cut the post in two: " Київ та Київщині" alone would have been a place report
    assert len(geo._sentences(POST)) == 1


def test_the_city_administrations_day_notice_is_not_this_alerts_threat():
    assert geo.parse_kmda("Протягом доби існує загроза застосування балістичного озброєння по Києву") is None
    r = geo.parse_kmda("Загроза застосування балістичного озброєння!")
    assert r["kind"] == "threat" and r["threats"][0]["threat_type"] == "ballistic_missiles"


def test_the_ai_reader_is_told_the_same_and_the_feed_reads_it_in_english():
    assert '"попередження на 24 години щодо застосування балістики"' in ai_reader.SYSTEM and ai_reader.PROMPT_VERSION == "6"
    assert translate.translate_offline(POST) == \
        "A warning was issued for 24 hours regarding the enemy's use of ballistic weapons on Kyiv and Kyiv region"


# ---- 1.58.61: tonight -----------------------------------------------------------------------------------------------
# 27 Oct, 16:59, relayed by the trackers; the ballistic strip for 25 minutes, the afternoon before the night it warned of
# (the owner: "again, it's a news"). Its second paragraph is last night's count.
TONIGHT = ("❗️Отримано попередження про повторну загрозу застосування балістичного озброєння по обʼєктах у Києві та "
           "Київській області цієї ночі.\n\nВночі було застосовано лише 16 з майже 60 готових до застосування балістичних "
           "ракет. Жодного «Циркона» застосовано не було.")


def test_a_warning_for_tonight_and_last_nights_count_raise_nothing():
    for ch in CHANNELS + ("eRadarrua", "kpszsu"):
        assert geo.parse_for_channel(ch, TONIGHT) == [], ch
        tags = server.tag_feed_text(TONIGHT, ch)
        assert tags == ["alert", "forecast"], (ch, tags)
    assert server.is_relevant(TONIGHT, ["alert", "forecast"], "kyiv_airdef")
    assert geo.looks_like_summary(geo._norm("Вночі було застосовано лише 16 з майже 60 готових до застосування балістичних ракет."))
    for t in ("Попередження: сьогодні вночі ймовірна масована атака на Київ",
              "Протягом ночі можливі повторні удари балістикою по столиці, будьте уважні",
              "Прогноз на наступну ніч: очікується комбінований удар"):
        assert geo.drop_span_warnings(t) == "", t
        assert "ballistic_missiles" not in server.tag_feed_text(t, "kyiv_airdef"), t


def test_tonight_alone_or_a_target_in_the_sentence_is_still_read():
    # no word of notice: in the night itself it may be the threat of the moment
    t = "Загроза балістики цієї ночі для Києва"
    assert geo.drop_span_warnings(t) == t and "ballistic_missiles" in server.tag_feed_text(t, "chyste_nebo")
    for t in ("Шахеди на Бровари, цієї ночі очікуємо ще", "1 на Яготин, протягом доби можливі ще",
              "Реактивний курсом на Київ, найближчу добу можливі нові"):
        assert geo.drop_span_warnings(t) == t, t
        assert geo.parse_for_channel("kyiv_airdef", t), t
    en = translate.translate_offline(TONIGHT)
    assert en.startswith("❗️A warning was received about repeated threat of the use of ballistic weapons") and "tonight" in en
