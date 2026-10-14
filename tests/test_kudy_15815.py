"""1.58.15 — a channel for all of Ukraine that writes lists: @kudy_letyt.

The owner: "I added this channel for all of Ukraine as a source and allowed it on the map — however I see it places
nothing". Its posts are lists — an oblast heading, then a target a line, "2х БпЛА курсом на Кременчук" — up to 1,500
characters: read as news by their length alone, they were never stored. And "Новий реактивний БпЛА з Брянщини залітає
на Чернігівщину" placed nothing: "залітає на" was read as where it goes next, not where it is now.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import geo  # noqa: E402
import server  # noqa: E402

LIST = open(os.path.join(os.path.dirname(__file__), "data", "kudy_letyt_123204.txt"), encoding="utf-8").read()


def marks(text, ch="kudy_letyt"):
    return [(m.get("type"), m.get("place"), m.get("oblast_uid")) for m in geo.parse_for_channel(ch, text)]


def test_a_long_list_of_targets_is_stored_and_read_line_by_line():
    assert len(LIST) > geo.NEWS_MAX_CHARS and geo.looks_like_target_list(geo._norm(LIST))
    tags = server.tag_feed_text(server._clean_post(LIST), "kudy_letyt", None)
    assert "news" not in tags and server.is_relevant(LIST, tags, "kudy_letyt")
    got = marks(LIST)
    assert len(got) >= 15
    assert ("drones", "→ Вишгород", "14") in got and ("drones", "→ Кривий Ріг", "9") in got
    assert ("drones", "→ Березівка", "18") in got


def test_an_article_stays_an_article_however_long():
    art = ("Уряд розширив програму страхування воєнних ризиків. " * 20) + "\nБпЛА курсом на Київ"
    assert geo.looks_like_news(geo._norm(art))
    prose = "Вночі ворог атакував. " + "Шахеди летіли над областю, ППО працювала, " * 25
    assert geo.looks_like_news(geo._norm(prose))              # long prose, not a list: news, as before
    assert not geo.looks_like_target_list(geo._norm("Київщина:\nБпЛА курсом на Бучу"))   # too short to be a list


def test_flying_into_an_oblast_is_being_in_it():
    assert marks("Новий реактивний БпЛА з Брянщини залітає на Чернігівщину") == [("drones", "область", "25")]
    assert marks("Реактивний БпЛА залетів на Чернігівщину") == [("drones", "область", "25")]
    assert marks("Група БпЛА залітає на Полтавщину з Сумщини") == [("drones", "область", "19")]   # Poltava, not Sumy
    # leaving for it is still where it goes next (1.45, @controlkrop)
    assert ("drones", "область", "24") not in marks("2 реактивних повз Смоліне вилітають на Черкащину", "controlkrop")


def test_the_oblast_it_flies_along_the_border_of_is_not_where_it_is():
    got = marks("Полтавщина:\n15х БпЛА змійкою по межі з Харківщиною курсують від Чутового до Світлогірського\n"
                "БпЛА курсом на Кременчук")
    assert all(u != "22" for _, _, u in got) and any(u == "19" for _, _, u in got)
