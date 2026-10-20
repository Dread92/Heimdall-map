"""1.58.40 — the bot's alerts, lighter.

The owner, on an alert ("⚠️ ~11 km from Вишеньки … ❔ Probably a drone — type not stated · Prolisky / ➡️ Heading
north-west / ↕️ Height … / 🕒 00:30 / ⚠️ From channel posts, not radar …"): no course, no clock (it repeats Telegram's),
no "from channel posts" line — "the place must not be cluttered"; "drone" when it is probably a drone; 10 km instead
of 15; no "confirmed shot down". Kept: what a post did not say is still not said — the label stays "probably a drone"
(CLAUDE.md: never invent a threat type), and the reminder moves to the first message and the bot's description.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import test_tgbot_15838 as base  # noqa: E402
import tgbot  # noqa: E402

A, T0, iso, mark = base.A, base.T0, base.iso, base.mark


def _one(b, api, marks):
    b._st.marks = marks
    b.tick()
    b.flush()
    return api.texts(A)[-1]


def _bot(place="Гнідин", lang="uk"):
    b, st, api, kv, clock = base.bot()
    base.say(b, A, place, lang=lang)
    if b.pick.get(A):
        base.press(b, A, "a:0")
    b._st = st
    return b, st, api, clock


def test_ten_km_instead_of_fifteen():
    assert tgbot.NEAR_KM == 10.0
    b, st, api, clock = _bot()
    n0 = len(api.texts(A))
    _one(b, api, [mark(place="Гора", lon=30.862, lat=50.374, tag="#1")])                  # 12 km: no longer
    assert len(api.texts(A)) == n0
    t = _one(b, api, [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#2")])            # 8 km
    assert t.startswith("⚠️ ~8 км від <b>Гнідин</b>")


def test_an_alert_is_the_place_the_target_its_height_and_the_map():
    b, st, api, clock = _bot(lang="en")
    hist = [{"channel": "kyiv_airdef", "ts": iso(T0 - 180), "alt_m": 2100}]
    t = _one(b, api, [mark(place="Проліски", lon=30.7796, lat=50.3921, type="unknown", tag="#3", heading=315, history=hist,
                           evidence={"heading": {"matched": "на північний захід", "confidence": "high", "method": "stated"}})])
    lines = t.split("\n")
    assert lines[0].startswith("⚠️ ~9 km from <b>Гнідин (Hnidyn)</b>") and lines[1].startswith("❔ <b>Probably a drone</b> · ")
    assert "type not stated" not in t and "Heading" not in t and "➡️" not in t and "🕒" not in t and "not radar" not in t
    assert lines[2].startswith("↕️ Height: ~2100 m (posted at ") and lines[-1].startswith("🗺 <a href=")
    assert len(lines) == 4
    assert tgbot.LABEL["uk"]["unknown_dr"] == "Ймовірно, дрон"                      # not "Дрон": the post did not say it


def test_heading_for_the_place_is_still_said_once_as_the_post_said_it():
    b, st, api, clock = _bot(place="Бровари")
    t = _one(b, api, [mark(place="Княжичі", lon=30.75, lat=50.47, target="Бровари", heading=20, tag="#4",
                           evidence={"heading": {"matched": "на Бровари", "confidence": "high", "method": "stated"}})])
    assert t.startswith("🎯 Курс на ваше місце: <b>Бровари</b> (так у дописі)") and t.count("Курс") == 1


def test_a_target_shot_down_is_not_followed_by_a_message_nor_by_no_new_reports():
    b, st, api, clock = _bot()
    _one(b, api, [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#50")])
    n = len(api.calls)
    clock.t += 120
    st.marks = [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#50", stale=True),
                {"id": "c1/x#down", "type": "drones", "status": "down", "place": "Проліски", "lon": 30.7796, "lat": 50.3921,
                 "oblast_uid": "14", "ts": iso(T0 + 100), "channel": "kyiv_airdef"}]
    b.tick()
    b.flush()
    assert len(api.calls) == n and not [x for x in api.texts(A) if "Збито" in x]
    assert any(p.get("ended") for p in b.sent.values())                          # it ended: told nothing more of it
    clock.t += tgbot.END_AFTER_S + 5
    st.marks = []
    b.tick()
    b.flush()
    assert len(api.calls) == n


def test_the_reminder_is_in_the_first_message_and_the_bots_description():
    b, st, api, kv, clock = base.bot()
    call = api.call
    api.call = lambda method, fields, files=None: {"username": "heimdall_bot"} if method == "getMe" else call(method, fields, files)
    b.setup()
    desc = {(f.get("language_code") or "uk"): f for m, f, _ in api.calls if m == "setMyDescription"}
    short = {(f.get("language_code") or "uk"): f for m, f, _ in api.calls if m == "setMyShortDescription"}
    assert "не радар" in desc["uk"]["description"] and "not radar" in desc["en"]["description"]
    assert "не радар" in short["uk"]["short_description"] and len(short["en"]["short_description"]) <= 120
    assert all(len(f["description"]) <= 512 for f in desc.values())
    base.raw(b, A, "/start")
    base.press(b, A, "l:uk")
    assert "не радар" in api.texts(A)[-1]


def test_the_docs_say_it():
    root = os.path.join(HERE, "..")
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(root, "docs", doc), encoding="utf-8").read()
        assert "1.58.40" in s and "10 km" in s, doc
    assert "## 1.58.40" in open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
