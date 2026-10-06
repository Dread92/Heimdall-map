"""1.41: "the app goes off sometimes". The server records what it needs to say why (its CPU, the CPU the host took
away, memory, slow requests, every start), the dashboard shows it, and the app opens and says it is reconnecting
when the server does not answer — without ever showing stored data as current."""
import json
import os
import re

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, SW, ADMIN, I18N, SRC = (_read("static/kyiv.html"), _read("static/light.html"), _read("static/sw.js"),
                                     _read("static/admin.html"), _read("static/i18n.js"), _read("app/server.py"))


def test_vitals_sample_the_process_and_note_only_slow_requests():
    st = server.State(server.Store(":memory:"), {})
    v = server.Vitals(st)
    v._prev = (v._prev or (0, [0.0, 0, 0, 0, 0, 0]))
    v._prev = (v._prev[0] - 10, v._prev[1])
    v.sample()
    v.note("/api/state?x=1", 2500)
    v.note("/api/version", 120)                       # fast: not kept
    v.note("/api/stream", 600000)                     # a live line is long by nature: never "slow"
    r = v.report()
    assert r["slow_1h_n"] == 1 and r["slow_1h"][0]["path"] == "/api/state?x=1"
    assert set(r) >= {"cpu", "steal", "rss", "late", "starts_7d", "restarts_same_build_7d", "boots", "uptime_s"}
    assert "ip" not in json.dumps(r).lower().replace("ip\"", "")    # nothing about who


def test_every_start_is_kept_with_its_build_and_a_same_build_start_counts_as_a_restart():
    st = server.State(server.Store(":memory:"), {})
    server.Vitals(st)
    server.Vitals(st)
    v = server.Vitals(st)
    boots = json.loads(st.store.kv_get("boots"))
    assert len(boots) == 3 and all({"ts", "build", "app"} <= set(b) for b in boots)
    assert v.report()["restarts_same_build_7d"] == 2 and v.report()["starts_7d"] == 3


def test_requests_are_timed_and_the_dashboard_shows_the_server():
    i = SRC.index("    def do_GET(self):")
    assert "v.note(self.path.split(\"?\")[0], (time.monotonic() - t0) * 1000)" in SRC[i:i + 400]
    assert '"process": vt.report() if vt else None' in SRC
    assert "state.vitals = Vitals(state)" in SRC
    assert 'id="srv"' in ADMIN and "drawSrv(ON.process);" in ADMIN
    for key in ("sv_h", "sv_cpu", "sv_steal", "sv_mem", "sv_slow", "sv_starts"):
        assert len(re.findall(r"\b" + key + r":'", ADMIN)) == 2, key    # English and Ukrainian


def test_the_pages_are_kept_for_when_the_server_does_not_answer_but_never_the_data():
    keep = SW[SW.index("const SHELL"):SW.index("// the addresses")]
    assert "'/m'" in keep and "'/light'" in keep and "/static/kyiv-map.json" in keep and "/api/" not in keep
    shell = SW[SW.index("const SHELL"):SW.index("\n", SW.index("const SHELL"))]
    assert "kyiv-map" not in shell and "'/m'" not in shell                  # nothing big downloaded ahead on 2G
    assert "if (r.status >= 500) return caches.match(key)" in SW            # a deploy or an overloaded host
    assert SW.index("fetch(e.request)") < SW.index("caches.match(key)")      # network first
    assert "if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});" in PAGE
    assert "navigator.serviceWorker.register('/sw.js')" in LIGHT


def test_the_app_says_it_has_no_connection_and_what_does_not_depend_on_it():
    assert 'id="netbar"' in PAGE and "t('net_t')" in PAGE and "t('net_b')" in PAGE
    assert "const down=everOK?(!netOK&&sec>15):Date.now()-T_LOAD>15000" in PAGE
    assert "t(down?'net_t':'net_wait')" in PAGE                               # never "updated 5 s ago" before data
    for word in ("do not depend on Heimdall", "від Heimdall не залежать", "ne dépendent pas de Heimdall"):
        assert word in I18N, word
    assert "if(Date.now()-LAST_OK>15000){ $('off').hidden=false;" in LIGHT


def test_the_diagnostics_script_writes_where_git_never_looks():
    bat = _read("scripts/diagnose.bat")
    assert "fly machine status" in bat and "fly logs" in bat and "diag\\fly-diag.txt" in bat
    assert "auth token" not in bat and "secrets" not in bat                  # never a key or a token
    assert "diag/" in _read(".gitignore")
