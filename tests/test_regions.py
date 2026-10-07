"""1.43: the regions — one live tracker per oblast, the oblasts as compartments of the dashboard, posts in Russian.

Five channels joined the defaults, each the tracker of one oblast: Chernihiv, Odesa, Cherkasy, Kharkiv, Dnipro. Odesa,
Kharkiv and Dnipro joined the map. A channel's oblast ("home") is how its posts are read — that oblast's villages and
city districts, which a regional tracker names post after post — and the dashboard switches a whole oblast off: its
channels are not read and nothing reported there is drawn, counted or pushed. Kyiv is always on.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, ADMIN, DOC = (_read("static/kyiv.html"), _read("static/light.html"), _read("static/admin.html"),
                           _read("docs/TECHNICAL.md"))


def _state():
    return server.State(server.Store(":memory:"), {})


def _marks(ch, text):
    return geo.parse_for_channel(ch, text)


# -- the compartments ---------------------------------------------------------------------------------------------

def test_each_new_channel_speaks_for_its_oblast_and_the_three_new_oblasts_are_on_the_map():
    st = _state()
    homes = {"chernihiv_nebo": "25", "monitoringodesa": "18", "chyste_nebocherkasy": "24", "radar_kharkov": "22", "RadarDnepr": "9"}
    for ch, uid in homes.items():
        assert st.channel_home(ch) == uid and st.channel_mode(ch) == "map"
        assert geo.CHANNEL_HOME[ch] == uid                       # and its posts are read as that oblast's
    for uid in ("18", "22", "9", "25", "24", "14", "31"):
        assert uid in server.SCOPE_UIDS
    assert "27" not in server.SCOPE_UIDS                        # Lviv: no tracker, not on the map by default
    ids = [r["id"] for r in st.regions()]
    assert ids[:2] == ["31", "ua"] and "22" in ids and "14" not in ids     # Kyiv oblast is part of Kyiv's compartment


def test_an_oblast_switched_off_leaves_the_map_and_its_channel_is_not_read():
    st = _state()
    kharkiv = {"oblast_uid": "22", "lat": 49.99, "lon": 36.23}
    assert server.in_scope(kharkiv) and "radar_kharkov" in st.channels_read("web")
    assert st.region_set("22", False)[0]
    assert not server.in_scope(kharkiv)
    assert st.channel_mode("radar_kharkov") == "off" and "radar_kharkov" not in st.channels_read("web")
    assert "22" not in st.snapshot()["scope"]
    again = server.State(st.store, {})                           # it survives a restart (kv "regions")
    assert again.channel_mode("radar_kharkov") == "off" and not again.region_on("22")
    assert again.region_set("22", True)[0] and server.in_scope(kharkiv) and again.channel_mode("radar_kharkov") == "map"


def test_an_oblast_never_on_can_be_switched_on_and_kyiv_never_off():
    st = _state()
    lviv = {"oblast_uid": "27", "lat": 49.84, "lon": 24.03}
    assert not server.in_scope(lviv)
    assert st.region_set("27", True)[0] and server.in_scope(lviv)
    assert st.region_set("31", False) == (False, "Kyiv is always on")
    assert st.region_set("27", False)[0] and not server.in_scope(lviv)


def test_a_channel_added_from_the_dashboard_belongs_to_the_oblast_chosen_and_can_be_moved():
    st = _state()
    assert st.channel_update("add", "controlpoltava", via="web", home="19") == (True, "ok")
    assert st.channel_home("controlpoltava") == "19" and st.channel_mode("controlpoltava") == "trial"
    assert geo.CHANNEL_HOME["controlpoltava"] == "19"
    assert st.channel_update("set", "controlpoltava", home="ua")[0]
    assert st.channel_home("controlpoltava") == "ua" and "controlpoltava" not in geo.CHANNEL_HOME
    st.channel_update("delete", "controlpoltava")


def test_a_regional_channels_warning_is_for_the_readers_of_its_oblast():
    st = _state()
    now = datetime.now(timezone.utc).isoformat()
    st.store.add_feed([{"post_id": "radar_kharkov/1", "channel": "radar_kharkov", "ts": now, "text": "Шахед на Мерефу", "tags": ["drones"]},
                       {"post_id": "kpszsu/1", "channel": "kpszsu", "ts": now, "text": "БпЛА на Харківщині", "tags": ["drones"]}])
    feed = {p["channel"]: p for p in st.store.feed(10)}
    assert feed["radar_kharkov"]["home"] == "22" and "home" not in feed["kpszsu"]
    assert "if(p.home&&!mine.has(p.home)) continue;" in PAGE          # the ballistic / MiG strip
    assert "p = dict(p, home=home)" in _read("app/server.py")        # and the live line's posts carry it too


def test_the_pages_follow_the_servers_scope():
    st = _state()
    assert st.snapshot()["scope"] == sorted(server.SCOPE_UIDS, key=int)
    assert "fetch('/api/places?oblast=scope')" in PAGE and "/api/places?oblast=scope" in LIGHT
    assert "const REG=scopeRegs();" in PAGE and "['10','25','20','19','24','4']" not in PAGE
    assert 'set(SCOPE_UIDS) if oq == "scope"' in _read("app/server.py")


def test_the_dashboard_shows_the_channels_oblast_by_oblast_with_a_switch_each():
    for k in ("function drawRegions(", "class=\"rgtog\"", "'/api/admin/region'", "data-k=\"home\"", "id=\"ch_newhome\""):
        assert k in ADMIN, k
    for k in ("h_channels_rg", "rg_on_q", "rg_off_q", "rg_note"):
        assert ADMIN.count(k + ":") == 2, k                              # English and Ukrainian
    assert "/api/admin/region" in DOC


# -- reading a regional tracker -------------------------------------------------------------------------------------

def test_a_chernihiv_line_with_two_reports_is_two_jet_drones_on_their_routes():
    ms = _marks("chernihiv_nebo", "Чернігівщина: 2 реакти від Куликівки на Лихачів 1 реакт на Добрянку")
    assert [(m["place"], m["target"], m["count"], m["jet"]) for m in ms] == [
        ("Куликівка", "Лихачів", 2, True), ("→ Добрянка", "Добрянка", 1, True)]
    route = _marks("chernihiv_nebo", "1 реакт Любеч-Славутич")[0]
    assert route["place"] == "Любеч" and route["target"] == "Славутич" and route["heading"] is not None


def test_a_village_is_read_only_in_its_own_oblast():
    # Іванівка is dozens of villages; from Kyiv it is nothing at all
    assert _marks("kyiv_airdef", "Іванівка") == []
    # Дмитрівка from the Chernihiv tracker is in Chernihiv oblast — never the one near Kyiv, 200 km away
    m = _marks("chernihiv_nebo", "Новий реактивний з Сумщини на Дмитрівку.")[0]
    assert m["oblast_uid"] == "25" and m["target"].startswith("Дмитрівка (") and m["lon"] > 32.5


def test_an_area_between_two_places_is_not_a_route():
    ms = geo.parse_for_channel("eRadarrua", "Харківщина: 5 БпЛА в районі Котельва - Коломак")
    assert ms and all(m["heading"] is None for m in ms)


def test_a_post_in_russian_is_read_like_one_in_ukrainian():
    assert geo.looks_russian("Шахед отлетел от Харькова снова на Мерефу") and not geo.looks_russian("Шахед на Мерефу курсом")
    m = _marks("radar_kharkov", "Шахед отлетел от Харькова снова на Мерефу")[0]
    assert m["place"] == "Харків" and m["target"] == "Мерефа" and m["type"] == "drones"
    m = _marks("radar_kharkov", "БпЛА Молния на Русскую Лозовую")[0]
    assert m["target"] == "Руська Лозова" and m["type"] == "drones"
    m = _marks("radar_kharkov", "Еще БпЛА на Лесное - Пятихатки")[0]           # a district of the city, by its Russian name
    assert m["place"].startswith("Лісне") and m["target"].startswith("П'ятихатки") and m["heading"] is not None
    assert _marks("radar_kharkov", "Предварительно уничтожен")[0]["status"] == "down"
    assert "drones" in server.tag_feed_text("Ударный БпЛА на Северную Салтовку", "radar_kharkov")
    # the text the reader sees is never changed
    st = _state()
    st.store.add_feed([{"post_id": "radar_kharkov/2", "channel": "radar_kharkov", "ts": datetime.now(timezone.utc).isoformat(),
                        "text": "Ударный БпЛА на Северную Салтовку", "tags": ["drones"]}])
    assert st.store.feed(5)[0]["text"] == "Ударный БпЛА на Северную Салтовку"


def test_a_name_several_villages_share_is_the_one_near_the_channels_last_report_or_nothing():
    m = _marks("monitoringodesa", "Ивановка")[0]
    assert m["ambiguous"] and len(m["candidates"]) > 2
    st = _state()
    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    posts = [{"post_id": "monitoringodesa/1", "channel": "monitoringodesa", "ts": t0.isoformat(), "text": "Розквит", "tags": []},
             {"post_id": "monitoringodesa/2", "channel": "monitoringodesa", "ts": (t0 + timedelta(minutes=3)).isoformat(), "text": "Ивановка", "tags": []}]
    out = st._marks_from_posts(posts, [], {})
    iv = [x for x in out if x["place"].startswith("Іванівка")]
    assert len(iv) == 1 and iv[0]["place"] == "Іванівка (Березівський р-н)" and "candidates" not in iv[0]
    # with nothing before it, nobody can say which Іванівка — it is not drawn
    alone = st._marks_from_posts(posts[1:], [], {})
    assert not [x for x in alone if x["place"].startswith("Іванівка")]


def test_the_regional_gazetteer_is_built_from_geonames_and_kept_off_the_map_labels():
    doc = json.loads(_read("data/regional_places.json"))
    assert set(doc["oblasts"]) == {"25", "24", "18", "22", "9"} and "GeoNames" in doc["_about"]
    assert "Лихачів" in geo.PLACES and "Лихачів" not in list(geo.PLACES)       # looked up, never iterated
    assert "geonames.org" in DOC.lower() and "build_places.py" in DOC


def test_the_light_page_fetches_the_far_raions_only_for_a_place_there():
    far = json.loads(_read("static/light-map-x.json"))
    assert {r["obl"] for r in far["raions"]} == {"18", "22", "9"}
    base = json.loads(_read("static/light-map.json"))
    assert not {r["obl"] for r in base["raions"]} & {"18", "22", "9"}
    assert "fetch('/static/light-map-x.json')" in LIGHT and "await loadLMX(OBL)" in LIGHT


def test_a_trackers_fundraising_its_tally_of_the_night_and_its_stories_are_not_sightings():
    beg = ("Читающие Радар Харьков, для канала очень важна финансовая поддержка, этим вы нам поможете делать канал "
           "эффективнее\n\n💳 MonoBank:\n4874 1000 3308 5674")
    tally = ("❗Уночі Сили ППО збили 161 ціль ворога\n\nОсновні напрямки удару — Київщина, Харківщина, Дніпропетровщина.\n\n"
             "Вдалося знищити або подавити 117 ударних безпілотників, 5 балістичних ракет та 39 крилатих ракет.")
    story = ("😡Ворожий дрон знову атакував дільницю ДТЕК на Дніпропетровщині\n\nСьогодні вранці FPV-дрон упав на в’їзді на "
             "територію дільниці.\n\nЦе вже дев’ята атака на цю дільницю від початку вересня.")
    for ch, text in (("radar_kharkov", beg), ("RadarDnepr", tally), ("RadarDnepr", story)):
        tags = server.tag_feed_text(text, ch)
        assert tags == ["news"] and not server.is_relevant(text, tags, ch), text[:40]
        assert geo.parse_for_channel(ch, text) == [] or ch == "RadarDnepr"
    assert _marks("radar_kharkov", beg) == []                      # the card number never reaches the map or the feed


def test_both_words_of_a_two_word_village_decline():
    m = _marks("radar_kharkov", "БпЛА Молния на Малую Даниловку")[0]
    assert m["target"] == "Мала Данилівка"


def test_a_target_far_away_is_not_near_and_not_the_whole_region():
    # Odesa is on the map now: from Kyiv, a mark there is not in the Near list, and a ballistic one there is not
    # "no distance — the whole region"
    assert "if(d>NEAR_MAX) continue;" in PAGE and "const NEAR_MAX=350;" in PAGE
    assert "imm:IMMEDIATE.has(m.type)&&d<=REGION_R" in PAGE
