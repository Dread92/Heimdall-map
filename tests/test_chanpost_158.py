"""1.58 — the owner's private Telegram channel: one post per target over Kyiv and Kyiv oblast, with the map around it.

The owner: "a small private Telegram channel that posts alerts like the channels we read, with a 'screenshot' of the
app where the drone is (Kyiv + Kyiv oblast only)"; picked: "one post per target, updated" and "the app's style, drawn
on the server". Its rules are the app's: no course a post did not state, no outcome, nothing but the official data
paints an alert, the token is the owner's and is never written anywhere.
"""
import io
import json
import os
import re
import sys
import urllib.error
from datetime import datetime, timezone

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import chanpost  # noqa: E402
import mapshot  # noqa: E402

GLY = open(os.path.join(ROOT, "static", "glyphs.js"), encoding="utf-8").read()
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
T0 = datetime(2026, 10, 12, 18, 40, tzinfo=timezone.utc).timestamp()
TOKEN = "123456:SECRET-token-of-the-owner"


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def mark(place="Бровари", lon=30.79, lat=50.51, t=T0, uid="14", tag="#12", **kw):
    m = {"id": f"chyste_nebo/1#{place}", "type": "drones", "place": place, "lon": lon, "lat": lat, "oblast_uid": uid,
         "ts": iso(t), "pos_ts": iso(t), "channel": "chyste_nebo", "tag": {"night": "2026-10-12", "id": tag},
         "history": [], "heading": None, "evidence": {"heading": {"confidence": "none"}}}
    m.update(kw)
    return m


# ---- the picture -----------------------------------------------------------------------------------------------
def _shapes(svg):
    """glyphs.js's shapes → polygons [(x, y), …] (absolute M/L paths) and rectangles (x, y, w, h)."""
    polys, rects = [], []
    for d in re.findall(r'<path class="glyph[^"]*" d="([^"]+)"', svg):
        if re.search(r"[a-z]", d):                       # a relative path with arcs (the Banderol's canopy)
            continue
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
        polys.append(list(zip(nums[0::2], nums[1::2])))
    for x, y, w, h in re.findall(r'<rect class="glyph" x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg):
        rects.append((float(x), float(y), float(w), float(h)))
    return polys, rects


def _glyph_js(name):
    body = re.search(r"const SHAHED_BODY=(.*?);\n", GLY, re.S).group(1)
    if name in ("drone", "jetdrone"):
        own = re.search(name + r":SHAHED_BODY\+(.*?)\n\s*\+'<g class=\"jetfx\">", GLY, re.S).group(1)
        return body + own
    m = re.search(r"\b" + name + r":'(.*?)',?\n", GLY) or re.search(r"G\." + name + r"='(.*?)';?\n", GLY)
    return m.group(1)


@pytest.mark.parametrize("name", ["drone", "jetdrone", "missile", "ballistic", "banderol", "supersonic", "unknown"])
def test_the_silhouettes_are_the_apps(name):
    polys, rects = _shapes(_glyph_js(name))
    mine = mapshot.GLYPHS[name]
    my_polys = [p for p in mine if not isinstance(p, tuple)]
    my_rects = [p[1:] for p in mine if isinstance(p, tuple)]
    assert my_polys == polys
    if name == "banderol":                                # the canopy (an arc path) is drawn as its bounding box
        assert my_rects[:-1] == rects and my_rects[-1] == (-4.3, -8.4, 8.6, 3.9)
    else:
        assert my_rects == rects
    if name == "jetdrone":                                # the jet's flame
        fl = re.search(r'jetdrone:.*?<path class="flame" d="([^"]+)"', GLY, re.S).group(1)
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", fl)]
        assert mapshot.FLAME == list(zip(nums[0::2], nums[1::2]))


def test_no_outcome_is_ever_drawn():
    for g in ("down", "impact", "lost", "clear"):
        assert g in GLY and g not in mapshot.GLYPHS


def test_a_target_of_no_stated_type_is_drawn_and_turned_as_the_app_does():
    assert "const MSL_NEAR_KM=150;" in TAC                 # mapshot.as_drone: 150 km
    assert "const asDrone=m=>m.type==='unknown'&&!m.status&&!mslCtx(m);" in TAC
    u = mark(type="unknown")
    assert mapshot.as_drone(u) and mapshot.glyph_of(u, True) == "drone"
    assert not mapshot.as_drone(u, [(30.9, 50.6)]) and mapshot.glyph_of(u, False) == "unknown"
    # orientOf: a course a post reported (with a confidence) turns it; none → `face`; a warning sign stays upright
    assert "if(!ev||!ev.confidence||ev.confidence==='none') return fc;" in TAC
    assert mapshot.orient(mark(heading=250, face=10, evidence={"heading": {"confidence": "high"}})) == 250
    assert mapshot.orient(mark(heading=250, face=10)) == 10
    assert mapshot.orient(mark(face=197)) == 197
    assert mapshot.orient(mark(type="unknown", face=197), drone_like=False) == 0
    assert mapshot.orient(mark(status="impact", face=197)) == 0


def test_the_official_alerts_are_painted_as_the_page_paints_them():
    f = mapshot.alert_fill
    assert f([{"oblast_uid": "31", "location_type": "city"}]) == {"kyiv-city": "R"}
    whole = f([{"oblast_uid": "14", "location_type": "oblast", "alert_level": "yellow"}])
    assert set(whole) == {"bucha", "vyshhorod", "brovary", "boryspil", "obukhiv", "bila-tserkva", "fastiv"}
    assert set(whole.values()) == {"Y"}
    assert f([{"oblast_uid": "14", "location_type": "raion", "location_title": "Броварський район"}]) == {"brovary": "R"}
    assert f([{"oblast_uid": "14", "location_type": "hromada", "raion_key": "fastiv", "alert_level": "yellow"}]) == {"fastiv": "Y"}
    # red wins over yellow, whatever the order
    assert f([{"oblast_uid": "14", "location_type": "hromada", "raion_key": "bucha"},
              {"oblast_uid": "14", "location_type": "hromada", "raion_key": "bucha", "alert_level": "yellow"}]) == {"bucha": "R"}
    assert f([{"oblast_uid": "25", "location_type": "oblast"}]) == {"obl:25": "R"}
    assert f([]) == {}


def test_the_picture_is_a_photo_of_the_whole_oblast():
    pytest.importorskip("PIL")
    from PIL import Image
    shot = mapshot.MapShot()
    assert len(shot.towns) > 20 and len(shot.raion_lbl) == 7 and shot.districts
    act = [{"oblast_uid": "31", "location_type": "city"}]
    for m in (mark(heading=250, target="Київ", history=[{"lon": 31.31, "lat": 50.36, "ts": 1}]),
              mark(type="ballistic_missiles", place="Київ", lon=30.52, lat=50.45, uid="31"),
              mark(type="unknown", place="Фастів", lon=29.92, lat=50.08),
              mark(type="banderol_missiles", place="Вишгород", lon=30.49, lat=50.58)):
        jpg = shot.render(m, act, "21:40")
        assert jpg[:3] == b"\xff\xd8\xff" and len(jpg) < 900_000
        assert Image.open(io.BytesIO(jpg)).size == (1080, 1350)            # 1.58.10: portrait, 4:5
    # 1.58.10: the same view whatever the target — Kyiv oblast and the city whole (tests/test_channel_1587.py)
    assert shot.view(mark(place="Фастів", lon=29.92, lat=50.08)) == shot.view(mark())


# ---- what the channel says ---------------------------------------------------------------------------------------
def test_only_flying_targets_over_kyiv_and_its_oblast_are_posted():
    assert chanpost.eligible(mark()) and chanpost.eligible(mark(uid="31", place="Київ"))
    for bad in (mark(uid="25"), mark(lon=None), mark(status="impact"), mark(status="down"), mark(stale=True),
                mark(superseded_by="x"), mark(place="→ "), mark(place="→ Київщина"), mark(place="область"),
                mark(place=""), mark(type="guided_aerial_bombs"), mark(needs_context=True)):
        assert not chanpost.eligible(bad), bad


def test_a_target_whose_post_named_only_where_it_heads_is_posted_as_such():
    # "Балістика на Київ" — the most urgent post there is: the app draws it at Kyiv as an approach, and so does the
    # channel, saying that where it is now was not said, with no course ray and no position of its own
    bal = mark(type="ballistic_missiles", place="→ Київ", target="Київ", lon=30.52, lat=50.45, uid="31",
               approach=True, dest_only=True)
    assert chanpost.eligible(bal) and chanpost.approach(bal)
    cap = chanpost.caption(bal, T0, "https://kyiv-air-watch-gb.fly.dev")
    assert "🚀 <b>Балістична ракета</b> · → Київ" in cap
    assert "➡️ Курс на Київ (так у дописі)\n📍 Де саме зараз — у дописі не сказано" in cap
    shots = []

    class Rec:
        def render(self, m, active, when, ray=True, missiles=(), others=()):
            shots.append(ray)
            return b"png"
    p, st = poster(shot=Rec())
    st.marks = [bal]
    p.tick()
    assert shots == [False]                                          # no course ray from a town it has not reached


def test_a_course_is_said_only_when_a_post_stated_one():
    url = "https://kyiv-air-watch-gb.fly.dev"
    cap = chanpost.caption(mark(), T0, url)
    assert "Курс" not in cap and "➡️" not in cap
    # worked out by the app from two reports of a live channel: drawn by the app with its caveat, never said here
    derived = mark(heading=250, evidence={"heading": {"matched": "Бровари → Київ", "confidence": "medium",
                                                     "method": "bearing between the two latest reports of this live-tracking channel"}})
    assert chanpost.stated_course(derived) is None and "Курс" not in chanpost.caption(derived, T0, url)
    assert chanpost.stated_course(mark(heading=250)) is None                      # no confidence: no course
    said = mark(heading=270, evidence={"heading": {"matched": "курсом на захід", "confidence": "medium",
                                                   "method": "compass word after 'course'"}})
    assert chanpost.stated_course(said) == "Курс: захід"
    assert chanpost.stated_course(mark(target="Київ", heading=250)) == "Курс на Київ"
    assert "➡️ Курс на Київ (так у дописі)" in chanpost.caption(mark(target="Київ"), T0, url)


def test_the_caption_says_what_and_where():
    url = "https://kyiv-air-watch-gb.fly.dev"
    cap = chanpost.caption(mark(count=3, alt={"m": 100, "state": None}), T0 - 300, url)
    assert "🛵 <b>Шахед ×3</b> · Бровари" in cap and "Висота: ~100 м (у дописі)" in cap
    assert "chyste_nebo" not in cap and "(перший допис" in cap               # 1.58.7: no channel named (the owner)
    assert chanpost.WARN in cap and 'href="https://kyiv-air-watch-gb.fly.dev/m"' in cap
    assert chanpost.label_of(mark(type="banderol_missiles"))[1] == "Бандероль (реактивний дрон)"   # never a cruise missile
    assert chanpost.label_of(mark(jet=True))[1] == "Реактивний дрон"
    assert chanpost.label_of(dict(mark(type="unknown"), _drone=True))[1].startswith("Ймовірно, дрон")
    closed = chanpost.end_text(mark(), {"k": "quiet", "t": T0})
    assert closed.startswith("⏹ Нових дописів після ") and "🛵 <b>Шахед</b> · Бровари" in closed
    for c in (cap, closed):                    # what became of it is said by an outcome's own line (1.58.7) only
        for word in ("збит", "знищ", "влуч", "вибух", "приліт", "ППО", "уражен", "безпечн"):
            assert word not in c.lower(), word
    assert "<script" not in chanpost.caption(mark(place="<script>"), T0, url)                     # escaped


# ---- the publisher -----------------------------------------------------------------------------------------------
class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class KV:
    def __init__(self):
        self.d = {}

    def kv_get(self, k):
        return self.d.get(k)

    def kv_set(self, k, v):
        self.d[k] = v


class API:
    def __init__(self, fail=None):
        self.calls, self.mid, self.fail = [], 100, fail

    def call(self, method, fields, files=None):
        self.calls.append((method, fields, files))
        if self.fail:
            e, self.fail = self.fail, None
            raise e
        if method in ("sendPhoto", "sendMessage"):
            self.mid += 1
            return {"message_id": self.mid}
        return True


class Shot:
    def render(self, m, active, when, ray=True, missiles=(), others=()):
        return b"\x89PNG-" + m["place"].encode()


class State:
    def __init__(self):
        self.marks = []

    def markers_now(self):
        return self.marks

    def snapshot(self):
        return {"active": [{"oblast_uid": "31", "location_type": "city"}]}


def poster(api=None, kv=None, clock=None, logs=None, shot=Shot()):
    st = State()
    p = chanpost.ChannelPoster(st, TOKEN, "-100555", "https://kyiv-air-watch-gb.fly.dev", api=api or API(),
                               shot=shot, log=(lambda *a: logs.append(" ".join(map(str, a)))) if logs is not None else (lambda *a: None),
                               clock=clock or Clock(), kv=kv or KV())
    return p, st


def test_a_post_for_each_new_report_in_reply_to_the_last_then_closed():
    # 1.58.7, the owner: "instead of editing the post, we need to add a screenshot every time"
    clk, api, kv = Clock(), API(), KV()
    p, st = poster(api, kv, clk)
    st.marks = [mark(t=T0 - 30)]
    p.tick()
    assert [c[0] for c in api.calls] == ["sendPhoto"] and api.calls[0][2]["photo"][1] == b"\x89PNG-" + "Бровари".encode()
    assert "reply_parameters" not in api.calls[0][1]
    # the same target (its tag), reported again 20 s later: not posted yet …
    clk.t += 20
    st.marks = [mark(place="Княжичі", lon=30.75, lat=50.47, t=clk.t - 5, history=[{"lon": 30.79, "lat": 50.51, "ts": 1}])]
    p.tick()
    assert len(api.calls) == 1
    # … then a new post, once, in reply to the first — never an edit
    clk.t += chanpost.UPDATE_EVERY_S
    p.tick()
    p.tick()
    assert [c[0] for c in api.calls] == ["sendPhoto", "sendPhoto"]
    f = api.calls[1][1]
    assert f["reply_parameters"] == {"message_id": 101, "allow_sending_without_reply": True} and "Княжичі" in f["caption"]
    assert not any(c[0].startswith("edit") for c in api.calls)
    # the same report again: nothing new to post
    clk.t += chanpost.UPDATE_EVERY_S
    p.tick()
    assert len(api.calls) == 2
    # gone for five minutes: its closing line, in reply to its last post, with the time of its last report
    st.marks = []
    clk.t += chanpost.END_AFTER_S + 1
    p.tick()
    m, f, _ = api.calls[2]
    assert m == "sendMessage" and f["text"].startswith("⏹ Нових дописів після ") and "Княжичі" in f["text"]
    assert f["reply_parameters"]["message_id"] == 102
    p.tick()
    assert len(api.calls) == 3
    # a restart (a deploy) keeps the posts: nothing is posted twice
    p2, st2 = poster(api, kv, clk)
    st2.marks = [mark(place="Княжичі", lon=30.75, lat=50.47, t=T0 + 20 - 5)]
    p2.tick()
    assert len(api.calls) == 3


def test_nothing_old_is_posted_after_a_restart_and_the_budget_holds():
    clk, api = Clock(), API()
    p, st = poster(api, clock=clk)
    st.marks = [mark(t=T0 - chanpost.FRESH_S - 5)]
    p.tick()
    assert api.calls == []
    st.marks = [mark(place=f"P{i}", tag=f"#{i}", t=T0 - i) for i in range(30)]
    p.tick()
    assert len(api.calls) == chanpost.BUDGET
    assert api.calls[0][2]["photo"][1] == b"\x89PNG-P0"          # the most recent report first
    clk.t += 61
    p.tick()
    assert len(api.calls) == 30


def test_telegram_asking_to_wait_is_obeyed():
    clk = Clock()
    api = API(fail=chanpost.TgError(429, "sendPhoto: Too Many Requests: retry after 20", 20))
    p, st = poster(api, clock=clk)
    st.marks = [mark(t=T0)]
    p.tick()
    p.tick()
    assert len(api.calls) == 1
    clk.t += 22
    p.tick()
    assert [c[0] for c in api.calls] == ["sendPhoto", "sendPhoto"]
    assert p.health()["ok"] is True


def test_without_pillow_the_channel_posts_its_text():
    api = API()
    p, st = poster(api, shot=False)
    p.shot = None
    st.marks = [mark(t=T0)]
    p.tick()
    m, f, files = api.calls[0]
    assert m == "sendMessage" and files is None and f["link_preview_options"] == {"is_disabled": True}
    assert "text only" in p.health()["note"]


# ---- the token ---------------------------------------------------------------------------------------------------
def test_the_token_is_never_logged_stored_or_shown(monkeypatch):
    logs, kv = [], KV()
    api = API(fail=chanpost.TgError(400, "sendPhoto: Bad Request: chat not found"))
    p, st = poster(api, kv, logs=logs)
    st.marks = [mark(t=T0)]
    p.tick()
    st.marks = [mark(t=T0)]
    p.tick()
    blob = json.dumps(kv.d) + "\n".join(logs) + json.dumps(p.health()) + json.dumps(p.stats)
    assert logs and TOKEN not in blob and "SECRET" not in blob
    assert p.health()["ok"] is True                         # it worked again after the error

    # the Bot API's errors carry the method and Telegram's words, never the address (which holds the token)
    def boom(req, timeout=None, context=None):
        raise urllib.error.URLError(f"cannot reach {req.full_url}")
    monkeypatch.setattr(chanpost.urllib.request, "urlopen", boom)
    with pytest.raises(chanpost.TgError) as e:
        chanpost.BotAPI(TOKEN).call("sendMessage", {"chat_id": 1, "text": "x"})
    assert TOKEN not in str(e.value) and "sendMessage" in str(e.value)

    def denied(req, timeout=None, context=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"ok":false,"error_code":401,"description":"Unauthorized"}'))
    monkeypatch.setattr(chanpost.urllib.request, "urlopen", denied)
    with pytest.raises(chanpost.TgError) as e:
        chanpost.BotAPI(TOKEN).call("getMe", {})
    assert TOKEN not in str(e.value) and e.value.code == 401


def test_it_runs_only_when_the_owner_has_set_both_secrets():
    assert not chanpost.configured({}) and not chanpost.configured({"TG_BOT_TOKEN": "x"})
    assert chanpost.configured({"TG_BOT_TOKEN": "x", "TG_CHANNEL_ID": "-100"})
    assert chanpost.start(object(), env={}) is None
    assert "if chanpost and chanpost.configured():" in SRV and "official.append(self.channel.health())" in SRV
    assert "TG_BOT_TOKEN" not in re.sub(r"#.*", "", SRV.split("def main():")[1]).replace(
        '"channel: off — TG_BOT_TOKEN / TG_CHANNEL_ID not set (scripts/set-telegram-channel.bat)"', "")
    docker = open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8").read()
    assert "fonts-dejavu-core" in docker
    assert re.search(r"^Pillow>=", open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read(), re.M)


def test_the_setup_script_keeps_the_token_out_of_files_and_the_screen():
    bat = open(os.path.join(ROOT, "scripts", "set-telegram-channel.bat"), encoding="utf-8", newline="").read()
    assert bat.startswith("<# : ") and "\r\n" in bat
    assert '-AsSecureString' in bat and 'ZeroFreeBSTR' in bat
    assert '| fly secrets import -a $app' in bat                       # through the command's input
    for bad in ("Out-File", "Set-Content", "Add-Content", "Write-Host $tok", "Write-Host ($tok", "> $"):
        assert bad not in bat, bad
    # on an error, only the method's name: the address with the token is never printed
    tg = re.search(r"function Tg\(.*?\r\n\}", bat, re.S).group(0)
    assert "Write-" not in tg and "$_.ErrorDetails.Message" in tg
    assert "$script:tgErr.Replace($script:tok, '<token>')" in tg          # Telegram's words, the token masked
    # 1.58.1: when the bot is told nothing (no update, or another program reads its updates), the channel's id is asked
    # and checked with Telegram (getChat) — the owner's bot was an administrator and the script still found nothing
    assert "Telegram says: " in bat and "'getChat'" in bat and "Show Peer IDs in Profile" in bat
    assert "('-100' + $bare)" in bat
    assert "can_post_messages" in bat and "can_edit_messages" in bat
