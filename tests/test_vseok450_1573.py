"""1.57.3: "4.5.0" (@vseok450), a live tracker of Kyiv and its oblast — the owner's choice — on trial first.

Its posts of 11 Oct 2026 (12:46–13:38), read through the Kyiv trackers' rules. On trial its posts are in the feed,
flagged, and raise nothing — until the owner puts it on the map from the dashboard.
"""
import geo
import server


def test_it_is_a_kyiv_channel_on_trial_until_the_owner_says():
    assert "vseok450" in server.AUTHORITATIVE_CHANNELS and server.CHANNEL_HOME_DEFAULT["vseok450"] == "31"
    st = server.State(server.Store(":memory:"), {})
    assert st.channel_mode("vseok450") == "trial" and st.channel_mode("kyiv_airdef") == "map"
    assert st.channel_home("vseok450") == "31"
    ok, _ = st.channel_update("set", "vseok450", mode="map")
    assert ok and st.channel_mode("vseok450") == "map"


def _read(t):
    geo.CHANNEL_HOME["vseok450"] = "31"
    return [(m.get("place"), m.get("target"), bool(m.get("approach")), m.get("type")) for m in geo.parse_for_channel("vseok450", t)]


def test_its_posts():
    assert _read("1-й до Чабанів") == [("→ Чабани", "Чабани", True, "unknown")]          # heading for, not at
    assert [p for p, _, _, _ in _read("Яготин\nБогуслав\n3 Чернігівська")] == ["Яготин", "Богуслав"]
    assert _read("Відбій🫂") == [] and _read("Повертаємось до цього посту👆") == []
    assert _read("2 Чернігівська\n1+1 Черкаська\n\nПоки не плануйте нічого\nПоборемо🫂") == []   # counts by oblast: no place
