"""1.58.3 — the private channel's kill switch on the dashboard, and a server panel that says why it restarted.

The owner: "il faudrait faire un killswitch dans le analytic board"; then, of the dashboard's server panel after the
1.58 deploy (CPU 99 % max, /api/stats 16.6 s, "Starts in 7 days: 58 · without a new version (crash, out of memory,
watchdog): 10"): "should we take any kind of action, should I worry". A restart with the same code was counted as a
crash, though a secret set, a deploy of the docs alone and Fly moving the machine all restart it the same way.
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import chanpost  # noqa: E402
import server  # noqa: E402
from test_chanpost_158 import API, KV, T0, Clock, mark, poster  # noqa: E402

ADM = {"X-Admin-Key": "adm-test"}   # 1.58.21: the dashboard key in a header — never in the address

ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()


# ---- the switch -------------------------------------------------------------------------------------------------------
def test_off_the_channel_makes_no_call_at_all_and_on_it_carries_on():
    clk, api, kv = Clock(), API(), KV()
    p, st = poster(api, kv, clk)
    st.marks = [mark(t=T0)]
    p.tick()
    assert [c[0] for c in api.calls] == ["sendPhoto"]
    kv.kv_set(chanpost.KV_ON, "0")
    clk.t += 60
    st.marks = [mark(place="Княжичі", lon=30.75, lat=50.47, t=clk.t), mark(place="Бровари", tag="#13", t=clk.t)]
    p.tick()                                            # a new report and a new target: nothing sent
    clk.t += chanpost.END_AFTER_S + 60
    st.marks = []
    p.tick()                                            # a closing line: nothing sent either
    assert len(api.calls) == 1
    assert p.health()["note"].startswith("switched OFF on the dashboard")
    kv.kv_set(chanpost.KV_ON, "1")
    p.tick()                                            # on again: the target gone meanwhile is closed …
    assert [c[0] for c in api.calls] == ["sendPhoto", "sendMessage"]      # 1.58.7: its closing line, in reply
    st.marks = [mark(place="Ірпінь", tag="#14", t=clk.t - 30 * 60)]
    p.tick()                                            # … and nothing reported while it was off is posted late
    assert len(api.calls) == 2


def test_the_switch_is_on_unless_set_off():
    p, _ = poster()
    assert p.enabled()
    p.kv.kv_set(chanpost.KV_ON, "1")
    assert p.enabled()
    p.kv.kv_set(chanpost.KV_ON, "0")
    assert not p.enabled()


def test_the_dashboard_route_needs_the_key_and_sets_the_switch():
    st = server.State(server.Store(":memory:"), {})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(path, body, k=False):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=dict({"Content-Type": "application/json"}, **(ADM if k else {})))
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            try:
                post("/api/admin/channel_switch", {"on": False})
                raise AssertionError("switched without the key")
            except urllib.error.HTTPError as e:
                assert e.code in (401, 403)
            assert st.store.kv_get("chan_on") is None
            d = post("/api/admin/channel_switch", {"on": False}, k=True)
            assert st.store.kv_get("chan_on") == "0" and d["channel"]["on"] is False
            d = post("/api/admin/channel_switch", {"on": True}, k=True)
            assert st.store.kv_get("chan_on") == "1" and d["channel"]["on"] is True
            on = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/api/online", headers=ADM), timeout=10).read())
            assert set(on["channel"]) == {"configured", "running", "on", "health"}
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_the_switch_is_on_the_live_tab_in_both_languages():
    assert '<div class="aisws chsw" id="chsw" hidden></div>' in ADMIN
    assert ADMIN.index('id="chsw"') < ADMIN.index('<details class="nk" id="nk">')        # above the danger zone
    assert "fetch('/api/admin/channel_switch'" in ADMIN and "confirm(tr(want?'cs_q_on':'cs_q_off'))" in ADMIN
    for k in ("cs_h:", "cs_none:", "cs_setup:", "cs_note_on:", "cs_note_off:", "cs_q_off:", "cs_q_on:", "sv_starts2:", "sv_unknown:"):
        assert ADMIN.count(k) == 2, k


# ---- why it restarted -------------------------------------------------------------------------------------------------
def _vitals(boots, ex, tmp_path):
    st = server.State(server.Store(":memory:"), {})
    st.store.kv_set("boots", json.dumps(boots))
    with mock.patch.object(server, "DB_PATH", str(tmp_path / "alerts.sqlite")):
        if ex:
            server.record_exit(ex)
        v = server.Vitals(st)
    return v


def _hour_ago():
    return (server.datetime.now(server.timezone.utc) - server.timedelta(hours=1)).isoformat()


def test_a_start_after_a_stop_signal_is_a_clean_restart(tmp_path):
    prev = {"ts": _hour_ago(), "build": server.BUILD, "app": "1.58"}
    v = _vitals([prev], "stop", tmp_path)
    assert v.boots[-1]["prev_end"] == "stop"
    r = v.report()["restarts_7d"]
    assert r["stop"] == 1 and r["unclean"] == 0 and r["new_build"] == 0


def test_a_start_with_nothing_written_is_unexpected_and_a_new_build_is_a_deploy(tmp_path):
    prev = {"ts": _hour_ago(), "build": server.BUILD, "app": "1.58"}
    v = _vitals([prev], None, tmp_path)
    assert v.boots[-1]["prev_end"] == "unclean" and v.report()["restarts_7d"]["unclean"] == 1
    old = {"ts": _hour_ago(), "build": "0ld", "app": "1.57"}
    v = _vitals([old], "stop", tmp_path)
    assert v.report()["restarts_7d"]["new_build"] == 1


def test_a_stop_written_before_the_previous_start_does_not_count_for_it(tmp_path):
    # the file from an older stop, then a run that crashed: no new line was written — unexpected
    with mock.patch.object(server, "DB_PATH", str(tmp_path / "alerts.sqlite")):
        server.record_exit("stop")
    later = {"ts": "2099-01-01T00:00:00+00:00", "build": server.BUILD, "app": "1.58"}
    st = server.State(server.Store(":memory:"), {})
    st.store.kv_set("boots", json.dumps([later]))
    with mock.patch.object(server, "DB_PATH", str(tmp_path / "alerts.sqlite")):
        v = server.Vitals(st)
    assert v.boots[-1]["prev_end"] == "unclean"


def test_the_watchdog_and_the_signals_write_how_the_process_ended():
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert 'record_exit("watchdog")\n                os._exit(3)' in src
    assert "for sg in (signal.SIGINT, signal.SIGTERM):" in src and 'record_exit("stop")\n        raise KeyboardInterrupt' in src
    assert "last-exit.json" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    # and the first /api/stats after a start is computed in the background, not while a reader waits
    assert 'threading.Thread(target=warm, daemon=True, name="warm").start()' in src
    # the CPU line is red for a dedicated CPU's trouble, not for a start
    assert "row(P.cpu.avg>50?'bad'" in ADMIN
