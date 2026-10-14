"""1.58.24 — stabilisation: what a review of 1.58.16 → 1.58.23 found, each case as it was found.

The limits (1.58.17) must never refuse what a reader needs: pages opening together behind one address waited for the
same answer and each spent the allowance on it; off Fly, a client could write his own address; the desktop page's
events log was refused in a mass alert. A hromada in two pieces was tinted on one in the channel picture, and a
hromada's alert did not keep its raion on in the channel. On the map, stale drones counted in an oblast's "~N", a
target placed in an oblast did not light its name, and the tap area shrank zoomed out."""
import http.client
import os
import re
import threading
import time
import urllib.error
import urllib.request

import chanpost
import limits
import pytest
import server
from test_limits_15817 import _get, _serve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


TAC, LIGHT, ADMIN = _read("static", "kyiv.html"), _read("static", "light.html"), _read("static", "admin.html")


@pytest.fixture
def on_fly(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "heimdall-test")


# ---- the shared answers ------------------------------------------------------------------------------------------------
def _state():
    st = server.State(server.Store(":memory:"), {})
    st._resp, st._resp_locks, st._resp_used = {}, {}, {}      # the class keeps one set for the process: this test's own
    return st


def test_pages_waiting_for_the_same_answer_spend_one_build_between_them():
    st = _state()
    asked, built, got = [], [], []
    go = threading.Event()

    def gate():
        asked.append(1)
        return len(asked) == 1                         # one build in this client's allowance, no more

    def build():
        built.append(1)
        time.sleep(0.2)
        return {"places": [1, 2, 3]}

    def page():
        go.wait()
        got.append(st.cached("places:14,31", 3600, build, gate=gate))
    ts = [threading.Thread(target=page) for _ in range(40)]
    for t in ts:
        t.start()
    go.set()
    for t in ts:
        t.join(10)
    assert len(built) == 1 and len(asked) == 1         # the others waited for it and spent nothing
    assert len(got) == 40 and all(h is not None and h[3] == {"places": [1, 2, 3]} for h in got)


def test_a_refused_question_leaves_nothing_behind():
    st = _state()
    for i in range(500):
        assert st.cached(f"hist:{i}:odd", 60, lambda: {"x": 1}, gate=lambda: False) is None
    assert not any(k.startswith("hist:") for k in list(st._resp) + list(st._resp_locks) + list(st._resp_used))


def test_an_answer_still_asked_for_is_not_pushed_out_by_odd_questions():
    st = _state()
    st.cached("places:14,31", 3600, lambda: {"p": 1})
    for i in range(st.RESP_MAX + 100):
        st.cached(f"hist:{i}:", 60, lambda: {"i": 1})
        if i % 50 == 0:
            st.cached("places:14,31", 3600, lambda: {"p": 2})   # the pages keep asking for it
    assert len(st._resp) <= st.RESP_MAX and st._resp["places:14,31"][3] == {"p": 1}
    assert len(st._resp_used) <= st.RESP_MAX + 1


# ---- the address -------------------------------------------------------------------------------------------------------
def test_off_fly_the_header_is_not_believed(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    assert limits.client_ip({"Fly-Client-IP": "203.0.113.50"}, "151.101.1.1") == "151.101.1.1"
    assert limits.client_ip({"Fly-Client-IP": "203.0.113.50"}, "10.1.2.3") is None      # Render's proxy: never limited
    monkeypatch.setenv("FLY_APP_NAME", "x")
    assert limits.client_ip({"Fly-Client-IP": "203.0.113.50"}, "172.16.0.2") == "203.0.113.50"


# ---- over HTTP ---------------------------------------------------------------------------------------------------------
def test_the_events_log_is_one_copy_and_never_refused_in_a_mass_alert(on_fly):
    st = server.State(server.Store(":memory:"), {})
    st.limits = limits.Limits({"build": (1, 0.001), "write": (1, 0.001), "push": (1, 0.001)})
    srv, old, base = _serve(st)
    try:
        for i in range(20):                            # one desktop page, an event after another
            code, body, _ = _get(base, "/api/events_log?limit=60", ip="198.51.100.77")
            assert code == 200 and "events" in body, i
        assert _get(base, "/api/events_log?limit=100000", ip="198.51.100.78")[0] == 200
        assert _get(base, "/api/events_log?limit=abc", ip="198.51.100.79")[0] == 200
        assert {k for k in st._resp if k.startswith("evlog:")} <= {"evlog:60", "evlog:200", "evlog:500"}
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_a_negative_length_is_refused_and_a_finished_session_signs_out(on_fly):
    st = server.State(server.Store(":memory:"), {})
    srv, old, base = _serve(st)
    try:
        host = base.split("//")[1]
        c = http.client.HTTPConnection(host, timeout=10)
        c.putrequest("POST", "/api/flag")
        c.putheader("Content-Length", "-1")
        c.putheader("Content-Type", "application/json")
        c.endheaders()
        assert c.getresponse().status == 413
        c.close()

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        req = urllib.request.Request(base + "/admin/logout", data=b"", headers={"Cookie": "hsess=ended-long-ago"})
        try:
            urllib.request.build_opener(NoRedirect).open(req, timeout=10)
            raise AssertionError("no redirect")
        except urllib.error.HTTPError as e:
            assert e.code == 303 and e.headers["Location"] == "/admin"
            assert "hsess=;" in e.headers["Set-Cookie"] and "Max-Age=0" in e.headers["Set-Cookie"]
    finally:
        srv.shutdown()
        server.Handler.state = old
    src = _read("app", "server.py")
    assert "if n < 0 or n > 65536:" in src
    assert "if signed:\n            self._sec(" in src                 # an ended session's sign-out is not logged
    assert "(r.ok&&body.everyone)){ location.reload();" in ADMIN       # everyone signed out: this page too


# ---- hromadas ----------------------------------------------------------------------------------------------------------
def test_a_hromada_alert_keeps_its_raion_on_in_the_channel():
    assert chanpost.area_on("bucha", {"hr:14:701": "R"})                # Borshchahivska is in Bucha raion
    assert not chanpost.area_on("brovary", {"hr:14:701": "R"})
    assert chanpost.area_on("14:*", {"hr:14:701": "Y"})
    assert chanpost.area_on("bucha", {"bucha": "Y"}) and not chanpost.area_on("bucha", {})


def test_the_channel_picture_fills_every_piece_of_a_hromada():
    src = _read("app", "mapshot.py")
    i = src.index("for fk, lvl in fills.items():")
    block = src[i:src.index("if tinted:", i)]
    assert "for r in rings:" in block and "ImageChops.logical_xor" in block and "rings[0]" not in block


# ---- the map -----------------------------------------------------------------------------------------------------------
def test_the_oblast_estimate_counts_no_stale_drone_and_a_placed_one_lights_the_name():
    assert "if(m.status||m.endedBy||m.stale||m.type!=='drones'||!m.oblast_uid) continue;" in TAC
    assert ".concat(Object.keys(OBLPLACED)));" in TAC


def test_a_target_is_as_easy_to_tap_zoomed_out():
    assert "kx(Math.max(18*MSK,18*KPX))" in TAC and "14*KPX" not in TAC


def test_a_failing_live_line_is_asked_again_later_and_later_one_at_a_time():
    for page, fail, start in ((TAC, "esFail", "function connect(){\n  clearTimeout(esT); try{ es&&es.close(); }catch(e){}"),
                              (LIGHT, "esF", "clearTimeout(esT); try{ esL&&esL.close(); }catch(e){}")):
        assert start in page
        # 3 s (the Tactical page) or 5 s (Light), doubled at each failure up to 30 s, ±25 %
        assert re.search(r"Math\.min\((30000|3e4),(3000|5e3)\*2\*\*(Math\.min\()?" + fail + r"\+\+(,\d\))?\)\*\((0)?\.75\+Math\.random\(\)(\*0\.5|/2)\)", page)
        assert fail + "=0;" in page                     # a line that worked starts again from the shortest wait
    assert "setTimeout(connect,3000)" not in TAC and "setTimeout(connectLive,5000)" not in LIGHT
