"""1.58.46 — feedback, the donation jar, the jet drone's flame, and the audit of 22 October 2026 (docs/TECHNICAL.md §11.2).

The owner: "we need a clean way to collect feedback and bug reports" — "a feedback integration we can reach from our admin
dashboard" (+ a Telegram ping); "a small jar with coins at the bottom right of the map"; "the jet Shahed's animation must be
clearer — flames behind the engine"; and "a full cyber security audit — see whether flaws are exploitable and fix them".
Each fix of the audit has a line here, so that none of them is undone by accident.
"""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import chanpost  # noqa: E402
import limits  # noqa: E402
import push  # noqa: E402
import server  # noqa: E402
import tgbot  # noqa: E402


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, ADMIN, INDEX, MOBILE = _read("static", "kyiv.html"), _read("static", "admin.html"), _read("static", "index.html"), _read("static", "mobile.html")
I18N, GUIDE, SW, FB = _read("static", "i18n.js"), _read("static", "guide.html"), _read("static", "sw.js"), _read("static", "feedback.html")
M3D, SRC = _read("static", "models3d.js"), _read("app", "server.py")


@pytest.fixture(autouse=True)
def _on_fly(monkeypatch):
    """Fly-Client-IP is believed on Fly alone: these tests speak as Fly's proxy does."""
    monkeypatch.setenv("FLY_APP_NAME", "heimdall-test")


def _serve(st):
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, old, f"http://127.0.0.1:{srv.server_address[1]}"


def _call(base, path, obj=None, ip="203.0.113.7", ctype="application/json", raw=None, **hd):
    data = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else None)
    h = {"Fly-Client-IP": ip, **hd}
    if data is not None:
        h["Content-Type"] = ctype
    req = urllib.request.Request(base + path, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None


class _Bot:
    username, public_url = "heimdall_test_bot", "https://heimdall.com.ua"

    def __init__(self):
        self.sent = []

    def send(self, chat, method, fields, **k):
        self.sent.append((chat, method, fields))


# ---- feedback -----------------------------------------------------------------------------------------------------------
def test_feedback_is_kept_shown_and_pinged_without_a_place_or_a_link():
    st = server.State(server.Store(":memory:"), {})
    st.bot = _Bot()
    srv, old, base = _serve(st)
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "k" * 32}):
            A = {"X-Admin-Key": "k" * 32}
            body = {"kind": "bug", "text": "Froze at https://evil.example‮ <b>x</b>", "contact": "@reader_one",
                    "page": "tactical", "lang": "uk", "build": "abc123", "look": "night", "screen": "412x915"}
            assert _call(base, "/api/feedback", body, **{"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120"}) == (200, {"ok": True})
            assert _call(base, "/api/feedback", {"text": "hi"})[0] == 400                          # a few words
            assert _call(base, "/api/feedback", {"text": "spam spam", "website": "x"}) == (200, {"ok": True})   # a bot: nothing kept
            assert _call(base, "/api/feedback", {"text": "from elsewhere"}, Origin="https://evil.example")[0] == 403
            assert _call(base, "/api/feedback", {"text": "from elsewhere"}, **{"Sec-Fetch-Site": "cross-site"})[0] == 403
            assert _call(base, "/api/feedback", raw=b'{"text":"plain form"}', ctype="text/plain")[0] == 415
            assert _call(base, "/api/feedback", raw=b"[]")[0] == 400 and _call(base, "/api/feedback", raw=b"{")[0] == 400
            assert _call(base, "/api/admin/feedback")[0] == 401
            code, d = _call(base, "/api/admin/feedback", **A)
            (it,) = d["items"]
            assert it["text"] == "Froze at https://evil.example <b>x</b>" and it["contact"] == "@reader_one"
            assert it["device"] == "Android Chrome · 412x915" and d["counts"]["new"] == 1 and d["tg"]["linked"] is False
            assert set(it) == {"id", "ts", "kind", "text", "contact", "page", "lang", "build", "look", "device", "status"}
            # the ping: linked with the dashboard's code from the owner's chat; a stranger's tries do not void it
            c = _call(base, "/api/admin/feedback_tg", {"action": "code"}, **A)[1]["code"]
            for _ in range(6):
                assert not st.feedback_tg_claim("AAAAAAAA", 999)
            assert st.feedback_tg_claim(c, 777) and st.store.kv_get("fb_chat") == "777"
            assert _call(base, "/api/feedback", {"kind": "idea", "text": "See t.me/bad and https://x.example/y /unlink @a", "contact": "e@x.org"},
                         ip="198.51.100.9")[0] == 200
            (chat, method, f), = st.bot.sent
            assert chat == 777 and method == "sendMessage" and "parse_mode" not in f
            assert "https://x" not in f["text"] and "x.example" not in f["text"] and "t.me/" not in f["text"]
            assert "/unlink" not in f["text"] and "e@x.org" not in f["text"]
            assert "contact given" in f["text"] and "/admin" in f["text"]
            assert _call(base, "/api/feedback", {"text": "a second one, within the minute"}, ip="198.51.100.10")[0] == 200
            assert len(st.bot.sent) == 1                                                         # one a minute at most
            assert _call(base, "/api/admin/feedback", {"id": it["id"], "status": "done"}, **A)[1]["counts"]["done"] == 1
            assert _call(base, "/api/admin/feedback", {"id": it["id"], "status": "done"}, Origin="https://evil.example", **A)[0] == 403
            assert _call(base, "/api/admin/feedback", {"id": it["id"], "delete": True}, **A)[0] == 200
            assert _call(base, "/api/admin/feedback_tg", {"action": "unlink"}, **A)[1]["tg"]["linked"] is False
            # the jar: a Monobank jar or nothing
            assert _call(base, "/api/admin/donate", {"jar": "https://evil.example/jar/123456"}, **A)[0] == 400
            assert _call(base, "/api/admin/donate", {"jar": "javascript:alert(1)"}, **A)[0] == 400
            assert _call(base, "/api/admin/donate", {"jar": "https://send.monobank.ua/jar/8AbCdEf123"}, **A)[0] == 200
            assert _call(base, "/api/donate") == (200, {"jar": "https://send.monobank.ua/jar/8AbCdEf123"})
            assert _call(base, "/api/admin/donate", {"jar": ""}, **A)[0] == 200 and _call(base, "/api/donate")[1] == {"jar": None}
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_feedback_is_limited_by_address_not_by_browser():
    st = server.State(server.Store(":memory:"), {})
    srv, old, base = _serve(st)
    try:
        codes = [_call(base, "/api/feedback", {"text": f"message {i}"}, **{"User-Agent": f"UA {i}"})[0] for i in range(8)]
        assert codes[:6] == [200] * 6 and codes[6:] == [429, 429]                    # the `feedback` allowance, whatever the UA
        assert _call(base, "/api/feedback", {"text": "another network"}, ip="2001:db8:1:2::5")[0] == 200
        assert limits.net_key("2001:db8:1:2::5") == limits.net_key("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
        assert limits.net_key("::ffff:203.0.113.7") == "203.0.113.7"
    finally:
        srv.shutdown()
        server.Handler.state = old
    s = server.Store(":memory:")
    for i in range(6):
        assert s.feedback_add({"ts": server.now_iso(), "kind": "bug", "text": "x", "day_hash": "same"})
    assert s.feedback_add({"ts": server.now_iso(), "kind": "bug", "text": "x", "day_hash": "same"}) is None
    assert server.clean_text("a​b\x85c﻿d‮e\x00", 50) == "abcde"


def test_the_feedback_form_and_the_jar_on_the_pages():
    sheet = PAGE[PAGE.index("function feedbackSheet(kind){"):PAGE.index("$('fbbtn').onclick")]
    for no in ("HOME", "SLOTS", "slots", "GEO", "lat", "lon"):
        assert no not in sheet, no                                                          # never a place
    assert "body={kind:k,text:txt,contact:$('fbc').value.trim(),website:$('fbw').value,page:'tactical'" in sheet
    assert '<button class="mi" id="fbbtn" type="button" data-t="fb_menu">' in PAGE
    assert "`<a class=\"hf-fb\" href=\"/feedback\" data-hf=\"feedback\">${_hx(t('fb_link'))}</a>`" in I18N
    for k in ("fb_title", "fb_noplace", "fb_send", "jar_aria", "jar_btn", "jar_why"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k
    assert "textContent" in FB and "innerHTML" not in FB and "fetch('/api/feedback'" in FB
    assert '<button class="jarbtn" id="jarbtn" type="button" data-t-title="jar_aria"' in PAGE
    assert "body.lite .jarbtn{display:none}" in PAGE and "@media (prefers-reduced-motion:no-preference){.jarbtn .drop" in PAGE
    sup = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]
    assert "/^https:\\/\\/send\\.monobank\\.ua\\/jar\\/[A-Za-z0-9]{6,24}$/.test(DONATE_JAR)" in sup
    assert 'rel="noopener noreferrer"' in sup and "${esc(jar)}" in sup
    assert "ngoSite:'https://07300.org.ua'" in I18N


def test_the_dashboard_shows_every_word_as_text():
    fb = ADMIN[ADMIN.index("let FB=null"):ADMIN.index("async function fbPost(")]
    assert "${escA(x.text)}" in fb and "${escA(x.device)}" in fb and "fbContact(x.contact)" in fb
    assert "esc(x." not in fb
    assert "const esc=t=>String(t==null?'':t).replace(/[&<>\"']/g," in ADMIN                     # encoded, not stripped
    assert 'data-tab="feedback"' in ADMIN and "if(t==='feedback') loadFB();" in ADMIN


# ---- the jet drone's flame ----------------------------------------------------------------------------------------------
def test_the_jet_drones_flame():
    assert "g.add(flame(-7.6, 6.6, 1.3, 0, 1.75, true));" in M3D
    assert "if (big) cone(r * 1.45, len * 1.12, MAT.plume);" in M3D and "g.userData.flame = big ? 2 : 1;" in M3D
    assert "if (o.userData.flame === 2)" in M3D
    assert "flames.forEach(f => { f.visible = false; }); R.render(SCENE, CAM);" in M3D            # their own layer, no outline
    assert "body.forEach(m => { m.colorWrite = false; });" in M3D


# ---- the audit ------------------------------------------------------------------------------------------------------------
def test_an_official_alerts_words_are_data():
    bad = '"><img src=x onerror=alert(1)>'
    a = server.safe_alert({"alert_type": bad, "location_type": bad, "alert_level": bad, "location_title": "Київ‮",
                           "notes": "x\x00y", "threats": [{"threat_type": bad, "level": "red"},
                                                          {"threat_type": "drones", "level": bad, "source_message": "ok​"}]})
    assert a["alert_type"] == "air_raid" and a["location_type"] == "unknown" and a["alert_level"] is None
    assert a["location_title"] == "Київ" and a["notes"] == "xy"
    assert a["threats"] == [{"threat_type": "drones", "level": None, "source_message": "ok"}]
    assert "return safe_alert({" in SRC and "return [safe_alert(x) for x in out.values()]" in SRC
    assert "alerts = [safe_alert(a) for a in alerts or []]" in SRC and "    def upsert_alert(self, a):\n        a = safe_alert(a)" in SRC
    # and the pages escape them
    assert "${esc(THREAT[t.threat_type]?.[1]||t.threat_type)}" in PAGE
    assert "${esc(ATYPE[a.alert_type]||a.alert_type)} · ${esc(LT(a.location_type))}" in PAGE
    assert "plain ${/^(red|yellow)$/.test(a.alert_level)?a.alert_level:''}" in PAGE
    assert "${esc(a.location_type)}" in INDEX and "esc(ATYPE[a.alert_type]?.[1]||a.alert_type)" in INDEX
    assert "subs.map(a=>esc(a.location_title_en||a.location_title))" in MOBILE and "${esc(ATYPE[a.alert_type]||a.alert_type)}" in MOBILE


def test_push_subscriptions_are_the_services_own():
    P = "B" + "A" * 86
    good = {"keys": {"p256dh": P, "auth": "A" * 22}}
    for ep in ("https://fcm.googleapis.com/fcm/send/abc123def456", "https://updates.push.services.mozilla.com/wpush/v2/gAAAA",
               "https://web.push.apple.com/QGuQyavXutnMH", "https://wns2-par02p.notify.windows.com/w/?token=BQYAAA"):
        assert push.clean_subscription(dict(good, endpoint=ep)), ep
    for ep in ("https://fcm.googleapis.com:81/fcm/send/abc123def456", "https://x.fcm.googleapis.com/fcm/send/abc123def456",
               "https://anything.push.apple.com/abcdefghijklmnop", "https://fcm.googleapis.com:99999/fcm/send/abc123def456",
               "https://notify.windows.com.evil.example/w/?token=x"):
        assert push.clean_subscription(dict(good, endpoint=ep)) is None, ep
    assert push.CONNECT_S == 4 and "c.timeout = min(self.timeout, CONNECT_S)" in _read("app", "push.py")
    assert '"ORDER BY COALESCE(fails,0), last_ok DESC"' in SRC


def test_the_answers_cache_has_a_weight():
    st = server.State(server.Store(":memory:"), {})
    st.cached("state", 5, lambda: {"s": 1})
    with mock.patch.object(server.State, "RESP_BYTES", 400_000):
        for i in range(60):
            st.cached(f"hist:{i}:", 60, lambda: {"rows": "x" * 20_000})
        w = sum(3 * len(v[1]) + len(v[2] or b"") for k, v in st._resp.items() if ":" in k)
        assert w <= 400_000 and "state" in st._resp and f"hist:{59}:" in st._resp
    assert "hours = next(h for h in (24, 72, 168) if h >= self._int(q, \"hours\", 24, 1, 168))" in SRC


def test_a_header_key_takes_a_try_and_a_slow_body_is_refused():
    st = server.State(server.Store(":memory:"), {})
    srv, old, base = _serve(st)
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "right-key-0123456789"}), mock.patch.object(server.time, "sleep", lambda s: None):
            codes = [_call(base, "/api/usage", **{"X-Admin-Key": "wrong"})[0] for _ in range(6)]
            assert all(c in (401, 403) for c in codes)
            assert _call(base, "/api/usage", **{"X-Admin-Key": "right-key-0123456789"})[0] == 403     # the tries are spent
            assert _call(base, "/api/usage", ip="198.51.100.20", **{"X-Admin-Key": "right-key-0123456789"})[0] == 200
        assert st.admin.report()["fails_24h"] >= 5                                                 # each one logged
        with mock.patch.object(server.Handler, "BODY_S", 0.5):
            import socket
            s = socket.create_connection(("127.0.0.1", srv.server_address[1]))
            s.sendall(b"POST /api/feedback HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 50\r\n\r\n{")
            time.sleep(0.8)
            s.sendall(b'"')
            s.settimeout(5)
            assert b"408" in s.recv(200).split(b"\r\n")[0]
            s.close()
    finally:
        srv.shutdown()
        server.Handler.state = old
    assert server.Server.MAX_HANDLERS == 384 and 'server_version = "Heimdall"' in SRC
    assert server.Handler._safe_next("/m\r\nX-Injected: 1") == "/m" and server.Handler._safe_next("/\t/evil.example") == "/m"
    assert server.Handler._safe_next("/light?x=1") == "/light?x=1"


def test_channel_names_stay_out_of_public_answers():
    st = server.State(server.Store(":memory:"), {})
    assert st.public({"active": [{"notes": "@KyivCityOfficial: повітряна тривога"}]})["active"][0]["notes"] == "Telegram: повітряна тривога"
    assert 'st.public({"alerts": st.store.history(hours' in SRC and 'st.public({"events": st.store.events(n)})' in SRC
    assert 'text, channel = "", ""          # 1.58.46, the audit (S12)' in SRC
    assert "if now - getattr(self, \"_pub_scan_at\", -1e9) < 300:" in SRC


def test_the_bot_answers_floods_last_and_never_shows_its_token():
    st = server.State(server.Store(":memory:"), {})
    sent = []
    api = type("A", (), {"call": lambda self, m, f, files=None: sent.append((m, f.get("chat_id"))) or {}})()
    b = tgbot.TgBot(st, "123:x", "https://heimdall.com.ua", api=api, gaz=tgbot.Gazetteer({}), shot=False)
    b.send(1, "sendMessage", {"text": "alert"})
    for i in range(30):
        b._callback({"id": str(i), "data": "x", "message": {"chat": {"id": 42, "type": "private"}, "message_id": 1}})
    assert len(b.replies) <= 2 * tgbot.IN_PER_MIN                      # a flood of presses: answered up to the chat's limit
    b.flush(1)
    assert sent[0] == ("sendMessage", 1)                                # the alert first, the answers after
    assert b.replies.maxlen == tgbot.REPLIES_MAX
    tok = "123456789:" + "A" * 35
    assert tgbot.configured({"TG_BOT_TOKEN": " " + tok + "\r\n"}) and not tgbot.configured({"TG_BOT_TOKEN": "x"})
    assert chanpost.BotAPI(tok + " \n")._token == tok
    assert tgbot.TOKEN_RX.sub("<token>", "InvalidURL /bot" + tok + "/getMe") == "InvalidURL /bot<token>/getMe"
    assert chanpost.esc('a"b<') == "a&quot;b&lt;"


def test_the_small_ones():
    assert "if(ORDER.indexOf(q)>=0) return q;" in GUIDE and "if(GD[q]) return q;" not in GUIDE
    assert "'/static/shelters.json'];" in SW and "'/static/shelters.js', '/static/shelters.json'" not in SW
    assert 're.fullmatch(r"/static/(?:logo|heimdall-)[A-Za-z0-9_-]*\\.(?:png|webp)", u.path)' in SRC
    assert '"X-Goog-Api-Key": KEYS["google_cloud"]' in _read("app", "translate.py") and "v2?key=" not in _read("app", "translate.py")
    assert "NEW_PER_NET = 2000" in SRC


def test_the_supply_chain():
    import hashlib
    sh = _read("scripts", "build_three.sh")
    sha = re.search(r"BUNDLE_SHA256=([0-9a-f]{64})", sh).group(1)
    with open(os.path.join(ROOT, "static", "vendor", "three-m3d.min.js"), "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == sha
    assert "--ignore-scripts" in sh
    for wf in ("ci.yml", "fly-deploy.yml"):
        y = _read(".github", "workflows", wf)
        assert "permissions:\n  contents: read" in y and "persist-credentials: false" in y
        for use in re.findall(r"uses: (\S+)", y):
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", use), use
    assert "Pillow>=10.3" in _read("requirements.txt")
    gi, di = _read(".gitignore"), _read(".dockerignore")
    for p in ("*.session", "*.jks", "*.keystore", ".env.*", "*.mbtiles"):
        assert p in gi, p
    for p in ("**/*.sqlite", "**/__pycache__/", "vapid.json", ".env", "*.pem", "*.session", "diag/"):
        assert p in di, p
