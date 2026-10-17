"""1.29: the live line. One thread holds every open page, and it sends what changed instead of every page
downloading everything again after each post. The changes must rebuild EXACTLY what the server serves: the page
applies them with static/live.js (run here with node), and anything that does not fit is fetched in full."""
import json
import os
import random
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone

import pytest
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "static", "live.js")
NODE = shutil.which("node")


def _apply_in_node(cases):
    """[(kind, current, delta)] -> what static/live.js makes of each (None = 'fetch it in full')."""
    prog = ("const L=require(process.argv[1]);const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));"
            "const idf={mk:m=>String(m.id),fd:p=>p.post_id};"
            "console.log(JSON.stringify(cases.map(([k,cur,d])=>k==='st'?L.state(cur,d):L.list(cur,d,idf[k]))));")
    out = subprocess.run([NODE, "-e", prog, LIVE], input=json.dumps(cases), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_list_changes_rebuild_the_list_exactly():
    rnd = random.Random(7)
    cases, want = [], []
    items = [{"post_id": f"p{i}", "text": f"t{i}", "n": 0} for i in range(40)]
    nxt = 40
    for step in range(300):
        prev = server._keyed(items, lambda p: p["post_id"])
        cur_items = [dict(x) for x in items]
        r = rnd.random()
        if r < 0.3:                                   # a new post at the head, the oldest dropped
            k = rnd.randint(1, 3)
            cur_items = [{"post_id": f"p{nxt + j}", "text": "new", "n": 0} for j in range(k)] + cur_items[:40 - k]
            nxt += k
        elif r < 0.55:                                # a translation arrives for one post
            cur_items[rnd.randrange(len(cur_items))]["text"] += " (en)"
        elif r < 0.7:                                 # a new post AND a changed one
            cur_items[rnd.randrange(len(cur_items))]["n"] += 1
            cur_items = [{"post_id": f"p{nxt}", "text": "new", "n": 0}] + cur_items[:39]
            nxt += 1
        elif r < 0.85:                                # order changes
            rnd.shuffle(cur_items)
        else:                                         # entries removed in the middle
            del cur_items[rnd.randrange(len(cur_items))]
        cur = server._keyed(cur_items, lambda p: p["post_id"])
        cases.append(["fd", items, server._list_delta(prev, cur)])
        want.append(cur_items)
        items = cur_items
    got = _apply_in_node(cases)
    assert all(_canon(g) == _canon(w) for g, w in zip(got, want))
    kinds = {k for _, _, d in cases for k in d if k not in ("b", "h")}
    assert {"set", "pre", "n", "ids"} <= kinds                   # every form was exercised


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_state_changes_rebuild_the_state_exactly():
    def snap(active, obl, src, extra):
        return {"active": active, "oblasts": obl, "sources": src, "eradar": extra, "favourites": ["31", "14"],
                "config": {"demo": False, "canonical": None}, "notice": None}

    def entries(s):
        e = server._keyed(s["active"], server._alert_id)
        e["rest"] = {k: server._canon(v) for k, v in s.items() if k not in ("now", "active")}
        e["restd"] = {k: {sk: server._canon(sv) for sk, sv in v.items()} for k, v in s.items()
                      if k not in ("now", "active") and isinstance(v, dict)}
        e["h"] = "x" + e["h"]
        e["obj"] = s
        return e
    a1 = [{"location_uid": "31", "alert_type": "air_raid", "level": "red"}]
    s1 = snap(a1, {"31": {"status": "A"}, "14": {"status": "N"}}, {"ua": {"ok": True, "last": "1"}}, None)
    a2 = [{"location_uid": "14", "alert_type": "air_raid", "level": "yellow"}] + a1
    s2 = snap(a2, {"31": {"status": "A"}, "14": {"status": "P"}}, {"ua": {"ok": True, "last": "2"}}, {"ts": "t", "counts": {}})
    s3 = snap(a2[:1], {"31": {"status": "N"}, "14": {"status": "P"}}, {"ua": {"ok": True, "last": "3"}, "tg": {"ok": False}}, None)
    s3["notice"] = {"id": "n1", "text": {"en": "hello"}, "level": "info"}
    cases, want = [], []
    for a, b in ((s1, s2), (s2, s3), (s3, s1)):
        cases.append(["st", a, server._state_delta(entries(a), entries(b))])
        want.append(b)
    got = _apply_in_node(cases)
    assert [_canon(g) for g in got] == [_canon(w) for w in want]
    assert "sub" in cases[0][2] and "oblasts" in cases[0][2]["sub"] and "31" not in cases[0][2]["sub"]["oblasts"]


def _read_events(sock, until, want):
    buf, out = b"", []
    sock.settimeout(0.5)
    while time.time() < until and len(out) < want:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        while b"\n\n" in buf:
            msg, buf = buf.split(b"\n\n", 1)
            ev = data = None
            for line in msg.decode("utf-8").split("\n"):
                if line.startswith("event: "):
                    ev = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
            if ev:
                out.append((ev, data))
    return out


def test_one_thread_holds_every_page_and_a_new_post_reaches_them_as_a_change():
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5})
    old_state = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    st.hub = server.StreamHub(st)
    st.hub.start()
    port = srv.server_address[1]
    socks = []
    try:
        time.sleep(0.3)
        base = threading.active_count()
        for i in range(60):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(b"GET /api/stream?sync=mk,st,fd&lang=en HTTP/1.1\r\nHost: x\r\n\r\n")
            socks.append(s)
        hellos = [_read_events(s, time.time() + 5, 1) for s in socks]
        assert all(h and h[0][0] == "hello" and set(h[0][1]["h"]) == {"mk", "st", "fd"} for h in hellos)
        time.sleep(0.3)
        # sixty open pages, and no thread for any of them
        assert threading.active_count() <= base + 2, (base, threading.active_count())
        assert st.hub.online()["total"] == 60
        # a new post: the event, then one sync carrying it at the head of the feed
        post = {"post_id": "t/1", "channel": "kpszsu", "ts": datetime.now(timezone.utc).isoformat(),
                "text": "Шахед на Бровари", "tags": ["drones", "kyiv"], "text_en": "Shahed toward Brovary"}
        st.store.add_feed([post])
        st.publish({"kind": "feed", "ts": post["ts"], "post": post})
        for s in socks[:5] + socks[-5:]:
            evs, t_end = [], time.time() + 5
            while time.time() < t_end and not any(e == "sync" and "fd" in d for e, d in evs):
                evs += _read_events(s, t_end, 1)
            kinds = [e for e, _ in evs]
            assert "feed" in kinds, kinds
            fd = [d for e, d in evs if e == "sync" and "fd" in d][0]["fd"]
            assert fd["pre"][0]["post_id"] == "t/1" and fd["h"] == st.feed_pub(150)[3]["h"]     # 1.58.36: the public copy's hash
        # a page that goes away is forgotten
        for s in socks[:30]:
            s.close()
        t_end = time.time() + 5
        while time.time() < t_end and st.hub.online()["total"] != 30:
            st.publish({"kind": "tr", "ts": server.now_iso(), "post_id": "t/1", "lang": "en"})
            time.sleep(0.2)
        assert st.hub.online()["total"] == 30
    finally:
        for s in socks:
            try:
                s.close()
            except OSError:
                pass
        srv.shutdown()
        server.Handler.state = old_state


def test_the_pages_use_the_live_line_and_ask_only_as_a_safety_net():
    page = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
    light = open(os.path.join(ROOT, "static", "light.html"), encoding="utf-8").read()
    for p in (page, light):
        assert '<script src="/static/live.js"></script>' in p
    assert "const L=window.LiveSync" in page and "L.part('mk',d.mk,H.mk,MK)" in page
    assert "LiveSync.part('mk',d.mk,HL.mk,MKS)" in light
    assert "if(liveOK()&&!force&&Date.now()-lastPingAt<60000)" in page      # once a minute while it beats
    assert "if(force!==true&&liveOK()){ upd(); paint(); return; }" in light
    # a new post no longer makes the page download the feed and the marks while the line is up
    assert "if(!LIVE_SYNC||LITE)loadFeed(true);if(!LIVE_SYNC)loadMarkers();" in page


def test_the_team_message_expires_by_itself():
    st = server.State(server.Store(":memory:"), {})
    st.set_notice({"id": "n1", "text": {"en": "x"}, "level": "info", "ts": server.now_iso(),
                   "until": "2000-01-01T00:00:00+00:00"})
    assert st.notice_now() is None and st.notice is None
    assert (st.store.kv_get("notice") or "") == ""
    st.set_notice({"id": "n2", "text": {"uk": "y"}, "level": "warn", "ts": server.now_iso(), "until": None})
    assert st.snapshot()["notice"]["id"] == "n2"                 # it travels in the alerts state
