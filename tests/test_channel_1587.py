"""1.58.7 — the private channel keeps track: a post for each new report, the villages named, the height drawn, what
became of each target marked, the official all-clear said; and a target whose post gave only where it is heading is
held off the map while that place has no official alert.

The owner, of the wider picture of 1.58.5: "it needs to be zoomed as it was before, but mark the name of the villages at
least so people can orient themselves"; "no need to say the source of info"; "display altitude on the screenshot";
"instead of editing the post, we need to add a screenshot every time — it's better to keep track of what's going on";
"when the alarm is over, or it exploded or fell, or the threat is no longer here, we should mark it too". And of a jet
drone the Air Force put "on the east of Kyiv oblast, towards the capital", drawn on Kyiv: "alarm ALWAYS is better — you
see Kyiv isn't under alarm yet, so why put a drone icon here, it's dangerous" (picked: off the map until the alert).
"""
import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import areas  # noqa: E402
import chanpost  # noqa: E402
import mapshot  # noqa: E402
import server  # noqa: E402
from test_chanpost_158 import API, KV, T0, TOKEN, Clock, Shot, iso, mark  # noqa: E402

I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
LIGHT = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()

CITY = {"oblast_uid": "31", "location_type": "city"}
BROVARY = {"oblast_uid": "14", "location_type": "raion", "location_title": "Броварський район"}


class State:
    def __init__(self, active=()):
        self.marks, self.act = [], list(active)

    def markers_now(self):
        return self.marks

    def snapshot(self):
        return {"active": self.act}


def poster(active=(), api=None, kv=None, clock=None, shot=Shot()):
    st = State(active)
    p = chanpost.ChannelPoster(st, TOKEN, "-100555", "https://kyiv-air-watch-gb.fly.dev", api=api or API(), shot=shot,
                               log=lambda *a: None, clock=clock or Clock(), kv=kv or KV())
    return p, st


def outcome(status, place="Княжичі", lon=30.75, lat=50.47, t=T0, typ="drones", **kw):
    m = {"id": f"chyste_nebo/9#{status}", "type": typ, "status": status, "place": place, "lon": lon, "lat": lat,
         "oblast_uid": "14", "ts": iso(t), "channel": "chyste_nebo"}
    m.update(kw)
    return m


# ---- the picture: the closer view, the villages, the height ------------------------------------------------------------
def inside(shot, view, lon, lat):
    x0, y0, span = view
    x, y = shot.proj(lon, lat)
    return x0 <= x <= x0 + span and y0 <= y <= y0 + span


def test_the_whole_oblast_and_only_it():
    # 1.58.10, the owner: "a change of tactics, it's too unreadable — a snapshot of the oblast, the whole oblast on the
    # screenshot (but ONLY Kyiv oblast and the city of Kyiv)" — the closer views and the villages are gone
    shot = mapshot.MapShot()
    assert not hasattr(shot, "villages") and not hasattr(mapshot, "VIL_MAX")
    assert shot.view(mark(place="Переяслав", lon=31.45, lat=50.07)) == shot.view(mark(place="Оболонь", lon=30.5,
                                                                                         lat=50.51, uid="31"))
    for lon, lat in ((30.52, 50.45), (30.73, 51.52), (29.3, 50.6), (31.9, 50.2), (30.0, 49.25)):   # Kyiv, Slavutych,
        x, y = shot.to_pixel(lon, lat)                                      # the west, the east, the south of the oblast
        assert 0 <= x <= mapshot.W and mapshot.HEAD <= y <= mapshot.H - mapshot.FOOT, (lon, lat)
    drawn = []
    real = shot._label
    shot._label = lambda d, q, text, font, colour, boxes, bounds, anchor="lm": (
        real(d, q, text, font, colour, boxes, bounds, anchor) and (drawn.append(text) or True))
    jpg = shot.render(mark(place="Переяслав", lon=31.45, lat=50.07), [], "21:40")
    assert {"Київ", "Бровари", "Біла Церква"} <= set(drawn)
    assert not set(drawn) & {"Житомир", "Чернігів", "Ніжин", "Прилуки", "Черкаси", "Коростень"}   # no town around
    # and nothing of the oblasts around is drawn: outside it, the plain background
    import io as _io

    from PIL import Image as _Image
    im = _Image.open(_io.BytesIO(jpg)).convert("RGB")
    for lon, lat in ((28.9, 50.3), (32.6, 50.9), (31.0, 49.3)):            # Zhytomyr, Chernihiv, Cherkasy oblasts
        x, y = shot.to_pixel(lon, lat)
        if 0 <= x < mapshot.W and mapshot.HEAD < y < mapshot.H - mapshot.FOOT:
            px_ = im.getpixel((int(x), int(y)))
            assert all(abs(a - b) <= 8 for a, b in zip(px_, mapshot.OUT_BG)), (lon, lat, px_)


def test_the_target_is_drawn_smaller():
    # the owner: "and the Shahed is far too big"
    assert mapshot.GLYPH_SC == 2.6 and mapshot.OTHER_SC == 1.7 and mapshot.HALO == 36


def test_the_height_a_post_gave_is_on_the_picture():
    assert mapshot.ALT_UK == chanpost.ALT_STATE
    assert mapshot.alt_text({"alt": {"m": 150}}) == "↕ ~150 м" and mapshot.alt_text({"alt": {"state": "low"}}) == "↕ низько"
    assert mapshot.alt_text({"alt": {"state": "made-up"}}) is None and mapshot.alt_text({}) is None
    shot = mapshot.MapShot()
    pills = []
    real = shot._pill
    shot._pill = lambda d, box, text, font, alt=None: (pills.append((text, alt)), real(d, box, text, font, alt))
    shot.render(mark(place="Бровари", alt={"m": 150}), [], "21:40")
    shot.render(mark(place="Бровари"), [], "21:40")
    assert pills == [("Бровари", "↕ ~150 м"), ("Бровари", None)]


def test_no_channel_is_named_in_a_post():
    cap = chanpost.caption(mark(channel="chyste_nebo"), T0, "https://h")
    assert "chyste_nebo" not in cap and "за @" not in cap
    assert chanpost.WARN in cap                                        # "from channel posts, not radar" stays


# ---- held off the map ---------------------------------------------------------------------------------------------------
def test_the_areas_are_the_pages_shapes():
    assert areas.area_at(30.52, 50.45) == ("31", "kyiv-city")
    assert areas.area_at(30.79, 50.51) == ("14", "brovary")
    assert areas.area_at(30.95, 50.35) == ("14", "boryspil")
    fills = areas.alert_fill([BROVARY])
    assert areas.under_alert(30.79, 50.51, fills) and not areas.under_alert(30.52, 50.45, fills)
    assert areas.under_alert(30.52, 50.45, areas.alert_fill([CITY]))
    assert areas.under_alert(10.0, 10.0, {})                           # no known area: nothing held on a guess
    assert mapshot.alert_fill is areas.alert_fill


def _held(m, active):
    st = server.State(server.Store(":memory:"), {})
    st.active = {str(i): a for i, a in enumerate(active)}
    st._hold([m])
    return m.get("held")


def test_a_drone_said_only_to_be_heading_for_kyiv_is_held_until_kyiv_is_under_alert():
    ap = dict(type="drones", place="→ Київ", lon=30.52, lat=50.45, oblast_uid="31", approach=True, dest_only=True)
    assert _held(dict(ap), []) is True
    assert _held(dict(ap), [BROVARY]) is True                          # an alert elsewhere does not count
    assert not _held(dict(ap), [CITY])
    assert not _held(dict(ap, type="ballistic_missiles"), [])          # a missile is never held
    assert not _held(dict(ap, type="cruise_missiles"), [])
    assert _held(dict(ap, type="banderol_missiles"), []) is True       # a jet drone
    assert not _held(dict(type="drones", place="Бровари", lon=30.79, lat=50.51, oblast_uid="14"), [])   # where it IS
    assert not _held(dict(ap, status="down"), [])
    assert "self._hold(out)\n        out.sort(" in SRV


def test_the_pages_keep_it_in_their_lists_and_off_their_maps():
    assert "&&!HIDDEN_STATUS.has(m.status)&&!m.held);" in TAC
    assert "vague:m.place==='область'||!!m.held" in TAC and "if(m.held) bits.push(t('mc_held'));" in TAC
    assert "if((m.place==='\\u043e\\u0431\\u043b\\u0430\\u0441\\u0442\\u044c'||m.held)&&!IMMEDIATE.has(m.type)) continue;" in LIGHT
    assert I18N.count("mc_held:") == 3
    # and no "near you" push from it
    assert 'elif m.get("place") != "область" and not m.get("held") and d <= radius + HOME_CELL_KM / 2:' in SRV


def test_the_channel_posts_a_held_target_without_its_silhouette():
    shot = mapshot.MapShot()
    calls = []
    real = shot._glyph
    shot._glyph = lambda d, o, here, sc, alpha=255, drone_like=False: (calls.append(o.get("place")),
                                                                       real(d, o, here, sc, alpha, drone_like))
    held = mark(place="→ Київ", lon=30.52, lat=50.45, uid="31", approach=True, dest_only=True, target="Київ", _held=True,
                history=[{"lon": 30.62, "lat": 50.11, "ts": 1, "place": "Обухів"}])
    assert shot.render(held, [], "21:40")[:3] == b"\xff\xd8\xff" and calls == []
    shot.render(dict(held, _held=False), [], "21:40")
    assert calls == ["→ Київ"]
    got = []

    class Rec:
        def render(self, m, active, when, ray=True, missiles=(), others=()):
            got.append((m["place"], bool(m.get("_held")), sorted(o["place"] for o in others)))
            return b"jpg"
    api = API()
    p, st = poster(api=api, shot=Rec())
    st.marks = [mark(place="→ Київ", lon=30.52, lat=50.45, uid="31", approach=True, dest_only=True, target="Київ",
                     held=True, tag="#1"), mark(place="Бровари", tag="#2")]
    p.tick()
    assert ("→ Київ", True, ["Бровари"]) in got and ("Бровари", False, []) in got      # never drawn among the others
    cap = next(c[1]["caption"] for c in api.calls if "Київ" in c[1]["caption"])
    assert "Офіційної тривоги там поки немає" in cap
    m = st.marks[0]
    assert chanpost.signature(m) != chanpost.signature(dict(m, held=False))            # the alert starts: a new post


# ---- a new post for each new report -------------------------------------------------------------------------------------
def test_each_new_report_is_a_new_post_in_reply_to_the_last_and_a_new_start_replies_too():
    clk, api, kv = Clock(), API(), KV()
    p, st = poster(api=api, kv=kv, clock=clk)
    places = [("Бровари", 30.79, 50.51), ("Княжичі", 30.75, 50.47), ("Бортничі", 30.68, 50.4)]
    for i, (pl, lon, lat) in enumerate(places):
        st.marks = [mark(place=pl, lon=lon, lat=lat, t=clk.t)]
        p.tick()
        clk.t += chanpost.UPDATE_EVERY_S
    sent = [c for c in api.calls if c[0] == "sendPhoto"]
    assert len(sent) == 3 and not any(c[0].startswith("edit") for c in api.calls)
    assert [c[1].get("reply_parameters", {}).get("message_id") for c in sent] == [None, 101, 102]
    assert "(перший допис" in sent[2][1]["caption"]
    assert p.posts[chanpost.key_of(st.marks[0])]["n"] == 3
    # gone, closed; reported again later: a new post, in reply to the closing line
    st.marks = []
    clk.t += chanpost.END_AFTER_S + 1
    p.tick()
    assert api.calls[-1][0] == "sendMessage" and api.calls[-1][1]["reply_parameters"]["message_id"] == 103
    clk.t += 60
    st.marks = [mark(place="Бровари", t=clk.t)]
    p.tick()
    assert api.calls[-1][0] == "sendPhoto" and api.calls[-1][1]["reply_parameters"]["message_id"] == 104


def test_a_target_reported_every_few_seconds_is_posted_at_most_once_a_minute():
    clk, api = Clock(), API()
    p, st = poster(api=api, clock=clk)
    for i in range(24):                                                # two minutes, a new place every 5 s
        st.marks = [mark(place=f"P{i}", lon=30.79 - i * 0.005, t=clk.t)]
        p.tick()
        clk.t += 5
    assert 2 <= len(api.calls) <= 3


# ---- what became of it -------------------------------------------------------------------------------------------------
def test_the_outcome_words_are_the_apps():
    uk = I18N[I18N.index("st_damage:'Пошкодження на землі'"):]
    for k, (_, word) in chanpost.OUTCOME.items():
        assert f"st_{k}:'{word}'" in uk, k


def test_outcomes_are_linked_as_the_tactical_page_links_them():
    tr = mark(place="Бровари", heading=270, t=T0)
    k = chanpost.key_of(tr)
    near = outcome("down", place="Княжичі", lon=30.75, lat=50.47, t=T0 + 120)        # 4 km west, ahead of its course
    assert chanpost.link_outcomes([tr, near]) == {k: near}
    assert chanpost.link_outcomes([tr, outcome("down", t=T0 + 41 * 60)]) == {}           # too late
    assert chanpost.link_outcomes([tr, outcome("down", t=T0 - 180)]) == {}               # before it, by more than 2 min
    assert chanpost.link_outcomes([tr, outcome("down", typ="cruise_missiles", t=T0 + 60)]) == {}   # another family
    behind = outcome("impact", place="Калинівка", lon=30.95, lat=50.51, t=T0 + 60)       # 11 km east, behind it
    assert chanpost.link_outcomes([tr, behind]) == {}
    assert chanpost.link_outcomes([dict(tr, heading=None), behind]) == {k: behind}       # no course: any side
    far_clear = outcome("clear", place="Бориспіль", lon=30.95, lat=50.35, t=T0 + 60)     # "clear", 21 km … ok
    assert chanpost.link_outcomes([dict(tr, heading=None), far_clear]) == {k: far_clear}
    assert chanpost.link_outcomes([dict(tr, heading=None), dict(far_clear, lon=31.2, lat=50.3)]) == {}   # 33 km: no
    assert chanpost.link_outcomes([tr, outcome("fire", t=T0 + 60)]) == {}                # fire never ends a flight
    # one outcome closes one target; the gone one the channel posted counts too
    two = chanpost.link_outcomes([near], extra=[("gone", dict(tr, heading=None))])
    assert two == {"gone": near}


def test_an_outcome_is_marked_in_reply_without_where_it_happened():
    clk, api = Clock(), API()
    p, st = poster(api=api, clock=clk)
    st.marks = [mark(place="Бровари", heading=270, t=clk.t)]
    p.tick()
    clk.t += 90
    st.marks.append(outcome("down", place="Княжичі", lon=30.75, lat=50.47, t=clk.t - 10))
    p.tick()
    m, f, files = api.calls[-1]
    assert m == "sendMessage" and files is None and f["reply_parameters"]["message_id"] == 101
    assert f["text"].startswith("⬇️ <b>Збито / Приземлено</b> — так у дописі о ") and "Бровари" in f["text"]
    assert "Княжичі" not in f["text"] and "chyste_nebo" not in f["text"]                # not where, not who said it
    n = len(api.calls)
    clk.t += chanpost.END_AFTER_S + 60
    p.tick()
    st.marks = []
    p.tick()
    assert len(api.calls) == n                                                       # nothing more about it


def test_an_outcome_after_no_new_reports_is_still_said_once_and_a_target_already_down_is_not_posted():
    clk, api = Clock(), API()
    p, st = poster(api=api, clock=clk)
    st.marks = [mark(place="Бровари", t=clk.t)]
    p.tick()
    st.marks = []
    clk.t += chanpost.END_AFTER_S + 5
    p.tick()
    assert api.calls[-1][1]["text"].startswith("⏹")
    st.marks = [outcome("impact", place="Бровари", lon=30.79, lat=50.5, t=clk.t)]
    p.tick()
    p.tick()
    assert [c[1].get("text", "")[:1] for c in api.calls[1:]] == ["⏹", "💥"]
    api2 = API()
    p2, st2 = poster(api=api2, clock=clk)
    st2.marks = [mark(place="Гоголів", lon=31.03, lat=50.5, tag="#7", t=clk.t),
                 outcome("down", place="Гоголів", lon=31.03, lat=50.5, t=clk.t)]
    p2.tick()
    assert api2.calls == []


# ---- the official all-clear -----------------------------------------------------------------------------------------------
def test_area_of_a_target():
    assert chanpost.area_of(mark(place="Оболонь", lon=30.5, lat=50.51, uid="31")) == "kyiv-city"
    assert chanpost.area_of(mark()) == "brovary"
    east = mark(place="область", lon=31.3, lat=50.4, evidence={"position": {"quad": "e"}})
    assert chanpost.area_of(east) == "14:*"
    assert chanpost.area_on("14:*", {"fastiv": "R"}) and not chanpost.area_on("14:*", {"kyiv-city": "R"})
    assert set(chanpost.OBL14) == {k for _, k in areas.RAION_STEM}


def test_the_all_clear_of_the_targets_area_is_said_once_a_minute_after_it_and_closes_it():
    clk, api = Clock(), API()
    p, st = poster([BROVARY], api=api, clock=clk)
    st.marks = [mark(place="Бровари", t=clk.t)]
    p.tick()
    assert p.posts[chanpost.key_of(st.marks[0])]["area"] == "brovary"
    clk.t += 20
    st.act = []                                                         # the official alert ends …
    p.tick()
    clk.t += 30
    st.act = [BROVARY]                                                  # … a flicker of the feed: it is back
    p.tick()
    clk.t += 20
    st.act = []
    p.tick()
    clk.t += chanpost.CLEAR_AFTER_S - 10
    p.tick()
    assert len(api.calls) == 1                                          # not a minute yet
    clk.t += 15
    p.tick()
    m, f, _ = api.calls[-1]
    assert m == "sendMessage" and f["text"].startswith("✅ <b>Відбій тривоги</b> о ")
    assert f["text"].endswith("· Броварський район (офіційно)") and f["reply_parameters"]["message_id"] == 101
    clk.t += chanpost.END_AFTER_S + 60
    st.marks = []
    p.tick()
    assert len(api.calls) == 2                                          # closed by it: no "no new reports" after


def test_no_all_clear_for_an_alert_this_run_did_not_see_nor_while_switched_off():
    clk, api, kv = Clock(), API(), KV()
    p, st = poster([BROVARY], api=api, kv=kv, clock=clk)
    st.marks = [mark(place="Бровари", t=clk.t)]
    p.tick()
    # a restart: the alerts are not read yet; the post's area seems free — no all-clear from that
    p2, st2 = poster([], api=api, kv=kv, clock=clk)
    st2.marks = list(st.marks)
    for _ in range(20):
        clk.t += 5
        p2.tick()
    assert len(api.calls) == 1
    # an alert seen, then the channel switched off while it ends: nothing said late
    st2.act = [BROVARY]
    p2.tick()
    kv.kv_set(chanpost.KV_ON, "0")
    st2.act = []
    clk.t += 120
    p2.tick()
    kv.kv_set(chanpost.KV_ON, "1")
    clk.t += 5
    p2.tick()
    clk.t += 120
    p2.tick()
    assert not any("Відбій" in (c[1].get("text") or "") for c in api.calls)
    # a held target heading for Kyiv while Kyiv has no alert is in no watched area
    api3 = API()
    p3, st3 = poster([], api=api3, clock=clk)
    st3.marks = [mark(place="→ Київ", lon=30.52, lat=50.45, uid="31", approach=True, dest_only=True, held=True, t=clk.t)]
    p3.tick()
    assert p3.watch == {}


@pytest.mark.parametrize("doc", ["SAFETY.md", "TECHNICAL.md"])
def test_the_docs_say_it(doc):
    s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
    assert "1.58.7" in s
    assert re.search(r"held", s)


# ---- 1.58.9: one source, and the height it gave -------------------------------------------------------------------------
def test_the_channel_posts_the_kyiv_trackers_alone():
    # the owner: "for the Telegram bot we'll take a single source: t.me/chyste_nebo" (1.58.9) — then, chyste_nebo silent
    # from 03:59 while the two others reported a drone towards Boryspil: "all the Kyiv sources" (1.58.12)
    assert chanpost.SOURCES == ("chyste_nebo", "kyiv_airdef", "kievinfo_kyiv")
    assert chanpost.eligible(mark()) and chanpost.eligible(mark(channel="kyiv_airdef"))
    assert chanpost.eligible(mark(channel="kievinfo_kyiv")) and not chanpost.eligible(mark(channel="kpszsu"))
    clk, api = Clock(), API()
    p, st = poster(api=api, clock=clk)
    st.marks = [mark(place="Бровари", tag="#1", t=clk.t), mark(place="Бориспіль", lon=30.95, lat=50.35, tag="#2",
                                                              channel="kpszsu", t=clk.t)]
    p.tick()
    assert len(api.calls) == 1 and "Бровари" in api.calls[0][1]["caption"]
    # an outcome another channel reported is not their word
    clk.t += 60
    st.marks.append(outcome("down", place="Бровари", lon=30.79, lat=50.5, t=clk.t, channel="war_monitor"))
    p.tick()
    assert len(api.calls) == 1
    st.marks[-1]["channel"] = "kyiv_airdef"
    p.tick()
    assert api.calls[-1][1]["text"].startswith("⬇️")


def test_a_height_an_earlier_report_gave_is_carried_with_its_time():
    # the owner: "I see the altitude is not shown most of the time" — @chyste_nebo: "Бондарня другий 4600", then "На
    # Клавдієво", "Другий Бородянка": the height was said once, then only places
    h = {"lon": 30.0, "lat": 50.7, "ts": iso(T0 - 240), "channel": "chyste_nebo", "place": "Бондарня", "alt_m": 4600}
    m = mark(place="Бородянка", lon=29.92, lat=50.65, history=[h])
    alt, at = chanpost.stated_alt(m)
    assert alt["m"] == 4600 and at == T0 - 240
    cap = chanpost.caption(m, None, "https://h")
    assert f"↕️ Висота: ~4600 м (у дописі о {chanpost.hhmm(T0 - 240)})" in cap
    assert chanpost.stated_alt(mark(alt={"m": 3800}, history=[h]))[0]["m"] == 3800          # its own first
    assert chanpost.stated_alt(mark(history=[dict(h, channel="war_monitor")])) == (None, None)  # its sources only
    assert chanpost.stated_alt(mark(history=[dict(h, alt_m=None)])) == (None, None)            # never guessed
    old = dict(h, ts=iso(T0 - 5 * 60))                                                         # 5 min: too old (4 max)
    assert chanpost.stated_alt(mark(history=[old])) == (None, None)
    assert chanpost.ALT_MAX_S == 4 * 60 and "const ALT_MAX_MIN=4;" in I18N
    assert chanpost.signature(m) != chanpost.signature(dict(m, history=[dict(h, alt_m=3800)]))
    got = []

    class Rec:
        def render(self, m, active, when, ray=True, missiles=(), others=()):
            got.append(mapshot.alt_text(m))
            return b"jpg"
    pp, _ = poster(shot=Rec())
    pp.picture(m, [])
    assert got == [f"↕ ~4600 м · {chanpost.hhmm(T0 - 240)}"]


def test_a_height_said_as_on_n_metres_is_read():
    import geo
    for text, want in (("Від Пирятина йде повільна на 300 метрах", 300), ("Ірпінь на 400 м", 400),
                       ("Бровари на 500м", 500), ("Висота 2200", 2200)):
        got = [(m.get("alt") or {}).get("m") for m in geo.parse_for_channel("chyste_nebo", text)]
        assert want in got, (text, got)
    assert geo.parse_altitude("на 300 м від мосту") is None                                  # a distance
