"""1.58.54 — the bot's line on the dashboard says how it is now.

The owner: "i keep seeing telegram bot failing" — "updates: TgError 0 getUpdates: network — URLError", last check "never".
One long poll that failed (Telegram out of reach a moment) turned the line red until a message went out — the next poll,
5 s later, did not turn it back. Now each thread fails and recovers by itself, red only while it keeps failing (3 times in
a row, or 2 minutes); "last check" is its last answered poll; the error says what the network did, never its text.
"""
import io
import os
import socket
import ssl
import sys
import urllib.error

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(__file__))
import chanpost  # noqa: E402
import tgbot  # noqa: E402
from chanpost import TgError  # noqa: E402
from test_tgbot_15838 import TOKEN, bot, iso  # noqa: E402

BOT = open(os.path.join(ROOT, "app", "tgbot.py"), encoding="utf-8").read()
NET = "getUpdates: network — URLError (timed out)"


def fails(api, n=1, err=None):
    """The fake Bot API's next `n` getUpdates fail."""
    real, left = api.call, [n]

    def call(method, fields, files=None):
        if method == "getUpdates" and left[0] > 0:
            left[0] -= 1
            raise err or TgError(0, NET)
        return [] if method == "getUpdates" else real(method, fields, files)
    api.call = call


def test_one_failed_poll_is_not_a_failure_and_the_next_poll_ends_it():
    b, st, api, kv, clock = bot()
    fails(api, 1)
    assert b._turn("updates", b.poll) == (None, NET)
    h = b.health()
    assert h["ok"] is True and h["error"] is None and h["last"] is None          # never answered yet: "never", honestly
    clock.t += 5
    assert b._turn("updates", b.poll) == (0, None)
    h = b.health()
    assert h["ok"] is True and h["last"] == iso(clock.t) and b.stats["down"] == {}


def test_a_poll_that_keeps_failing_shows_with_its_cause_and_its_end_is_logged():
    logs = []
    b, st, api, kv, clock = bot(logs=logs)
    fails(api, 3)
    for _ in range(2):
        b._turn("updates", b.poll)
        clock.t += 35
    assert b.health()["ok"] is True
    b._turn("updates", b.poll)
    h = b.health()
    assert h["ok"] is False and h["error"].startswith(f"updates: {NET} — 3 failure(s) in a row since ")
    assert "TgError 0" not in h["error"]                                          # Telegram's words, not the class
    clock.t += 5
    b._turn("updates", b.poll)
    assert b.health()["ok"] is True and any("updates working again after 3 failure(s)" in x for x in logs)


def test_two_minutes_of_failing_is_a_failure_too():
    b, st, api, kv, clock = bot()
    fails(api, 2)
    b._turn("updates", b.poll)
    clock.t += tgbot.FAIL_S
    b._turn("updates", b.poll)
    assert b.health()["ok"] is False


def test_another_reader_is_still_shown_and_is_no_answered_poll():
    b, st, api, kv, clock = bot()
    fails(api, 1, TgError(409, "getUpdates: Conflict: terminated by other getUpdates request"))
    assert b._turn("updates", b.poll) == (-1, None)
    h = b.health()
    assert h["ok"] is False and "getUpdates conflict" in h["error"] and h["last"] is None


def test_a_message_lost_to_the_network_goes_again_once():
    b, st, api, kv, clock = bot()
    b.send(111, "sendMessage", {"text": "x"})
    api.fail["sendMessage"] = TgError(0, "sendMessage: network — URLError (connection reset)")
    b.flush()
    assert len(api.sent(111)) == 1 and b.out and b.health()["ok"] is True
    b.flush()
    assert len(api.sent(111)) == 1                                                # it waits 5 s
    clock.t += 6
    b.flush()
    assert len(api.sent(111)) == 2 and not b.out and b.stats["down"] == {}
    # twice out of reach: counted (not red for one), never a third time
    b.send(111, "sendMessage", {"text": "y"})
    api.fail["sendMessage"] = TgError(0, "sendMessage: network — URLError (timed out)")
    b.flush()
    clock.t += 6
    api.fail["sendMessage"] = TgError(0, "sendMessage: network — URLError (timed out)")
    b.flush()
    assert not b.out and b.stats["down"]["message"]["n"] == 1 and b.health()["ok"] is True


def test_messages_that_keep_failing_show_until_one_goes():
    b, st, api, kv, clock = bot()
    for i in range(3):
        b.send(111, "sendMessage", {"text": str(i)})
        api.fail["sendMessage"] = TgError(400, "sendMessage: Bad Request: can't parse entities")
        b.flush()
    h = b.health()
    assert h["ok"] is False and h["error"].startswith("message: sendMessage: Bad Request: can't parse entities — 3 failure(s)")
    b.send(111, "sendMessage", {"text": "ok"})
    b.flush()
    assert b.health()["ok"] is True


def test_last_check_is_the_last_answered_poll_and_the_last_alert_is_in_the_note():
    b, st, api, kv, clock = bot()
    b.stats["last_alert_t"] = clock.t - 600
    fails(api, 0)
    b._turn("updates", b.poll)
    h = b.health()
    assert h["last"] == iso(clock.t) and f"alerts 0 (last {chanpost.hhmm(clock.t - 600)})" in h["note"]
    assert 'self._up("message")' in BOT and 'stats["failing"]' not in BOT and 'failing=True' not in BOT                # one way to fail, one way back


# ---- what the network did, from its class and number — never its text ------------------------------------------------
@pytest.mark.parametrize("err,why", [
    (urllib.error.URLError(socket.timeout("timed out")), " (timed out)"),
    (urllib.error.URLError("timed out"), " (timed out)"),
    (urllib.error.URLError(socket.gaierror(-3, "Temporary failure in name resolution")), " (DNS: gaierror -3)"),
    (urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")), " (connection refused)"),
    (ConnectionResetError(104, "Connection reset by peer"), " (connection reset)"),
    (TimeoutError("The read operation timed out"), " (timed out)"),
    (urllib.error.URLError(OSError(101, "Network is unreachable")), " (OSError 101)"),
    (urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")), " (TLS certificate)"),
    (urllib.error.URLError(f"cannot reach https://api.telegram.org/bot{TOKEN}/getUpdates"), ""),
    (ValueError("Expecting value"), ""),
])
def test_net_why(err, why):
    assert chanpost.net_why(err) == why


def test_the_bot_api_names_the_cause_and_waits_for_its_long_poll(monkeypatch):
    seen = []

    def slow(req, timeout=None, context=None):
        seen.append(timeout)
        raise urllib.error.URLError(socket.timeout("timed out"))
    monkeypatch.setattr(chanpost.urllib.request, "urlopen", slow)
    api = chanpost.BotAPI(TOKEN)
    with pytest.raises(TgError) as e:
        api.call("getUpdates", {"offset": 0, "timeout": tgbot.POLL_S})
    assert str(e.value) == f"0 {NET}" and TOKEN not in str(e.value)
    with pytest.raises(TgError):
        api.call("sendMessage", {"chat_id": 1, "text": "x"})
    assert seen == [tgbot.POLL_S + 20, 30]

    def gone(req, timeout=None, context=None):
        raise urllib.error.URLError(f"cannot reach {req.full_url}")
    monkeypatch.setattr(chanpost.urllib.request, "urlopen", gone)
    with pytest.raises(TgError) as e:
        api.call("getUpdates", {"timeout": 25})
    assert str(e.value) == "0 getUpdates: network — URLError" and "SECRET" not in str(e.value)

    def denied(req, timeout=None, context=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"ok":false,"error_code":401,"description":"Unauthorized"}'))
    monkeypatch.setattr(chanpost.urllib.request, "urlopen", denied)
    b, *_ = bot()
    b.api = api
    for _ in range(tgbot.FAIL_N):
        b._turn("updates", b.poll)
    assert b.health()["error"].startswith("updates: getUpdates: Unauthorized — 3 failure(s)")
