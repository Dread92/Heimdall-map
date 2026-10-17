"""1.58.36 — the owner: "the sources, we are not going to show them." A reader is shown no channel: not in the answers
(a token in place of every name, the ids included, the channels' health as one line), not in the pages (no name, no link
to the post, no map of names), not in the README. The service and the dashboard keep the real names."""
import json
import os
import re
import sys
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import server  # noqa: E402


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, LIGHT, I18N, README = _read("static", "kyiv.html"), _read("static", "light.html"), _read("static", "i18n.js"), _read("README.md")


def test_a_channel_reaches_a_reader_only_as_a_token():
    st = server.State(server.Store(":memory:"), {"telegram_channels": ["kpszsu", "kyiv_airdef"]})
    tok = st.pub_ch("kpszsu")
    assert re.fullmatch(r"c[0-9a-f]{8}", tok) and tok == st.pub_ch("kpszsu") and tok != st.pub_ch("kyiv_airdef")
    assert st.real_ch(tok) == "kpszsu" and st.real_ch("c00000000") is None
    assert st.pub_id("kpszsu/123#0") == f"{tok}/123#0" and st.real_id(f"{tok}/123#0") == "kpszsu/123#0"
    assert st.pub_id("ub:31") == "ub:31" and st.real_id("ukrainealarm:31") == "ukrainealarm:31"   # an official key is not a channel
    obj = {"markers": [{"id": "kpszsu/1#0", "channel": "kpszsu", "oc": "kyiv_airdef", "superseded_by": "kyiv_airdef/2#0",
                        "history": [{"id": "kpszsu/0#0", "ch": "kpszsu"}], "text": "@kpszsu wrote", "place": "Бровари"}],
           "sources": {"ukrainealarm_proxy": {"ok": True}, "tg:kpszsu": {"ok": True}, "tga:kyiv_airdef": {"ok": False}},
           "config": {"demo": False, "channels": ["kpszsu"], "canonical": "heimdall.com.ua"}}
    pub = st.public(obj)
    m = pub["markers"][0]
    assert m["id"] == f"{tok}/1#0" and m["channel"] == tok and m["oc"] == st.pub_ch("kyiv_airdef")
    assert m["superseded_by"].startswith(st.pub_ch("kyiv_airdef") + "/") and m["history"][0]["ch"] == tok
    assert m["text"] == "@kpszsu wrote" and m["place"] == "Бровари"            # the post's own words are the post's
    assert pub["sources"] == {"ukrainealarm_proxy": {"ok": True}, "channels": {"ok": True, "n": 2, "n_ok": 1}}
    assert pub["config"] == {"demo": False, "canonical": "heimdall.com.ua"}
    assert obj["markers"][0]["channel"] == "kpszsu" and "channels" in obj["config"]   # a copy: the real object is untouched
    # the map is rebuilt from the feed after a restart
    st2 = server.State(st.store, {})
    st2.store.conn.execute("INSERT INTO feed(post_id,channel,ts,text,tags) VALUES(?,?,?,?,?)", ("kpszsu/5", "kpszsu", "2026-10-18T00:00:00Z", "x", "[]"))
    st2.store.conn.commit()
    assert st2.real_id(f"{tok}/5") == "kpszsu/5"                               # the same salt (kv), the same token


def _serve(st):
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", old


def test_the_answers_name_no_channel_and_a_flag_comes_back_with_the_name():
    st = server.State(server.Store(":memory:"), {"demo": True})
    srv, base, old = _serve(st)
    try:
        for p in ("/api/state", "/api/markers", "/api/feed?limit=25", "/api/impacts?hours=24"):
            body = urllib.request.urlopen(base + p, timeout=10).read().decode("utf-8")
            # the demo's alert source ("source": "demo") and config flag stay: an official source is not a channel
            assert "demo/" not in body and '"channel": "demo"' not in body and '"oc": "demo"' not in body, p
        fd = json.loads(urllib.request.urlopen(base + "/api/feed?limit=25", timeout=10).read())["feed"]
        if fd:
            assert re.fullmatch(r"c[0-9a-f]{8}", fd[0]["channel"]) and fd[0]["post_id"].startswith(fd[0]["channel"] + "/")
            req = urllib.request.Request(base + "/api/flag", data=json.dumps({"marker": fd[0]["post_id"] + "#0", "reason": "place"}).encode(),
                                         headers={"Content-Type": "application/json"})
            assert json.loads(urllib.request.urlopen(req, timeout=10).read())["ok"] is True
            row = st.store.conn.execute("SELECT post_id, channel FROM flags ORDER BY id DESC LIMIT 1").fetchone()
            assert row[0] == fd[0]["post_id"].replace(fd[0]["channel"], "demo", 1) and row[1] == "demo"
        stt = json.loads(urllib.request.urlopen(base + "/api/state", timeout=10).read())
        assert "channels" not in stt["config"]
    finally:
        srv.shutdown(); server.Handler.state = old


def test_the_pages_show_no_channel():
    assert "const CH=" not in PAGE and "CH[" not in PAGE and "t.me/" not in PAGE and "t.me/" not in LIGHT
    assert "sh_post:" not in I18N and "st_af_post:" not in I18N
    for handle in ("@kpszsu", "@kyiv_airdef", "@war_monitor", "@monitor_ukr", "@kyivoda", "@KyivCityOfficial", "@povitryanatrivogaaa"):
        assert handle not in I18N and handle not in PAGE and handle not in LIGHT and handle not in README, handle
    assert "const src=`${fmtT(m.ts)} (${t('tp_ago',Math.round(agoMin(m.ts)))})`;" in PAGE
    assert "cor.map(o=>fmtT(o.ts)).join(', ')" in PAGE and "L.push(`(${CH" not in PAGE
    assert '<div class="when">${fmtT(p.ts)}</div>' in PAGE
    assert "+`<div>${fmtT(m.ts)}</div></div>`" in LIGHT
    assert "${k}${v.n?` ${v.n_ok}/${v.n}`:''}" in PAGE                     # the health line: "channels 27/31"
    assert "readers are not shown them" in README and "1.58.36" in _read("docs", "TECHNICAL.md")
