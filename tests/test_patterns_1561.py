"""1.56.1: the patterns from the first night the posts are kept, said in words; one bulletin an hour.

The owner (10 Oct 2026): "instead of an AI bulletin every 20 minutes, really only one an hour, on the dashboard" — "it
would be interesting already now to see whether you can identify patterns, in plain English".
"""
import os
from datetime import datetime, timedelta, timezone

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)
P = {"Чернігів": (31.29, 51.49), "Козелець": (31.11, 50.91), "Бровари": (30.79, 50.51), "Київ": (30.52, 50.45),
     "Бобровиця": (31.40, 50.75), "Славутич": (30.75, 51.52)}


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def test_two_places_at_one_moment_are_no_move_and_a_banderol_is_a_jet_drone():
    pts = [(ago(m), *P[pl], pl, None) for pl, m in [("Чернігів", 100), ("Козелець", 100), ("Козелець", 60), ("Бровари", 30)]]
    mv = server.Patterns.moves_of(pts)
    assert [(m["place_from"], m["place_to"]) for m in mv] == [("Чернігів", "Козелець"), ("Козелець", "Бровари")]
    assert mv[0]["minutes"] == 40.0 and all(m["minutes"] >= server.MOVE_MIN_MIN for m in mv)
    assert server.move_kind("banderol_missiles", 1) == "banderol" == server.move_kind("banderol", 0)


class _State:
    """What the replay needs of the State: its tracks for a window, here made up."""
    def __init__(self, store, tracks):
        self.store, self.tracks, self.asked = store, tracks, []

    def _replay_alerts(self, start, end):
        return []

    def _replay_tracks(self, start, end, alerts):
        self.asked.append(start)
        t = start + timedelta(hours=10)
        return [{"ty": ty, "jet": jet, "p": [[int((t + timedelta(minutes=m)).timestamp()), *P[pl], pl] for pl, m in path]}
                for ty, jet, path in self.tracks]

    def missile_active(self):
        return 0


def test_the_nights_before_the_tags_are_read_again_from_their_posts():
    st = server.Store(":memory:")
    first = (NOW - timedelta(days=9)).isoformat()
    st.conn.execute("INSERT INTO feed(post_id, channel, ts, text, tags) VALUES(?,?,?,?,?)", ("c/1", "c", first, "x", "[]"))
    tagged = server.tag_night((NOW - timedelta(days=2)).isoformat())
    st.conn.execute("INSERT INTO target_points(report,night,n,ts,lon,lat,place,alt_m) VALUES(?,?,?,?,?,?,?,?)",
                    ("r/1#0", tagged, 1, (NOW - timedelta(days=2)).isoformat(), 30.5, 50.4, "Київ", None))
    st.conn.commit()
    state = _State(st, [("drones", 0, [("Чернігів", 0), ("Козелець", 40), ("Бровари", 80)]),
                        ("banderol_missiles", 1, [("Славутич", 0), ("Київ", 12)])])
    pat = server.Patterns(st, state)
    pat.REPLAY_PAUSE_S = 0
    todo = pat.replay_nights()
    assert todo and todo[0] == server.tag_night(first) and todo[-1] < tagged and len(todo) in (6, 7, 8)
    pat.REPLAY_PER_TICK = 3
    pat.tick()
    rows = st.conn.execute("SELECT night, n, seq, place_from, place_to, kind, src, ver FROM track_moves WHERE src='replay' ORDER BY night, n, seq").fetchall()
    assert len({r[0] for r in rows}) == 3 and rows[0][1] == server.Patterns.REPLAY_N
    assert [r[3:6] for r in rows if r[0] == todo[0]] == [("Чернігів", "Козелець", "drone"), ("Козелець", "Бровари", "drone"),
                                                         ("Славутич", "Київ", "banderol")]
    assert {r[6] for r in rows} == {"replay"} and {r[7] for r in rows} == {server.MOVES_VERSION}
    assert pat.replay_nights() == todo[3:]                                  # done once, not again
    pat.tick()
    pat.tick()
    assert pat.replay_nights() == [] and len(state.asked) == len(todo)
    # the live tags' nights are the tags': never read again
    assert all(r[0] < tagged for r in st.conn.execute("SELECT night FROM track_moves WHERE src='replay'"))
    d = server.Patterns.report(st, 0, "drones", 1, 1)
    assert d["coverage"]["by_src"]["replay"] == len(todo) * 3 and "replay" in d["plain"]["en"][0] or "read again" in d["plain"]["en"][0]


def test_while_kyiv_is_under_alert_the_old_nights_wait():
    st = server.Store(":memory:")
    st.conn.execute("INSERT INTO feed(post_id, channel, ts, text, tags) VALUES(?,?,?,?,?)", ("c/1", "c", (NOW - timedelta(days=4)).isoformat(), "x", "[]"))
    st.conn.commit()
    state = _State(st, [("drones", 0, [("Чернігів", 0), ("Козелець", 40)])])
    state.lock = server.threading.Lock()
    state.active = {"k": {"oblast_uid": "31", "alert_type": "air_raid"}}
    pat = server.Patterns(st, state)
    pat.REPLAY_PAUSE_S = 0
    assert pat.busy()
    pat.tick()
    assert state.asked == []
    state.active = {}
    assert not pat.busy()


def _mark(st, mid, minutes, place, heading=None, target=None):
    lon, lat = P[place]
    st.conn.execute("INSERT INTO marker_log(id,ts,post_id,channel,type,status,place,oblast_uid,lon,lat,heading,count,jet,pos_conf,evidence,target) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, ago(minutes), mid, "c", "drones", None, place, "25", lon, lat, heading, 1, 0,
                                                              "high", "{}", target))


def test_the_patterns_in_plain_words():
    st = server.Store(":memory:")
    for i in range(40):                                   # Slavutych: 30 courses south, 10 north
        _mark(st, f"s/{i}", 30 + i, "Славутич", 180 if i < 30 else 0, "Київ" if i < 6 else None)
    for i in range(10):                                   # Kozelets: 10 tracks, 8 next reported in Brovary
        night = server.tag_night(ago(400))
        st.conn.execute("INSERT INTO targets(night,n,prefix,type) VALUES(?,?,?,?)", (night, i + 1, "?", "drones"))
        nxt = "Бровари" if i < 8 else "Бобровиця"
        for k, (pl, m) in enumerate([("Козелець", 200 + i), (nxt, 160 + i)] + ([("Київ", 130 + i)] if i < 8 else [])):
            lon, lat = P[pl]
            st.conn.execute("INSERT INTO target_points(report,night,n,ts,lon,lat,place,alt_m) VALUES(?,?,?,?,?,?,?,?)",
                            (f"t{i}/{k}#0", night, i + 1, ago(m), lon, lat, pl, None))
    st.conn.commit()
    server.Patterns(st).tick(replay=False)
    d = server.Patterns.report(st, 30, "drones", 1, 3)
    en, uk = d["plain"]["en"], d["plain"]["uk"]
    assert len(en) == len(uk) and d["plain"]["found"] == len(en) - 1 >= 3
    assert "not radar" in en[0] and "не радар" in uk[0] and "40 courses stated" in en[0]
    assert any(s.startswith("Славутич: of the 40 courses the posts gave here, 75% were south and 25% north") for s in en), en
    assert any("Славутич: із 40 курсів" in s and "75% — на південь" in s for s in uk)
    assert any("the next report put the target in Бровари 8 times out of 10" in s for s in en), en
    assert any("8 of the 10 tracks that passed here were last reported in Київ" in s for s in en), en
    assert not any("will" in s or "probably" in s for s in en)                   # what was reported, never a forecast
    sl = next(c for c in d["cells"] if c["name"] == "Славутич")
    assert sl["said"][0] == {"place": "Київ", "n": 6, "p": 100.0, "lo": sl["said"][0]["lo"], "hi": 100.0}   # of the 6 that named one
    # the threshold: an area with too few reports says nothing
    st2 = server.Store(":memory:")
    for i in range(10):
        _mark(st2, f"q/{i}", 30 + i, "Славутич", 180)
    assert server.Patterns.report(st2, 30, "drones", 1, 1)["plain"]["found"] == 0


def test_the_dashboard_and_the_docs():
    page, doc = _read("static/admin.html"), _read("docs/TECHNICAL.md")
    assert "card('ptw',tr('pt_plain'),pl[0]" in page and page.count("pt_plain:") == 2 and page.count("pt_plain_none:") == 2
    assert "tr('bul_every')" in page and "once an hour" in page
    for s in ("MOVE_MIN_MIN", "build_replay", "REPLAY_PER_TICK", "Patterns.plain", "PLAIN_LO"):
        assert s in doc, s
    assert "ai_bulletin_minutes`, 20, gone" in doc
