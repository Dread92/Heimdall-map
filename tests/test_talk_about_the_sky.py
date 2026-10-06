"""1.41.2: a live tracker talking ABOUT the sky is not a sighting in it.

On 6 Oct 2026, between two waves, @chyste_nebo explained how ballistics works. Its example ("до прикладу —
напрямок Бровари …") became a ballistic missile heading for Brovary, with the region's "shelter now" push; its
description of its own method ("якщо ціль знищена над Києвом …") two shoot-downs. The same night @kyiv_airdef
passed on what the enemy "plans" — and a ballistic missile was drawn at Dnipro. The posts are kept verbatim."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402
import server  # noqa: E402

TALK = [
    ("chyste_nebo", "Поки вас тут багато, я дещо розповім про балістику"),
    ("chyste_nebo", "До прикладу- напрямок Бровари і все що за ними може бути ціль ми не вгадаємо з вами . Бо це може "
                    "бути пряма траєкторія до вишневого або Боярки. Або вона піде кудись в бік. Балістика відносна штука"
                    " . Не чекайте точність як рух метро. Ніхто вам чітко не дасть це.\nЯкщо побачили надпис « Ціль» "
                    "або тривогу дали і написали загроза балістики!!!! Все! Ви вже повинні бути готові. І аж до "
                    "офіційного відбою ви в тонусі!!! Ніхто і ніякий канал вам відбій НЕ ДАЄ!!!"),
    ("chyste_nebo", "І останнє по цій темі. Я описую ціль до зникнення і даю точки ймовірної цілі наперед . Якщо ціль "
                    "знищена над Києвом, а залишкова інерція на моніторі буде йти до Білої Церкви, я буду писати до "
                    "самого кінця поки не зникне."),
]
PLAN = ("kyiv_airdef", "Від 01:30 по 03:00 ворог планує запустити загалом до 40 балістичних ракет по Києву/Київщині, "
                       "Харкову, Дніпрі.")
LIVE = [
    ("chyste_nebo", "Балістика на Київ!", "ballistic_missiles"),
    ("chyste_nebo", "На Бровари", "unknown"),
    ("kyiv_airdef", "Бровари", "unknown"),
    ("chyste_nebo", "Шахед планує на Бровари", "drones"),          # "планує" is also a glide: still a sighting
    ("kpszsu", "🏍 Реактивний БпЛА повз Ірпінь в напрямку Києва.", "drones"),
]


def test_an_example_a_lesson_or_the_channels_method_places_nothing():
    for ch, t in TALK:
        assert geo.parse_for_channel(ch, t) == [], t[:50]
        assert geo.parse_post(t) == [], t[:50]


def test_nor_does_it_raise_anything_or_end_anything():
    for ch, t in TALK:
        tags = server.tag_feed_text(t, ch)
        assert tags == ["news"], (t[:50], tags)                         # no ballistic, no "clear", no "alert"
        assert not server.is_relevant(t, tags, ch)


def test_what_the_enemy_plans_is_a_forecast_not_a_launch():
    ch, t = PLAN
    assert server.tag_feed_text(t, ch) == ["forecast"]
    assert geo.parse_for_channel(ch, t) == []


def test_a_sighting_is_still_a_sighting():
    for ch, t, kind in LIVE:
        ms = geo.parse_for_channel(ch, t)
        assert ms and ms[0]["type"] == kind, (t, ms)
        assert "news" not in server.tag_feed_text(t, ch) and "forecast" not in server.tag_feed_text(t, ch)
