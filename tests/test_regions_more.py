"""1.44: five more oblasts with a tracker of their own — Sumy (@kabusumy), Mykolaiv (@air_alert_mk), Poltava
(@PoltavaRadar), Vinnytsia (@vinnytsiappo), Zhytomyr (@zt_radar) — and Mykolaiv oblast on the map.

Their villages are read like those of 1.43's five oblasts: only in a post from the oblast's own tracker or one that
names the oblast. The posts below are the channels' own, from 7 October 2026.
"""
import os
from datetime import datetime, timedelta, timezone

import geo
import server
import translate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = {"kabusumy": "20", "air_alert_mk": "17", "PoltavaRadar": "19", "vinnytsiappo": "4", "zt_radar": "10"}


def _state():
    return server.State(server.Store(":memory:"), {})


def _marks(ch, text):
    return [(m["type"], geo.display_place(m.get("place")), m.get("oblast_uid"), m.get("status"))
            for m in geo.parse_for_channel(ch, server._clean_post(text))]


def test_each_new_tracker_speaks_for_its_oblast_and_mykolaiv_is_on_the_map():
    st = _state()
    for ch, uid in NEW.items():
        assert ch in server.AUTHORITATIVE_CHANNELS and st.channel_home(ch) == uid and geo.CHANNEL_HOME[ch] == uid
        assert st.channel_mode(ch) == "map"
    assert "17" in server.DEFAULT_SCOPE and "17" in server.SCOPE_UIDS
    assert server.CHANNEL_VIA_DEFAULT["kabusumy"] == "api"          # its web preview is off, like Cherkasy's
    assert any(r["id"] == "17" for r in st.regions())


def test_the_new_oblasts_villages_are_read_only_where_they_belong():
    # "Ромодан" under the Poltava heading of an єРадар post is the village; it used to be the oblast centre
    ms = geo.parse_for_channel("eRadarrua", "🛵 Київщина\n- реактивний на Кагарлик\n🛵 Полтавщина\n- реактивний Ромодан")
    assert [(m["place"], m["oblast_uid"]) for m in ms if m["oblast_uid"] == "19"] == [("Ромодан", "19")]
    assert not geo.parse_for_channel("kyiv_airdef", "Ромодан")       # from Kyiv: nothing
    assert _marks("vinnytsiappo", "🛵 Реактивний Шахед на село Самгородок Хмільницького району") == [
        ("drones", "Самгородок (Хмільницький р-н)", "4", None)]
    assert _marks("zt_radar", "🛵 Реактивний шахед в сторону Народичі") == [("drones", "→ Народичі", "10", None)]
    assert _marks("air_alert_mk", "‼️Увага!\nРеактивний БпЛА на Врадіївку на Миколаївщині з південного сходу") == [
        ("drones", "→ Врадіївка", "17", None)]


def test_a_channels_signature_is_not_a_place():
    # "💪 Телеграм канал ППО Вінниця" under every post put a target on Vinnytsia
    assert _marks("vinnytsiappo", "🛵 Реактивний Шахед на Оратів\n\n💪 Телеграм канал ППО Вінниця") == [
        ("drones", "→ Оратів", "4", None)]
    assert translate.strip_promo("🛸 1× реактивний БпЛА тримає курс у напрямку с. Теплик.\n\nВінниця Радар | Підписатись") == \
        "🛸 1× реактивний БпЛА тримає курс у напрямку с. Теплик."
    assert translate.strip_promo("🛸Загроза БПЛА - Очаків\n\n🔄 Моніторинг Миколаїв | Підписатись") == "🛸Загроза БПЛА - Очаків"
    assert translate.strip_promo("Шахед на Бровари | Підписатись на канал") == "Шахед на Бровари"   # the first line stays
    # and the feed's tags are read without it
    assert "4" not in str(server.tag_feed_text(server._clean_post("📡 Без загроз на Вінниччині\n\n💪 Телеграм канал ППО Вінниця"), "vinnytsiappo"))


def test_the_poltava_tracker():
    assert _marks("PoltavaRadar", "Не фіксується.") == [("drones", None, "19", "lost")]
    assert not [m for m in geo.parse_for_channel("kyiv_airdef", "Загроз не фіксується") if m.get("status") == "lost"]
    # the oblast named is where it came from: the Svitlohirske it flies to is Poltava's, not Dnipro's
    ms = geo.parse_for_channel("PoltavaRadar", "Реактивний БпЛА з Дніпропетровщини на Світлогірське.")
    assert [m["place"] for m in ms] == ["→ Світлогірське (Полтавський р-н)"] and ms[0]["oblast_uid"] == "19"
    assert _marks("PoltavaRadar", "З'явився реактивний БпЛА повз Варварівку західним курсом.") == [
        ("drones", "Варварівка (Полтавський р-н)", "19", None)]


def test_the_sumy_trackers_words():
    assert _marks("kabusumy", "‼️Пуски КАБів напрямок Глухова/Есмані‼️") == [("guided_aerial_bombs", "→ Глухів", "20", None)]
    # "летять високо" is how high they fly, not the village of Високе
    assert all("Високе" not in (m[1] or "") for m in _marks(
        "kabusumy", "Пролітають Кром'яне летять високо попередній курс тримають в бік Могриця/Грунівка/Сінне"))
    assert _marks("zt_radar", "То свої ❤️") == []                    # "it's ours"


def test_guided_bombs_that_fell_were_not_shot_down():
    st = _state()
    now = datetime.now(timezone.utc)
    rows = [{"post_id": f"kabusumy/{i}", "channel": "kabusumy", "ts": (now - timedelta(minutes=ago)).isoformat(timespec="seconds"),
             "text": text, "tags": server.tag_feed_text(text, "kabusumy"), "text_en": text, "en_fallback": True}
            for i, (ago, text) in enumerate([(3, "КАБи на Юнаківку"), (2, "💣 КАБ Юнаківка"), (1, "Впали")])]
    st.store.add_feed(rows)
    out = [m for m in st.markers() if m.get("status")]
    assert [(m["status"], m["type"], m["place"]) for m in out] == [("impact", "guided_aerial_bombs", "Юнаківка")]


def test_mykolaivs_raions_reach_the_light_page_only_for_a_place_there():
    import json
    with open(os.path.join(ROOT, "static", "light-map-x.json"), encoding="utf-8") as f:
        far = json.load(f)
    assert {r["uk"] for r in far["raions"] if r["obl"] == "17"} == {
        "Баштанський район", "Вознесенський район", "Миколаївський район", "Первомайський район"}
