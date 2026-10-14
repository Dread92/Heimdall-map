"""1.58.25 — @nikalert: Nikopol and Dnipro, straight on the map.

The owner: "we'll add t.me/nikalert for Dnipro — straight on the map" (then: "Nikopol/dnipro"). Its posts, as its web
preview shows them (tests/data/nikalert_2026_10.json), read before it went on the map: two streams — 🪖 Nikopol's own
targets (FPV and strike drones from across the reservoir, shelling) and Ⓜ️ the oblast's monitors it relays — a threat
written as a list, newest line first, the same list struck through once it is over, and its news, history and service
posts in between. See docs/TECHNICAL.md §7.3c.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import geo  # noqa: E402
import server  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "data", "nikalert_2026_10.json"), encoding="utf-8") as _f:
    POSTS = {p["id"]: p["text"] for p in json.load(_f)["posts"]}
geo.CHANNEL_HOME["nikalert"] = "9"          # as the server sets it from its channel list


def read(pid):
    """What the map draws for a post: stored (is_relevant), then read — the server's own two steps."""
    text = POSTS[pid] if isinstance(pid, int) else pid
    clean = server._clean_post(text)
    tags = server.tag_feed_text(clean, "nikalert", None)
    if not server.is_relevant(text, tags, "nikalert"):
        return None
    return [(m.get("type"), m.get("status"), m.get("place"), m.get("oblast_uid")) for m in geo.parse_for_channel("nikalert", clean)]


# ---- the channel ------------------------------------------------------------------------------------------------------
def test_it_is_a_default_channel_of_dnipropetrovsk_oblast_on_the_map():
    assert "nikalert" in server.AUTHORITATIVE_CHANNELS and server.CHANNEL_HOME_DEFAULT["nikalert"] == "9"
    assert "nikalert" not in server.CHANNEL_MODE_DEFAULT          # the owner: straight on the map, not on trial
    assert "nikalert" not in server.CHANNEL_VIA_DEFAULT           # its web preview is open
    assert geo.CHANNEL_PARSER["nikalert"] is geo.parse_nikalert


# ---- 🪖 Nikopol's own --------------------------------------------------------------------------------------------------
def test_a_threat_list_is_one_target_at_its_newest_place():
    assert read(376000) == [("drones", None, "Покровське (Нікопольський р-н)", "9")]   # "Загроза ФПВ ◼️ с. Покровське"
    assert read(376002) == [("drones", None, "Нікополь", "9")]                         # Shaheds: Nikopol, then two more lines
    assert read(375935) == [("drones", None, "Вищетарасівка", "9")]
    assert read(375391) == [("drones", None, "Покров", "9")]
    # its own spelling, a tomato for the "o"; a hospital it does not know is passed over for the line before
    assert read(374774) == [("drones", None, "Новопавлівка (Нікопольський р-н)", "9")]
    assert read(374780) == [("drones", None, "Новопавлівка (Нікопольський р-н)", "9")]
    assert read(374793) == [("drones", None, "Нікополь", "9")]                         # "3-я Дільниця", then Nikopol
    assert read(374794) == [("drones", None, "Капулівка", "9")]                         # "Центр села" 09:23, Kapulivka 09:20


def test_a_hromada_or_a_landmark_alone_is_no_place():
    assert read(374790) == []        # "◼️ 11:28 Покровська ТГ" — not Pokrovsk in Donetsk oblast
    assert read(374798) == []        # a yacht club, a hotel, a clinic of Nikopol


def test_a_recap_of_a_threat_that_is_over_is_never_a_target_but_how_it_ended():
    for pid in (375930, 375933, 375936, 375957, 375960, 375975, 375976, 375993):
        assert all(m[1] for m in read(pid) or []), pid             # an outcome at most, never a target
    assert "⭕" in POSTS[375993] and "17:37" in POSTS[375993]   # read whole, it was a drone "×37" shot down at Nikopol
    # its newest line is the outcome the map knows, at the list's newest place it knows — the target is closed
    assert read(375975) == [("drones", "impact", "Нікополь", "9")]                     # "Дрон впав з 💥детонацією"
    assert read(375936) == [("drones", "down", "Добра Надія (Нікопольський р-н)", "9")]   # "Дрон впав"
    assert read(375957) == [("drones", "lost", "Нікополь", "9")]                       # "Сигнал втрачено"
    assert read(375933)[0][:2] == ("drones", "clear")                                  # "Без загроз"
    assert read(375976) == [] and read(375930) == []      # shelling over; a market and a hromada: no place


def test_its_own_posts_with_the_town_of_the_heading():
    assert read(375998) == [("drones", None, "Нікополь", "9")]           # "Нкпл: 🟠 17:42 Увага! Атака ударних БпЛА"
    assert read(375954) == [("drones", None, "Нікополь", "9")]           # "Атака дронів-камікадзе"
    assert read(375398) == [("drones", None, "Нікополь", "9")]           # "Шахед в повітрі"
    assert read(375396) == [("drones", "impact", "Нікополь", "9")]       # "Детонація дрону": an explosion
    assert read(374783) == [("drones", "down", "Капулівка", "9")]        # "Падіння дрону без детонації в с. Капулівка"
    assert read(375384) in ([], None) and read(375991) in ([], None)      # a district, no weapon: nothing


def test_shelling_is_not_the_sky():
    for pid in (375962, 375963, 375994, 375943):
        assert read(pid) in ([], None), pid


# ---- Ⓜ️ the monitors --------------------------------------------------------------------------------------------------
def test_a_monitors_label_is_whose_report_not_where():
    assert read(375380) == [("unknown", None, "Обухівка (Дніпровський р-н)", "9")]       # "Dнпр: Обухівка 🛵"
    assert read(374796)[0][2] == "Курилівка (Дніпровський р-н)"                          # not at Dnipro
    assert read(375965) == []                                     # "Dнпр: Тривожимось через загрозу балістики з півночі"
    assert read(375978) == []                                     # "Кр.Ріг : Загрозу балістики зняли, … з Херсонщини …"


def test_the_oblasts_relays_are_placed_in_dnipropetrovsk_oblast_only():
    assert read(375999) == [("drones", None, "→ Вищетарасівка", "9")]   # from Zaporizhzhia oblast towards Vyshchetarasivka
    for pid in (375985, 375995, 375996, 375377, 375932):              # Polohy, Tokmak, "ТОТ Запоріжжя", Kherson oblast
        assert read(pid) in ([], None), pid
    assert read(376004) == [("drones", None, "→ Дніпро", "9")]          # "Реактивний на Дніпро"


def test_a_banderol_is_a_banderol():
    got = read(375362)
    assert got[0][:3] == ("banderol_missiles", None, "Магдалинівка (Самарівський р-н)")   # "2х КР «Бандероль»"
    assert all(g[0] != "cruise_missiles" for pid in (375362, 375373, 375374, 375382, 375390, 375394) for g in read(pid))


def test_news_history_and_service_posts_are_not_even_stored():
    for pid in (375953, 375958, 375938, 375942, 375947, 375987, 374799, 376005):
        assert read(pid) is None, pid
    for pid in (375955, 375959, 375967, 375971):                   # the official alerts it relays: no mark
        assert read(pid) in ([], None), pid


# ---- a name several villages share ------------------------------------------------------------------------------------
def test_the_hromada_centre_behind_a_namesake_is_its_own_place_again():
    assert geo.PLACES["Покровське (Нікопольський р-н)"] == (34.1521, 47.5521, "9")
    assert geo.PLACES["Покровське"][:2] == (36.24, 47.98)              # the core town keeps the name alone
    assert geo._MERGE_KM == 25
    got = geo._parse_live("БпЛА на Нову Січ", "9")                     # its other name finds it
    assert got and abs(got[0]["lon"] - 34.152) < 0.01


def test_each_stream_is_its_own_previous_report():
    assert geo.context_stream("nikalert", POSTS[376000]) == "/nik"
    assert geo.context_stream("nikalert", POSTS[376004]) == "/m"
    assert geo.context_stream("nikalert", POSTS[375380]).startswith("/m:")
    assert geo.context_stream("RadarDnepr", POSTS[376000]) == ""
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "marker_ttl_minutes": 45})
    now = datetime.now(timezone.utc)
    posts = []
    for i, (dm, pid) in enumerate(((-4, 376002), (-3, 376000), (-1, 376004))):
        clean = server._clean_post(POSTS[pid])
        posts.append({"post_id": f"nikalert/{pid}", "channel": "nikalert", "ts": (now + timedelta(minutes=dm)).isoformat(),
                      "text": clean, "tags": server.tag_feed_text(clean, "nikalert", None)})
    st.store.add_feed(posts)
    got = {m["id"].split("#")[0]: m for m in st.markers_now()}
    # the jet drone "на Дніпро" stays drawn as approaching Dnipro — not moved onto the FPV at Pokrovske a minute before
    assert got["nikalert/376004"]["place"] == "→ Дніпро"
    assert got["nikalert/376000"]["place"] == "Покровське (Нікопольський р-н)"
