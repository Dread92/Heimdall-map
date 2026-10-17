"""The server under an attack's load (25 Sep 2026). Every new post made every open page ask for the marks, the feed
and the state at once; each request recomputed them from scratch, and the marks' computation called the machine
translator — over the network, up to 6 s a post — for any post without an English text. The requests piled up
and the server stopped answering, twice. Measured on a copy with 200 posts in the window: 3 requests/s with time-
outs before, ~1,000/s with none after."""
import os
import threading
import time
from datetime import datetime, timezone

import server

SRC = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "server.py"), encoding="utf-8").read()


def test_the_marks_never_wait_on_a_network_translation(monkeypatch):
    st = server.State(server.Store(":memory:"), {})
    with st.store.lock:
        st.store.conn.execute("INSERT INTO feed(post_id,channel,ts,text,tags) VALUES(?,?,?,?,?)",
                              ("t/1", "kyiv_airdef", datetime.now(timezone.utc).isoformat(), "Шахед над Броварами", "[]"))
        st.store.conn.commit()

    def no_network(*a, **k):
        raise AssertionError("a network translation in the marks' path")
    monkeypatch.setattr(server, "to_en", no_network)
    if server._tr:
        monkeypatch.setattr(server._tr, "machine", no_network)
    posts = st.store.feed_since(45)
    assert posts and posts[0]["text_en"]                 # the offline glossary, instantly


def test_one_computation_for_everybody():
    st = server.State(server.Store(":memory:"), {})
    calls = []

    def build():
        calls.append(1)
        time.sleep(0.2)
        return {"x": 1}
    out = []
    ts = [threading.Thread(target=lambda: out.append(st.cached("k", 10, build, ver=1))) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1 and len({id(h[1]) for h in out}) == 1      # built once, the same bytes for all
    st.cached("k", 10, build, ver=2)
    assert len(calls) == 2                                             # a change (a new post) rebuilds it


def test_the_busy_answers_are_cached():
    for route, key in (('"/api/markers"', "st.markers_pub()"), ('"/api/state"', 'st.state_pub()'),      # 1.58.36: the public copies, cached too
                       ('"/api/feed"', 'st.feed_now(limit)'), ('"/api/stats"', 'st.cached(f"stats:')):
        i = SRC.index(f"if u.path == {route}:")
        assert key in SRC[i:i + 700], route
    assert "state.markers_now()" in SRC                                # the proximity pushes share it too
    assert "request_queue_size = 128" in SRC


def test_state_and_feed_go_through_the_one_cache():
    """1.29: the helpers the routes and the stream hub share are the cache, not a recomputation."""
    for name, key in (("state_now", 'self.cached("state", 5, self._state_obj, ver=self.seq)'),
                      ("feed_now", 'self.cached(f"feed:{limit}", 15, lambda: self._feed_obj(limit), ver=self.seq)')):
        i = SRC.index(f"    def {name}(self")
        assert key in SRC[i:i + 300], name
