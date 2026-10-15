"""1.58.27 — every night in one file, for an analysis of patterns.

The owner: "for the AI reports — could we make a sort of mega JSON document with all the reports compiled? (I don't know
if it's good practice for pattern learning) … so that I can hand you the readable report and then analyse the patterns".
One file for a window of nights: JSON Lines — a header line, then one night a line, its record (the facts the rules
recorded, State.night_summary) and the AI's report on it — for code to read; or the same as text. The record is the
source; the AI's report is a reading of it, never the source of a number.
"""
import gzip
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest import mock

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


ADMIN, DOC = _read("static", "admin.html"), _read("docs", "TECHNICAL.md")


def _state():
    st = server.State(server.Store(":memory:"), {})
    today = datetime.now(timezone.utc).date()
    n1, n2 = (today - timedelta(days=3)).isoformat(), (today - timedelta(days=2)).isoformat()
    with st.store.lock:
        for night, n in ((n1, 1), (n1, 2), (n2, 1)):
            st.store.conn.execute("INSERT INTO targets(night,n,prefix,origin,first_ts,last_ts,type) VALUES(?,?,?,?,?,?,?)",
                                  (night, n, "N", "north", f"{night}T20:00:00+00:00", f"{night}T21:00:00+00:00", "drones"))
        st.store.conn.commit()
    st.store.ai_report_save({"night": n1, "at": f"{n2}T06:00:00+00:00", "until": f"{n2}T09:00:00+00:00", "model": "m",
                             "tok_in": 1, "tok_out": 1, "cost": 0.01, "text": "1. The night in brief\nTwo tags.", "error": None})
    return st, n1, n2


def test_one_night_a_line_with_its_record_and_the_ais_report():
    st, n1, n2 = _state()
    lines = st.nights_export(n1, n2, "jsonl").splitlines()
    head, rows = json.loads(lines[0]), [json.loads(x) for x in lines[1:]]
    assert head["schema"] == "heimdall-nights/1" and head["nights"] == 2 and head["from"] == n1 and "not radar" in head["_about"]
    assert [r["night"] for r in rows] == [n1, n2]                       # oldest first
    assert rows[0]["summary"]["night"] == n1 and rows[0]["summary"]["targets"]["tags"] == 2
    assert rows[0]["ai_report"]["text"].startswith("1. The night") and rows[1]["ai_report"] is None
    assert st.export_nights("2000-01-01", "2000-12-31") == []          # nothing recorded: no night


def test_the_same_as_text():
    st, n1, n2 = _state()
    md = st.nights_export(n1, n2, "md")
    assert md.startswith(f"# Heimdall — the nights {n1} → {n2} (2)") and "not radar" in md
    assert f"## {n1}" in md and f"## {n2}" in md and f"HEIMDALL — NIGHT {n1}" in md
    assert "### The AI's report (m)" in md and md.count("### The AI's report") == 1


def test_the_dashboards_alone_downloaded_as_a_file():
    st, n1, n2 = _state()
    old = server.Handler.state
    server.Handler.state = st
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/admin/nights_export"

    def get(q, **hd):
        try:
            r = urllib.request.urlopen(urllib.request.Request(base + q, headers=hd), timeout=20)
            return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)
    try:
        with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm-test"}):
            assert get("?format=jsonl")[0] == 403                                    # no key, no session
            k = {"X-Admin-Key": "adm-test"}
            assert get("?format=csv", **k)[0] == 400 and get(f"?from={n2}&to={n1}", **k)[0] == 400
            code, body, hd = get(f"?format=jsonl&from={n1}&to={n2}", **k)
            assert code == 200 and hd["Content-Disposition"] == f'attachment; filename="heimdall-nights-{n1}_{n2}.jsonl"'
            assert len(body.decode("utf-8").splitlines()) == 3
            code, body, hd = get(f"?format=md&from={n1}&to={n2}", **dict(k, **{"Accept-Encoding": "gzip"}))
            assert code == 200 and hd.get("Content-Encoding") == "gzip" and f"## {n1}" in gzip.decompress(body).decode("utf-8")
            assert get("?format=jsonl", **k)[0] == 200                              # the last 90 days by default
    finally:
        srv.shutdown()
        server.Handler.state = old


def test_on_the_dashboard_and_in_the_docs():
    for key in ("an_n_all:", "an_n_all_j:", "an_n_all_t:", "an_n_all_h:"):
        assert ADMIN.count(key) == 2, key                                          # English and Ukrainian
    assert 'href="/api/admin/nights_export?format=jsonl" download' in ADMIN and 'href="/api/admin/nights_export?format=md" download' in ADMIN
    assert "/api/admin/nights_export" in DOC and "heimdall-nights/1" in DOC
