"""1.31: the Telegram channels read are managed from the dashboard. The six defaults stay in code; the dashboard
adds, switches and removes. A channel added there starts on TRIAL: its posts show in the feed, flagged, and put
nothing on the map, raise no banner and send no alert until the admin switches it to the map."""
import os
from datetime import datetime, timezone

import server

SRC = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "server.py"), encoding="utf-8").read()


def _state():
    return server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "telegram_api_channels": ["chyste_nebo"]})


def _post(st, pid, channel, text):
    p = {"post_id": pid, "channel": channel, "ts": datetime.now(timezone.utc).isoformat(), "text": text,
         "tags": server.tag_feed_text(text, channel)}
    st.store.add_feed([p])
    st.publish({"kind": "feed", "ts": p["ts"], "post": p})


def test_a_channel_name_is_read_from_what_people_paste():
    for s in ("kyiv_airdef", "@kyiv_airdef", "t.me/kyiv_airdef", "https://t.me/s/kyiv_airdef", "https://t.me/kyiv_airdef/12345"):
        assert server.normalize_channel(s) == "kyiv_airdef", s
    for bad in ("", "ab", "kyiv airdef", "https://evil.example/x", "1abc", "a" * 40, "../etc"):
        assert server.normalize_channel(bad) is None, bad


def test_the_defaults_then_the_dashboard_changes_survive_a_restart():
    st = _state()
    assert [e["name"] for e in st.channel_list] == server.AUTHORITATIVE_CHANNELS
    # every default is on the map — but a new tracker, on trial until the owner puts it there (1.57.3)
    assert all(e["mode"] == server.CHANNEL_MODE_DEFAULT.get(e["name"], "map") and e["builtin"] for e in st.channel_list)
    assert st.channel_mode("vseok450") == "trial"
    assert st.channels_read("api") == ["chyste_nebo"]
    ok, _ = st.channel_update("add", "@new_tracker")
    assert ok and st.channel_mode("new_tracker") == "trial"             # a new channel starts on trial
    assert "new_tracker" in st.channels_read("web")
    assert st.channel_update("add", "t.me/new_tracker")[0] is False     # already there
    assert st.channel_update("delete", "kpszsu")[0] is False             # a default can be switched off, not removed
    st.channel_update("set", "kpszsu", mode="off")
    assert "kpszsu" not in st.channels_read("web")
    st.channel_update("set", "chyste_nebo", via="web")
    # a restart: the same database, a new process
    st2 = server.State(st.store, st.cfg)
    assert st2.channel_mode("new_tracker") == "trial" and st2.channel_mode("kpszsu") == "off"
    assert "chyste_nebo" in st2.channels_read("web")
    st2.channel_update("delete", "new_tracker")
    assert st2.channel_mode("new_tracker") == "off"                      # its recent posts stop counting at once
    assert all(e["name"] != "new_tracker" for e in st2.channel_list)


def test_a_channel_on_trial_is_in_the_feed_but_never_on_the_map():
    st = _state()
    st.channel_update("add", "new_tracker")
    text = "Шахед над Броварами курсом на Київ"
    _post(st, "new_tracker/1", "new_tracker", text)
    assert server.tag_feed_text(text, "new_tracker")                    # the post itself does read as a threat
    assert not [m for m in st.markers() if m.get("channel") == "new_tracker"]
    assert all(p["channel"] != "new_tracker" for p in st.store.feed_since(45))   # nor the banners, counts, summaries
    shown = [p for p in st.store.feed(50) if p["channel"] == "new_tracker"]
    assert shown and "trial" in shown[0]["tags"] and "drones" not in shown[0]["tags"]
    # the admin puts it on the map: the same post now places its mark
    st.channel_update("set", "new_tracker", mode="map")
    st._resp.clear()
    assert [m for m in st.markers() if m.get("channel") == "new_tracker"]
    # switched off: gone from the map and from the feed
    st.channel_update("set", "new_tracker", mode="off")
    assert not [m for m in st.markers() if m.get("channel") == "new_tracker"]
    assert all(p["channel"] != "new_tracker" for p in st.store.feed(50))


def test_a_trial_post_raises_nothing_on_a_page_and_the_dashboard_is_admin_only():
    i = SRC.index("        for p in sorted(new, key=lambda p: p[\"ts\"]):")
    assert 'p = dict(p, tags=["trial"])' in SRC[i:i + 300]       # the live event: no tag a page could react to
    i = SRC.index('if u.path == "/api/admin/channel":')
    body = SRC[i:i + 1600]
    assert "if not self._admin_ok(q):" in body[:300]
    assert "tgme_widget_message_wrap" in body                          # a web channel must actually be readable
    # the readers take the list afresh each round
    assert 'self.state.channels_read("web")' in SRC and 'want = self.state.channels_read("api")' in SRC
