"""1.45: seven more oblasts with a tracker of their own — Kherson (@kherson_monitoring), Kirovohrad (@controlkrop),
Khmelnytskyi (@radarhmel), Ternopil (@radarofternopil), Rivne (@rivne_radar), Lviv (@ppoualviv), Volyn (@lutsk_radar) —
and what the owner found on the map:

- "Чернігівщина: 1 реакт біля Бобровиці на новий Басань, далі Київщина / 3 реакти на Славутич з півночі" drew three
  jet drones in the middle of Chernihiv oblast. A post that names a town it is heading for is drawn at that town, and
  a target reported for a whole oblast is never a pin at the oblast centre: the region is marked instead;
- the "villages and small towns", rivers, roads, airports and rings layers did nothing outside Kyiv oblast;
- on a computer the street tiles should be there at every zoom.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = {"kherson_monitoring": "23", "controlkrop": "15", "radarhmel": "3", "radarofternopil": "21", "rivne_radar": "5",
       "ppoualviv": "27", "lutsk_radar": "8"}


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, SW, SRV = _read("static/kyiv.html"), _read("static/light.html"), _read("static/sw.js"), _read("app/server.py")


def _state():
    return server.State(server.Store(":memory:"), {})


def _marks(ch, text, near=None):
    _state()                                                       # loads the channels' home oblasts into geo
    return [(m["type"], geo.display_place(m.get("place")), m.get("oblast_uid"))
            for m in geo.parse_for_channel(ch, server._clean_post(text), near)]


def _run(posts):
    st = _state()
    now = datetime.now(timezone.utc)
    st.store.add_feed([{"post_id": f"{ch}/{8000 + i}", "channel": ch, "ts": (now - timedelta(minutes=ago)).isoformat(timespec="seconds"),
                        "text": text, "tags": server.tag_feed_text(text, ch), "text_en": text, "en_fallback": True}
                       for i, (ch, ago, text) in enumerate(posts)])
    return st.markers()


def test_each_new_tracker_speaks_for_its_oblast():
    st = _state()
    for ch, uid in NEW.items():
        assert ch in server.AUTHORITATIVE_CHANNELS and st.channel_home(ch) == uid and geo.CHANNEL_HOME[ch] == uid, ch
        assert st.channel_mode(ch) == "map" and uid in server.DEFAULT_SCOPE
    assert _marks("rivne_radar", "Шахед в бік Сарн") == [("drones", "→ Сарни", "5")]
    assert _marks("lutsk_radar", "Шахед на Ковель") == [("drones", "→ Ковель", "8")]
    assert _marks("radarofternopil", "БпЛА на Кременець") == [("drones", "→ Кременець", "21")]
    assert _marks("kherson_monitoring", "Шахед над Білозеркою") == [("drones", "Білозерка (Херсонський р-н)", "23")]
    assert _marks("controlkrop", "Реактивний на Кропивницький") == [("drones", "→ Кропивницький", "15")]


def test_a_raion_named_is_its_centre_town_and_a_raion_alert_notice_is_nothing():
    assert _marks("ppoualviv", "Шахед у Самбірському районі") == [("drones", "Самбірський р-н", "27")]
    assert _marks("ppoualviv", "БпЛА в напрямку Самбірського району") == [("drones", "→ Самбірський р-н", "27")]
    for text in ("Тривога — Вараський район", "Відбій — Вараський район"):
        assert _marks("rivne_radar", text) == [], text


def test_a_tracker_following_its_target_into_the_next_oblast():
    # "Це він на Хмельниччині", then "Далі на Плужне": a Khmelnytskyi village, read because the channel just named it
    assert _marks("rivne_radar", "Далі на Плужне") == []
    assert _marks("rivne_radar", "Далі на Плужне", ["3"]) == [("unknown", "→ Плужне", "3")]
    ms = _run([("rivne_radar", 6, "Це він на Хмельниччині"), ("rivne_radar", 3, "Далі на Плужне")])
    assert [(m["place"], m["oblast_uid"]) for m in ms] == [("→ Плужне", "3")]


def test_a_town_it_is_heading_for_is_never_the_oblast_centre():
    text = "Чернігівщина: 1 реакт біля Бобровиці на новий Басань, далі Київщина\n3 реакти на Славутич з півночі"
    ms = geo.parse_for_channel("chernihiv_nebo", text)
    assert [(m["place"], m["oblast_uid"]) for m in ms] == [("Бобровиця", "25"), ("→ Славутич", "14")]
    assert all(m["place"] != "область" for m in ms)
    # an oblast it comes FROM is still all the post says of where it is — the region is marked, not a point
    assert geo.parse_for_channel("war_monitor", "БпЛА з Чернігівщини курсом на Київ")[0]["place"] == "область"


def test_a_raion_is_an_area_not_a_point():
    _state()
    m = geo.parse_for_channel("vinnytsiappo", "🛵 Реактивний Шахед залітає у Гайсинський район попередніми курсом на Теплик")[0]
    assert (m["place"], m["approach"], m["heading"]) == ("→ Теплик", True, None)        # no course from Гайсин
    m = geo.parse_for_channel("ppoualviv", "Шахед у Самбірському районі")[0]
    assert m["place"] == "Самбірський р-н" and m["evidence"]["position"]["confidence"] == "low"
    i18n = _read("static/i18n.js")
    assert "s=s.replace(/ р-н(?=\\)|$)/,LANG==='fr'?' raïon':' raion');" in i18n            # "Sambirskyi raion" — 1.47: no nested brackets in French


def test_vector_is_a_course():
    assert _marks("kyiv_airdef", "2х вектор Велика Димерка/Бровари") == [("unknown", "→ Велика Димерка", "14")]
    ms = geo.parse_for_channel("kyiv_airdef", "шахед з Требухова вектор Бровари")
    assert [(m["place"], m["target"]) for m in ms] == [("Требухів", "Бровари")]


def test_a_target_reported_for_a_whole_oblast_marks_the_region_not_a_point():
    # the map: no silhouette at the oblast centre — the weapon and its count on the region, the posts one tap away
    i = PAGE.index("let OBLEVT={};")
    tick = PAGE[PAGE.index("function tick(){"):PAGE.index("const ids=new Set(live.map(m=>m.id));")]
    assert "if(!m.status){ if(m.oblast_uid&&!m.endedBy)(g[m.oblast_uid]=g[m.oblast_uid]||[]).push(m); return false; }" in tick
    chip = PAGE[i:PAGE.index("function oblEventSheet", i)]
    assert "G[gk]" in chip and "KIND_COL(m)" in chip and '<path class="obring live"' in chip   # 1.51: any target in the air
    assert "const px=v=>`calc(var(--k,1)*${v.toFixed(1)}px)`;" in chip          # its size in screen pixels at every zoom
    # the Near list keeps it, without a distance, as "Chernihiv oblast · somewhere in the oblast"
    assert "vague:m.place==='область'" in PAGE and "km=(r.imm||r.vague)?'—'" in PAGE
    assert "o?o+' · '+t(m.oblast_uid==='31'?'city_somewhere':'obl_somewhere')" in PAGE   # 1.49: Kyiv city, "in the city"
    # a push never says "within 15 km of you" for it, and the Light radar does not draw it
    assert 'elif m.get("place") != "область" and d <= radius + HOME_CELL_KM / 2:' in SRV
    assert "if(m.place==='\\u043e\\u0431\\u043b\\u0430\\u0441\\u0442\\u044c'&&!IMMEDIATE.has(m.type)) continue;" in LIGHT


def test_the_villages_layer_covers_every_oblast_on_the_map():
    v = geo.villages({"27", "18", "5"})
    assert len(v) > 250 and {u for *_, u in v} == {"27", "18", "5"}
    names = {(n, u) for n, _, _, u in v}
    assert all("(" not in n for n, _ in names)
    assert not any(n == "Самбірський р-н" for n, _ in names)          # a raion is not a village
    # the core gazetteer's towns are not drawn twice (a village of the same name in another oblast is its own place)
    assert not names & {(k.split(" (")[0], val[2]) for k, val in dict.items(geo.PLACES) if val[2] in ("27", "18", "5")}
    assert '"villages", [None])[0] == "scope"' in SRV and "geo.villages(sc)" in SRV
    # fetched the first time the layer is on, never before
    assert "'/api/places?villages=scope'" in PAGE and "if(LAYERS.minor) loadVillages();" in PAGE
    assert "if(cb.dataset.l==='minor'&&cb.checked)loadVillages();" in PAGE


def test_rivers_roads_and_landmarks_for_the_whole_country():
    doc = json.loads(_read("static/map-ua.json"))
    assert {r["en"] for r in doc["rivers"]} >= {"Dnipro", "Dniester", "Southern Bug", "Desna", "Siverskyi Donets", "Prut"}
    assert all(r["uk"] and r["fr"] for r in doc["rivers"]) and len(doc["roads"]) > 50
    kinds = {p["k"] for p in doc["pois"]}
    assert kinds == {"air", "nuc", "pow"}
    assert not [p for p in doc["pois"] if "base" in p["en"].lower() or "field" in p["en"].lower()]   # civil airports only
    assert {"Lviv airport", "Odesa airport", "Rivne NPP", "Burshtyn TPP"} <= {p["en"] for p in doc["pois"]}
    assert "Natural Earth" in doc["license"] and "GeoNames" in doc["license"]
    assert "fetch('/static/map-ua.json')" in PAGE and "function drawUA(ua){" in PAGE
    assert "'/static/map-ua.json'" in SW and '"static/map-ua.json"' in SRV          # kept offline; part of the build id
    assert os.path.exists(os.path.join(ROOT, "scripts", "build_mapdata.py"))


def test_the_rings_are_around_the_readers_oblast_capital():
    assert "const OBL_CAP={" in PAGE and "function drawRings(){" in PAGE
    i = PAGE.index("function setMyOblast(uid){")
    assert "drawRings();" in PAGE[i:PAGE.index("\n", i)]


def test_the_tiles_only_once_zoomed_in_on_every_device():
    # 1.45.1: 1.45 put them under the whole country on a computer, and zoomed out the map was unreadable
    assert "DESKTOP" not in PAGE and "TILE_MAXW" not in PAGE and "tfar" not in PAGE
    assert "const on=want&&VB.w<=150&&MAP" in PAGE and "placeTiles(g,Math.max(8,Math.min(18,tileZoom())),TILE_URL,120);" in PAGE   # 1.47: shared placement
    assert "svg.tiled .road,svg.tiled .roadlbl,svg.tiled .river" in PAGE
    assert "always on a computer" not in PAGE and "always on a computer" not in _read("static/i18n.js")
    # and only inside Ukraine: Moldova, Romania, Belarus and Russia are not drawn under the map
    assert '<g id="tiles" clip-path="url(#uaclip)"></g>' in PAGE
    assert "<clipPath id=\"uaclip\">${(MAP.oblasts||[]).map(o=>`<path d=\"${o.path}\"/>`).join('')}</clipPath>" in PAGE


# -- 1.45.1 ---------------------------------------------------------------------------------------------------------

def test_a_side_of_a_town_is_not_the_town():
    _state()
    # the Air Force, 7 Oct 2026: drawn ON Mykolaiv, "±5 km, high confidence"
    m = geo.parse_for_channel("kpszsu", "🛵 БпЛА на півночі від Миколаєва, курс на захід.")[0]
    assert (m["place"], m["oblast_uid"], m["heading"]) == ("область", "17", 270)      # the oblast is marked, not a point
    assert m["evidence"]["position"]["rel"] == 0 and m["evidence"]["position"]["ref"] == "Миколаїв"
    for text, uid in (("БпЛА північніше Харкова курсом на південь", "22"), ("Шахед на сході від Києва", "14")):
        ms = geo.parse_for_channel("kpszsu", text)
        assert [(x["place"], x["oblast_uid"]) for x in ms] == [("область", uid)], text
    # a smaller town: still there, but with low confidence and "north-west of Brovary" on the card
    m = geo.parse_for_channel("kpszsu", "БпЛА на північному заході від Броварів")[0]
    assert m["place"] == "Бровари" and m["evidence"]["position"]["confidence"] == "low" and m["evidence"]["position"]["rel"] == 315
    # a distance given is used
    m = geo.parse_for_channel("kpszsu", "БпЛА за 20 км на північ від Кременчука")[0]
    assert m["place"] == "Кременчук" and abs(m["lat"] - (geo.PLACES["Кременчук"][1] + 20 / 111)) < 0.01
    # "біля / від … на північ" are unchanged
    assert geo.parse_for_channel("kpszsu", "Шахед біля Миколаєва")[0]["place"] == "Миколаїв"
    assert "if(ps.rel!=null&&ps.ref) return t('rq_of'," in PAGE
    i18n = _read("static/i18n.js")
    assert i18n.count("rq_of:") == 3 and "rq_of:'{0} від н.п. {1}'" in i18n
    import translate
    assert translate.translate_offline("🛵 БпЛА на півночі від Миколаєва, курс на захід.") == "🛵 UAV north of Mykolaiv, heading west."


def test_the_estimate_along_the_heading_is_suspended():
    assert "let ESTIMATE=false;\n" in PAGE and "ESTIMATE=localStorage.getItem('est')" not in PAGE
    assert '<button class="mi tg" id="est" type="button" style="display:none!important">' in PAGE   # .mi.tg is flex!important


def test_the_villages_layer_shows_names_at_an_oblasts_width():
    # 1.45.1: they appeared only below 90 km of map (40 on a phone) — on an oblast's view the layer did nothing
    # with the layer on, the small towns and villages stay up to 300 km of map (an oblast's view is 260)
    assert "svg.veryfar.no-minor .town:not(.big)" in PAGE and "svg.classList.toggle('vilfar',VB.w>300);" in PAGE
    assert "svg.vilfar .town:not(.big):not(.rg):not(.uac):not(.tw2),svg.vilfar .towndot:not(.rg):not(.uac):not(.tw2){display:none}" in PAGE   # 1.49: and the main towns
    assert "svg.far .town.minor,svg.far .towndot.minor{display:none}" in PAGE          # a phone: up to 90 km
    assert ".towndot[data-hid]{display:none!important}" in PAGE                         # no nameless dots
    v = geo.villages({"27"})
    a = {k.split(" (")[0] for k, (kind, _, _) in geo._REG_META.items() if kind == "A" and geo.REGIONAL[k][2] == "27"}
    assert v[0][0] in a                                                                  # hromada centres first
