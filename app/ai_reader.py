"""1.50: a second reader of the channels' posts — a language model through OpenRouter — in SHADOW MODE.

Nothing it says reaches the map, the alerts, the feed or a push. It reads the same posts the rules read, its reading
is checked against the post (every fact must quote the post's own words; every place must be one this server offered
it from its gazetteer) and compared with the rules' reading, and the dashboard shows where the two disagree: posts the
rules missed, places or weapons they read differently. That is what it is for, first — finding what the rules get
wrong, so the rules can be fixed (deterministic, free, instant) — and only later, once it has proved itself, perhaps
a fallback for posts nothing else can read. docs/TECHNICAL.md §7.6, docs/SAFETY.md.

The prompt is a component, not a sentence: fixed rules taken from docs/SAFETY.md (SYSTEM), worked examples (EXAMPLES),
the post's context assembled per post (the channel, its previous posts, the CANDIDATE places), and a strict output
schema (SCHEMA). PROMPT_VERSION is stored with every reading, so two versions can be compared on the same posts.

Only public posts are sent — a channel's own text, its name, place names from our gazetteer. Never a reader, a
watched place, an address, a device.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone

PROMPT_VERSION = "1"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MAX_CANDIDATES = 30
PER_HOUR = 400                       # posts a reader of this server sends at most in an hour

KINDS = ["shahed", "jet_drone", "drone", "cruise_missile", "ballistic_missile", "guided_bomb", "aircraft", "unknown"]
STATUSES = ["in_flight", "shot_down", "impact", "lost"]
RELATIONS = ["at", "heading_to", "from", "near", "side_of", "in_oblast", "none"]
DIRS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]
# our own words for them (the rules' marker types), to compare the two readings
KIND_TYPE = {"shahed": "drones", "jet_drone": "drones", "drone": "drones", "cruise_missile": "cruise_missiles",
             "ballistic_missile": "ballistic_missiles", "guided_bomb": "guided_aerial_bombs",
             "aircraft": "tactic_aircraft_activity", "unknown": "unknown"}
STATUS_OF = {"in_flight": None, "lost": None, "shot_down": "down", "impact": "impact"}
# the rules' types that say the same as the model's word ("Реактивний" is a drone to the rules, "Бандерол" a banderol)
KIND_OK = {"shahed": {"drones"}, "jet_drone": {"drones", "banderol_missiles"}, "drone": {"drones", "banderol_missiles"},
           "cruise_missile": {"cruise_missiles"}, "ballistic_missile": {"ballistic_missiles"},
           "guided_bomb": {"guided_aerial_bombs"}, "aircraft": {"tactic_aircraft_activity"}}
# a long run of digits — a card number in a fundraising line — never leaves the server and is never stored here
_CARD_RX = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")


def mask(text):
    return _CARD_RX.sub("[…]", text or "")

SYSTEM = """You read ONE Telegram post from a Ukrainian air-threat monitoring channel and extract only what it STATES about aerial targets (drones, missiles, guided bombs, aircraft). People decide whether to take cover from what is drawn, so a wrong position is worse than none.

Rules:
1. Never infer. A position, heading, count, altitude or weapon the post does not state is null (or "unknown" for the weapon). A likely guess is still a guess.
2. Quote. Every non-null fact carries the exact words of the post that state it, copied character for character into its *_quote field. If you cannot quote it, it is null.
3. Places only from CANDIDATES, by their id (c1, c2…, or o<number> for an oblast). Never output coordinates. A place the post names that is not in CANDIDATES: place_id null, its words in place_quote.
4. The relation to the place is what the words say:
   - "на X", "курсом на X", "в напрямку X", "у бік X" = heading_to X — the target is NOT at X;
   - "над X", "в районі X", "біля X" said of where it is now, or X alone in a tracker's line = at X; "поблизу X", "неподалік X" = near X;
   - "з X", "від X", "із X" = from X;
   - "північніше X", "на півночі від X", "за 20 км на північ від X" = side_of X (side n; distance_km 20 only if written);
   - an oblast only ("на Київщині", "Сумщина", "в Черкаській області") = in_oblast, with the oblast's o-id.
5. A city named with no place in it ("над Києвом", "околиці Києва", "правий берег Києва") is the city itself (relation at, the city's id). Never pick a district or a street the post does not name.
6. Weapons, by the post's words: "шахед", "герань", "мопед", "ударний БпЛА" = shahed; "реактивний", "реактивний БпЛА/дрон", "Бандерол" = jet_drone (Banderol is a jet drone, never a cruise missile); "БпЛА", "дрон" of no stated kind = drone; "крилата ракета", "Калібр", "Х-101", "Х-55" = cruise_missile; "балістика", "балістична", "Іскандер", "КН-23" = ballistic_missile; "КАБ", "керовані авіабомби" = guided_bomb; "тактична авіація", "МіГ", "Су-34" = aircraft; nothing said ("ціль", "увага") = unknown.
7. Status only when stated: "збито", "знищено", "мінус", "мінуснули", "приземлили" (of a target) = shot_down; "вибух", "вибухи", "приліт", "влучання" = impact; "втрачено контакт", "зник", "не фіксується" = lost; otherwise in_flight.
8. One entry per target or group, in the order of the post. A count only if written ("2 шахеди", "група з 5", "×3", "кілька" is not a number).
9. Heading only when the post gives a course as a direction ("курс на захід" = w); from_side only when it says where it comes from as a direction ("з півночі" = n). A town it flies to is heading_to that town, not a heading.
10. Altitude only when written ("висота 2200", "на 1,5 км" = 1500), in metres.
11. Nothing about aerial targets — an alert starting or ending alone ("Відбій"), news, a fundraiser, the Air Force's morning totals: targets [].
12. PREVIOUS POSTS are context only. "Далі на X" continues the last target named there; but never copy a fact from them into this post's entry unless this post states it.
13. Unsure? Say so in "uncertain" in one short English sentence, and still give only what is stated."""

_NS = {"type": ["string", "null"]}
_NI = {"type": ["integer", "null"]}
_DIR = {"type": ["string", "null"], "enum": DIRS + [None]}
TARGET = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "kind": {"type": "string", "enum": KINDS}, "kind_quote": _NS,
        "count": _NI, "count_quote": _NS,
        "status": {"type": "string", "enum": STATUSES}, "status_quote": _NS,
        "place_id": _NS, "place_quote": _NS,
        "relation": {"type": "string", "enum": RELATIONS},
        "side": _DIR, "distance_km": _NI,
        "from_side": _DIR, "from_quote": _NS,
        "heading": _DIR, "heading_quote": _NS,
        "altitude_m": _NI, "altitude_quote": _NS,
    },
}
TARGET["required"] = list(TARGET["properties"])
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"targets": {"type": "array", "items": TARGET}, "uncertain": _NS},
          "required": ["targets", "uncertain"]}


def _t(**kw):
    """One target of an example, the fields not given null."""
    base = {k: None for k in TARGET["properties"]}
    base.update(kind="unknown", status="in_flight", relation="none")
    base.update(kw)
    return base


# Worked examples, given as earlier turns of the conversation: each is a post, its candidates, the right reading.
EXAMPLES = [
    ("@kpszsu (oblast: —)", [], "2 шахеди з півночі на Бровари",
     "c1 | Бровари | Київська область\no14 | Київська область",
     {"targets": [_t(kind="shahed", kind_quote="шахеди", count=2, count_quote="2 шахеди", place_id="c1",
                     place_quote="на Бровари", relation="heading_to", from_side="n", from_quote="з півночі")],
      "uncertain": None}),
    ("@kyiv_airdef (oblast: Kyiv city)", ["[21:02] Дрон над Троєщиною"], "Збито ціль над Оболонню",
     "c1 | Оболонь | м. Київ\nc2 | Троєщина | м. Київ\no31 | м. Київ",
     {"targets": [_t(kind="unknown", status="shot_down", status_quote="Збито", place_id="c1",
                     place_quote="над Оболонню", relation="at")], "uncertain": None}),
    ("@kpszsu (oblast: —)", [], "БпЛА на півночі від Миколаєва, курс на захід.",
     "c1 | Миколаїв | Миколаївська область\no17 | Миколаївська область",
     {"targets": [_t(kind="drone", kind_quote="БпЛА", place_id="c1", place_quote="на півночі від Миколаєва",
                     relation="side_of", side="n", heading="w", heading_quote="курс на захід")], "uncertain": None}),
    ("@monitor_ukr (oblast: —)", [], "Реактивний на Київщині, висота 2200. Ще один шахед над Києвом",
     "c1 | Київ | м. Київ\no14 | Київська область\no31 | м. Київ",
     {"targets": [_t(kind="jet_drone", kind_quote="Реактивний", place_id="o14", place_quote="на Київщині",
                     relation="in_oblast", altitude_m=2200, altitude_quote="висота 2200"),
                  _t(kind="shahed", kind_quote="шахед", count=1, count_quote="один шахед", place_id="c1",
                     place_quote="над Києвом", relation="at")], "uncertain": None}),
    ("@kyivoda (oblast: Kyiv oblast)", [], "Відбій повітряної тривоги в Київській області.", "o14 | Київська область",
     {"targets": [], "uncertain": None}),
]


def user_message(channel_line, previous, text, cand_lines):
    prev = "\n".join(f"- {p}" for p in previous) if previous else "(none)"
    return (f"CHANNEL: {channel_line}\nPREVIOUS POSTS (oldest first, context only):\n{prev}\n\n"
            f"POST:\n{text}\n\nCANDIDATES (id | name | oblast):\n{cand_lines or '(none)'}")


def messages(channel_line, previous, text, cand_lines, cache=False):
    """The whole conversation: the fixed part first (rules, then the examples), the post last — the order lets the
    provider reuse the unchanged beginning from one post to the next (prompt caching; for Anthropic's models the end
    of that part is marked, `cache`)."""
    out = [{"role": "system", "content": SYSTEM}]
    for ch, prev, post, cands, ans in EXAMPLES:
        out.append({"role": "user", "content": user_message(ch, prev, post, cands)})
        out.append({"role": "assistant", "content": json.dumps(ans, ensure_ascii=False)})
    if cache:
        out[-1]["content"] = [{"type": "text", "text": out[-1]["content"], "cache_control": {"type": "ephemeral"}}]
    out.append({"role": "user", "content": user_message(channel_line, previous, text, cand_lines)})
    return out


# ---- the candidates: the places this server knows that the post may be naming -------------------------------------
def candidates(geo, text, channel, home=None, near=(), oblast_names=None):
    """[(id, key, label)] — the gazetteer's places the post's words match (core gazetteer, the regional villages of
    the oblasts in play), and those oblasts. `key` is the gazetteer key (geo.PLACES) or "o<uid>" for an oblast."""
    oblast_names = oblast_names or {}
    try:
        t = geo.prepare(text, channel).lower()
    except Exception:
        t = text.lower()
    uids = [u for u in [home, *near] if u and u not in ("ua",)]
    try:
        uids += [u for _, u, _, _ in geo._find_oblasts_all(t)]
    except Exception:
        pass
    names = []
    try:
        names += [n for _, _, n in geo._find_places(t, home)]
    except Exception:
        pass
    for u in dict.fromkeys(uids):
        if u == "31":
            continue
        try:
            for _, _, keys in geo._find_regional(t, u):
                names += keys
        except Exception:
            pass
    out, seen = [], set()
    for n in names:
        if n in seen or len(out) >= MAX_CANDIDATES:
            continue
        seen.add(n)
        p = geo.PLACES.get(n)
        if not p:
            continue
        out.append((f"c{len(out) + 1}", n, f"{n} | {oblast_names.get(p[2], p[2])}"))
    for u in dict.fromkeys(uids):
        if u in oblast_names and f"o{u}" not in seen:
            seen.add(f"o{u}")
            out.append((f"o{u}", f"o{u}", oblast_names[u]))
    return out


# ---- checking the reading against the post -------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower().replace("’", "'").replace("ʼ", "'").replace("`", "'")).strip()


def validate(out, text, cands):
    """(targets, dropped) — the model's targets with every fact the post does not bear out removed: a quote that is
    not in the post, a place that is not a candidate, a number its quote does not hold."""
    nt = _norm(text)
    ids = {c[0]: c for c in cands}
    ok = lambda q: bool(q) and len(_norm(q)) >= 2 and _norm(q) in nt      # noqa: E731
    dropped, res = 0, []
    for raw in (out or {}).get("targets") or []:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        t = {k: raw.get(k) for k in TARGET["properties"]}
        if t["kind"] not in KINDS or (t["kind"] != "unknown" and not ok(t["kind_quote"])):
            dropped += t["kind"] != "unknown"
            t["kind"], t["kind_quote"] = "unknown", None
        if t["status"] not in STATUSES or (t["status"] != "in_flight" and not ok(t["status_quote"])):
            dropped += t["status"] not in ("in_flight", None)
            t["status"], t["status_quote"] = "in_flight", None
        if t["count"] is not None and not (isinstance(t["count"], int) and 0 < t["count"] < 500 and ok(t["count_quote"])
                                           and re.search(r"\d|од[иі]н|два|дві|три|чотири|п.ять", _norm(t["count_quote"]))):
            dropped += 1
            t["count"], t["count_quote"] = None, None
        if t["place_id"] is not None and not (t["place_id"] in ids and ok(t["place_quote"])):
            dropped += 1
            t["place_id"] = None
        if t["place_id"] is None or t["relation"] not in RELATIONS:
            t["relation"] = "none"
        if t["relation"] != "side_of":
            t["side"], t["distance_km"] = None, None
        if t["side"] not in DIRS:
            t["side"] = None
        if t["distance_km"] is not None and not (isinstance(t["distance_km"], int) and str(t["distance_km"]) in nt):
            dropped += 1
            t["distance_km"] = None
        for f, q in (("from_side", "from_quote"), ("heading", "heading_quote")):
            if t[f] is not None and not (t[f] in DIRS and ok(t[q])):
                dropped += 1
                t[f], t[q] = None, None
        if t["altitude_m"] is not None and not (isinstance(t["altitude_m"], int) and 30 <= t["altitude_m"] <= 20000
                                                and ok(t["altitude_quote"]) and re.search(r"\d", t["altitude_quote"])):
            dropped += 1
            t["altitude_m"], t["altitude_quote"] = None, None
        if t["kind"] == "unknown" and t["place_id"] is None and t["status"] == "in_flight":
            dropped += 1
            continue            # nothing the post bears out is left of it
        t["place"] = ids[t["place_id"]][1] if t["place_id"] else None
        res.append(t)
    return res, dropped


# ---- the two readings side by side ---------------------------------------------------------------------------------
def _canon(w):
    """Kyiv itself is the city's region to the rules (a post naming no place in it, geo._city_settle)."""
    return "o31" if w == "Київ" else w


def _where_rules(m):
    p = m.get("place") or ""
    if p == "область":
        return "o" + str(m.get("oblast_uid") or "")
    return _canon(p[2:] if p.startswith("→ ") else p)


def summarise_rules(ms):
    return [{"where": _where_rules(m), "type": m.get("type"), "status": m.get("status"),
             "approach": bool(m.get("approach"))} for m in ms or []]


def summarise_ai(targets, places=None):
    """`places`: the gazetteer (geo.PLACES) — a side of a town ("north of Mykolaiv") may be read by the rules as the
    town's oblast (geo._rel_settle): `alt` is that oblast."""
    out = []
    for t in targets:
        w = _canon(t.get("place") or "")
        p = (places or {}).get(t.get("place") or "")
        out.append({"where": w, "kind": t["kind"], "status": STATUS_OF.get(t["status"]),
                    "approach": t["relation"] == "heading_to", "relation": t["relation"],
                    "alt": f"o{p[2]}" if p and t["relation"] == "side_of" else None})
    return out


def compare(rules, ai):
    """One word for how the two readings of a post relate: agree, place, kind, status, ai_only, rules_only, none.
    Only the places both name decide `place`; a weapon or a status one of them leaves unsaid is no disagreement."""
    if not rules and not ai:
        return "none"
    if not ai:
        return "rules_only"
    if not rules:
        return "ai_only"
    rw = {r["where"] for r in rules if r["where"]}
    aw = []
    for a in ai:
        w = a["where"]
        if w and w not in rw and a.get("alt") in rw:
            w = a["alt"]
        aw.append(w)
    if rw != {w for w in aw if w}:
        return "place"
    for a, w in zip(ai, aw):
        rs = [r for r in rules if r["where"] == w]
        known = {r["type"] for r in rs} - {"unknown", None}
        if a["kind"] in KIND_OK and known and not (KIND_OK[a["kind"]] & known):
            return "kind"
    for w in {w for w in aw if w}:
        r_st = {r["status"] for r in rules if r["where"] == w}
        a_st = {a["status"] for a, x in zip(ai, aw) if x == w}
        if r_st != a_st:
            return "status"
    return "agree"


# ---- the reader --------------------------------------------------------------------------------------------------
class AIReader(threading.Thread):
    """Reads the queued posts one at a time, within the month's budget (`ai_reader_monthly_usd`, counted from what
    OpenRouter says each call cost) and PER_HOUR posts an hour. Paused 10 minutes when OpenRouter refuses the key or
    the credits, a minute when it says to slow down."""

    def __init__(self, cfg, store, geo, rules_fn, oblast_names, previous_fn=None, log=print):
        super().__init__(daemon=True, name="ai-reader")
        self.cfg, self.store, self.geo, self.rules_fn = cfg, store, geo, rules_fn
        self.oblast_names, self.previous_fn, self.log = oblast_names, previous_fn, log
        self.q = deque(maxlen=400)
        self.cond = threading.Condition()
        self.lock = threading.Lock()
        self.down_until = 0.0
        self.last_error = None
        self.hour, self.n_hour = None, 0
        self.month, self.spent = None, 0.0
        self.skipped = {}           # posts not read since the start, by why: paused, budget, rate

    def key(self):
        return self.cfg.get("openrouter_key")

    def model(self):
        return self.cfg.get("ai_reader_model") or DEFAULT_MODEL

    def cap(self):
        try:
            return max(0.0, float(self.cfg.get("ai_reader_monthly_usd", 10)))
        except (TypeError, ValueError):
            return 0.0

    def enabled(self):
        return bool(self.key()) and self.cap() > 0 and self.cfg.get("ai_reader", True) is not False

    def _roll(self):
        m = datetime.now(timezone.utc).strftime("%Y-%m")
        if m != self.month:
            self.month = m
            try:
                self.spent = float(self.store.kv_get(f"ai_usd:{m}") or 0)
            except (TypeError, ValueError):
                self.spent = 0.0

    # -- feeding it ---------------------------------------------------------------------------------------------
    # a stored post is read when the tagger saw a target or a place in it…
    WANT = {"drones", "ballistic_missiles", "banderol_missiles", "cruise_missiles", "tactic_aircraft_activity",
            "guided_aerial_bombs", "impact", "air_defense", "unknown", "geo", "kyiv", "region"}
    # …and a post the server set aside as not about the sky, when it names a place and is short — a tracker's line
    # ("Ціль на Бровари"), the misses the reader is there to find; a long one is news
    PLACE_TAGS = {"geo", "kyiv", "region"}
    SHORT = 300

    def wants(self, post, stored=True):
        tags = set(post.get("tags") or ())
        if tags & {"trial", "af_summary", "retract"}:
            return False
        if stored:
            return bool(tags & self.WANT)
        return bool(tags & self.PLACE_TAGS) and len(post.get("text") or "") <= self.SHORT

    def add(self, post, near=(), home=None, stored=True):
        """A new post of a channel on the map (never one on trial: the server does not draw those either), with the
        oblasts the channel named in its last posts (`near`) and the channel's own (`home`)."""
        if not self.enabled() or not self.wants(post, stored):
            return
        with self.cond:
            self.q.append((post, tuple(near or ()), home, stored))
            self.cond.notify()

    def run(self):
        while True:
            with self.cond:
                while not self.q:
                    self.cond.wait(30)
                item = self.q.popleft()
            if not self.enabled():
                continue
            try:
                why = self.read(*item)
                if why in ("paused", "budget", "rate"):
                    self.skipped[why] = self.skipped.get(why, 0) + 1
            except Exception as e:              # never the reader's death: the next post is read
                self.last_error = f"{type(e).__name__}"
                self.log("ai reader:", type(e).__name__, str(e)[:120])

    # -- one post -----------------------------------------------------------------------------------------------
    def _allowed(self):
        if not self.enabled():
            return "off"
        now = time.time()
        if now < self.down_until:
            return "paused"
        with self.lock:
            self._roll()
            if self.spent >= self.cap():
                return "budget"
            hr = int(now // 3600)
            if hr != self.hour:
                self.hour, self.n_hour = hr, 0
            if self.n_hour >= PER_HOUR:
                return "rate"
            self.n_hour += 1
        return None

    def read(self, post, near=(), home=None, stored=True):
        why = self._allowed()
        if why:
            return why
        ch, text = post["channel"], mask(post["text"])
        home = home if home not in ("", "ua") else None
        cands = candidates(self.geo, text, ch, home, near, self.oblast_names)
        prev = [mask(p) for p in (self.previous_fn(ch, post["ts"]) if self.previous_fn else [])]
        line = f"@{ch} (oblast: {self.oblast_names.get(home, '—') if home else '—'})"
        msgs = messages(line, prev, text, "\n".join(f"{i} | {lab}" for i, _, lab in cands), cache=self.model().startswith("anthropic/"))
        t0 = time.time()
        res = self.call(msgs)
        ms = int((time.time() - t0) * 1000)
        rules = summarise_rules(self.rules_fn(ch, text, list(near)))
        if res.get("error"):
            self._save(post, text, stored, ms, res, None, rules, 0, "error")
            return "error"
        targets, dropped = validate(res["out"], text, cands)
        ai = summarise_ai(targets, getattr(self.geo, "PLACES", None))
        verdict = compare(rules, ai)
        self._save(post, text, stored, ms, res, {"targets": targets, "uncertain": (res["out"] or {}).get("uncertain")},
                   rules, dropped, verdict)
        return verdict

    def call(self, msgs):
        """{"out": dict, "cost", "tok_in", "tok_out"} or {"error": "..."} — the one request to OpenRouter."""
        # 1.50.1: only parameters every model that takes a JSON schema accepts. With require_parameters, one the model
        # does not take (claude-haiku-5.5 takes no `temperature`) leaves no provider at all: "HTTP 404: No endpoints".
        body = {"model": self.model(), "max_tokens": 1200, "messages": msgs,
                "response_format": {"type": "json_schema", "json_schema": {"name": "heimdall_reading", "strict": True,
                                                                             "schema": SCHEMA}},
                "provider": {"require_parameters": True}, "usage": {"include": True}}
        req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={
            "Authorization": "Bearer " + self.key(), "Content-Type": "application/json", "X-Title": "Heimdall (shadow reader)"})
        try:
            ctx = getattr(self, "ssl_ctx", None)
            with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                msg = (json.loads(e.read() or b"{}").get("error") or {}).get("message") or ""
            except Exception:
                pass
            err = f"HTTP {e.code}" + (f": {msg[:140]}" if msg else "")
            if e.code in (401, 402, 403, 404):          # the key, the credit, or a model / parameter nobody serves
                self.down_until = time.time() + 600
            elif e.code == 429:
                self.down_until = time.time() + 60
            self.last_error = err
            self.log("ai reader:", err)
            return {"error": err}
        except Exception as e:
            self.last_error = type(e).__name__
            return {"error": type(e).__name__}
        usage = data.get("usage") or {}
        cost = float(usage.get("cost") or 0)
        with self.lock:
            self._roll()
            self.spent += cost
            try:
                self.store.kv_set(f"ai_usd:{self.month}", f"{self.spent:.6f}")
            except Exception:
                pass
        try:
            out = json.loads(data["choices"][0]["message"]["content"])
        except Exception:
            self.last_error = "not JSON"
            return {"error": "not JSON", "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens")}
        self.last_error = None
        return {"out": out, "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens"),
                "model": data.get("model") or self.model()}

    def _save(self, post, text, stored, ms, res, ai, rules, dropped, verdict):
        try:
            self.store.ai_save({"post_id": post["post_id"], "ts": post["ts"], "channel": post["channel"], "text": text,
                                "stored": 1 if stored else 0,
                                "model": res.get("model") or self.model(), "prompt_v": PROMPT_VERSION, "ms": ms,
                                "tok_in": res.get("tok_in"), "tok_out": res.get("tok_out"), "cost": res.get("cost") or 0,
                                "verdict": verdict, "rules": rules, "ai": ai, "dropped": dropped, "error": res.get("error")})
        except Exception as e:
            self.log("ai reader: not saved:", type(e).__name__)

    def stats(self):
        with self.lock:
            self._roll()
            spent = self.spent
        counts = {}
        try:
            counts = self.store.ai_counts(self.month)
        except Exception:
            pass
        return {"key": bool(self.key()), "enabled": self.enabled(), "model": self.model(), "prompt_v": PROMPT_VERSION,
                "month": self.month, "usd_month": round(spent, 4), "cap_usd": self.cap(), "queued": len(self.q),
                "paused": time.time() < self.down_until, "last_error": self.last_error, "skipped": dict(self.skipped),
                **counts}
