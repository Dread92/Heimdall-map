"""1.58.35 — the audit of 18 October 2026, fixed (docs/TECHNICAL.md §11.1).

The two serious findings, reproduced on the demo server before the fix: a crafted `#carry=` link planted HTML in the
band for good (a script with the four pins within reach), and `/api/push/subscribe` kept any string as an endpoint
(every notification waited on it; the server could be pointed at any host). Then the headers, the whole-app lock on
sessions, the trusted address, the request timeout, the 400s, the dashboard's files, the cell snapped on the phone,
the container's user. Each guard has a line here, so that none of them is undone by accident."""
import base64
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import adminauth  # noqa: E402
import push  # noqa: E402
import server  # noqa: E402


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, INDEX = _read("static", "kyiv.html"), _read("static", "light.html"), _read("static", "i18n.js"), _read("static", "index.html")
SRC = _read("app", "server.py")
P256 = base64.urlsafe_b64encode(b"\x04" + b"\x11" * 64).decode().rstrip("=")
AUTH = base64.urlsafe_b64encode(b"\x22" * 16).decode().rstrip("=")
GOOD = {"endpoint": "https://fcm.googleapis.com/fcm/send/dBw1ab2cd3EF4gh5", "keys": {"p256dh": P256, "auth": AUTH}}


# ---- F1: the link that planted HTML ----------------------------------------------------------------------------------
def test_the_carried_settings_have_one_shape_each():
    for page in (PAGE, LIGHT):
        imp = page[page.index('<script id="carry">'):page.index("</script>", page.index('<script id="carry">'))]
        assert "function shape(k,v)" in imp and "ok.indexOf(k)" not in imp
        assert "lang:/^(uk|en|fr)$/" in imp and "sndvol:/^\\d{1,3}$/" in imp
        assert "if(k==='myobl') return /^\\d{1,2}$/.test(String(o.uid))?JSON.stringify({uid:String(o.uid)}):null;" in imp
        assert "typeof o[q]!=='boolean'" in imp                               # layers: a map of booleans, nothing else
        assert "if(v!==null&&localStorage.getItem(k)===null) localStorage.setItem(k,v);" in imp
        for place_key in ("'slots'", "'home'", "'geo'"):
            assert place_key not in imp


def test_an_unknown_oblast_is_nothing_and_the_band_escapes_its_names():
    assert "const oblName=uid=>(OBL_N[uid]||['','',''])[LI()];" in I18N
    assert "if(u&&/^\\d{1,2}$/.test(u)&&OBL_N[u]) MYOBL={uid:u,name:oblName(u)};" in PAGE
    assert "const ON=esc(oblFull(MYU));" in PAGE
    assert "`${esc(rname(r))} ${l==='R'?t('b_red'):t('b_yel')}`" in PAGE and "`${esc(h)} ${l==='R'?t('b_red'):t('b_yel')}`" in PAGE
    assert "raionAlerts.map(a=>esc(LANG==='uk'?a.location_title:(a.location_title_en||a.location_title)))" in PAGE
    assert "${THREAT[g.type]?.en||esc(g.type)}" in INDEX and "sort().map(esc).join(', ')" in INDEX


# ---- F2 / F3: a subscription is a browser's or nothing ---------------------------------------------------------------
def test_only_a_browsers_subscription_is_accepted():
    assert push.clean_subscription(GOOD) == GOOD
    assert push.clean_subscription(dict(GOOD, expirationTime=None)) == GOOD
    assert push.clean_subscription(dict(GOOD, extra="x", keys=dict(GOOD["keys"], more="y"))) == GOOD    # nothing of the client's own
    for host in ("updates.push.services.mozilla.com", "wns2-par02p.notify.windows.com", "web.push.apple.com", "android.googleapis.com"):
        assert push.clean_subscription(dict(GOOD, endpoint=f"https://{host}/x/abcdefghijklmnop"))
    for bad in ("http://fcm.googleapis.com/fcm/send/dBw1ab2cd3EF4gh5",                  # not https
                "https://10.255.255.1:1/x", "https://evil.example/fcm/send/x",             # not a push service
                "https://fcm.googleapis.com.evil.example/x", "https://user:pw@fcm.googleapis.com/x",
                "https://fcm.googleapis.com", "not-even-a-url", "https://fcm.googleapis.com/a b",
                "https://fcm.googleapis.com/" + "x" * 1100):
        assert push.clean_subscription(dict(GOOD, endpoint=bad)) is None, bad
    assert push.clean_subscription(dict(GOOD, keys={"p256dh": "zz", "auth": "zz"})) is None
    assert push.clean_subscription(dict(GOOD, keys={"p256dh": P256, "auth": AUTH + "AA"})) is None
    assert push.clean_subscription(dict(GOOD, keys={})) is None
    assert push.clean_subscription("x") is None and push.clean_subscription(None) is None
    assert 'raise ValueError("push endpoint must be https")' in _read("app", "push.py")      # plain http: this machine only


def test_the_store_keeps_endpoint_and_keys_and_counts_the_strikes():
    st = server.Store(":memory:")
    st.push_add(push.clean_subscription(GOOD), {"lat": 50.45, "lon": 30.52}, ["bridges"], "uk")
    row = st.push_get(GOOD["endpoint"])
    assert row and row["sub"] == GOOD and row["topics"] == ["bridges"] and row["lang"] == "uk"
    assert st.push_get("https://fcm.googleapis.com/other") is None and st.push_count() == 1
    st.push_outcome(GOOD["endpoint"], 0); st.push_outcome(GOOD["endpoint"], 400)
    assert st.push_count() == 1
    st.push_outcome(GOOD["endpoint"], 201)                                   # a delivery clears the strikes
    st.push_outcome(GOOD["endpoint"], 0); st.push_outcome(GOOD["endpoint"], 0)
    assert st.push_count() == 1
    st.push_outcome(GOOD["endpoint"], 503); st.push_outcome(GOOD["endpoint"], 429)    # the service's trouble: no strike
    assert st.push_count() == 1
    st.push_outcome(GOOD["endpoint"], 403)                                   # the third strike
    assert st.push_count() == 0 and st.push_all() == []


def test_rows_stored_before_the_check_are_removed_at_start():
    st = server.Store(":memory:")
    st.conn.execute("INSERT INTO push_subs(endpoint,sub,home,created,last_ok) VALUES(?,?,?,?,?)",
                    ("http://10.255.255.1:1/x", json.dumps({"endpoint": "http://10.255.255.1:1/x"}), "{}", "t", "t"))
    st.conn.execute("INSERT INTO push_subs(endpoint,sub,home,created,last_ok) VALUES(?,?,?,?,?)",
                    (GOOD["endpoint"], json.dumps(GOOD), "{}", "t", "t"))
    st.conn.commit()
    assert st.push_purge_invalid() == 1 and st.push_count() == 1 and st.push_get(GOOD["endpoint"])


def _serve(st):
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", old


def _post(url, obj, headers=None):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def test_the_routes_refuse_junk_and_a_test_goes_to_a_stored_phone_only():
    st = server.State(server.Store(":memory:"), {})
    st.pusher = type("P", (), {"enabled": True, "pub": "k", "sent": [], "send_test": lambda self, ep: self.sent.append(ep)})()
    srv, base, old = _serve(st)
    try:
        assert _post(base + "/api/push/subscribe", {"subscription": {"endpoint": "http://10.255.255.1:1/x", "keys": {"p256dh": "zz", "auth": "zz"}}})[0] == 400
        assert _post(base + "/api/push/subscribe", {"subscription": {"endpoint": "not-even-a-url"}})[0] == 400
        assert _post(base + "/api/push/subscribe", {"subscription": GOOD, "home": {"lat": 50.45, "lon": 30.52}})[0] == 200
        assert _post(base + "/api/push/test", {"endpoint": "https://fcm.googleapis.com/fcm/send/unknown0000000000"})[0] == 404
        assert _post(base + "/api/push/test", {"endpoint": GOOD["endpoint"]})[0] == 200 and st.pusher.sent == [GOOD["endpoint"]]
        assert _post(base + "/api/push/test", {"endpoint": 5})[0] == 400
        key = json.loads(urllib.request.urlopen(base + "/api/push/key", timeout=10).read())
        assert key == {"enabled": True, "key": "k"}                               # no count of subscribers
    finally:
        srv.shutdown(); server.Handler.state = old


# ---- F7, F10: the headers, the 400s, the dashboard's files -------------------------------------------------------------
def test_every_answer_carries_the_headers_and_a_bad_parameter_is_a_400():
    st = server.State(server.Store(":memory:"), {})
    srv, base, old = _serve(st)
    try:
        for path, html_ in (("/m", True), ("/light", True), ("/api/version", False), ("/static/i18n.js", False), ("/sw.js", False)):
            with urllib.request.urlopen(base + path, timeout=10) as r:
                h = r.headers
            assert h["X-Content-Type-Options"] == "nosniff" and h["Referrer-Policy"] == "strict-origin-when-cross-origin", path
            assert "geolocation=(self)" in h["Permissions-Policy"] and "camera=()" in h["Permissions-Policy"], path
            assert h["Strict-Transport-Security"] is None                     # plain http here: HSTS only over https
            if html_:
                csp = h["Content-Security-Policy"]
                assert csp.startswith("default-src 'self'; script-src 'self' 'unsafe-inline';") and "connect-src 'self'" in csp
                assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp and "base-uri 'self'" in csp
                assert "https://fonts.googleapis.com" in csp and "https://tile.openstreetmap.org" in csp
                assert h["X-Frame-Options"] == "DENY"
            else:
                assert h["Content-Security-Policy"] is None, path
        for path in ("/api/stats?days=abc", "/api/impacts?hours=x", "/api/feed?limit=zz", "/api/history?hours=1e3"):
            code, body, _ = _get(base + path)
            assert code == 400 and body["error"].startswith("bad parameter: "), path
        code, body, _ = _get(base + "/api/stats?days=7")
        assert code == 200
        assert _get(base + "/static/admin.html")[0] == 404 and _get(base + "/static/access-login.html")[0] == 404
        assert _get(base + "/static/../app/server.py")[0] == 404
    finally:
        srv.shutdown(); server.Handler.state = old


def _get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}") if "json" in (r.headers.get("Content-Type") or "") else {}, r.headers
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}"), e.headers
        except ValueError:
            return e.code, {"html": raw.decode("utf-8", "replace")}, e.headers


def test_a_500_says_nothing_of_the_exception():
    assert 'self._json({"error": str(e)}, 500)' not in SRC
    assert SRC.count('self._json({"error": "server error"}, 500)') == 2
    assert "class BadRequest(ValueError)" in SRC and SRC.count('self._json({"error": f"bad parameter: {e}"}, 400)') == 2
    assert "int(q.get(" not in SRC                                             # every integer parameter goes through _int


# ---- F4: the whole-app lock on sessions ------------------------------------------------------------------------------------
def test_the_lock_is_a_sign_in_page_and_a_session():
    st = server.State(server.Store(":memory:"), {})
    srv, base, old = _serve(st)
    try:
        with mock.patch.dict(os.environ, {"ACCESS_KEY": "priv-key-for-the-test"}):
            code, body, h = _get(base + "/m")
            assert code == 401 and 'action="/access/login"' in body["html"] and 'name="next" value="/m"' in body["html"]
            assert h["Content-Security-Policy"] and "uak=" not in (h.get("Set-Cookie") or "")
            code, body, _ = _get(base + "/m?key=priv-key-for-the-test")                 # the old way: refused, and told
            assert code == 401 and "no longer goes in the address" in body["html"]
            assert _get(base + "/api/state")[0] == 401 and _get(base + "/tiles/sat/5/1/1.webp")[0] == 401
            # a wrong key: 401, the form again; the right one: 303 with the session cookie, back where the reader was
            req = urllib.request.Request(base + "/access/login", data=b"key=wrong&next=%2Flight", method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            try:
                urllib.request.urlopen(req, timeout=10); raise AssertionError("a wrong key opened the app")
            except urllib.error.HTTPError as e:
                assert e.code == 401

            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            op = urllib.request.build_opener(NoRedirect)
            req = urllib.request.Request(base + "/access/login", data=b"key=priv-key-for-the-test&next=%2Flight", method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            try:
                op.open(req, timeout=10); raise AssertionError("no redirect")
            except urllib.error.HTTPError as e:
                assert e.code == 303 and e.headers["Location"] == "/light"
                ck = e.headers["Set-Cookie"]
                assert ck.startswith("hacc=") and "HttpOnly" in ck and "SameSite=Strict" in ck and f"Max-Age={adminauth.ACCESS_TTL_S}" in ck
                token = ck.split(";")[0]
            assert _get(base + "/api/version", {"Cookie": token})[0] == 200
            assert _get(base + "/api/version", {"X-Access-Key": "priv-key-for-the-test"})[0] == 200
            assert _get(base + "/api/version", {"Cookie": "hsess=" + token.split("=", 1)[1]})[0] == 401
            # `next` never leaves this site
            req = urllib.request.Request(base + "/access/login", data=b"key=priv-key-for-the-test&next=https%3A%2F%2Fevil.example%2F", method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            try:
                op.open(req, timeout=10)
            except urllib.error.HTTPError as e:
                assert e.code == 303 and e.headers["Location"] == "/m"
            # a cross-site form is refused
            req = urllib.request.Request(base + "/access/login", data=b"key=priv-key-for-the-test", method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://evil.example"})
            try:
                op.open(req, timeout=10); raise AssertionError("cross-site login accepted")
            except urllib.error.HTTPError as e:
                assert e.code == 403
        assert _get(base + "/api/version")[0] == 200                              # no key: open to everyone
    finally:
        srv.shutdown(); server.Handler.state = old


# ---- F5, F6, F9, the container ------------------------------------------------------------------------------------------------
def test_the_rest_of_the_guards():
    assert re.search(r"class Handler\(BaseHTTPRequestHandler\):.*?\n    timeout = 20\n", SRC, re.S)
    body = SRC[SRC.index("def _peer_ip(self):"):SRC.index("def _peer_ip(self):") + 600]
    assert "return limits.client_ip(self.headers, peer) or peer" in body
    assert 'self.headers.get("X-Forwarded-For")' not in SRC                     # nowhere, not only here
    assert "home:cellOf(GEO)" in PAGE.replace(" ", "") and "const CELL={lat:10/111,lon:10/71};" in PAGE
    assert "os.path.commonpath([STATIC, p]) == STATIC" in SRC
    dk, entry = _read("Dockerfile"), _read("docker-entry.sh")
    assert "useradd --system --uid 10001" in dk and 'CMD ["./docker-entry.sh"]' in dk and "COPY docker-entry.sh" in dk
    assert "setpriv --reuid=heimdall --regid=heimdall" in entry and "exec python app/server.py" in entry
    bat = _read("deploy-fly.bat")
    assert "fly secrets set ADMIN_KEY" not in bat and "fly secrets set DEEPL_KEY" not in bat and "| fly secrets import" in bat
    for s in ("### 11.1 The audit of 18 October 2026 (1.58.35)", "`POST /access/login`", "push.clean_subscription", "Handler._int"):
        assert s in _read("docs", "TECHNICAL.md"), s
