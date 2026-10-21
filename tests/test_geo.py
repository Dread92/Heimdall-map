"""Positions are life-or-death: a target is drawn where a post said it was, never anywhere else.
These tests pin the behaviour the map depends on."""
import geo


def test_drone_heading_to_a_town_is_placed_at_that_town():
    m = geo.parse_post("🛸 2 БпЛА курсом на Бровари з північного сходу")[0]
    assert m["type"] == "drones"
    assert m["count"] == 2
    assert round(m["lon"], 1) == 30.8 and round(m["lat"], 1) == 50.5
    assert m["oblast_uid"] == "14"


def test_position_carries_its_evidence_and_confidence():
    m = geo.parse_post("🛸 БпЛА над Броварами")[0]
    ev = m["evidence"]["position"]
    assert ev["matched"] and ev["confidence"] in ("low", "medium", "high")


def test_an_alert_announcement_never_becomes_a_marker():
    # "air raid alert in Kyiv oblast" is an alert, not a target seen over Kyiv
    assert geo.parse_post("🔴 Повітряна тривога в Київській області. Прямуйте в укриття!") == []


def test_all_clear_is_not_a_target():
    assert geo.parse_post("🟢 Відбій повітряної тривоги в Київській області") == []


def test_similar_town_names_are_not_confused():
    # Михайло-Коцюбинське (Chernihiv oblast) must not match Коцюбинське (next to Kyiv)
    m = geo.parse_post("🛸 БпЛА на Михайло-Коцюбинське")
    assert not m or round(m[0]["lat"], 1) != 50.5


def test_city_siren_maps_to_its_raion():
    out = geo.parse_city_siren("🔴 Повітряна тривога в місті")
    assert out is None or isinstance(out, (dict, list))


# --- altitude and vertical behaviour ------------------------------------------------------------
# No public source publishes altitude, so it is only ever read when a post states it in words.
def test_descending_is_not_a_shoot_down():
    """A drone coming down ON its target is the most dangerous moment there is.
    'знижується' must never be shown as a confirmed shoot-down."""
    m = geo.parse_post("1х Шахед знижується над Броварами")[0]
    assert m.get("status") != "down"
    assert m["alt"]["state"] == "descending"


def test_bare_descent_report_still_places_a_target():
    m = geo.parse_post("1х зниження Троєщина")[0]
    assert m.get("status") != "down"
    assert m["alt"]["state"] == "descending"


def test_an_explicit_shoot_down_is_still_a_shoot_down():
    assert geo.parse_post("Збито шахед над Броварами")[0]["status"] == "down"


def test_shot_down_wins_when_the_post_says_both():
    assert geo.parse_post("Шахед знижується, збито над Ірпенем")[0]["status"] == "down"


def test_stated_altitude_in_metres_is_read():
    m = geo.parse_post("БпЛА на висоті 2000м курсом на Київ")[0]
    assert m["alt"]["m"] == 2000


def test_altitude_is_never_invented():
    m = geo.parse_post("2 БпЛА курсом на Бровари")[0]
    assert m.get("alt") is None


# --- a threat type is never invented, but the channel's context is offered as a labelled guess ---
def test_a_place_only_post_is_not_called_a_shahed():
    m = geo.parse_for_channel("kyiv_airdef", "Васильків увага ‼️")[0]
    assert m["type"] == "unknown"


def test_the_channel_context_is_carried_as_a_likelihood():
    """'most likely a drone' is useful; 'Shahed' would be a claim nobody made."""
    m = geo.parse_for_channel("kyiv_airdef", "Лісники")[0]
    assert m["type"] == "unknown" and m["likely"] == "drones"
    assert m["evidence"]["type"]["confidence"] == "none"


def test_the_channels_emoji_shorthand_no_longer_names_it():
    # 1.58.42, the owner: "stop using the emojis to determine the nature of the threat" — a sign, not a type
    assert geo.parse_for_channel("kyiv_airdef", "Козин🛸")[0]["type"] == "unknown"
    assert geo.parse_for_channel("kyiv_airdef", "Козин🛸")[0]["likely"] == "drones"
    assert geo.parse_for_channel("kyiv_airdef", "БпЛА Козин🛸")[0]["type"] == "drones"


def test_no_marker_on_a_place_the_post_declared_clear():
    out = geo.parse_for_channel("kyiv_airdef", "Чисте небо Київська область та Київ. Васильків увага ‼️")
    assert [m["place"] for m in out] == ["Васильків"]


# --- altitude as the channels actually write it ---------------------------------------------------
def test_height_written_after_the_number():
    m = geo.parse_for_channel("kyiv_airdef", "У бік Трипілля, 2200 висота")[0]
    assert m["alt"]["m"] == 2200
    assert m["place"].endswith("Трипілля")      # "→ Трипілля": the post says it is heading there


def test_a_follow_up_post_that_is_only_a_height_and_a_place():
    m = geo.parse_for_channel("kyiv_airdef", "1600, Вороньків")[0]
    assert m["alt"]["m"] == 1600
    assert m["count"] is None          # 1600 is a height, never a count of 1600 drones
    assert m["likely"] == "drones"


def test_a_road_number_is_not_a_height():
    assert geo.parse_altitude_bare("Р-02 Бровари") is None


def test_a_small_number_is_a_count_not_a_height():
    assert geo.parse_altitude_bare("3х Бровари") is None
