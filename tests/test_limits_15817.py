"""1.58.17 — limits on abuse of the public API (the audit's first recommendation).

The owner picked "limit the abuse" (not signed tokens, not Cloudflare Turnstile): a mobile operator puts thousands of
phones behind one address, so what is limited is what costs the server — an answer nobody else asked for, a flag, a
flood of push requests, hundreds of live lines — never the alert status, the marks, the feed or a usual question."""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from unittest import mock

import limits
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


# ---- the allowance -----------------------------------------------------------------------------------------------------
def test_a_burst_then_the_refill():
    c = Clock()
    lim = limits.Limits({"build": (3, 0.5)}, clock=c)
    assert [lim.take("a", "build") for _ in range(3)] == [0, 0, 0]
    assert lim.take("a", "build") == 2               # one more in 2 s
    assert lim.take("b", "build") == 0               # another client has its own
    c.t += 2.0
    assert lim.take("a", "build") == 0
    assert lim.report()["build"] == 1


def test_the_address_is_fly_s_and_never_kept():
    assert limits.client_ip({"Fly-Client-IP": "203.0.113.7", "X-Forwarded-For": "1.2.3.4"}, "172.16.0.2") == "203.0.113.7"
    assert limits.client_ip({"X-Forwarded-For": "1.2.3.4"}, "198.51.100.9") == "198.51.100.9"   # not what a client writes
    assert limits.client_ip({}, "127.0.0.1") is None and limits.client_ip({}, "::1") is None   # this machine
    with mock.patch.dict(os.environ, {"FLY_APP_NAME": "x"}):
        assert limits.client_ip({}, "172.16.0.2") is None      # Fly's proxy: everybody at once — never limited
    lim = limits.Limits()
    h = lim.who("203.0.113.7")
    assert len(h) == 16 and "203" not in h and h == lim.who("203.0.113.7")
    assert "203.0.113.7" not in repr(lim.b) and limits.Limits().who("203.0.113.7") != h   # salted per process and day


def test_full_buckets_are_forgotten():
    c = Clock()
    lim = limits.Limits({"build": (2, 1.0)}, clock=c)
    for i in range(10):
        lim.take(f"c{i}", "build")
    c.t += 5
    lim._prune(c())
    assert lim.b == {}


# ---- the cache: a refused rebuild is given the last copy ---------------------------------------------------------------
def test_a_refused_rebuild_gets_the_last_copy_and_a_never_built_one_none():
    st = server.State(server.Store(":memory:"), {})
    n = []
    hit = st.cached("stats:14", 120, lambda: n.append(1) or {"v": len(n)})
    assert st.cached("stats:14", 120, lambda: n.append(1) or {"v": 9}, gate=lambda: False) is hit   # fresh: no gate
    st._resp["stats:14"] = (time.time() - 999,) + hit[1:]
    stale = st.cached("stats:14", 120, lambda: n.append(1) or {"v": 9}, gate=lambda: False)
    assert stale[3] == {"v": 1} and len(n) == 1         # stale, not rebuilt
    assert st.cached("stats:3", 120, lambda: {"v": 3}, gate=lambda: False) is None
    assert st.cached("stats:3", 120, lambda: {"v": 3}, gate=lambda: True)[3] == {"v": 3}


def test_the_kept_answers_are_bounded():
    st = server.State(server.Store(":memory:"), {})
    st.cached("state", 5, lambda: {"s": 1})
    for i in range(st.RESP_MAX + 50):
        st.cached(f"hist:{i}:", 60, lambda: {"i": 1})
    assert len(st._resp) <= st.RESP_MAX and "state" in st._resp


# ---- over HTTP ---------------------------------------------------------------------------------------------------------
def _serve(st):
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, old, f"http://127.0.0.1:{srv.server_address[1]}"


def _get(base, path, ip="203.0.113.7", **hd):
    req = urllib.request.Request(base + path, headers=dict({"Fly-Client-IP": ip}, **hd))
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read() or b"null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), dict(e.headers)


def test_unusual_questions_are_limited_and_the_usual_ones_never():
    st = server.State(server.Store(":memory:"), {})
    st.limits = limits.Limits({"build": (3, 0.001), "write": (1, 0.001), "push": (2, 0.001)})
    srv, old, base = _serve(st)
    try:
        # three different windows nobody else asked for: built; the fourth is refused, with when to try again
        now = int(time.time()) // 60 * 60
        codes = [_get(base, f"/api/replay?from={now - 7200 - 60 * i}&to={now - 60 * i}")[0] for i in range(4)]
        assert codes == [200, 200, 200, 429]
        code, body, hd = _get(base, f"/api/replay?from={now - 9000}&to={now - 3000}")
        assert code == 429 and int(hd["Retry-After"]) >= 1 and body["retry_after"] >= 1
        # a window already built is still given to this client
        assert _get(base, f"/api/replay?from={now - 7200}&to={now}")[0] == 200
        # what a reader needs is never limited
        for p in ("/api/state", "/api/markers", "/api/feed?limit=80", "/api/version"):
            assert _get(base, p)[0] == 200, p
        # another address has its own allowance; this machine and the dashboard have none
        assert _get(base, f"/api/replay?from={now - 9000}&to={now - 3000}", ip="198.51.100.1")[0] == 200
        req = urllib.request.Request(base + f"/api/replay?from={now - 9600}&to={now - 3600}")
        assert urllib.request.urlopen(req, timeout=10).status == 200
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            assert _get(base, f"/api/replay?from={now - 9660}&to={now - 3660}", Cookie="uadm=adm-test")[0] == 200
        # the events log is a query each time; its size is bounded
        assert _get(base, "/api/events_log?limit=100000", ip="198.51.100.2")[0] == 200
        assert st.limits.report()["build"] >= 2
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_flags_and_bodies():
    st = server.State(server.Store(":memory:"), {})
    st.limits = limits.Limits({"build": (3, 0.001), "write": (1, 0.001), "push": (2, 0.001)})
    srv, old, base = _serve(st)

    def post(path, body, ip="203.0.113.9"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json", "Fly-Client-IP": ip})
        try:
            return urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        first = post("/api/flag", {"marker": "x/1", "reason": "other"})
        assert first != 429 and post("/api/flag", {"marker": "x/1", "reason": "other"}) == 429
        assert post("/api/flag", b"{" + b" " * 70000 + b"}", ip="203.0.113.10") == 413
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_the_live_lines_of_one_client_are_counted():
    hub = server.StreamHub.__new__(server.StreamHub)
    hub.plock, hub.pending, hub.by_who, hub.clients = threading.Lock(), [], {}, {}
    hub.wake = lambda: None
    for _ in range(3):
        hub.add(None, "uk", set(), True, "tac", who="h1")
    hub.add(None, "uk", set(), True, "tac")
    assert hub.count_of("h1") == 3 and hub.count_of("h2") == 0
    hub._unwho("h1")
    assert hub.count_of("h1") == 2
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert "hub.count_of(who) >= limits.STREAMS" in src and limits.STREAMS >= 200


def test_the_dashboard_shows_the_refusals():
    assert "tr('sv_lim'" in ADMIN and ADMIN.count("sv_lim:") == 2
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert '"limits": st.limits.report()' in src
