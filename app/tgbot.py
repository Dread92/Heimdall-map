"""1.58.38: the owner's Telegram bot, one to one — it replaces the private channel (app/chanpost.py, no longer started).

The owner (20 Oct 2026): "we need to completely re-think the Telegram bot: the bot will ask the user, one to one, what
location they want to be alerted on — if they write Hnidyn, the bot sends them a message only when their place is
mentioned, or a threat is detected nearby". His answers to the questions that followed: it replaces the channel; it
writes when a post names the place, or when a target is reported within 15 km of it; up to 4 places a user.
1.58.40, the owner: "the place must not be cluttered" — 10 km instead of 15; no course, no clock, no "not radar" line in
an alert (the reminder is in the first message and the bot's description); "probably a drone" without "— type not
stated"; a target shot down is not followed by a message.

Its rules (docs/SAFETY.md, "The bot writes about a place because it was given one"):
  - a place is one of the gazetteer's (the towns, villages and Kyiv districts the map knows), found by its name — in
    Ukrainian, Russian or Latin letters — or from a location the user shares, which is used once to list the nearest
    such places and is never kept, logged or sent on. What the server keeps: the chat's number, its language, the
    places chosen. No name, no username, no phone, no message. /stop deletes all of it, and so does blocking the bot;
  - it says what the map shows and nothing more, in the channel's words (chanpost): the type and the place a post gave,
    the height a post gave (fresh) and when, the map's link; "from channel posts, not radar" in the first message and the
    bot's description (1.58.40: not in every alert); a distance only from the place the post named to the user's place,
    as the app's Near list measures it; never the channel; a course only as "heading for your place", when a post said it;
  - "nearby" is the app's own push rule (server.proximity_watch): a live target — no outcome, not faded, not superseded,
    not the AI's alone — placed at a town a post named (not an oblast, not a raion, not held off the map), within
    NEAR_KM; a ballistic or supersonic missile is said for the whole region (geo.REGION_ALERT_KM), with no distance;
  - a target is told once per place, and again only when it comes to the place (named there, or heading for it), or
    CLOSER_KM nearer at most every UPDATE_GAP_S; its end is what the map shows: an outcome a post reported, in the
    app's words and without where it happened (1.58.40: not a shot down — nothing follows it), or no new reports for
    END_AFTER_S. Telegram never starts or ends an
    alert: the bot says nothing of an alert or an all-clear;
  - the token is the owner's (the Fly secret TG_BOT_TOKEN, the channel's bot): read from the environment, never written
    to the database, a log or an answer. The logs carry counts, never a chat, a text or a place.
"""
import collections
import difflib
import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone

import chanpost
from chanpost import BotAPI, TgError, esc, hhmm, report_t

try:
    import geo
except Exception:  # pragma: no cover
    geo = None
try:
    import areas
except Exception:  # pragma: no cover
    areas = None
try:
    import mapshot
except Exception:  # pragma: no cover
    mapshot = None
try:
    from translate import translit
except Exception:  # pragma: no cover
    def translit(s):
        return s

KV_ON = "bot_on"                  # the dashboard's switch ("0" = off: no alert goes out; the commands still answer)
KV_OFFSET = "bot_offset"          # the next update to read (Telegram keeps them 24 h)
KV_SENT = "bot_sent"              # what each chat was told of each target (a restart does not tell it again)
MAX_PLACES = 4                    # the owner's pick: "up to 4", as the app's pins
NEAR_KM = 10.0                    # the owner's pick: "15 km"; 1.58.40: "10 km instead of 15"
MENTION_KM = 3.0                  # a post's place named like the user's and this close to it is the user's place
FRESH_S = 5 * 60                  # a report older than this is not told late (after a restart, a pause)
UPDATE_GAP_S = 180                # a target told already: "closer" again at most this often
CLOSER_KM = 3.0                   # … and only when this much closer
END_AFTER_S = 10 * 60             # no new report for this long: "no new reports since HH:MM"
CHAT_GAP_S = 20                   # one alert message a chat at most this often (a swarm is one message); a missile waits not
KEEP_S = 6 * 3600                 # what is kept of the targets told
TICK_S = 5
POLL_S = 25                       # getUpdates' long poll (BotAPI waits 30 s)
RATE_PER_S = 25                   # Telegram: about 30 messages a second in all, one a second in one chat
IN_PER_MIN = 20                   # a chat's messages to the bot answered each minute (more are ignored)
PICK_TTL_S = 15 * 60
SEARCH_MAX = 6
LIST_MAX = 5                      # targets listed in one message
LOC_KM = 12.0                     # a shared location: the places this close
LANGS = ("uk", "en")             # 1.58.39, the owner: "the bot must be in Ukrainian and English"
TYPES = chanpost.TYPES + ("guided_aerial_bombs",)
RANK = {"near": 1, "dest": 2, "here": 3, "region": 3}
# the gazetteer's entries that are not a place to live in: bridges, roads, squares, plants, reservoirs, airports
SKIP_RX = re.compile(r"водосховищ|АЕС|ГЕС|ТЕЦ|аеропорт|траса|шосе|проспект|метро|площа|набережн|очисні|дамба|(?:^|\s)міст(?:\s|$)|"
                     r"^Столиця$|берег$|^Рембаза$|^ДВРЗ$|^Політех$", re.I)

LABEL = {
    "uk": {k: v[1] for k, v in chanpost.LABEL.items()} | {"guided_aerial_bombs": "КАБ", "unknown_dr": "Ймовірно, дрон"},
    "en": {"drones": "Shahed", "jet": "Jet drone", "ballistic_missiles": "Ballistic missile", "cruise_missiles": "Cruise missile",
           "supersonic_missiles": "Supersonic missile (Kh-22/32)", "unspecified_missiles": "Missile",
           "banderol_missiles": "Banderol (jet drone)", "unknown_dr": "Probably a drone",
           "unknown": "Drone or missile — type not stated", "guided_aerial_bombs": "Guided bomb (KAB)"},
}
EMOJI = {k: v[0] for k, v in chanpost.LABEL.items()} | {"guided_aerial_bombs": "💣"}
COMPASS = {"uk": chanpost.COMPASS, "en": ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")}
ALT_STATE = {"uk": chanpost.ALT_STATE, "en": {"low": "low", "high": "high", "descending": "descending", "climbing": "climbing"}}
# what became of a target, in the app's own words (static/i18n.js st_down … st_clear)
OUTCOME = {"uk": {k: v[1] for k, v in chanpost.OUTCOME.items()},
           "en": {"down": "Confirmed shot down", "impact": "Explosion (impact or interception — not known which)",
                  "lost": "Lost from tracking", "clear": "Area reported clear"}}
OUT_EMOJI = {k: v[0] for k, v in chanpost.OUTCOME.items()}

T = {
    "uk": {
        "start": "👋 Це бот Heimdall — неофіційної мапи повітряних загроз.\n\nНапишіть назву міста чи села (наприклад, <b>Гнідин</b>) "
                 "або надішліть геолокацію. Я напишу вам, коли допис каналу назве це місце або повідомить ціль ближче ніж за "
                 "{km} км від нього. До {n} місць.\n\n{warn}\n\n🔒 Я зберігаю лише номер цього чату, мову й обрані місця — не "
                 "ім'я, не телефон, не ваші повідомлення. Геолокація потрібна лише раз, щоб знайти найближчі населені пункти, і "
                 "не зберігається. /stop видаляє все.\n\n/places — ваші місця · /lang — мова · /stop — зупинити",
        "added": "✅ Додано: {p}\nНапишу, коли його назве допис або ціль буде ближче ніж за {km} км. Місць: {i} з {n}.",
        "already": "{p} — уже у ваших місцях.",
        "full": "У вас уже {n} місця — спершу приберіть одне в /places.",
        "pick": "Знайшов кілька — котре?",
        "none": "Не знайшов «{q}». Напишіть назву, як на мапі — українською чи латиницею: Гнідин, Бровари, Оболонь…",
        "places": "Ваші місця ({i} з {n}). Натисніть, щоб прибрати:",
        "no_places": "Місць поки немає. Напишіть назву міста чи села.",
        "removed": "Прибрано: {p}.",
        "stopped": "Готово: ваші місця й мову видалено, повідомлень більше не буде. /start — почати знову.",
        "lang": "Мова повідомлень:",
        "lang_set": "Мова: українська.",
        "loc_none": "Поруч немає населеного пункту з мапи. Напишіть назву.",
        "loc_pick": "Найближчі населені пункти (вашу геолокацію не збережено):",
        "expired": "Цей вибір застарів — напишіть назву ще раз.",
        "cancel": "Скасувати", "cancelled": "Скасовано.",
        "here": "📍 Допис назвав ваше місце: <b>{p}</b>",
        "dest": "🎯 Курс на ваше місце: <b>{p}</b> (так у дописі)",
        "near": "⚠️ ~{d} км від <b>{p}</b> (від місця, яке назвав допис)",
        "region": "🚨 <b>{what}</b> — у вашому регіоні ({p}). Негайно в укриття.",
        "s_here": "📍 {p}", "s_dest": "🎯 → {p}", "s_near": "~{d} км від {p}", "s_region": "🚨 регіон {p}",
        "many": "⚠️ Нові цілі біля ваших місць: {n}",
        "more": "…і ще {n}",
        "unsaid": "📍 Де саме зараз — у дописі не сказано",
        "held": "⚪ Офіційної тривоги там поки немає — на мапі її не показано, доки тривогу не оголосять",
        "alt": "↕️ Висота: {a}", "alt_m": "~{m} м", "alt_at": " (у дописі о {t})",
        "said": "так у дописі о {t}",
        "quiet": "⏹ Нових дописів після {t} немає",
        "map": "Мапа Heimdall",
        "warn": chanpost.WARN,
        "about": "Heimdall — неофіційна мапа повітряних загроз. Пише вам, коли допис каналу називає ваше місце або повідомляє "
                 "ціль поруч.",
        "about_short": "Неофіційна мапа повітряних загроз · з дописів каналів, не радар",
        "cmd_start": "Як це працює", "cmd_places": "Мої місця", "cmd_lang": "Мова", "cmd_stop": "Зупинити й видалити все",
        "obl": "обл.",
    },
    "en": {
        "start": "👋 This is the Heimdall bot — an unofficial air-threat map of Ukraine.\n\nWrite the name of a town or village "
                 "(for example <b>Hnidyn</b>) or share a location. I will write to you when a channel post names that place, or "
                 "reports a target less than {km} km from it. Up to {n} places.\n\n{warn}\n\n🔒 I keep only this chat's "
                 "number, its language and the places you choose — no name, no phone, none of your messages. A shared location "
                 "is used once to find the nearest towns and villages, and is not kept. /stop deletes everything.\n\n"
                 "/places — your places · /lang — language · /stop — stop",
        "added": "✅ Added: {p}\nI will write when a post names it or a target is less than {km} km from it. Places: {i} of {n}.",
        "already": "{p} is already one of your places.",
        "full": "You already have {n} places — remove one in /places first.",
        "pick": "I found several — which one?",
        "none": "I did not find “{q}”. Write the name as on the map, in Ukrainian or Latin letters: Hnidyn, Brovary, Obolon…",
        "places": "Your places ({i} of {n}). Tap one to remove it:",
        "no_places": "No places yet. Write the name of a town or village.",
        "removed": "Removed: {p}.",
        "stopped": "Done: your places and language are deleted, no more messages. /start to begin again.",
        "lang": "Language of the messages:",
        "lang_set": "Language: English.",
        "loc_none": "No town or village of the map near there. Write a name.",
        "loc_pick": "The nearest towns and villages (your location was not kept):",
        "expired": "That choice has expired — write the name again.",
        "cancel": "Cancel", "cancelled": "Cancelled.",
        "here": "📍 A post named your place: <b>{p}</b>",
        "dest": "🎯 Heading for your place: <b>{p}</b> (as the post said)",
        "near": "⚠️ ~{d} km from <b>{p}</b> (from the place the post named)",
        "region": "🚨 <b>{what}</b> — in your region ({p}). Take shelter now.",
        "s_here": "📍 {p}", "s_dest": "🎯 → {p}", "s_near": "~{d} km from {p}", "s_region": "🚨 region of {p}",
        "many": "⚠️ New targets near your places: {n}",
        "more": "…and {n} more",
        "unsaid": "📍 Where it is now: the post did not say",
        "held": "⚪ No official alert there yet — not on the map until one is declared",
        "alt": "↕️ Height: {a}", "alt_m": "~{m} m", "alt_at": " (posted at {t})",
        "said": "as a post said at {t}",
        "quiet": "⏹ No new reports since {t}",
        "map": "Heimdall map",
        "warn": "⚠️ From channel posts, not radar. The siren and the official alert come first.",
        "about": "Heimdall — an unofficial air-threat map. It writes to you when a channel post names your place or reports a "
                 "target near it.",
        "about_short": "Unofficial air-threat map · from channel posts, not radar",
        "cmd_start": "How it works", "cmd_places": "My places", "cmd_lang": "Language", "cmd_stop": "Stop and delete everything",
        "obl": "oblast",
    },
}


# 1.58.39, the owner: "the bot must be in Ukrainian and English — it can ask the preferred language as its first question"
CHOOSE = "🇺🇦 Оберіть мову повідомлень\n🇬🇧 Choose the language of the messages"
LANG_KB = [[{"text": "🇺🇦 Українська", "callback_data": "l:uk"}, {"text": "🇬🇧 English", "callback_data": "l:en"}]]


def tr(lang, k, **kw):
    s = (T.get(lang) or T["uk"]).get(k) or T["uk"][k]
    return s.format(**kw) if kw else s


def lang_of(code):
    """A Telegram user's language → the bot's, before they chose one: Ukrainian for uk/ru/be (and unknown), else English."""
    c = (code or "").lower()[:2]
    return "uk" if c in ("uk", "ru", "be", "") else "en"


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


# ---- the gazetteer ------------------------------------------------------------------------------------------------
def base_name(key):
    """"Іванівка (Броварський р-н) 2" → "Іванівка"."""
    return re.sub(r" \d+$", "", (key or "").split(" (")[0]).strip()


def canon(s):
    """One spelling for comparing names whatever the letters: Ukrainian, Russian ("Гнидин") or Latin ("Hnydin") → the
    Latin letters, with the vowels and the pairs people write differently made one (y/i, kh/h, ie/e, iu/u, ia/a)."""
    s = translit((s or "").lower().replace("ё", "е"))
    s = re.sub(r"[^a-z]", "", s.lower())
    for a, b in (("shch", "sc"), ("kh", "h"), ("zh", "z"), ("ts", "c"), ("ch", "c"), ("sh", "s"), ("ie", "e"), ("iu", "u"),
                 ("ia", "a"), ("yi", "i"), ("y", "i"), ("j", "i"), ("w", "v"), ("x", "ks"), ("ii", "i")):
        s = s.replace(a, b)
    return s


class Gazetteer:
    """The places a user can choose: the core gazetteer's (geo.PLACES) and the regional ones (geo.REGIONAL: the villages
    of the oblasts read regionally, Kyiv oblast's since 1.54.7), without the raions and what is not a place to live."""

    def __init__(self, oblasts=None):
        self.oblasts = oblasts or {}          # uid → (Ukrainian name, English name)
        self._idx = None
        self._lock = threading.Lock()

    def _build(self):
        rows = {}
        if geo is not None:
            meta = getattr(geo, "_REG_META", {})
            for k, v in dict.items(geo.PLACES):
                if not SKIP_RX.search(k):
                    rows[k] = (v[0], v[1], v[2], "C", 10 ** 7, None)
            for k, v in geo.REGIONAL.items():
                kind, pop, raion = meta.get(k, ("P", 0, None))
                if kind == "R" or k in rows or SKIP_RX.search(k):
                    continue
                rows[k] = (v[0], v[1], v[2], kind, pop or 0, raion)
        idx = {}
        for k, (lon, lat, uid, kind, pop, raion) in rows.items():
            b = base_name(k)
            idx[k] = {"key": k, "base": b, "c": canon(b), "lon": lon, "lat": lat, "uid": uid, "kind": kind, "pop": pop,
                      "raion": raion}
        by_c = collections.defaultdict(list)
        for e in idx.values():
            by_c[e["c"]].append(e["key"])
        for e in idx.values():
            e["namesakes"] = len(by_c[e["c"]])
        self._by_c = by_c
        self._idx = idx

    @property
    def idx(self):
        if self._idx is None:
            with self._lock:
                if self._idx is None:
                    self._build()
        return self._idx

    def get(self, key):
        return self.idx.get(key)

    @staticmethod
    def _order(e):
        return ({"C": 0, "A": 1, "X": 2, "P": 3}.get(e["kind"], 4), -(e["pop"] or 0), e["key"])

    def search(self, text):
        """The places named so: the same name first (all its namesakes), else the names starting so, else the
        nearest spellings. At most SEARCH_MAX."""
        q = canon(text)
        if len(q) < 2:
            return []
        idx = self.idx
        exact = [idx[k] for k in self._by_c.get(q, ())]
        if exact:
            return sorted(exact, key=self._order)[:SEARCH_MAX]
        if len(q) >= 4:
            pre = [e for e in idx.values() if e["c"].startswith(q)]
            if pre:
                return sorted(pre, key=lambda e: (len(e["c"]),) + self._order(e))[:SEARCH_MAX]
        near = difflib.get_close_matches(q, list(self._by_c), n=SEARCH_MAX, cutoff=0.8)
        out = []
        for c in near:
            out += sorted((idx[k] for k in self._by_c[c]), key=self._order)
        return out[:SEARCH_MAX]

    def nearest(self, lat, lon, km=LOC_KM, n=4):
        """The places within `km` of a point, the nearest first — a shared location, used once."""
        out = []
        for e in self.idx.values():
            if abs(e["lat"] - lat) > km / 100 or abs(e["lon"] - lon) > km / 60:
                continue
            d = haversine_km(lat, lon, e["lat"], e["lon"])
            if d <= km:
                out.append((d, e))
        out.sort(key=lambda x: (x[0], self._order(x[1])))
        return [e for _, e in out[:n]]

    def where(self, e, lang):
        """The raion and oblast of a place, for telling namesakes apart."""
        parts = []
        r = e.get("raion")
        if not r and e["uid"] == "14" and areas is not None:
            a = areas.area_at(e["lon"], e["lat"])
            if a and a[0] == "14" and a[1] in chanpost.AREA_UK:
                r = chanpost.AREA_UK[a[1]].replace(" район", " р-н")
        if r:
            parts.append(r)
        o = self.oblasts.get(e["uid"])
        if o and e["uid"] != "31":
            en = o[1] if re.search(r"oblast|crimea|city", o[1], re.I) else f"{o[1]} {tr(lang, 'obl')}"
            parts.append(o[0].replace(" область", " обл.") if lang == "uk" else en)
        elif e["uid"] == "31" and e["base"] != "Київ":
            parts.append("Київ" if lang == "uk" else "Kyiv")
        return " · ".join(parts)

    def label(self, e, lang, where=False):
        """"Гнідин" (uk), "Гнідин (Hnidyn)" (en) — with its raion and oblast when `where`."""
        n = e["base"] if lang == "uk" else f"{e['base']} ({translit(e['base'])})"
        w = self.where(e, lang) if where else ""
        return n + (" — " + w if w else "")


# ---- what the bot keeps -------------------------------------------------------------------------------------------
class BotStore:
    """Two small tables in the server's database: the chats (number, language) and their places (the gazetteer's key).
    Nothing else of a user is ever written."""

    def __init__(self, conn, lock):
        self.conn, self.lock = conn, lock
        with lock:
            conn.execute("CREATE TABLE IF NOT EXISTS bot_chats(chat_id INTEGER PRIMARY KEY, lang TEXT, since TEXT, last TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS bot_places(chat_id INTEGER, key TEXT, added TEXT, PRIMARY KEY(chat_id, key))")
            conn.commit()
        self._all = None

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def chat(self, chat_id):
        with self.lock:
            r = self.conn.execute("SELECT lang FROM bot_chats WHERE chat_id=?", (int(chat_id),)).fetchone()
        return {"lang": r[0]} if r else None

    def chat_set(self, chat_id, lang):
        now = self._now()
        with self.lock:
            self.conn.execute("INSERT INTO bot_chats(chat_id,lang,since,last) VALUES(?,?,?,?) "
                              "ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang, last=excluded.last",
                              (int(chat_id), lang if lang in LANGS else "uk", now, now))
            self.conn.commit()
        self._all = None

    def places(self, chat_id):
        with self.lock:
            return [r[0] for r in self.conn.execute("SELECT key FROM bot_places WHERE chat_id=? ORDER BY rowid",
                                                    (int(chat_id),)).fetchall()]

    def place_add(self, chat_id, key):
        with self.lock:
            n = self.conn.execute("SELECT COUNT(*) FROM bot_places WHERE chat_id=?", (int(chat_id),)).fetchone()[0]
            if n >= MAX_PLACES:
                return False
            self.conn.execute("INSERT OR IGNORE INTO bot_places(chat_id,key,added) VALUES(?,?,?)", (int(chat_id), key, self._now()))
            self.conn.commit()
        self._all = None
        return True

    def place_del(self, chat_id, key):
        with self.lock:
            self.conn.execute("DELETE FROM bot_places WHERE chat_id=? AND key=?", (int(chat_id), key))
            self.conn.commit()
        self._all = None

    def forget(self, chat_id):
        with self.lock:
            self.conn.execute("DELETE FROM bot_places WHERE chat_id=?", (int(chat_id),))
            self.conn.execute("DELETE FROM bot_chats WHERE chat_id=?", (int(chat_id),))
            self.conn.commit()
        self._all = None

    def all_places(self):
        """[(chat_id, lang, key)] — read again at most every 3 s."""
        c = self._all
        if c and time.monotonic() - c[0] < 3:
            return c[1]
        with self.lock:
            rows = self.conn.execute("SELECT p.chat_id, c.lang, p.key FROM bot_places p JOIN bot_chats c ON c.chat_id=p.chat_id "
                                     "ORDER BY p.chat_id, p.rowid").fetchall()
        out = [(r[0], r[1] or "uk", r[2]) for r in rows]
        self._all = (time.monotonic(), out)
        return out

    def counts(self):
        with self.lock:
            chats = self.conn.execute("SELECT COUNT(*) FROM bot_chats").fetchone()[0]
            places = self.conn.execute("SELECT COUNT(*) FROM bot_places").fetchone()[0]
            users = self.conn.execute("SELECT COUNT(DISTINCT chat_id) FROM bot_places").fetchone()[0]
        return {"chats": chats, "with_places": users, "places": places}


# ---- what a message says ------------------------------------------------------------------------------------------
def label_key(m):
    t = m.get("type")
    if t == "drones" and m.get("jet"):
        return "jet"
    if t == "unknown":
        return "unknown_dr" if m.get("_drone") else "unknown"
    return t if t in EMOJI else "unknown"


def head_line(m, lang):
    k = label_key(m)
    n = m.get("count")
    place = geo.display_place(chanpost.place_text(m)) if geo else chanpost.place_text(m)
    if lang != "uk":                                    # the map's English and French pages name places in Latin letters
        place = translit(place)
    return (f"{EMOJI.get(k, '❔')} <b>{esc(LABEL[lang].get(k) or LABEL['uk'][k])}{' ×' + str(n) if isinstance(n, int) and n > 1 else ''}"
            f"</b> · {esc(place)}")


def alt_text(m, lang):
    alt, at = chanpost.stated_alt(m)
    if not alt:
        return None
    a = tr(lang, "alt_m", m=int(alt["m"])) if alt.get("m") else ALT_STATE[lang][alt["state"]]
    return tr(lang, "alt", a=a) + (tr(lang, "alt_at", t=hhmm(at)) if at else "")


def body_lines(m, lang):
    """1.58.40, the owner: no course here ("on va pas préciser la direction") — "heading for your place" is the trigger
    line, when a post said it; the picture keeps the stated course."""
    lines = [head_line(m, lang)]
    if chanpost.approach(m):
        lines.append(tr(lang, "unsaid"))
    if m.get("held"):
        lines.append(tr(lang, "held"))
    a = alt_text(m, lang)
    if a:
        lines.append(esc(a))
    return lines


def foot(lang, t, url):
    """1.58.40, the owner: "the place must not be cluttered" — no clock (Telegram shows the time) and no reminder (it is
    in the first message and the bot's description): the map's link only."""
    return [f'🗺 <a href="{esc(url.rstrip("/"))}/m">{esc(tr(lang, "map"))}</a>']


def trigger_line(h, lang, label, short=False):
    k = h["kind"]
    if k == "region":
        what = LABEL[lang].get(label_key(h["m"])) or LABEL["uk"].get(label_key(h["m"]), "")
        return tr(lang, "s_region", p=esc(label)) if short else tr(lang, "region", what=esc(what), p=esc(label))
    d = h.get("d")
    dk = f"{d:.0f}" if d is not None else "?"
    return tr(lang, ("s_" if short else "") + k, p=esc(label), d=dk)


def alert_text(h, lang, label, url):
    """One target near one place: why (named, heading for it, how far, the region), what the post said, the reminder."""
    m = h["m"]
    lines = [trigger_line(h, lang, label)] + body_lines(m, lang) + foot(lang, report_t(m) or time.time(), url)
    return "\n".join(lines)[:1024]


def list_text(hits, lang, labels, url):
    """Several targets for one chat in one message (a swarm is one message, not ten)."""
    lines = [tr(lang, "many", n=len(hits))]
    for h in hits[:LIST_MAX]:
        lines.append("• " + trigger_line(h, lang, labels[h["place"]], short=True) + " — " + head_line(h["m"], lang))
    if len(hits) > LIST_MAX:
        lines.append(tr(lang, "more", n=len(hits) - LIST_MAX))
    lines += foot(lang, max(report_t(h["m"]) or 0 for h in hits) or time.time(), url)
    return "\n".join(lines)[:4000]


def end_text(m, end, lang):
    """What became of a target, in reply to what the chat was told: an outcome a post reported (never where), or no new
    reports since its last."""
    if end.get("k") == "outcome" and end.get("status") in OUTCOME[lang]:
        first = f"{OUT_EMOJI[end['status']]} <b>{esc(OUTCOME[lang][end['status']])}</b> — {tr(lang, 'said', t=hhmm(end['t']))}"
    else:
        first = tr(lang, "quiet", t=hhmm(end["t"]))
    return first + "\n" + head_line(m, lang)


# ---- the bot ------------------------------------------------------------------------------------------------------
def _h(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


class TgBot:
    """Reads its private messages (getUpdates) and answers them; every few seconds, compares the marks of the moment with
    every user's places and writes to the chats concerned. All its messages leave through one queue, at Telegram's pace."""

    def __init__(self, state, token, public_url, store=None, api=None, gaz=None, log=print, clock=time.time, kv=None,
                 shot=None, sat=None, oblasts=None):
        self.state, self.public_url, self.log, self.clock = state, public_url, log, clock
        self.api = api or BotAPI(token, getattr(state, "_ssl_ctx", None))
        self.kv = kv or getattr(state, "store", None)
        self.store = store or BotStore(self.kv.conn, self.kv.lock)
        self.gaz = gaz or Gazetteer(oblasts)
        if shot is None and mapshot is not None and getattr(mapshot, "Image", None) is not None:
            try:
                shot = mapshot.MapShot(sat=sat)
            except Exception as e:
                log("bot: no map picture —", type(e).__name__)
                shot = None
        self.shot = shot
        self.lock = threading.RLock()
        self.out = collections.deque()          # the messages waiting to go
        self.sent_at = collections.deque()      # the times of the last second's calls
        self.chat_last = {}                     # chat → time of its last alert message
        self.inbox = {}                         # chat → [times of its messages, this minute]
        self.pick = {}                          # chat → (time, [keys]) — a list offered to choose from
        self.pending = {}                       # chat → (time, what a new user wrote before choosing a language)
        self.photos = {}                        # picture key → Telegram's file id (one upload for many chats)
        self.pngs = collections.OrderedDict()   # picture key → the picture drawn (once for every chat told of it)
        self.pause_until = 0.0
        self.offset = None
        self.username = None
        self.stats = {"alerts": 0, "closed": 0, "replies": 0, "errors": 0, "blocked": 0, "last_error": None, "last_alert": None,
                      "failing": False, "conflict": False}
        self.sent = self._load()
        self._dirty_at = None

    # ---- the store of what was told ------------------------------------------------------------------------------
    def _load(self):
        try:
            raw = self.kv.kv_get(KV_SENT) if self.kv else None
            d = json.loads(raw) if raw else {}
        except (ValueError, TypeError, AttributeError):
            d = {}
        cut = self.clock() - KEEP_S
        return {k: v for k, v in d.items() if isinstance(v, dict) and (v.get("seen") or 0) >= cut}

    def _save(self, force=False):
        now = self.clock()
        if not force and self._dirty_at and now - self._dirty_at < 15:
            return
        self._dirty_at = now
        if self.kv:
            try:
                with self.lock:
                    raw = json.dumps(self.sent, ensure_ascii=False, separators=(",", ":"))
                self.kv.kv_set(KV_SENT, raw)
            except Exception as e:
                self.log("bot: could not save what it told —", type(e).__name__)

    def enabled(self):
        try:
            return (self.kv.kv_get(KV_ON) if self.kv else None) != "0"
        except Exception:
            return True

    # ---- the way out ---------------------------------------------------------------------------------------------
    def send(self, chat, method, fields, files=None, cb=None, front=False, pk=None):
        it = {"chat": chat, "method": method, "fields": dict(fields, chat_id=chat), "files": files, "cb": cb, "pk": pk}
        if front:
            self.out.appendleft(it)
        else:
            self.out.append(it)

    def flush(self, n=None):
        """Send what waits, at most RATE_PER_S a second (and `n` this call). Returns how many went."""
        done = 0
        while self.out and (n is None or done < n):
            now = self.clock()
            if now < self.pause_until:
                break
            while self.sent_at and now - self.sent_at[0] >= 1:
                self.sent_at.popleft()
            if len(self.sent_at) >= RATE_PER_S:
                break
            it = self.out.popleft()
            self.sent_at.append(now)
            if it.get("pk") and it.get("files") and self.photos.get(it["pk"]):
                it["fields"]["photo"], it["files"] = self.photos[it["pk"]], None        # uploaded once: its file id since
            try:
                r = self.api.call(it["method"], it["fields"], it.get("files"))
                self.stats["failing"] = False
            except TgError as e:
                r = None
                self._failed(it, e)
            if it.get("cb"):
                try:
                    it["cb"](r)
                except Exception as e:
                    self.log("bot: after a send —", type(e).__name__)
            done += 1
        return done

    def _failed(self, it, e):
        desc = (e.desc or "")[:200]
        if e.retry_after:                                   # Telegram asks to wait: all of it waits, this first
            self.pause_until = self.clock() + float(e.retry_after) + 1
            if not it.get("retried"):
                it["retried"] = True
                self.out.appendleft(it)
            return
        low = desc.lower()
        if e.code == 403 or "chat not found" in low or "user is deactivated" in low:
            self.forget(it["chat"])                        # blocked, or gone: what was kept of them goes
            self.stats["blocked"] += 1
            return
        if it["method"] in ("editMessageText", "answerCallbackQuery") and e.code == 400:
            return                                          # a button pressed twice, a message unchanged: nothing
        self.stats.update(errors=self.stats["errors"] + 1, last_error=desc, failing=True)
        self.log("bot:", desc)

    def forget(self, chat):
        """Everything kept of a chat goes: its places, its language, what it was told."""
        self.store.forget(chat)
        with self.lock:
            pre = f"{chat}|"
            for k in [k for k in self.sent if k.startswith(pre)]:
                del self.sent[k]
        self.pick.pop(chat, None)
        self.pending.pop(chat, None)
        self.chat_last.pop(chat, None)
        self._save(force=True)

    def health(self):
        st, c = self.stats, self.store.counts()
        ok = not st["failing"] and not st["conflict"]
        err = ("another program reads this bot's messages (getUpdates conflict)" if st["conflict"] else st["last_error"])
        return {"name": "telegram bot (private messages)", "ok": ok, "last": st["last_alert"], "error": None if ok else err,
                "note": ("switched OFF on the dashboard · " if not self.enabled() else "")
                        + (f"@{self.username} · " if self.username else "")
                        + f"users {c['with_places']} · places {c['places']} · alerts {st['alerts']} · closed {st['closed']}"
                        + f" · answers {st['replies']}" + (f" · left {st['blocked']}" if st["blocked"] else "")}

    def status(self):
        return {"username": self.username, **self.store.counts(), "alerts": self.stats["alerts"]}

    # ---- the messages it gets ------------------------------------------------------------------------------------
    def poll(self):
        """One long poll for updates; the offset is kept so a restart answers nothing twice."""
        if self.offset is None:
            try:
                self.offset = int((self.kv.kv_get(KV_OFFSET) if self.kv else None) or 0)
            except (TypeError, ValueError):
                self.offset = 0
        try:
            ups = self.api.call("getUpdates", {"offset": self.offset, "timeout": POLL_S,
                                               "allowed_updates": ["message", "callback_query", "my_chat_member"]}) or []
            self.stats["conflict"] = False
        except TgError as e:
            if e.code == 409:
                if not self.stats["conflict"]:
                    self.log("bot: another program reads this bot's updates (a webhook, or a second server) — waiting")
                self.stats["conflict"] = True
                return -1
            raise
        for u in ups:
            self.offset = max(self.offset, int(u.get("update_id", 0)) + 1)
            try:
                self.handle(u)
            except Exception as e:                          # one bad update never stops the others
                self.log("bot: an update failed —", type(e).__name__)
        if ups and self.kv:
            self.kv.kv_set(KV_OFFSET, str(self.offset))
        return len(ups)

    def _busy(self, chat):
        now = self.clock()
        if len(self.inbox) > 5000:
            self.inbox = {c: v for c, v in self.inbox.items() if v and now - v[-1] < 60}
            self.pending = {c: v for c, v in self.pending.items() if now - v[0] <= PICK_TTL_S}
        t = [x for x in self.inbox.get(chat, []) if now - x < 60]
        t.append(now)
        self.inbox[chat] = t
        return len(t) > IN_PER_MIN

    def _reply(self, chat, text, kb=None, edit=None):
        f = {"text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
        if kb is not None:
            f["reply_markup"] = {"inline_keyboard": kb}
        self.stats["replies"] += 1
        if edit:
            self.send(chat, "editMessageText", dict(f, message_id=edit), front=True)
        else:
            self.send(chat, "sendMessage", f, front=True)

    def _lang(self, chat, user=None):
        c = self.store.chat(chat)
        if c:
            return c["lang"]
        return lang_of((user or {}).get("language_code"))

    def handle(self, u):
        if "my_chat_member" in u:                           # a user who blocks the bot: forgotten
            mc = u["my_chat_member"]
            if (mc.get("chat") or {}).get("type") == "private" and (mc.get("new_chat_member") or {}).get("status") in ("kicked", "left"):
                self.forget(mc["chat"]["id"])
            return
        if "callback_query" in u:
            return self._callback(u["callback_query"])
        msg = u.get("message") or {}
        chat = (msg.get("chat") or {})
        if chat.get("type") != "private" or "id" not in chat:
            return                                          # a group, a channel: not this bot's business
        cid = chat["id"]
        if self._busy(cid):
            return
        lang = self._lang(cid, msg.get("from"))
        text = (msg.get("text") or "").strip()
        if not self.store.chat(cid) and not text.lower().startswith(("/stop", "/delete")):
            # a new user: the language first. What they wrote waits for it (in memory, a place name or a command only —
            # a shared location is never kept: they are asked to send it again)
            first = text if text and not text.lower().startswith(("/start", "/help")) else None
            self.pending[cid] = (self.clock(), first)
            return self._reply(cid, CHOOSE, LANG_KB)
        if msg.get("location"):
            return self._location(cid, lang, msg["location"])
        if text:
            self._text(cid, lang, text)

    def _text(self, cid, lang, text):
        if text.startswith("/"):
            cmd = text.split()[0].split("@")[0].lower()
            if cmd in ("/start", "/help"):
                return self._reply(cid, tr(lang, "start", km=int(NEAR_KM), n=MAX_PLACES, warn=tr(lang, "warn")))
            if cmd in ("/places", "/list", "/my"):
                return self._places(cid, lang)
            if cmd in ("/stop", "/delete"):
                self.forget(cid)
                return self._reply(cid, tr(lang, "stopped"))
            if cmd in ("/lang", "/language"):
                return self._reply(cid, tr(lang, "lang"), LANG_KB)
            return self._reply(cid, tr(lang, "start", km=int(NEAR_KM), n=MAX_PLACES, warn=tr(lang, "warn")))
        if len(text) > 60:
            return self._reply(cid, tr(lang, "none", q=esc(text[:40] + "…")))
        found = self.gaz.search(text)
        if not found:
            return self._reply(cid, tr(lang, "none", q=esc(text)))
        if len(found) == 1:
            return self._add(cid, lang, found[0]["key"])
        return self._offer(cid, lang, found, tr(lang, "pick"))

    def _offer(self, cid, lang, found, head):
        self.pick[cid] = (self.clock(), [e["key"] for e in found])
        kb = [[{"text": self.gaz.label(e, lang, where=True)[:60], "callback_data": f"a:{i}"}] for i, e in enumerate(found)]
        kb.append([{"text": tr(lang, "cancel"), "callback_data": "x"}])
        self._reply(cid, head, kb)

    def _location(self, cid, lang, loc):
        try:
            lat, lon = float(loc["latitude"]), float(loc["longitude"])
        except (KeyError, TypeError, ValueError):
            return
        found = self.gaz.nearest(lat, lon)
        del lat, lon, loc                                   # used once: never kept, logged or sent on
        if not found:
            return self._reply(cid, tr(lang, "loc_none"))
        self._offer(cid, lang, found, tr(lang, "loc_pick"))

    def _add(self, cid, lang, key, edit=None):
        e = self.gaz.get(key)
        if not e:
            return self._reply(cid, tr(lang, "expired"), edit=edit)
        have = self.store.places(cid)
        name = esc(self.gaz.label(e, lang, where=True))
        if key in have:
            return self._reply(cid, tr(lang, "already", p=name), edit=edit)
        if not self.store.chat(cid):
            self.store.chat_set(cid, lang)
        if not self.store.place_add(cid, key):
            return self._reply(cid, tr(lang, "full", n=MAX_PLACES), edit=edit)
        self._reply(cid, tr(lang, "added", p=name, km=int(NEAR_KM), i=len(have) + 1, n=MAX_PLACES), edit=edit)

    def _places(self, cid, lang, edit=None, head=None):
        have = self.store.places(cid)
        if not have:
            return self._reply(cid, (head + "\n" if head else "") + tr(lang, "no_places"), kb=[] if edit else None, edit=edit)
        kb = []
        for k in have:
            e = self.gaz.get(k)
            kb.append([{"text": "❌ " + (self.gaz.label(e, lang) if e else base_name(k))[:56], "callback_data": "d:" + _h(k)}])
        self._reply(cid, (head + "\n" if head else "") + tr(lang, "places", i=len(have), n=MAX_PLACES), kb, edit=edit)

    def _callback(self, q):
        """A button pressed: done, then Telegram told it was received (its answer goes first, before the reply)."""
        try:
            self._button(q)
        finally:
            chat = (q.get("message") or {}).get("chat") or {}
            self.send(chat.get("id") or 0, "answerCallbackQuery", {"callback_query_id": q.get("id")}, front=True)

    def _button(self, q):
        msg = q.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private" or "id" not in chat:
            return
        cid, data, mid = chat["id"], str(q.get("data") or ""), msg.get("message_id")
        if self._busy(cid):
            return
        lang = self._lang(cid, q.get("from"))
        if data == "x":
            self.pick.pop(cid, None)
            return self._reply(cid, tr(lang, "cancelled"), kb=[], edit=mid)
        if data.startswith("l:") and data[2:] in LANGS:
            lang, first = data[2:], not self.store.chat(cid)
            self.store.chat_set(cid, lang)
            if not first:
                return self._reply(cid, tr(lang, "lang_set"), kb=[], edit=mid)
            # the first choice: the question becomes the bot's explanation, then what they wrote before it is answered
            # (the answers go to the head of the queue: the last one queued leaves first — the explanation)
            p = self.pending.pop(cid, None)
            if p and p[1] and self.clock() - p[0] <= PICK_TTL_S:
                self._text(cid, lang, p[1])
            return self._reply(cid, tr(lang, "start", km=int(NEAR_KM), n=MAX_PLACES, warn=tr(lang, "warn")), kb=[], edit=mid)
        if data.startswith("a:"):
            p = self.pick.get(cid)
            try:
                i = int(data[2:])
            except ValueError:
                return
            if not p or self.clock() - p[0] > PICK_TTL_S or not (0 <= i < len(p[1])):
                return self._reply(cid, tr(lang, "expired"), kb=[], edit=mid)
            self.pick.pop(cid, None)
            return self._add(cid, lang, p[1][i], edit=mid)
        if data.startswith("d:"):
            for k in self.store.places(cid):
                if _h(k) == data[2:]:
                    self.store.place_del(cid, k)
                    with self.lock:
                        pre = f"{cid}|{k}|"
                        for sk in [sk for sk in self.sent if sk.startswith(pre)]:
                            del self.sent[sk]
                    e = self.gaz.get(k)
                    return self._places(cid, lang, edit=mid,
                                        head=tr(lang, "removed", p=esc(self.gaz.label(e, lang) if e else base_name(k))))
            return self._places(cid, lang, edit=mid)

    # ---- the alerts ----------------------------------------------------------------------------------------------
    def marks(self):
        return self.state.markers_now() or []

    def active(self):
        try:
            return self.state.snapshot().get("active") or []
        except Exception:
            return []

    @staticmethod
    def live(m):
        """A target as push's proximity_watch takes one: flying, on the map, from a post the rules read."""
        if m.get("lon") is None or m.get("lat") is None or m.get("type") not in TYPES:
            return False
        if m.get("status") or m.get("stale") or m.get("superseded_by") or m.get("endedBy") or m.get("ai"):
            return False
        return not (m.get("needs_context") or m.get("candidates"))

    def _same(self, name, e, m, d):
        """Is the place a post named (`name`) the user's place `e`? Its key, or its name with the same oblast (and, for a
        name several villages share, close to it)."""
        if not name:
            return False
        if name == e["key"]:
            return True
        if canon(base_name(geo.display_place(name) if geo else name)) != e["c"]:
            return False
        if d is not None:
            return d <= MENTION_KM
        if m.get("target_uid"):
            return m["target_uid"] == e["uid"]
        return e["namesakes"] == 1 or m.get("oblast_uid") == e["uid"]

    def hit(self, e, m):
        """Why a target concerns place `e`, or None: {"kind": here | dest | near | region, "d": km}."""
        d = haversine_km(e["lat"], e["lon"], m["lat"], m["lon"])
        if geo is not None and geo.is_immediate(m.get("type")):
            return {"kind": "region", "d": None} if d <= geo.REGION_ALERT_KM else None
        raw = (m.get("place") or "").strip()
        arrow = raw.startswith("→")
        named = raw.lstrip("→").strip()
        part = chanpost.part_of_oblast(m)
        if not arrow and not part and not chanpost.approach(m) and self._same(named, e, m, d):
            return {"kind": "here", "d": 0.0}
        tgt = m.get("target") or (named if arrow or chanpost.approach(m) else None)
        if tgt and self._same(tgt, e, m, None):
            return {"kind": "dest", "d": None}
        if part or arrow or chanpost.approach(m) or m.get("held") or named in ("", "область") or named.endswith(" р-н"):
            return None                                     # no town the post placed it at: no distance to anybody
        if d <= NEAR_KM:
            return {"kind": "near", "d": round(d, 1)}
        return None

    def tick(self):
        if not self.enabled():
            return
        now = self.clock()
        marks = self.marks()
        missiles = [(m["lon"], m["lat"]) for m in marks if m.get("type") in chanpost.MSL_TYPES and not m.get("status")
                    and m.get("lon") is not None and m.get("lat") is not None]
        cur = {}
        for m in marks:
            if self.live(m):
                k = chanpost.key_of(m)
                if k not in cur or report_t(m) > report_t(cur[k]):
                    cur[k] = m
        for k, m in cur.items():
            if m.get("type") == "unknown":
                cur[k] = dict(m, _drone=mapshot.as_drone(m, missiles) if mapshot else True)
        rows = self.store.all_places()
        by_place = collections.defaultdict(list)
        langs = {}
        for chat, lang, key in rows:
            by_place[key].append(chat)
            langs[chat] = lang if lang in LANGS else "uk"
        todo = collections.defaultdict(list)                # chat → hits to tell
        with self.lock:
            for p in self.sent.values():                    # still reported, wherever: not "no new reports"
                m = cur.get(p.get("track"))
                if m is not None and not p.get("ended"):
                    p.update(seen=now, last=max(p.get("last") or 0, report_t(m)), m=chanpost._slim(m))
            for key, chats in by_place.items():
                e = self.gaz.get(key)
                if not e:
                    continue
                for tk, m in cur.items():
                    h = self.hit(e, m)
                    if not h:
                        continue
                    for chat in chats:
                        sk = f"{chat}|{key}|{tk}"
                        p = self.sent.get(sk)
                        h2 = dict(h, m=m, place=key, sk=sk, track=tk)
                        if p is None or p.get("ended"):
                            if now - report_t(m) > FRESH_S or (p and report_t(m) <= (p.get("last") or 0)):
                                continue
                            todo[chat].append(dict(h2, reply=(p or {}).get("mid")))
                            continue
                        up = RANK[h["kind"]] > RANK.get(p.get("kind"), 0)
                        closer = (h["kind"] == "near" and p.get("kind") == "near" and p.get("d") is not None
                                  and h["d"] <= p["d"] - CLOSER_KM and now - (p.get("t") or 0) >= UPDATE_GAP_S)
                        if (up or closer) and now - report_t(m) <= FRESH_S:
                            todo[chat].append(dict(h2, reply=p.get("mid"), update=True))
            ends = self._ends(now, marks, cur)
        changed = bool(ends)
        for chat, hits in todo.items():
            urgent = any(h["kind"] == "region" for h in hits)
            if not urgent and now - self.chat_last.get(chat, 0) < CHAT_GAP_S:
                continue                                    # the next pass, in one message with whatever came meanwhile
            best = {}
            for h in hits:                                  # one line a target, for its most concerned place
                b = best.get(h["track"])
                if b is None or (RANK[h["kind"]], -(h["d"] or 0)) > (RANK[b["kind"]], -(b["d"] or 0)):
                    best[h["track"]] = h
            hits = sorted(best.values(), key=lambda h: (-RANK[h["kind"]], h["d"] or 0))
            all_h = [x for x in todo[chat] if x["track"] in best]
            self._tell(chat, langs.get(chat, "uk"), hits, all_h, now)
            changed = True
        for chat, items in ends.items():
            self._close(chat, langs.get(chat, "uk"), items)
        with self.lock:
            cut = now - KEEP_S
            for k in [k for k, p in self.sent.items() if (p.get("seen") or 0) < cut]:
                del self.sent[k]
                changed = True
        if changed:
            self._save()

    def _ends(self, now, marks, cur):
        """The targets told whose end the map now shows: an outcome a post reported (linked as the Tactical page links
        it), or no new report for END_AFTER_S. → {chat: [(sent key, end)]}"""
        extra = [(p["track"], p["m"]) for p in self.sent.values() if not p.get("ended") and p.get("m")
                 and p["track"] not in cur and now - (p.get("last") or 0) <= chanpost.OUTCOME_WINDOW_S + 120]
        seen, uniq = set(), []
        for k, m in extra:
            if k not in seen:
                seen.add(k)
                uniq.append((k, m))
        outcomes = chanpost.link_outcomes(marks, uniq)
        out = collections.defaultdict(list)
        for sk, p in self.sent.items():
            if p.get("ended") or p.get("kind") == "region":
                continue
            s_ = outcomes.get(p["track"])
            if s_ is not None:
                out[p["chat"]].append((sk, {"k": "outcome", "status": s_.get("status"),
                                            "t": chanpost.parse_ts(s_.get("ts")) or now}))
            elif p["track"] not in cur and now - (p.get("seen") or 0) >= END_AFTER_S:
                out[p["chat"]].append((sk, {"k": "quiet", "t": p.get("last") or now}))
        for chat, items in out.items():
            for sk, end in items:
                self.sent[sk].update(ended=True, end=end)
        return out

    def _picture_key(self, m):
        return json.dumps([chanpost.key_of(m), chanpost.signature(m)], ensure_ascii=False)

    def picture(self, m):
        """The map around the target (the channel's picture, Kyiv and its oblast only) — drawn once for every chat."""
        if not self.shot or m.get("oblast_uid") not in chanpost.SCOPE:
            return None
        try:
            mm = m
            if chanpost.part_of_oblast(mm):
                mm = dict(mm, place=chanpost.place_text(mm), _area_km=chanpost.AREA_KM)
            if mm.get("held"):
                mm = dict(mm, _held=True)
            alt, at = chanpost.stated_alt(mm)
            if alt and at:
                mm = dict(mm, alt=alt, _alt_t=hhmm(at))
            return self.shot.render(mm, self.active(), hhmm(report_t(m) or self.clock()),
                                    ray=chanpost.stated_course(m) is not None and not chanpost.approach(m))
        except Exception as e:
            self.log("bot: picture failed —", type(e).__name__)
            return None

    def _tell(self, chat, lang, hits, all_h, now):
        labels = {}
        for h in all_h:
            e = self.gaz.get(h["place"])
            labels[h["place"]] = self.gaz.label(e, lang) if e else base_name(h["place"])

        def done(r, hs=tuple(all_h)):
            mid = (r or {}).get("message_id")
            if not mid:
                return
            with self.lock:
                for h in hs:
                    p = self.sent.get(h["sk"])
                    if p is not None:
                        p["mid"] = mid
        with self.lock:
            for h in all_h:
                p = self.sent.get(h["sk"]) or {}
                self.sent[h["sk"]] = {"chat": chat, "track": h["track"], "kind": h["kind"], "d": h.get("d"), "t": now,
                                      "seen": now, "last": report_t(h["m"]), "m": chanpost._slim(h["m"]), "mid": p.get("mid")}
        self.chat_last[chat] = now
        self.stats["alerts"] += 1
        self.stats["last_alert"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        if len(hits) == 1:
            h = hits[0]
            text = alert_text(h, lang, labels[h["place"]], self.public_url)
            reply = {"reply_parameters": {"message_id": h["reply"], "allow_sending_without_reply": True}} if h.get("reply") else {}
            pk = self._picture_key(h["m"])
            fid = self.photos.get(pk)
            if fid:
                return self.send(chat, "sendPhoto", {"photo": fid, "caption": text, "parse_mode": "HTML", **reply}, cb=done)
            png = self.pngs.get(pk)
            if png is None:
                png = self.picture(h["m"]) or b""
                self.pngs[pk] = png
                while len(self.pngs) > 20:
                    self.pngs.popitem(last=False)
            if png:
                def done_photo(r, pk=pk):
                    ph = (r or {}).get("photo") or []
                    if ph and ph[-1].get("file_id"):
                        self.photos[pk] = ph[-1]["file_id"]
                        if len(self.photos) > 500:
                            self.photos.pop(next(iter(self.photos)))
                    done(r)
                return self.send(chat, "sendPhoto", {"caption": text, "parse_mode": "HTML", **reply},
                                 files={"photo": ("map.jpg", png, "image/jpeg")}, cb=done_photo, pk=pk)
            return self.send(chat, "sendMessage", {"text": text, "parse_mode": "HTML",
                                                   "link_preview_options": {"is_disabled": True}, **reply}, cb=done)
        self.send(chat, "sendMessage", {"text": list_text(hits, lang, labels, self.public_url), "parse_mode": "HTML",
                                        "link_preview_options": {"is_disabled": True}}, cb=done)

    def _close(self, chat, lang, items):
        """One message for what ended: in reply to what was told of it when it is one target. 1.58.40, the owner: not for
        a target shot down ("on va pas mettre les confirmed shot down") — it ends, and nothing is said."""
        with self.lock:
            ps = [(sk, self.sent[sk], end) for sk, end in items if sk in self.sent
                  and not (end.get("k") == "outcome" and end.get("status") == "down")]
        tracks = {}
        for sk, p, end in ps:
            tracks.setdefault(p["track"], (p, end))
        if not tracks:
            return
        self.stats["closed"] += len(tracks)
        lines = [end_text(p.get("m") or {}, end, lang) for p, end in tracks.values()]
        mids = [p.get("mid") for p, _ in tracks.values() if p.get("mid")]
        f = {"text": "\n\n".join(lines[:LIST_MAX]) + ("\n" + tr(lang, "more", n=len(lines) - LIST_MAX) if len(lines) > LIST_MAX else ""),
             "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
        if mids:
            f["reply_parameters"] = {"message_id": mids[-1], "allow_sending_without_reply": True}
        self.send(chat, "sendMessage", f)

    # ---- the threads ---------------------------------------------------------------------------------------------
    def setup(self):
        """Who the bot is (its @name, for the dashboard) and its menu of commands, in its two languages."""
        try:
            me = self.api.call("getMe", {}) or {}
            self.username = me.get("username")
        except TgError as e:
            self.log("bot: getMe —", e.desc[:120])
        for lang in LANGS:
            cmds = [{"command": c, "description": tr(lang, "cmd_" + c)} for c in ("start", "places", "lang", "stop")]
            code = {} if lang == "uk" else {"language_code": lang}
            for method, f in (("setMyCommands", {"commands": cmds}),
                              ("setMyDescription", {"description": tr(lang, "about") + "\n\n" + tr(lang, "warn")}),
                              ("setMyShortDescription", {"short_description": tr(lang, "about_short")})):
                try:
                    self.api.call(method, {**f, **code})
                except TgError:
                    pass

    def _loop(self, name, fn, every, first=None):
        if first:
            first()
        said = (None, 0.0)
        while True:
            try:
                r = fn()
                if r == -1:
                    time.sleep(30)
                    continue
            except Exception as e:                          # the bot never stops the rest of the server
                what = f"{type(e).__name__} {str(e)[:160]}"
                self.stats.update(errors=self.stats["errors"] + 1, failing=True, last_error=f"{name}: {what}"[:200])
                if what != said[0] or time.time() - said[1] > 600:      # Telegram unreachable: once, not every 5 s
                    self.log(f"bot: {name} failed —", what)
                    said = (what, time.time())
                time.sleep(5)
            if every:
                time.sleep(every)

    def start(self):
        threading.Thread(target=self._loop, args=("updates", self.poll, 0, self.setup), daemon=True, name="bot-in").start()
        threading.Thread(target=self._loop, args=("alerts", self.tick, TICK_S), daemon=True, name="bot-watch").start()
        threading.Thread(target=self._loop, args=("sending", lambda: self.flush(RATE_PER_S), 0.05), daemon=True,
                         name="bot-out").start()
        self.log("bot: answering its private messages and writing to " + str(self.store.counts()["with_places"]) + " users")
        return self


def configured(env=None):
    env = os.environ if env is None else env
    return bool(env.get("TG_BOT_TOKEN"))


def start(state, log=print, ssl_ctx=None, env=None, sat=None, oblasts=None):
    """Called by app/server.py's main(): the bot runs when the owner has set its token (the channel's, TG_BOT_TOKEN)."""
    env = os.environ if env is None else env
    if not configured(env):
        return None
    b = TgBot(state, env["TG_BOT_TOKEN"], chanpost.public_url(env), api=BotAPI(env["TG_BOT_TOKEN"], ssl_ctx), log=log,
              sat=sat, oblasts=oblasts)
    return b.start()
