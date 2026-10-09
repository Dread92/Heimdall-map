"""1.50: a second reader of the channels' posts — a language model through OpenRouter.

It never places, moves or removes a mark, and never touches the alerts, the feed or a push. It reads the same posts the
rules read, its reading is checked against the post (every fact must quote the post's own words; every place must be
one this server offered it from its gazetteer) and compared with the rules' reading, and the dashboard shows where the
two disagree: posts the rules missed, places or weapons they read differently — so the rules can be fixed
(deterministic, free, instant). 1.51: with the dashboard's switch on (`ai_live`, the kill switch), the facts it
quoted that the rules did not read — where a target comes from, its height, its speed — fill the TARGET TAGS
(N-07 ×2 · 2200 m), marked as read by the AI. docs/TECHNICAL.md §7.7, docs/SAFETY.md.

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
from collections import OrderedDict, deque
from datetime import datetime, timezone

PROMPT_VERSION = "3"     # 1.51: the parser's reading and the map in the prompt; vertical state, same_as
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

SYSTEM = """You are the second reader of Heimdall, a public air-threat map of Ukraine. People decide whether to take cover from what is drawn. A deterministic parser has already read the post (PARSER READING). Your job is to cross-check it against the post, the channel's previous posts and the targets already ON THE MAP from every channel: confirm it, correct it, and above all ADD the targets it missed. A target missed is worse than a duplicate: when the post names a place for a target, even in loose or unusual words, give it. But you never invent: every fact quotes the post, every place is one the post names, from CANDIDATES.

Rules:
1. Never infer. A fact the post does not state is left empty: "" for a text, 0 for a number, "none" for a direction, an origin or a vertical state, "unknown" for the weapon. A likely guess is still a guess.
2. Quote. Every fact you give carries the exact words of the post that state it, copied character for character into its *_quote field. If you cannot quote it, leave it empty.
3. Places only from CANDIDATES, by their id (c1, c2…, or o<number> for an oblast). Never output coordinates. A place the post names that is not in CANDIDATES: place_id "", its words in place_quote. Several candidates of the same name: the one in the CHANNEL'S OBLAST or in the OBLASTS ITS LAST POSTS NAMED — a regional tracker reports its own oblast and the one next to it.
4. The relation to the place is what the words say:
   - "на X", "курсом на X", "в напрямку X", "у бік X" = heading_to X — the target is NOT at X;
   - "над X", "в районі X", "біля X" said of where it is now, or X alone in a tracker's line = at X; "поблизу X", "неподалік X" = near X;
   - "з X", "від X", "із X" (a Ukrainian place) = from X;
   - "північніше X", "на півночі від X", "за 20 км на північ від X" = side_of X (side n; distance_km 20 only if written);
   - an oblast only ("на Київщині", "Сумщина", "в Черкаській області") = in_oblast, with the oblast's o-id.
5. A city named with no place in it ("над Києвом", "околиці Києва", "правий берег Києва") is the city itself (relation at, the city's id). Never pick a district or a street the post does not name.
6. Weapons, by the post's words: "шахед", "герань", "мопед", "ударний БпЛА" = shahed; "реактивний", "реактив", "реактивний БпЛА/дрон", "Бандерол" = jet_drone (Banderol is a jet drone, never a cruise missile); "БпЛА", "дрон" of no stated kind = drone; "крилата ракета", "Калібр", "Х-101", "Х-55" = cruise_missile; "балістика", "балістична", "Іскандер", "КН-23" = ballistic_missile; "КАБ", "керовані авіабомби" = guided_bomb; "тактична авіація", "МіГ", "Су-34" = aircraft; nothing said ("ціль", "увага") = unknown.
7. Status only when stated: "збито", "знищено", "мінус", "мінуснули", "приземлили" (of a target) = shot_down; "вибух", "вибухи", "приліт", "влучання" = impact; "втрачено контакт", "зник", "не фіксується" = lost; otherwise in_flight.
8. One entry per target or group, in the order of the post. A count only if written ("2 шахеди", "група з 5", "×3"; "кілька", "група" alone are not a number).
9. Origin: where the post says the target comes from, outside the places above — a direction ("з півночі" = n, "з південного сходу" = se) or a country or area ("з Білорусі", "з території РБ" = belarus; "з Росії", "з Брянщини", "з Курщини", "з боку Бєлгорода" = russia; "з моря", "з акваторії Чорного моря" = sea; "з Криму" = crimea; "з окупованих територій", "з ТОТ" = occupied). A Ukrainian oblast or town it comes from is relation from that place, never an origin.
10. Heading only when the post gives a course as a direction ("курс на захід" = w). A town it flies to is heading_to that town, not a heading.
11. Height, vertical state and speed matter most to the people under a target: give them whenever the post states them, and only for the target they are written for (the same line or paragraph; a height on a line of its own after several targets belongs to the target just above it). Altitude in metres ("висота 2200", "на 1,5 км" = 1500); vertical: "знижується", "пікірує", "скидає висоту" = descending; "набирає висоту" = climbing; "низько", "на малій висоті" = low; "високо", "на великій висоті" = high; speed ("швидкість 180 км/год" = 180).
12. Nothing about aerial targets — an alert starting or ending alone ("Відбій"), news, a fundraiser, the Air Force's morning totals: targets [].
13. PREVIOUS POSTS are context only. "Далі на X" continues the last target named there; but never copy a fact from them into this post's entry unless this post states it.
14. ON THE MAP NOW lists the targets other posts placed, by their tag (S-01, ?-04…). If one of this post's targets is one of them — the same weapon reported again near the same place, or "Далі на X" continuing it — put its tag in same_as; otherwise "". Such a target is still listed: same_as says which it is.
15. The PARSER READING may be wrong or miss targets. Never copy it; read the post yourself. Where it missed a target the post names, add it; where it misread one, your reading — by the post's words — is the one to give.
16. Unsure? Say so in "uncertain" in one short English sentence ("" when sure), and still give only what is stated.

Answer with the JSON object only — no other text, no code fence."""

ORIGINS = ["belarus", "russia", "sea", "crimea", "occupied"] + DIRS
# the facts a target can carry, and how each is written on the wire when the post does not state it. No field is
# nullable: a nullable field is a "union type" to Anthropic's structured outputs, which take at most 16 of them in
# a schema — and a provider that cannot compile the schema answers "HTTP 400: Provider returned error" (1.50.2).
TEXTS = ("kind_quote", "count_quote", "status_quote", "place_id", "place_quote", "origin_quote", "heading_quote",
         "altitude_quote", "vertical_quote", "speed_quote", "same_as")
VERTICALS = ["descending", "climbing", "low", "high"]
INTS = ("count", "distance_km", "altitude_m", "speed_kmh")
_S, _I = {"type": "string"}, {"type": "integer"}
_DIR = {"type": "string", "enum": DIRS + ["none"]}
TARGET = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "kind": {"type": "string", "enum": KINDS}, "kind_quote": _S,
        "count": _I, "count_quote": _S,
        "status": {"type": "string", "enum": STATUSES}, "status_quote": _S,
        "place_id": _S, "place_quote": _S,
        "relation": {"type": "string", "enum": RELATIONS},
        "side": _DIR, "distance_km": _I,
        "origin": {"type": "string", "enum": ORIGINS + ["none"]}, "origin_quote": _S,
        "heading": _DIR, "heading_quote": _S,
        "altitude_m": _I, "altitude_quote": _S,
        "vertical": {"type": "string", "enum": VERTICALS + ["none"]}, "vertical_quote": _S,
        "speed_kmh": _I, "speed_quote": _S,
        "same_as": _S,
    },
}
TARGET["required"] = list(TARGET["properties"])
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"targets": {"type": "array", "items": TARGET}, "uncertain": _S},
          "required": ["targets", "uncertain"]}


def wire(ans):
    """A reading as the model writes it: "" / 0 / "none" for what is not stated."""
    def one(t):
        o = {}
        for k in TARGET["properties"]:
            v = t.get(k)
            o[k] = ("" if k in TEXTS else 0 if k in INTS else "none" if k in ("side", "heading", "origin", "vertical") else v) if v is None else v
        return o
    return {"targets": [one(t) for t in ans.get("targets") or []], "uncertain": ans.get("uncertain") or ""}


def unwire(t):
    """…and back: what is not stated is None."""
    o = {k: t.get(k) for k in TARGET["properties"]}
    for k in TEXTS:
        if not isinstance(o[k], str) or not o[k].strip():
            o[k] = None
    for k in INTS:
        if o[k] in (0, None) or isinstance(o[k], bool):
            o[k] = None
    for k in ("side", "heading", "origin", "vertical"):
        if o[k] in ("none", ""):
            o[k] = None
    return o


def _t(**kw):
    """One target of an example, the fields not given unstated."""
    base = {k: None for k in TARGET["properties"]}
    base.update(kind="unknown", status="in_flight", relation="none")
    base.update(kw)
    return base


def channel_block(ch, home=None, near=()):
    """Who is speaking, and about which oblast (1.51: "the AI should know which oblast it is reading about — it is
    crucial"): the channel's own oblast, and the oblasts its posts of the last 30 minutes named."""
    own = (f"{home} — a regional tracker: a place it names alone is in or near this oblast" if home
           else "none — a country-wide channel")
    nb = ", ".join(near) if near else "—"
    return f"@{ch}\nCHANNEL'S OBLAST: {own}\nOBLASTS ITS LAST POSTS NAMED (30 min): {nb}"


# Worked examples, given as earlier turns of the conversation: each is a post, its candidates, the right reading.
EXAMPLES = [
    # (channel line, previous posts, post, candidates, parser reading, on the map now, the right reading)
    (channel_block("kpszsu"), [], "2 шахеди з півночі на Бровари",
     "c1 | Бровари | Київська область\no14 | Київська область", ["drone ×2 · heading to Бровари · from the n"], [],
     {"targets": [_t(kind="shahed", kind_quote="шахеди", count=2, count_quote="2 шахеди", place_id="c1",
                     place_quote="на Бровари", relation="heading_to", origin="n", origin_quote="з півночі")],
      "uncertain": None}),
    (channel_block("kyiv_airdef", "м. Київ", ["м. Київ"]), ["[21:02] Дрон над Троєщиною"], "Збито ціль над Оболонню",
     "c1 | Оболонь | м. Київ\nc2 | Троєщина | м. Київ\no31 | м. Київ", ["unknown · at Оболонь · shot down"],
     ["?-04 · drone · at Троєщина · @kyiv_airdef 21:02"],
     {"targets": [_t(kind="unknown", status="shot_down", status_quote="Збито", place_id="c1",
                     place_quote="над Оболонню", relation="at", same_as="?-04")], "uncertain": None}),
    (channel_block("kpszsu", None, ["Миколаївська область"]), [], "БпЛА на півночі від Миколаєва, курс на захід.",
     "c1 | Миколаїв | Миколаївська область\no17 | Миколаївська область", ["drone · in Миколаївська область"], [],
     {"targets": [_t(kind="drone", kind_quote="БпЛА", place_id="c1", place_quote="на півночі від Миколаєва",
                     relation="side_of", side="n", heading="w", heading_quote="курс на захід")], "uncertain": None}),
    (channel_block("monitor_ukr"), [], "Реактивний на Київщині, висота 2200. Ще один шахед над Києвом",
     "c1 | Київ | м. Київ\no14 | Київська область\no31 | м. Київ", ["drone · at Київ"], [],
     {"targets": [_t(kind="jet_drone", kind_quote="Реактивний", place_id="o14", place_quote="на Київщині",
                     relation="in_oblast", altitude_m=2200, altitude_quote="висота 2200"),
                  _t(kind="shahed", kind_quote="шахед", count=1, count_quote="один шахед", place_id="c1",
                     place_quote="над Києвом", relation="at")], "uncertain": None}),
    (channel_block("monitor_ukr"), [], "Група шахедів з території Білорусі на Житомирщину.\n\n1 реактив над Коростенем\nшвидкість 400 км/год, висота 3 км",
     "c1 | Коростень | Житомирська область\no10 | Житомирська область",
     ["drone ×3 · heading to Житомирська область · from belarus", "drone · at Коростень · 3000 m"], [],
     {"targets": [_t(kind="shahed", kind_quote="шахедів", place_id="o10", place_quote="на Житомирщину",
                     relation="heading_to", origin="belarus", origin_quote="з території Білорусі"),
                  _t(kind="jet_drone", kind_quote="реактив", count=1, count_quote="1 реактив", place_id="c1",
                     place_quote="над Коростенем", relation="at", speed_kmh=400, speed_quote="швидкість 400 км/год",
                     altitude_m=3000, altitude_quote="висота 3 км")], "uncertain": None}),
    # a regional tracker's bare name: the candidate in its oblast, not the namesake elsewhere
    (channel_block("rivne_radar", "Рівненська область", ["Рівненська область", "Житомирська область"]),
     ["[03:12] Шахед з Житомирщини на Сарни"], "Тепер на Висоцьк",
     "c1 | Висоцьк | Рівненська область\nc2 | Висоцьк (Житомирський р-н) | Житомирська область\no5 | Рівненська область",
     [], [],
     {"targets": [_t(kind="unknown", place_id="c1", place_quote="на Висоцьк", relation="heading_to")],
      "uncertain": "The weapon is the Shahed of the previous post, but this post does not name it."}),
    # the parser read nothing: the post names a place for a target in a tracker's loose words — it is given
    (channel_block("kyiv_airdef", "м. Київ", ["м. Київ"]), ["[22:10] Шахед курсом на Бортничі"], "Ціль заходить на Бортничі, низько, знижується",
     "c1 | Бортничі | м. Київ\no31 | м. Київ", [], ["S-07 · Shahed · heading to Бортничі · @kyiv_airdef 22:10"],
     {"targets": [_t(kind="unknown", place_id="c1", place_quote="на Бортничі", relation="heading_to",
                     vertical="descending", vertical_quote="знижується", same_as="S-07")], "uncertain": None}),
    (channel_block("kyivoda", "Київська область"), [], "Відбій повітряної тривоги в Київській області.", "o14 | Київська область", [], [],
     {"targets": [], "uncertain": None}),
]


def user_message(channel_line, previous, text, cand_lines, parser=(), on_map=()):
    prev = "\n".join(f"- {p}" for p in previous) if previous else "(none)"
    pr = "\n".join(f"- {p}" for p in parser) if parser else "(nothing)"
    om = "\n".join(f"- {p}" for p in on_map) if on_map else "(none)"
    return (f"CHANNEL: {channel_line}\nPREVIOUS POSTS (oldest first, context only):\n{prev}\n\n"
            f"POST:\n{text}\n\nCANDIDATES (id | name | oblast):\n{cand_lines or '(none)'}\n\n"
            f"PARSER READING (Heimdall's rules, for this post — may be wrong or incomplete):\n{pr}\n\n"
            f"ON THE MAP NOW (targets other posts placed, every channel, the last 30 minutes):\n{om}")


def messages(channel_line, previous, text, cand_lines, cache=False, parser=(), on_map=()):
    """The whole conversation: the fixed part first (rules, then the examples), the post last — the order lets the
    provider reuse the unchanged beginning from one post to the next (prompt caching; for Anthropic's models the end
    of that part is marked, `cache`)."""
    out = [{"role": "system", "content": SYSTEM}]
    for ch, prev, post, cands, pr, om, ans in EXAMPLES:
        out.append({"role": "user", "content": user_message(ch, prev, post, cands, pr, om)})
        out.append({"role": "assistant", "content": json.dumps(wire(ans), ensure_ascii=False)})
    if cache:
        out[-1]["content"] = [{"type": "text", "text": out[-1]["content"], "cache_control": {"type": "ephemeral"}}]
    out.append({"role": "user", "content": user_message(channel_line, previous, text, cand_lines, parser, on_map)})
    return out


_KW = {"drones": "drone", "banderol_missiles": "jet drone (Banderol)", "cruise_missiles": "cruise missile",
       "ballistic_missiles": "ballistic missile", "guided_aerial_bombs": "guided bomb", "tactic_aircraft_activity": "aircraft",
       "unknown": "unknown"}


def parser_lines(ms):
    """The rules' reading of the post, one line a mark, in the words the model is asked to use."""
    out = []
    for m in ms or []:
        p = m.get("place") or ""
        where = (f"in oblast {m.get('oblast_uid')}" if p == "область" else
                 f"heading to {p[2:]}" if p.startswith("→ ") else f"at {p}") if p else "no place"
        bits = [_KW.get(m.get("type"), m.get("type") or "?") + (f" ×{m['count']}" if (m.get("count") or 1) > 1 else ""), where]
        if (m.get("origin") or {}).get("o"):
            bits.append(f"from {m['origin']['o']}")
        if m.get("status"):
            bits.append({"down": "shot down", "impact": "impact", "lost": "lost"}.get(m["status"], m["status"]))
        if (m.get("alt") or {}).get("m"):
            bits.append(f"{m['alt']['m']} m")
        if (m.get("alt") or {}).get("state"):
            bits.append(m["alt"]["state"])
        out.append(" · ".join(bits))
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


_DIR_WORD = re.compile(r"півн|півд|схід|сход|зах|север|юг|восток|запад")
ORIGIN_WORDS = {
    "belarus": re.compile(r"білорус|беларус|\bрб\b|лукашенк|гомел|мозир|мозыр"),
    "russia": re.compile(r"\bрос|\bрф\b|брянщ|брянськ|брянск|курщ|курськ|курск|бєлгород|білгород|белгород|орловщ|смоленщ|"
                         r"воронеж|ростов|кубан|краснодар|таганрог|єйськ|ейск|приморсько|міллеров|шаталов|енгельс|саратов|моздок"),
    "sea": re.compile(r"\bмор[ея]|акваторі|чорного моря|черного моря"),
    "crimea": re.compile(r"крим|джанко|севастоп|чорноморськ"),
    "occupied": re.compile(r"окупов|\bтот\b|тимчасово"),
}


_VERT_WORD = re.compile(r"зниж|пікір|скида|набира|підійма|піднима|низьк|низько|мал\w*\s+висот|високо|велик\w*\s+висот|ешелон|"
                        r"снижа|пикир|высоко|низко")


def validate(out, text, cands, tags=()):
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
        t = unwire(raw)
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
        if t["heading"] is not None and not (t["heading"] in DIRS and ok(t["heading_quote"])):
            dropped += 1
            t["heading"], t["heading_quote"] = None, None
        # an origin is a direction or a country / area, in words that say so — never a Ukrainian oblast or town
        # ("з Чернігівщини" is relation from that place): its quote must hold a word of its class
        if t["origin"] is not None and not (
                t["origin"] in ORIGINS and ok(t["origin_quote"])
                and (_DIR_WORD if t["origin"] in DIRS else ORIGIN_WORDS[t["origin"]]).search(_norm(t["origin_quote"]))):
            dropped += 1
            t["origin"], t["origin_quote"] = None, None
        if t["altitude_m"] is not None and not (isinstance(t["altitude_m"], int) and 30 <= t["altitude_m"] <= 20000
                                                and ok(t["altitude_quote"]) and re.search(r"\d", t["altitude_quote"])):
            dropped += 1
            t["altitude_m"], t["altitude_quote"] = None, None
        if t["vertical"] is not None and not (t["vertical"] in VERTICALS and ok(t["vertical_quote"])
                                              and _VERT_WORD.search(_norm(t["vertical_quote"]))):
            dropped += 1
            t["vertical"], t["vertical_quote"] = None, None
        if t["same_as"] is not None and t["same_as"] not in tags:
            dropped += 1                        # only a tag it was shown
            t["same_as"] = None
        if t["speed_kmh"] is not None and not (isinstance(t["speed_kmh"], int) and 30 <= t["speed_kmh"] <= 5000
                                               and ok(t["speed_quote"]) and re.search(r"\d", t["speed_quote"])
                                               and re.search(r"км|km", _norm(t["speed_quote"]))):
            dropped += 1
            t["speed_kmh"], t["speed_quote"] = None, None
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


def match(targets, wheres, alone):
    """1.51: the AI target that is a given track's — the one at one of its places (`wheres`, canonical), or the only
    target of a post the rules also read as one target (`alone`). None rather than a guess."""
    if alone and len(targets) == 1:
        return targets[0]
    for t in targets:
        w = _canon(t.get("place") or "")
        if w and w in wheres:
            return t
    return None


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


def plain(msgs):
    """The same conversation without the caching marks: plain text messages only."""
    return [dict(m, content=m["content"][0]["text"]) if isinstance(m["content"], list) else m for m in msgs]


def _json_of(content):
    """The answer's JSON object — also when a model asked by the prompt alone wraps it in a code fence or a sentence."""
    if isinstance(content, (dict, list)):
        return content
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        i, j = content.find("{"), content.rfind("}")
        if i < 0 or j <= i:
            raise
        return json.loads(content[i:j + 1])


def _why(e):
    """What OpenRouter, and the provider behind it, said about a refused request. "Provider returned error" alone
    says nothing: the provider's own words are in error.metadata.raw (1.50.2)."""
    try:
        err = json.loads(e.read() or b"{}").get("error") or {}
    except Exception:
        return ""
    msg = str(err.get("message") or "")[:140]
    meta = err.get("metadata") or {}
    raw = meta.get("raw")
    if raw:
        try:
            r = json.loads(raw) if isinstance(raw, str) else raw
            raw = ((r.get("error") or {}).get("message") if isinstance(r.get("error"), dict) else r.get("error")) or r.get("message") or raw
        except Exception:
            pass
        msg += f" — {meta.get('provider_name') or 'provider'}: {str(raw)[:240]}"
    return msg


# ---- the reader --------------------------------------------------------------------------------------------------
class AIReader(threading.Thread):
    """Reads the queued posts one at a time, within the month's budget (`ai_reader_monthly_usd`, counted from what
    OpenRouter says each call cost) and PER_HOUR posts an hour. Paused 10 minutes when OpenRouter refuses the key or
    the credits, a minute when it says to slow down."""

    def __init__(self, cfg, store, geo, rules_fn, oblast_names, previous_fn=None, log=print, context_fn=None):
        super().__init__(daemon=True, name="ai-reader")
        self.cfg, self.store, self.geo, self.rules_fn = cfg, store, geo, rules_fn
        self.oblast_names, self.previous_fn, self.log = oblast_names, previous_fn, log
        self.context_fn = context_fn      # 1.51: (post, candidates) → (lines of the targets on the map, their tags)
        self.q = deque(maxlen=400)
        self.cond = threading.Condition()
        self.lock = threading.Lock()
        self.down_until = 0.0
        self.last_error = None
        self.hour, self.n_hour = None, 0
        self.month, self.spent = None, 0.0
        self.skipped = {}           # posts not read since the start, by why: paused, budget, rate
        self.recent = OrderedDict()  # post id → its checked targets (or None: read nothing / never read) — the tags

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
        return bool(self.key()) and self.cap() > 0 and self.cfg.get("ai_reader", True) is not False and self.switched_on()

    def switched_on(self):
        """1.51: the dashboard's switch (kv `ai_reader_on`): off stops every call at once."""
        try:
            return self.store.kv_get("ai_reader_on") != "0"
        except Exception:
            return True

    def live(self):
        """1.51: the other switch (kv `ai_live`): its facts in the target tags."""
        try:
            return self.store.kv_get("ai_live") != "0"
        except Exception:
            return True

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
        # 1.51: which oblast it speaks for and has been speaking about, what the rules read in this very post, and the
        # targets already on the map from every channel — the deterministic reading it is there to cross-check
        line = channel_block(ch, self.oblast_names.get(home) if home else None,
                             [self.oblast_names[u] for u in dict.fromkeys(near) if u in self.oblast_names])
        marks = self.rules_fn(ch, text, list(near))
        on_map, tags = [], ()
        if self.context_fn:
            try:
                on_map, tags = self.context_fn(post, cands)
            except Exception as e:
                self.log("ai reader: no map context:", type(e).__name__)
        msgs = messages(line, prev, text, "\n".join(f"{i} | {lab}" for i, _, lab in cands), cache=self.model().startswith("anthropic/"),
                        parser=parser_lines(marks), on_map=on_map)
        t0 = time.time()
        res = self.call(msgs)
        ms = int((time.time() - t0) * 1000)
        rules = summarise_rules(marks)
        if res.get("error"):
            self._save(post, text, stored, ms, res, None, rules, 0, "error")
            return "error"
        targets, dropped = validate(res["out"], text, cands, tags)
        ai = summarise_ai(targets, getattr(self.geo, "PLACES", None))
        verdict = compare(rules, ai)
        self._save(post, text, stored, ms, res, {"targets": targets, "uncertain": (res["out"] or {}).get("uncertain")},
                   rules, dropped, verdict)
        return verdict

    # How the answer's shape is asked for: 0 — a strict JSON schema the provider enforces; 1 — the prompt and the
    # examples alone (the provider refused the schema: 1.50.2). Either way the server checks every fact (validate).
    WAYS = ("schema", "prompt")
    way = 0

    def call(self, msgs):
        """{"out": dict, "cost", "tok_in", "tok_out"} or {"error": "..."} — the one request to OpenRouter. A provider
        that refuses the request as asked (400) is asked once more the simpler way, which is kept if it works."""
        res = self._request(msgs, self.way)
        if res.get("code") == 400 and self.way == 0:
            res2 = self._request(plain(msgs), 1)
            if not res2.get("error"):
                self.way = 1
                self.log("ai reader: the provider refused the JSON schema —", res["error"], "— answering by the prompt alone")
                return res2
            self.down_until = time.time() + 600       # refused both ways: no point asking again for every post
        elif res.get("code") == 400:
            self.down_until = time.time() + 600
        return res

    def _request(self, msgs, way):
        # 1.50.1: only parameters every model that takes a JSON schema accepts. With require_parameters, one the model
        # does not take (claude-haiku-5.5 takes no `temperature`) leaves no provider at all: "HTTP 404: No endpoints".
        body = {"model": self.model(), "max_tokens": 1200, "messages": msgs,
                "provider": {"require_parameters": True}, "usage": {"include": True}}
        if way == 0:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "heimdall_reading", "strict": True,
                                                                              "schema": SCHEMA}}
        req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={
            "Authorization": "Bearer " + self.key(), "Content-Type": "application/json", "X-Title": "Heimdall (shadow reader)"})
        try:
            ctx = getattr(self, "ssl_ctx", None)
            with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            why = _why(e)
            err = f"HTTP {e.code}" + (f": {why}" if why else "")
            if e.code in (401, 402, 403, 404):          # the key, the credit, or a model / parameter nobody serves
                self.down_until = time.time() + 600
            elif e.code == 429:
                self.down_until = time.time() + 60
            self.last_error = err
            self.log("ai reader:", err)
            return {"error": err, "code": e.code}
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
            out = _json_of(data["choices"][0]["message"]["content"])
        except Exception:
            self.last_error = "not JSON"
            return {"error": "not JSON", "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens")}
        self.last_error = None
        return {"out": out, "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens"),
                "model": data.get("model") or self.model(), "way": way}

    def _save(self, post, text, stored, ms, res, ai, rules, dropped, verdict):
        self._remember(post["post_id"], (ai or {}).get("targets") or None)
        try:
            self.store.ai_save({"post_id": post["post_id"], "ts": post["ts"], "channel": post["channel"], "text": text,
                                "stored": 1 if stored else 0,
                                "model": res.get("model") or self.model(), "prompt_v": PROMPT_VERSION + ("p" if res.get("way") == 1 else ""), "ms": ms,
                                "tok_in": res.get("tok_in"), "tok_out": res.get("tok_out"), "cost": res.get("cost") or 0,
                                "verdict": verdict, "rules": rules, "ai": ai, "dropped": dropped, "error": res.get("error")})
        except Exception as e:
            self.log("ai reader: not saved:", type(e).__name__)

    def targets_for(self, post_id):
        """The checked targets the reader found in a post, or None (not read, failed, nothing found). Kept in memory for
        the last few thousand posts; the database answers the others once."""
        with self.lock:
            if post_id in self.recent:
                self.recent.move_to_end(post_id)
                return self.recent[post_id]
        ts = None
        try:
            row = self.store.ai_get(post_id)
            ts = ((row or {}).get("ai") or {}).get("targets") if not (row or {}).get("error") else None
        except Exception:
            pass
        self._remember(post_id, ts or None)
        return ts or None

    def _remember(self, post_id, targets):
        with self.lock:
            self.recent[post_id] = targets
            self.recent.move_to_end(post_id)
            while len(self.recent) > 4000:
                self.recent.popitem(last=False)

    def stats(self):
        with self.lock:
            self._roll()
            spent = self.spent
        counts = {}
        try:
            counts = self.store.ai_counts(self.month)
        except Exception:
            pass
        return {"key": bool(self.key()), "enabled": self.enabled(), "reader_on": self.switched_on(), "live": self.live(), "model": self.model(), "prompt_v": PROMPT_VERSION,
                "month": self.month, "usd_month": round(spent, 4), "cap_usd": self.cap(), "queued": len(self.q),
                "paused": time.time() < self.down_until, "last_error": self.last_error, "skipped": dict(self.skipped),
                "format": self.WAYS[self.way],
                **counts}
