"""Three ways the map once said something that was not true.

Each of these shipped, each was spotted on the live map, and each is the same failure underneath: the app
stated more than its source supported. They are pinned here so they cannot come back quietly.
"""
import geo


def st(text):
    return geo._status_of(geo._norm(text))


def found(text):
    return [n for _, _, n in geo._find_places(geo._norm(text))]


# -- 1. a destroyed building is not an intercepted target ------------------------------------------

def test_a_destroyed_warehouse_is_damage_not_a_shoot_down():
    """"Склад … знищено" drew a green "confirmed shot down" over a strike site — the opposite meaning,
    and it inflated the interception count with somebody's ruined building."""
    assert st("Склад гуманітарного фонду Олени Зеленської у Києві знищено") == "damage"


def test_a_real_shoot_down_is_still_a_shoot_down():
    assert st("Збито ціль над Києвом") == "down"
    assert st("Знищено 12 шахедів на Київщині") == "down"


def test_debris_damaging_a_roof_reads_as_damage_not_an_interception():
    assert st("Внаслідок падіння уламків пошкоджено дах будинку в Оболоні") == "damage"


def test_an_interception_that_also_damaged_something_stays_an_interception():
    assert st("Збито 5 БпЛА, уламки пошкодили будинок") == "down"


def test_a_plain_damage_report_is_damage():
    assert st("У Дніпровському районі пошкоджено скління та фасад офісної будівлі") == "damage"
    assert st("Вибито вікна у кількох житлових будинках") == "damage"


# -- 2. an over-stemmed name is not a match --------------------------------------------------------

def test_kolomak_is_never_read_as_kolomyia():
    """Stemming cut "Коломия" down to "колом", which then swallowed "Коломак" — a different town 700 km
    east, in another oblast. Five Shaheds were drawn over Ivano-Frankivshchyna because of it."""
    assert "Коломия" not in found("Харківщина: 5 БпЛА в районі Котельва - Коломак")


def test_the_towns_that_do_decline_still_resolve():
    """The guard must not cost a single real match."""
    cases = [("БпЛА на Коломию", "Коломия"), ("БпЛА над Фастовом", "Фастів"), ("БпЛА на Броварах", "Бровари"),
             ("У Києві вибух", "Київ"), ("Шахед над Білою Церквою", "Біла Церква"),
             ("Дрон над Кропивницьким", "Кропивницький"), ("БпЛА курсом на Ніжин", "Ніжин"),
             ("Ціль на Бориспіль", "Бориспіль"), ("на Одесу", "Одеса")]
    for text, name in cases:
        assert name in found(text), text


# -- 3. the oblast a marker claims must be the oblast of the place it found -------------------------

def test_a_marker_never_claims_an_oblast_its_own_town_is_not_in():
    """The Kolomyia marker carried Kharkiv's oblast id and Ivano-Frankivsk's coordinates at the same time.
    That contradiction was visible inside the app before it was visible on the map."""
    for text in ["Харківщина: БпЛА на Полтаву", "Полтавщина: ціль на Харків", "Київщина: дрон на Житомир"]:
        for m in (geo.parse_post(text) or []):
            place = (m.get("place") or "").replace("→ ", "")
            if place in geo.PLACES:
                assert m["oblast_uid"] == geo.PLACES[place][2], (text, place, m["oblast_uid"])


# -- 4. a stated part of an oblast is not the oblast centre ----------------------------------------

def test_the_north_of_an_oblast_is_drawn_in_the_north():
    """"Реактивні БпЛА на півночі … Київщини" was dropped on the oblast centre, which for Kyiv oblast sits
    near Vasylkiv — in the south. A quadrant the post states is information; discarding it is the same
    failure as inventing one."""
    centre = [m for m in geo.parse_post("БпЛА над Київщиною") if m["place"] == "область"][0]
    north = [m for m in geo.parse_post("Реактивні БпЛА на півночі у західному напрямку Київщини.")
             if m["place"] == "область"][0]
    assert north["lat"] > centre["lat"] + 0.3
    assert north["evidence"]["position"]["quad"] == "n"


def test_a_course_word_never_moves_the_marker():
    """"у західному напрямку" is where it is going, not where it is. Only locative phrasing counts."""
    assert geo.oblast_quadrant(geo._norm("БпЛА у західному напрямку Київщини")) is None
    assert geo.oblast_quadrant(geo._norm("БпЛА курсом на південь Київщини")) is None


def test_the_quadrant_keeps_its_low_confidence():
    m = [x for x in geo.parse_post("БпЛА на сході Харківщини") if x["place"] == "область"][0]
    assert m["evidence"]["position"]["confidence"] == "low"


# -- 5. a press release is not an observation of the sky -------------------------------------------

NEWS = ("Уряд розширив існуючу програму страхування воєнних ризиків для бізнесу та спростив отримання "
        "компенсацій. Росія щодня цілеспрямовано атакує цивільні підприємства, складські та логістичні "
        "потужності. Бізнес зазнає значних втрат і потребує підтримки для швидкого відновлення. Розширюємо "
        "перелік майна, за пошкодження або знищення якого можна отримати компенсацію. Збільшуємо максимальну "
        "компенсацію страхової премії з 3 до 5 млн грн на рік для одного підприємства. Пільгові кредити тепер "
        "можна буде залучати для відновлення паливної та складської інфраструктури.")


def test_a_government_announcement_never_becomes_a_marker():
    """This one put "damage on the ground" over Kyiv and closed a live Shahed track with it. It is a policy
    announcement about insurance — the words "пошкодження" and "знищення" in it are about compensation."""
    assert st(NEWS) is None
    assert geo.parse_post(NEWS) == []


def test_policy_vocabulary_alone_disqualifies_an_outcome():
    for text in ["Уряд ухвалив постанову про компенсацію за знищене житло",
                 "Кабмін збільшив бюджет на відшкодування за пошкоджені підприємства"]:
        assert st(text) is None, text


def test_a_real_report_is_not_caught_by_the_news_filter():
    """The filter must not cost a single real observation."""
    for text, want in [("Збито ціль над Києвом", "down"),
                       ("Вибух у Києві", "impact"),
                       ("У Дніпровському районі пошкоджено скління та фасад офісної будівлі", "damage"),
                       ("Горить дах будинку в Оболоні", "fire"),
                       ("Київщина чисто", "clear")]:
        assert st(text) == want, text


# -- 6. an article, a fire station, and an oblast that is also a metro station ----------------------

FIRE_STATION = ("Під час робочої поїздки на Олевщину привітав із прийдешнім професійним святом працівників "
                "обласного комунального підприємства «Житомироблагроліс». В Олевську разом із першим "
                "заступником Житомирської обласної ради оглянули нову пожежну станцію. Тут є все необхідне "
                "для роботи — спеціальне спорядження, пожежна техніка, облаштовані приміщення та зона "
                "відпочинку для працівників. Такі умови дозволяють бути готовими до оперативного реагування "
                "на пожежі, особливо в умовах великих лісових масивів Олевщини.")


def test_a_visit_to_a_new_fire_station_is_not_a_fire():
    """The root "пожеж" is in the name of every fire service, engine and brigade in the country. On its own
    it cannot mean something is burning — this post drew a fire marker 9 km from Kyiv."""
    assert st(FIRE_STATION) is None
    assert geo.parse_post(FIRE_STATION) == []


def test_fire_service_vocabulary_alone_is_never_a_fire():
    for text in ["Оглянули нову пожежну станцію, пожежна техніка",
                 "Пожежники працюють у Броварах",
                 "Прибули пожежні розрахунки ДСНС"]:
        assert st(text) != "fire", text


def test_a_post_saying_there_is_no_fire_does_not_draw_one():
    """"Пожежі попередньо немає" drew a fire. And it must not cost the post its damage marker either."""
    text = ("У Дніпровському районі пошкоджені скління та фасад офісної будівлі. У Солом'янському районі "
            "зруйнована складська будівля. Пожежі попередньо немає.")
    assert st(text) == "damage"


def test_a_real_fire_is_still_a_fire():
    assert st("Горить дах будинку в Оболоні") == "fire"
    assert st("Пожежа в Дарницькому районі") == "fire"
    assert st("Внаслідок влучання виникла пожежа на складі") == "impact"


def test_an_oblast_adjective_is_not_the_kyiv_place_of_the_same_name():
    """"Житомирська" is a metro station on Kyiv's red line and also how every post names Zhytomyr oblast.
    Read as the station, a forestry post about Olevsk — 150 km away — planted a marker beside Kyiv."""
    for text in ["Житомирська обласна рада ухвалила рішення", "Житомирська область, відбій тривоги",
                 "Харківська ОВА повідомляє"]:
        assert "Житомирська" not in found(text), text


def test_the_kyiv_place_still_resolves_when_it_is_actually_meant():
    assert "Житомирська" in found("БпЛА на Житомирську")


def test_an_article_produces_no_status_of_any_kind():
    """The news guard now covers every status, not only the two that were caught first."""
    for text in [FIRE_STATION, NEWS]:
        assert st(text) is None, text[:60]


# -- 7. a Banderol is not a Kalibr, and a rocket emoji is not a ballistic missile -------------------

def kinds(text):
    return [m.get("type") for m in (geo.parse_post(text) or [])]


def test_banderol_is_its_own_weapon():
    """The S8000 "Бандероль" is a small jet missile launched from an Orion drone. It was drawn as a cruise
    missile, which folds away a distinction the source made and gives it a Kalibr's speed on the map."""
    assert kinds("Бандероль курсом на Конотоп") == ["banderol_missiles"]
    assert kinds("Бандероль 🚀 →Конотоп/р-н (Сумщина)") == ["banderol_missiles"]


def test_a_bare_rocket_emoji_is_a_missile_not_a_ballistic_one():
    """🚀 alone means "a missile" on these channels. Read as ballistic it handed the loudest treatment in the
    app — white spike, one-second refresh — to an emoji."""
    assert kinds("🚀 на Суми") == ["unspecified_missiles"]


def test_the_named_missiles_are_untouched():
    assert kinds("Крилаті ракети курсом на Одесу") == ["cruise_missiles"]
    assert kinds("Балістика на Київ") == ["ballistic_missiles"]


def test_the_feed_tag_and_the_marker_agree_about_a_banderol():
    """They disagreed before: the tag said cruise while the marker said ballistic, from the same post."""
    import server
    text = "Бандероль 🚀 →Конотоп/р-н (Сумщина)"
    assert "banderol_missiles" in server.tag_feed_text(text, "povitryanatrivogaaa")
    assert kinds(text) == ["banderol_missiles"]


# -- 8. where it IS versus where it is GOING ---------------------------------------------------------

def one(text, channel=None):
    ms = geo.parse_for_channel(channel, text) if channel else geo.parse_post(text)
    assert len(ms) == 1, [m.get("place") for m in (ms or [])]
    return ms[0]


def test_the_next_oblast_on_the_route_is_not_a_position():
    """"3х мгКР Бандероль у напрямку Ніжин. Далі Київщина" — the post says the missiles are heading for
    Nizhyn and will go on into Kyiv oblast. Reading "Київщина" as their position drew a second marker at
    the centre of Kyiv oblast, 150 km from the only place the post actually named."""
    m = one("3х мгКР Бандероль у напрямку Ніжин. Далі Київщина")
    assert (m["lon"], m["lat"]) != (30.3, 50.2)
    assert m["place"] != "область"
    assert "Ніжин" in str(m["place"]) or m.get("target") == "Ніжин"


def test_an_oblast_stated_plainly_is_still_a_position():
    """The guard must only fire on a continuation word — an oblast named on its own still places."""
    m = one("Шахеди на Чернігівщині")
    assert m["place"] == "область"
    assert m["oblast_uid"] == "25"


def test_the_destination_oblast_is_named_not_left_as_neighbouring():
    m = one('🚀 Баражуючий боєприпас "Бандероль" в районі н.п. Бахмач на Чернігівщині, курсом на Київщину.')
    assert m["place"] == "Бахмач" and m["target"] == "область"
    assert m["target_uid"] == "14"          # the map can now say "Kyiv oblast" instead of "neighbouring oblast"


def test_a_side_of_the_oblast_in_an_arrow_line_is_not_the_oblast_centre():
    """"Одещина: ➡️Південь/Одеса" was drawn at the centre of Odesa oblast — 90 km north of the south the
    channel had named, and on the same pixel as every other line of the same shape."""
    m = one("Одещина: ➡️Південь/Одеса", "povitryanatrivogaaa")
    assert m["place"] == "область"
    assert m["evidence"]["position"]["quad"] == "s"
    assert m["lat"] < 46.7 - 0.3


def test_a_town_whose_name_starts_like_a_compass_word_is_not_a_side():
    """Південне is a town, not "the south". Only exact compass words move the marker."""
    m = one("Одещина: ➡️Південне/Одеса", "povitryanatrivogaaa")
    assert m["evidence"]["position"].get("quad") is None


def test_the_arrow_line_keeps_its_oblast_when_it_shares_the_line():
    """The oblast used to count only when it sat on a line of its own ending in ":"."""
    assert geo.parse_for_channel("povitryanatrivogaaa", "Чернігівщина: ➡️Схід/Ніжин")


# -- 9. a heading is not a sighting, and a type belongs to its line ----------------------------------

def places(text, channel=None):
    ms = geo.parse_for_channel(channel, text) if channel else geo.parse_post(text)
    return [(m.get("type"), m.get("place")) for m in (ms or [])]


ERADAR = """🛵 Київщина
- реактивний на Кагарлик
- 7 бандеролей на зону ЧАЕС повз Остер/Десна
🛵 Полтавщина
- реактивний Ромодан"""


def test_an_oblast_heading_does_not_become_a_marker():
    """"🛵 Київщина" on its own line introduces the lines under it. Drawn as a sighting it put a marker on
    the oblast centre — for Kyiv oblast that is near Vasylkiv, 100 km south of the Chornobyl zone the very
    next line was actually about."""
    ms = geo.parse_for_channel("eRadarrua", ERADAR)
    assert not [m for m in ms if m["place"] == "область" and m["oblast_uid"] == "14"]
    # the Poltava line names a village: 1.44, Poltava's villages are read under "Полтавщина" (it used to be the oblast)
    assert not [m for m in ms if m["place"] == "область"]
    assert [(m["place"], m["oblast_uid"]) for m in ms if m["oblast_uid"] == "19"] == [("Ромодан", "19")]


def test_the_weapon_belongs_to_the_line_that_names_it():
    """One "бандеролей" in the post used to retype every line: the jet drone over Kaharlyk became a
    Banderol, which is a different weapon at a different speed."""
    got = dict((p, ty) for ty, p in places(ERADAR, "eRadarrua"))
    assert got["→ Кагарлик"] == "drones"          # "на Кагарлик": heading there, drawn as an approach
    assert got["Остер"] == "banderol_missiles"


def test_a_line_that_names_no_weapon_still_inherits_the_post():
    assert places("БпЛА:\n- на Ніжин\n- на Козелець") == [("drones", "→ Ніжин"), ("drones", "→ Козелець")]


def test_two_oblasts_in_one_sentence_are_two_reports_not_a_heading():
    """"КАБи на Сумщину та Донеччину" is a list. Its second half is a report, not a heading over anything."""
    assert len(places("🚀КАБи на Сумщину та Донеччину.")) == 2


def test_an_oblast_alone_in_a_post_is_still_the_report():
    assert places("🛵 Київщина") == [("drones", "область")]


def test_the_morning_tally_is_never_a_live_position():
    """"В ніч на 17.09 … противник застосував … 8× балістичних ракет по Києву" counts what was fired last
    night. It was drawn as eight ballistic missiles over Kyiv for as long as the post stayed in the feed."""
    assert geo.parse_post(
        "📡 В ніч на 17.09.26 за приблизними оцінками противник застосував для атаки:\n"
        "☄ 8× балістичних ракет по Києву.\n#зведення") == []
    assert places("Балістика на Київ") == [("ballistic_missiles", "→ Київ")]   # a live report is untouched (heading for Kyiv)
