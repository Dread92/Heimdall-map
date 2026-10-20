"""1.58.38 — the bot, one to one: it asks each user which places to watch and writes only about them.

The owner: "we need to completely re-think the Telegram bot: instead, the bot will ask the user, one to one, what
location they want to be alerted on — if they write Hnidyn, the bot sends them a message only when their place is
mentioned, or a threat is detected nearby". His picks: it replaces the channel; a post naming the place, or a target
within 15 km; up to 4 places. (1.58.40: 10 km, and the alerts lighter — tests/test_bot_15840.py.)
"""
import json
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import chanpost  # noqa: E402
import tgbot  # noqa: E402
from chanpost import TgError  # noqa: E402

SRV = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
BOT = open(os.path.join(ROOT, "app", "tgbot.py"), encoding="utf-8").read()
ADMIN = open(os.path.join(ROOT, "static", "admin.html"), encoding="utf-8").read()
T0 = datetime(2026, 10, 20, 0, 40, tzinfo=timezone.utc).timestamp()
TOKEN = "123456:SECRET-token-of-the-owner"
OBL = {"14": ("Київська область", "Kyiv oblast"), "31": ("м. Київ", "Kyiv city"), "17": ("Миколаївська область", "Mykolaiv"),
       "22": ("Харківська область", "Kharkiv")}
GAZ = tgbot.Gazetteer(OBL)
A, B = 111, 222                                           # two users' chats


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class KV:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.Lock()
        self.d = {}

    def kv_get(self, k):
        return self.d.get(k)

    def kv_set(self, k, v):
        self.d[k] = v


class API:
    def __init__(self):
        self.calls, self.mid, self.fail = [], 100, {}

    def call(self, method, fields, files=None):
        self.calls.append((method, fields, files))
        e = self.fail.pop(method, None)
        if e:
            raise e
        if method in ("sendPhoto", "sendMessage"):
            self.mid += 1
            r = {"message_id": self.mid}
            if method == "sendPhoto":
                r["photo"] = [{"file_id": "small"}, {"file_id": "FILE-" + str(self.mid)}]
            return r
        return True

    def sent(self, chat=None, method=None):
        return [(m, f, fl) for m, f, fl in self.calls if (chat is None or f.get("chat_id") == chat)
                and (method is None or m == method)]

    def texts(self, chat=None):
        return [f.get("text") or f.get("caption") or "" for m, f, _ in self.sent(chat)
                if m in ("sendMessage", "sendPhoto", "editMessageText")]


class Shot:
    def __init__(self):
        self.n = 0

    def render(self, m, active, when, ray=True, missiles=(), others=()):
        self.n += 1
        return b"JPEG-" + m["place"].encode()


class State:
    def __init__(self):
        self.marks = []

    def markers_now(self):
        return self.marks

    def snapshot(self):
        return {"active": []}


def bot(shot=None, logs=None):
    st, api, kv, clock = State(), API(), KV(), Clock()
    b = tgbot.TgBot(st, TOKEN, "https://heimdall.com.ua", api=api, gaz=GAZ, kv=kv, clock=clock, shot=shot or False,
                    log=(lambda *a: logs.append(" ".join(map(str, a)))) if logs is not None else (lambda *a: None))
    if shot is None:
        b.shot = None
    return b, st, api, kv, clock


def raw(b, chat, text, lang="uk"):
    b.handle({"update_id": 1, "message": {"chat": {"id": chat, "type": "private"}, "from": {"language_code": lang},
                                          "text": text}})
    b.flush()


def say(b, chat, text, lang="uk"):
    """A user's message — a new user first answers the bot's first question, the language (1.58.39)."""
    if not b.store.chat(chat) and not text.startswith("/stop"):
        raw(b, chat, "/start", lang)
        press(b, chat, "l:" + lang)
    raw(b, chat, text, lang)


def press(b, chat, data, mid=50):
    b.handle({"update_id": 2, "callback_query": {"id": "q", "data": data, "from": {"language_code": "uk"},
                                                 "message": {"message_id": mid, "chat": {"id": chat, "type": "private"}}}})
    b.flush()


def mark(place="Вишеньки", lon=30.72, lat=50.30, t=T0, uid="14", tag="#1", **kw):
    m = {"id": f"c1/{tag}#{place}", "type": "drones", "place": place, "lon": lon, "lat": lat, "oblast_uid": uid,
         "ts": iso(t), "pos_ts": iso(t), "channel": "kyiv_airdef", "tag": {"night": "2026-10-19", "id": tag},
         "history": [], "heading": None, "evidence": {"heading": {"confidence": "none"}}}
    m.update(kw)
    return m


# ---- finding a place ----------------------------------------------------------------------------------------------------
def test_a_place_is_found_by_its_name_in_any_letters():
    for q in ("Гнідин", "гнідин", "Гнидин", "Hnidyn", "Hnydin", "hnidin"):
        r = GAZ.search(q)
        assert r and r[0]["key"] == "Гнідин", q
    assert GAZ.label(GAZ.get("Гнідин"), "uk", where=True) == "Гнідин — Бориспільський р-н · Київська обл."
    assert GAZ.label(GAZ.get("Гнідин"), "en", where=True) == "Гнідин (Hnidyn) — Бориспільський р-н · Kyiv oblast"
    assert [e["key"] for e in GAZ.search("Оболонь")][0] == "Оболонь"            # the Kyiv district before its namesakes
    assert len(GAZ.search("Іванівка")) == tgbot.SEARCH_MAX                      # namesakes: a list to choose from
    assert GAZ.search("zzzz") == [] and GAZ.search("а") == []


def test_what_is_not_a_place_to_live_is_not_offered():
    keys = set(GAZ.idx)
    for k in ("Північний міст", "Київське водосховище", "Бориспіль аеропорт", "Житомирська траса", "ТЕЦ-5", "Запорізька АЕС"):
        assert k not in keys, k
    assert not any(k.endswith(" р-н") for k in keys)                            # a raion is no place
    assert {"Київ", "Троєщина", "Гнідин", "Бровари"} <= keys


def test_a_shared_location_lists_the_nearest_places_and_is_never_kept():
    b, st, api, kv, clock = bot()
    raw(b, A, "/start")
    press(b, A, "l:uk")
    api.calls.clear()
    b.handle({"update_id": 3, "message": {"chat": {"id": A, "type": "private"}, "from": {"language_code": "uk"},
                                          "location": {"latitude": 50.3291, "longitude": 30.7049}}})
    b.flush()
    (m, f, _), = api.sent(A)
    assert m == "sendMessage" and "не збережено" in f["text"]
    assert f["reply_markup"]["inline_keyboard"][0][0]["text"].startswith("Гнідин")
    dump = json.dumps(api.calls, ensure_ascii=False) + json.dumps(kv.d) + "".join(
        str(r) for r in kv.conn.execute("SELECT * FROM bot_chats UNION ALL SELECT chat_id, key, added, '' FROM bot_places"))
    assert "50.329" not in dump and "30.704" not in dump                        # not stored, not sent on
    assert "location" not in BOT.split("def _location")[1].split("def _add")[0].split("del lat, lon, loc")[1]


# ---- the conversation ---------------------------------------------------------------------------------------------------
def test_the_first_question_is_the_language_then_it_explains_and_says_what_is_kept():
    b, st, api, kv, clock = bot()
    raw(b, A, "/start")
    (m, f, _), = api.sent(A)
    assert f["text"] == tgbot.CHOOSE and [x["callback_data"] for x in f["reply_markup"]["inline_keyboard"][0]] == ["l:uk", "l:en"]
    assert b.store.chat(A) is None                                              # nothing kept before the answer
    press(b, A, "l:uk")
    m, f, _ = api.sent(A)[-1]
    assert m == "editMessageText" and f["message_id"] == 50 and f["reply_markup"] == {"inline_keyboard": []}
    t = f["text"]
    assert "10 км" in t and "До 4 місць" in t and "не радар" in t and "/stop видаляє все" in t
    assert "лише номер цього чату, мову й обрані місця" in t and b.store.chat(A) == {"lang": "uk"}
    raw(b, B, "/start", lang="fr")
    press(b, B, "l:en")
    assert "not radar" in api.texts(B)[-1] and "10 km" in api.texts(B)[-1] and b.store.chat(B) == {"lang": "en"}
    assert tgbot.LANGS == ("uk", "en") and "fr" not in tgbot.T and "fr" not in tgbot.LABEL


def test_a_name_adds_the_place_and_namesakes_are_offered_to_choose():
    b, st, api, kv, clock = bot()
    say(b, A, "Hnydin")
    assert "✅ Додано: Гнідин — Бориспільський р-н" in api.texts(A)[-1] and "Місць: 1 з 4" in api.texts(A)[-1]
    assert b.store.places(A) == ["Гнідин"]
    say(b, A, "Гнідин")
    assert "уже у ваших місцях" in api.texts(A)[-1] and b.store.places(A) == ["Гнідин"]
    say(b, A, "Іванівка")
    m, f, _ = api.sent(A)[-1]
    kb = f["reply_markup"]["inline_keyboard"]
    assert len(kb) == tgbot.SEARCH_MAX + 1 and kb[-1][0]["callback_data"] == "x" and kb[1][0]["callback_data"] == "a:1"
    press(b, A, "a:1")
    assert api.sent(A)[-1][0] == "editMessageText" and api.calls[-2][0] == "answerCallbackQuery"    # the answer first
    m, f, _ = api.sent(A)[-1]
    assert m == "editMessageText" and f["message_id"] == 50 and "✅ Додано: Іванівка" in f["text"]
    assert len(b.store.places(A)) == 2
    press(b, A, "a:1")                                                          # the list is used once
    assert "застарів" in api.texts(A)[-1]


def test_four_places_at_most_and_a_place_is_removed_with_its_button():
    b, st, api, kv, clock = bot()
    for q in ("Гнідин", "Бровари", "Троєщина", "Вишгород", "Бориспіль"):
        say(b, A, q)
        if "Знайшов кілька" in api.texts(A)[-1]:
            press(b, A, "a:0")
    assert len(b.store.places(A)) == 4 and "спершу приберіть одне" in api.texts(A)[-1]
    say(b, A, "/places")
    m, f, _ = api.sent(A)[-1]
    kb = f["reply_markup"]["inline_keyboard"]
    assert [r[0]["text"] for r in kb][0] == "❌ Гнідин" and len(kb) == 4
    press(b, A, kb[0][0]["callback_data"])
    assert "Гнідин" not in b.store.places(A) and "Прибрано: Гнідин" in api.texts(A)[-1]


def test_stop_and_blocking_the_bot_delete_everything_kept():
    b, st, api, kv, clock = bot()
    say(b, A, "Гнідин")
    st.marks = [mark()]
    b.tick()
    b.flush()
    assert any(k.startswith(f"{A}|") for k in b.sent)
    say(b, A, "/stop")
    assert b.store.places(A) == [] and b.store.chat(A) is None and not any(k.startswith(f"{A}|") for k in b.sent)
    assert "видалено" in api.texts(A)[-1]
    say(b, B, "Гнідин")
    b.handle({"update_id": 9, "my_chat_member": {"chat": {"id": B, "type": "private"}, "new_chat_member": {"status": "kicked"}}})
    assert b.store.places(B) == [] and b.store.chat(B) is None
    say(b, 333, "Гнідин")
    api.fail["sendMessage"] = TgError(403, "sendMessage: Forbidden: bot was blocked by the user")
    st.marks = [mark(tag="#2")]
    clock.t += 30
    b.tick()
    b.flush()
    assert b.store.places(333) == [] and b.stats["blocked"] == 1


def test_groups_and_channels_are_not_its_business_and_a_flood_is_ignored():
    b, st, api, kv, clock = bot()
    b.handle({"update_id": 4, "message": {"chat": {"id": -100, "type": "group"}, "text": "/start"}})
    b.flush()
    assert api.calls == []
    for _ in range(tgbot.IN_PER_MIN + 5):
        b.handle({"update_id": 5, "message": {"chat": {"id": A, "type": "private"}, "text": "/start"}})
    b.flush()
    assert len(api.sent(A)) == tgbot.IN_PER_MIN


def test_a_place_written_before_the_language_waits_for_it_and_the_language_can_be_changed():
    b, st, api, kv, clock = bot()
    raw(b, A, "Hnidyn", lang="en")
    assert api.texts(A) == [tgbot.CHOOSE] and b.store.places(A) == []
    press(b, A, "l:en")
    assert "This is the Heimdall bot" in api.texts(A)[-2] and "Added: Гнідин (Hnidyn)" in api.texts(A)[-1]
    raw(b, A, "/lang")
    assert api.sent(A)[-1][1]["reply_markup"]["inline_keyboard"] == tgbot.LANG_KB
    press(b, A, "l:uk")
    assert b.store.chat(A)["lang"] == "uk" and api.texts(A)[-1] == "Мова: українська."
    b.handle({"update_id": 7, "message": {"chat": {"id": B, "type": "private"}, "from": {"language_code": "uk"},
                                          "location": {"latitude": 50.33, "longitude": 30.70}}})
    b.flush()
    assert b.pending[B][1] is None                                              # a location is never kept waiting
    assert tgbot.lang_of("ru") == "uk" and tgbot.lang_of("fr") == "en" and tgbot.lang_of(None) == "uk"


def test_the_offset_is_kept_and_another_reader_is_waited_for():
    b, st, api, kv, clock = bot()
    ups = [{"update_id": 41, "message": {"chat": {"id": A, "type": "private"}, "text": "/start"}}]
    api.call = (lambda method, fields, files=None: ups if method == "getUpdates" else {"message_id": 1})
    assert b.poll() == 1 and kv.d["bot_offset"] == "42"
    logs = []
    b2, *_ = bot(logs=logs)

    def conflict(method, fields, files=None):
        raise TgError(409, "getUpdates: Conflict: terminated by other getUpdates request")
    b2.api.call = conflict
    assert b2.poll() == -1 and b2.health()["ok"] is False and "getUpdates conflict" in b2.health()["error"]


# ---- the alerts ---------------------------------------------------------------------------------------------------------
def _users(b, *pairs):
    for chat, q in pairs:
        say(b, chat, q)
        if b.pick.get(chat):                                    # namesakes: the first (the core gazetteer's)
            press(b, chat, "a:0")
        assert b.store.places(chat), q


def test_a_post_naming_the_place_is_told_and_a_target_nearby_too_with_its_distance():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Вишеньки"), (B, "Гнідин"))
    st.marks = [mark()]                                       # at Вишеньки, 3.3 km from Гнідин
    b.tick()
    b.flush()
    a, = [t for t in api.texts(A) if "Допис" in t]
    assert a.startswith("📍 Допис назвав ваше місце: <b>Вишеньки</b>") and "🛵 <b>Шахед</b> · Вишеньки" in a
    assert "не радар" not in a and "🕒" not in a and 'href="https://heimdall.com.ua/m"' in a          # 1.58.40
    bb = api.texts(B)[-1]
    assert bb.startswith("⚠️ ~3 км від <b>Гнідин</b> (від місця, яке назвав допис)")
    assert "kyiv_airdef" not in a + bb                         # never the channel


def test_heading_for_the_place_is_told_as_the_post_said_it():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Бровари"))
    st.marks = [mark(place="Княжичі", lon=30.75, lat=50.47, target="Бровари", heading=20,
                     evidence={"heading": {"matched": "на Бровари", "confidence": "high", "method": "stated"}})]
    b.tick()
    b.flush()
    t = api.texts(A)[-1]
    assert t.startswith("🎯 Курс на ваше місце: <b>Бровари</b> (так у дописі)") and "➡️" not in t      # 1.58.40: said once


def test_no_distance_from_a_place_no_post_gave():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"))
    st.marks = [mark(place="область", lon=30.3, lat=50.2, tag="#3"),                        # the oblast only
                mark(place="→ Бориспіль", lon=30.95, lat=50.35, approach=True, tag="#4"),    # heading for, not at
                mark(place="Щасливе", lon=30.79, lat=50.38, held=True, tag="#5"),            # held off the map
                mark(place="Щасливе", lon=30.79, lat=50.38, ai=True, tag="#6"),              # the AI's alone
                mark(place="Щасливе", lon=30.79, lat=50.38, status="down", tag="#7"),        # an outcome
                mark(place="Щасливе", lon=30.79, lat=50.38, stale=True, tag="#8"),           # faded
                mark(place="Щасливе", lon=30.79, lat=50.38, t=T0 - 400, tag="#9"),           # too old to tell late
                mark(place="Бориспіль", lon=30.95, lat=50.35, tag="#10"),                    # 17.5 km
                mark(place="Гора", lon=30.862, lat=50.374, tag="#11")]                       # 12 km: beyond 10 (1.58.40)
    b.tick()
    b.flush()
    assert [t for t in api.texts(A) if ("км від" in t or "Допис" in t) and "Це бот Heimdall" not in t] == []


def test_a_ballistic_missile_is_said_for_the_region_with_no_distance():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"), (B, "Харків"))
    st.marks = [mark(place="Бровари", lon=30.79, lat=50.51, type="ballistic_missiles", tag="#20")]
    clock.t += 1                                               # not held by the gap a chat's last message opened
    b.tick()
    b.flush()
    t = api.texts(A)[-1]
    assert t.startswith("🚨 <b>Балістична ракета</b> — у вашому регіоні (Гнідин). Негайно в укриття.") and "км" not in t.split("\n")[0]
    assert not [x for x in api.texts(B) if "🚨" in x]          # 400 km away


def test_a_target_is_told_once_then_again_only_when_it_comes_to_the_place_or_much_closer():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"))
    n0 = len(api.texts(A))
    st.marks = [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#30")]                         # 8 km
    b.tick()
    b.flush()
    assert len(api.texts(A)) == n0 + 1
    first_mid = api.mid
    clock.t += 60
    st.marks = [mark(place="Щасливе", lon=30.79, lat=50.38, t=clock.t, tag="#30")]
    b.tick()
    b.flush()
    assert len(api.texts(A)) == n0 + 1                          # reported again, no nearer: nothing
    clock.t += 60
    st.marks = [mark(place="Вишеньки", lon=30.72, lat=50.30, t=clock.t, tag="#30")]             # 3 km — but too soon
    b.tick()
    b.flush()
    assert len(api.texts(A)) == n0 + 1
    clock.t += tgbot.UPDATE_GAP_S
    st.marks = [mark(place="Вишеньки", lon=30.72, lat=50.30, t=clock.t, tag="#30")]
    b.tick()
    b.flush()
    m, f, _ = api.sent(A)[-1]
    assert f["text"].startswith("⚠️ ~3 км від") and f["reply_parameters"]["message_id"] == first_mid
    clock.t += 30
    st.marks = [mark(place="Гнідин", lon=30.7058, lat=50.3287, t=clock.t, tag="#30")]           # named: at once
    b.tick()
    b.flush()
    assert api.texts(A)[-1].startswith("📍 Допис назвав ваше місце: <b>Гнідин</b>")


def test_a_swarm_is_one_message():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"))
    n0 = len(api.texts(A))
    st.marks = [mark(place="Вишеньки", lon=30.72, lat=50.30, tag=f"#4{i}") for i in range(7)]
    b.tick()
    b.flush()
    t, = api.texts(A)[n0:]
    assert t.startswith("⚠️ Нові цілі біля ваших місць: 7") and t.count("• ") == tgbot.LIST_MAX and "…і ще 2" in t


def test_its_end_is_what_the_map_shows_and_never_where():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"))
    st.marks = [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#50"), mark(place="Вишеньки", lon=30.72, lat=50.30, tag="#51")]
    b.tick()
    b.flush()
    clock.t += 120
    n1 = len(api.texts(A))
    st.marks = [mark(place="Щасливе", lon=30.79, lat=50.38, tag="#50", stale=True),
                {"id": "c1/x#impact", "type": "drones", "status": "impact", "place": "Проліски", "lon": 30.7796, "lat": 50.3921,
                 "oblast_uid": "14", "ts": iso(T0 + 100), "channel": "kyiv_airdef"}]
    b.tick()
    b.flush()
    t = api.texts(A)[-1]
    assert len(api.texts(A)) == n1 + 1 and "💥 <b>Вибух" in t and "— так у дописі о" in t and "Проліски" not in t  # what, never where
    clock.t += tgbot.END_AFTER_S + 5
    st.marks = []
    b.tick()
    b.flush()
    assert api.texts(A)[-1].startswith("⏹ Нових дописів після") and "Вишеньки" in api.texts(A)[-1]
    n = len(api.calls)
    clock.t += 600
    b.tick()
    b.flush()
    assert len(api.calls) == n                                  # said once


def test_a_restart_does_not_tell_again_and_the_switch_stops_the_alerts():
    b, st, api, kv, clock = bot()
    _users(b, (A, "Гнідин"))
    st.marks = [mark()]
    b.tick()
    b.flush()
    b._save(force=True)
    n = len(api.texts(A))
    b2 = tgbot.TgBot(st, TOKEN, "https://heimdall.com.ua", api=api, gaz=GAZ, kv=kv, clock=clock, shot=False, log=lambda *a: None,
                     store=b.store)
    b2.shot = None
    clock.t += 30
    b2.tick()
    b2.flush()
    assert len(api.texts(A)) == n
    kv.d["bot_on"] = "0"
    st.marks = [mark(tag="#60", t=clock.t)]
    clock.t += 30
    b2.tick()
    b2.flush()
    assert len(api.texts(A)) == n and "switched OFF" in b2.health()["note"]
    say(b2, A, "/places")                                       # its commands still answer: /stop always works
    assert "Ваші місця" in api.texts(A)[-1]


def test_kyiv_and_its_oblast_get_the_maps_picture_drawn_once_for_everyone():
    shot = Shot()
    b, st, api, kv, clock = bot(shot=shot)
    _users(b, (A, "Гнідин"), (B, "Гнідин"))
    st.marks = [mark()]
    b.tick()
    b.flush()
    photos = api.sent(method="sendPhoto")
    assert len(photos) == 2 and shot.n == 1 and photos[0][2]["photo"][1] == "JPEG-Вишеньки".encode()
    assert photos[1][2] is None and photos[1][1]["photo"].startswith("FILE-")     # uploaded once, then its file id


def test_the_token_is_never_logged_stored_or_shown():
    logs = []
    b, st, api, kv, clock = bot(logs=logs)
    _users(b, (A, "Гнідин"))
    api.fail["sendMessage"] = TgError(500, "sendMessage: Internal Server Error")
    st.marks = [mark()]
    b.tick()
    b.flush()
    blob = json.dumps(kv.d) + " ".join(logs) + json.dumps(b.health()) + json.dumps(b.status())
    assert TOKEN not in blob and "SECRET" not in blob
    assert str(A) not in " ".join(logs) and "Гнідин" not in " ".join(logs)        # counts, never a chat or a place


# ---- the server -----------------------------------------------------------------------------------------------------
def test_the_server_runs_the_bot_instead_of_the_channel():
    assert "state.bot = tgbot.start(state, log=log, ssl_ctx=_SSL_CTX, sat=SAT, oblasts=NAME_BY_UID)" in SRV
    assert "chanpost.start(" not in SRV and not re.search(r"state\.channel\b", SRV)
    assert 'official.append(self.bot.health())' in SRV and 'if u.path == "/api/admin/bot_switch":' in SRV
    assert tgbot.configured({"TG_BOT_TOKEN": "x"}) and not tgbot.configured({"TG_CHANNEL_ID": "-100"})
    assert tgbot.start(object(), env={}) is None
    assert "fetch('/api/admin/bot_switch'" in ADMIN and "drawBotSw()" in ADMIN and "t.me/${esc(s.username)}" in ADMIN
    for k in ("bs_h:", "bs_none:", "bs_setup:", "bs_note_on:", "bs_note_off:", "bs_q_off:", "bs_q_on:", "bs_users:", "bs_link:"):
        assert ADMIN.count(k) == 2, k


def test_the_docs_say_it():
    for doc in ("SAFETY.md", "TECHNICAL.md"):
        s = open(os.path.join(ROOT, "docs", doc), encoding="utf-8").read()
        assert "1.58.38" in s and "tgbot" in s, doc
    assert "## 1.58.38" in open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()


def test_chanpost_words_are_shared():
    assert tgbot.LABEL["uk"]["drones"] == chanpost.LABEL["drones"][1] and tgbot.T["uk"]["warn"] == chanpost.WARN
    assert tgbot.OUTCOME["uk"]["down"] == chanpost.OUTCOME["down"][1]
