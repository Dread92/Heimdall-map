"""1.46: the server's work, measured and cut (docs/TECHNICAL.md §5.5).

A profile of the running service on an attack-night cadence (the channels read every 5 s) found 87 % of its CPU in
one place: every outgoing request built a new TLS context and loaded the system's ~150 root certificates into it,
15–25 ms each time. One shared context took the process from 10 % of a core to 1.6 %. The pages were also sent the
time of every source's last reading at each beat of the live line — ~80 % of what the line carried — and the marks
were rebuilt reading every post's oblasts again.
"""
import gzip
import json
import os
import ssl
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import geo
import server
import translate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8") as f:
    PAGE = f.read()


class _Resp:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"{}"


def test_every_outgoing_request_shares_one_tls_context():
    assert isinstance(server._SSL_CTX, ssl.SSLContext) and isinstance(translate._CTX, ssl.SSLContext)
    seen = []
    with mock.patch.object(urllib.request, "urlopen", lambda req, timeout=None, context=None: seen.append(context) or _Resp()):
        server.http_get("https://t.me/s/kpszsu")
        server.http_get("https://siren.pp.ua/api/v3/alerts/status")
    assert seen == [server._SSL_CTX, server._SSL_CTX]
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert "urlopen(req, timeout=120, context=_SSL_CTX)" in src            # the nightly summary
    tsrc = open(os.path.join(ROOT, "app", "translate.py"), encoding="utf-8").read()
    assert tsrc.count("_ur.urlopen(") == 3 == tsrc.count("context=_CTX) as r:")      # Google, DeepL, Google Cloud


def test_the_pages_get_whether_a_source_works_and_nothing_more():
    st = server.State(server.Store(":memory:"), {})
    st.set_source("tg:kpszsu", True, count=3, new=1)
    st.set_source("ukrainealarm_proxy", False, error="HTTP 502")
    assert st.snapshot()["sources"] == {"tg:kpszsu": {"ok": True}, "ukrainealarm_proxy": {"ok": False}}
    h = st._state_obj()["h"]
    # a new reading changes its time and its counts: the pages' state is the same
    with mock.patch.object(server, "now_iso", lambda: "2099-01-01T00:00:00Z"):
        st.set_source("tg:kpszsu", True, count=7, new=0)
    assert st._state_obj()["h"] == h
    st.set_source("tg:kpszsu", False, error="timeout")                 # a source that fails: that is news
    assert st._state_obj()["h"] != h
    assert st.sources["tg:kpszsu"]["error"] == "timeout"                 # the dashboard (/api/health) keeps the detail


def test_the_oblasts_a_post_names_are_read_once():
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    st.store.add_feed([{"post_id": f"rivne_radar/{i}", "channel": "rivne_radar", "ts": (now - timedelta(minutes=m)).isoformat(timespec="seconds"),
                        "text": t, "tags": ["drones"], "text_en": t, "en_fallback": True}
                       for i, (m, t) in enumerate([(6, "Це він на Хмельниччині"), (3, "Шахед на Сарни")])])
    calls = []
    real = geo.oblasts_named
    with mock.patch.object(geo, "oblasts_named", lambda *a: calls.append(a) or real(*a)):
        st.markers()
        n = len(calls)
        st.markers()
    assert n >= 2 and len(calls) == n                                       # the second pass reads none again


def test_the_place_lists_are_built_once_and_sent_gzipped():
    st = server.State(server.Store(":memory:"), {})
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/api/places?oblast=all"
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"Accept-Encoding": "gzip"}), timeout=10)
        assert r.headers.get("Content-Encoding") == "gzip"
        places = json.loads(gzip.decompress(r.read()))["places"]
        assert len(places) > 400 and "places:all" in st._resp
        built = st._resp["places:all"][0]
        urllib.request.urlopen(url, timeout=10).read()
        assert st._resp["places:all"][0] == built                       # not rebuilt
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_the_small_places_are_fetched_only_with_their_layer():
    i = PAGE.index("async function loadMap(){")
    body = PAGE[i:PAGE.index("\n}\n", i)]
    assert "/api/places?oblast=all" not in body and "if(LAYERS.minor) loadVillages();" in body
    assert "['/api/places?oblast=all','/api/places?villages=scope']" in PAGE and '<g id="minorg"></g><g id="villg"></g>' in PAGE


def test_sqlite_syncs_at_checkpoints():
    st = server.Store(":memory:")
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert 'PRAGMA synchronous=NORMAL' in src
    assert st.conn.execute("PRAGMA synchronous").fetchone()[0] == 1          # NORMAL
