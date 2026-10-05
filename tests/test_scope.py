"""Which channels this app believes, which region it watches, and who decides that an alert is over.

Three decisions, each of which used to be made somewhere it should not have been:

- The channel list lived in config.json, which is never shipped. Changing it in the code changed nothing on
  a machine whose config still listed thirty channels. The whitelist is code now, and the config is ignored.
- Telegram posts could start and end alerts. A channel writing "відбій" turned the band green while the
  government's own app was still red. Only the official alert data sets the colour now.
- The map took marks from all of Ukraine. It is Kyiv, its oblast, the five around it, and Sumy.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import geo  # noqa: E402
import server  # noqa: E402

SRC = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()


# ── the channels ───────────────────────────────────────────────────────────────────────────────────────
def test_the_six_channels_and_only_them():
    assert set(server.AUTHORITATIVE_CHANNELS) == {
        "war_monitor", "eRadarrua", "kyiv_airdef", "chyste_nebo", "kievinfo_kyiv", "kpszsu"}


def test_a_config_listing_other_channels_does_not_bring_them_back():
    """Every deployed config.json still lists the old thirty. They must not be read."""
    st = server.State(server.Store(":memory:"), {"telegram_channels": ["kyivoda", "odesa_alert", "war_monitor"]})
    server.Telegram(st, st.cfg)
    # 1.31: what is read is the defaults plus what the dashboard added — never the config's old list
    assert sorted(st.channels_read("web") + st.channels_read("api")) == sorted(server.AUTHORITATIVE_CHANNELS)


def test_a_channel_with_its_preview_switched_off_is_reported_as_unreadable():
    """chyste_nebo shows Telegram's landing page and no posts. "No drones reported" and "cannot read this
    channel" must never look the same in the sources panel."""
    body = SRC[SRC.index("    def poll(self, ch):"):]
    body = body[:body.index("\n    def ", 10)]
    assert "tgme_widget_message_wrap' not in page" in body
    assert "web preview disabled" in body


# ── who ends an alert ──────────────────────────────────────────────────────────────────────────────────
def test_telegram_never_starts_or_ends_an_alert():
    assert server.OFFICIAL_ALERTS_FROM_TELEGRAM is False
    i = SRC.index("self.official.ingest(")
    assert "OFFICIAL_ALERTS_FROM_TELEGRAM and" in SRC[i - 120:i], "Telegram posts reach the alert state again"


def test_a_channel_post_is_not_labelled_official():
    """The 'official' chip told readers a channel spoke for the state. None of the six does."""
    for ch in server.AUTHORITATIVE_CHANNELS:
        assert "official" not in server.tag_feed_text("Відбій повітряної тривоги!", ch)


def test_the_alert_sources_that_remain_are_the_official_data():
    for cls in ("AlertsInUa(state, cfg).start()", "detail = UkraineAlarm(state, cfg)", "Ubilling(state, cfg"):
        assert cls in SRC, f"{cls} is no longer started"


# ── the region ─────────────────────────────────────────────────────────────────────────────────────────
def test_the_region_is_kyiv_the_neighbours_and_sumy():
    assert server.REGION_UIDS == {"31", "14", "10", "25", "19", "24", "4", "20"}


def test_a_mark_in_the_region_is_kept_and_one_outside_is_dropped():
    assert server.in_scope({"oblast_uid": "14", "lat": 50.5, "lon": 30.5})
    assert server.in_scope({"oblast_uid": "20", "lat": 50.9, "lon": 34.8})           # Sumy
    assert not server.in_scope({"oblast_uid": "18", "lat": 46.48, "lon": 30.73})     # Odesa
    assert not server.in_scope({"oblast_uid": "22", "lat": 49.99, "lon": 36.23})     # Kharkiv


def test_a_mark_with_no_oblast_is_judged_by_distance():
    assert server.in_scope({"oblast_uid": None, "lat": 50.6, "lon": 30.9})
    assert not server.in_scope({"oblast_uid": None, "lat": 46.0, "lon": 31.0})       # the Black Sea


def test_the_filter_runs_before_anything_downstream_sees_the_marks():
    """Dropped in markers(), so the map, the counts, the proximity pushes and the light page all agree."""
    body = SRC[SRC.index("    def markers(self):"):]
    i, j = body.index("in_scope(m)"), body.index("self._chain_and_prune(out, ttl, kyiv_ends)")
    assert i < j


# ── the new live channel, read from its real posts ─────────────────────────────────────────────────────
def _read(text):
    return [(m["type"], m.get("place"), m.get("heading")) for m in geo.parse_for_channel("kievinfo_kyiv", text)]


def test_dymerka_is_not_dymer():
    """The stem "димер" plus up to three letters swallowed "димерка" and put a drone 35 km away, across the
    reservoir, on the wrong side of Kyiv."""
    got = _read("✈️Димерка - Бровари з північного-сходу реактив.")
    assert got and got[0][1] == "Велика Димерка", got


def test_a_route_written_a_dash_b_gives_the_heading():
    got = _read("✈️Димерка - Бровари з північного-сходу реактив.")
    assert got[0][2] is not None and 200 <= got[0][2] <= 240, got      # south-west, towards Brovary


def test_koncha_zaspa_is_one_place_not_a_route():
    assert _read("✈️Конча - Заспа") == [("drones", "Конча-Заспа", None)]


def test_two_places_on_two_lines_are_two_drones():
    got = _read("✈️Вишневе\n✈️Петрівці")
    assert [g[1] for g in got] == ["Вишневе", "Нові Петрівці"]


def test_the_plane_emoji_is_a_drone_only_on_the_live_channels():
    assert _read("✈️Соломʼянка")[0][0] == "drones"
    assert _read("✈️ Активність авіації на півночі") == [], "aviation activity was read as a Shahed"


def test_a_bare_place_with_no_mark_stays_an_honest_unknown():
    assert _read("Позняки")[0][0] == "unknown"


def test_a_place_the_gazetteer_does_not_know_is_left_out_not_guessed():
    """Мархалівка has no coordinates here. Placing it anywhere would be a position nobody reported."""
    got = _read("1х Коцюбинське\n1х Мархалівка")
    assert [g[1] for g in got] == ["Коцюбинське"]
