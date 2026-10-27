"""The AI of Heimdall — a language model through OpenRouter, within a monthly budget.

1.54, the owner: "the AI placing things on the map — we forget it". Since 1.54 the AI writes, it does not read for the
map: BULLETINS of the activity over the last hour and the last 24 hours, like a weather bulletin, in Ukrainian, English
and French in one call (server.Bulletins, ask_bulletin); and the report on each night for the dashboard (server.
NightReports, ask_text). Nothing it writes places, moves or removes a mark, sets an alert or sends a push; the bulletins
reach the app only behind the dashboard's switch, and each one is written from the server's own record of the window
(official alerts, the marks the rules drew, outcomes, the Air Force), never from a reader's data.

1.50–1.53 (retired in 1.54, not called by the server): a second reader of the channels' posts — one call a post, then a
check every 10 minutes — whose reading was checked against the post (every fact quoted, every place one of the
gazetteer's) and compared with the rules', and which drew the targets only it found (marked AI) and filled the target
tags. Its prompt, schema and validators below are kept with their tests and the dashboard's history of what it read;
docs/TECHNICAL.md §7.7, §7.10.

Only public text is sent — the channels' posts in the past, the record's place names and counts now. Never a reader, a
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

PROMPT_VERSION = "6"     # 1.52: where it is AND where it is going; bare names; alerts are not targets; 1.58.42: no emoji is a weapon; 1.58.60: a warning for the next day is no target
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MAX_CANDIDATES = 30
PER_HOUR = 400                       # posts a reader of this server sends at most in an hour

KINDS = ["shahed", "jet_drone", "drone", "cruise_missile", "ballistic_missile", "missile", "guided_bomb", "aircraft", "unknown"]
STATUSES = ["in_flight", "shot_down", "impact", "lost"]
RELATIONS = ["at", "heading_to", "from", "near", "side_of", "in_oblast", "none"]
DIRS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]
# our own words for them (the rules' marker types), to compare the two readings
KIND_TYPE = {"shahed": "drones", "jet_drone": "drones", "drone": "drones", "cruise_missile": "cruise_missiles",
             "ballistic_missile": "ballistic_missiles", "missile": "unspecified_missiles", "guided_bomb": "guided_aerial_bombs",
             "aircraft": "tactic_aircraft_activity", "unknown": "unknown"}
STATUS_OF = {"in_flight": None, "lost": None, "shot_down": "down", "impact": "impact"}
# the rules' types that say the same as the model's word ("Реактивний" is a drone to the rules, "Бандерол" a banderol)
KIND_OK = {"shahed": {"drones"}, "jet_drone": {"drones", "banderol_missiles"}, "drone": {"drones", "banderol_missiles"},
           "cruise_missile": {"cruise_missiles"}, "ballistic_missile": {"ballistic_missiles"},
           "missile": {"cruise_missiles", "ballistic_missiles", "unspecified_missiles", "supersonic_missiles", "banderol_missiles"},
           "guided_bomb": {"guided_aerial_bombs"}, "aircraft": {"tactic_aircraft_activity"}}
# 1.52 took the channels' emoji for a weapon (🛵 a Shahed, 🚀 a missile, 💣 a KAB …). 1.58.42, the owner: "stop using the
# emojis to determine the nature of the threat — the rocket / cruise missile emoji is very commonly used for jet drones".
# A weapon is quoted in words, or it is unknown.
# a long run of digits — a card number in a fundraising line — never leaves the server and is never stored here
_CARD_RX = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")


def mask(text):
    return _CARD_RX.sub("[…]", text or "")

SYSTEM = """You are the second reader of Heimdall, a public air-threat map of Ukraine. People decide whether to take cover from what is drawn. A deterministic parser has already read the post (PARSER READING). Your job is to cross-check it against the post, the channel's previous posts and the targets already ON THE MAP from every channel: confirm it, correct it, and above all ADD the targets it missed. A target missed is worse than a duplicate: when the post names a place for a target, even in loose or unusual words, give it. But you never invent: every fact quotes the post, every place is one the post names, from CANDIDATES.

Rules:
1. Never infer. A fact the post does not state is left empty: "" for a text, 0 for a number, "none" for a direction, an origin or a vertical state, "unknown" for the weapon. A likely guess is still a guess.
2. Quote. Every fact you give carries the exact words of the post that state it, copied character for character into its *_quote field. If you cannot quote it, leave it empty.
3. Places only from CANDIDATES, by their id (c1, c2…, or o<number> for an oblast). Never output coordinates. A place the post names that is not in CANDIDATES: place_id "", its words in place_quote. Several candidates of the same name: the one in the CHANNEL'S OBLAST or in the OBLASTS ITS LAST POSTS NAMED — a regional tracker reports its own oblast and the one next to it.
4. Two places per target: where it is (place_id, with its relation) and where it is going (toward_id). "на Житомирщині в напрямку Житомира" = place o10 in_oblast, toward Житомир; "повз Хорішки на Семенівку" = place Хорішки near, toward Семенівка; "з Требухова вектор Бровари" = place Требухів from, toward Бровари. When the post gives only where it is going, that place is place_id with relation heading_to and toward_id stays "". The relation to the place is what the words say:
   - "на X", "курсом на X", "в напрямку X", "у бік X", "вектор X" = heading_to X (or toward X, when the post also says where it is) — the target is NOT at X;
   - "над X", "в районі X", "біля X" said of where it is now = at X; "поблизу X", "неподалік X", "повз X", "околиці X" = near X;
   - a tracker's line that is only a place name, or a place and "увага" ("Яготин", "Наливайківка увага") = at X — give it: that is how trackers report a target;
   - "на Київщині, н.п. Гребінка", "в районі н.п. X" = at X — the settlement named is where it is;
   - "з X", "від X", "із X" (a Ukrainian place) = from X;
   - "північніше X", "на півночі від X", "за 20 км на північ від X" = side_of X (side n; distance_km 20 only if written);
   - an oblast only ("на Київщині", "Сумщина", "в Черкаській області") = in_oblast, with the oblast's o-id.
5. A city named with no place in it ("над Києвом", "околиці Києва", "правий берег Києва") is the city itself (relation at, the city's id). Never pick a district or a street the post does not name.
6. Weapons, by the post's words only — never by an emoji (the channels put 🚀 on jet drones; 🛵, 🏍, 🛸, 💣 alone are kind unknown): "шахед", "герань", "мопед", "ударний БпЛА" = shahed; "ракета" of no stated kind = missile; "реактивний", "реактив", "реактивний БпЛА/дрон", "Бандерол" = jet_drone (Banderol is a jet drone, never a cruise missile); "БпЛА", "дрон" of no stated kind = drone; "крилата ракета", "Калібр", "Х-101", "Х-55" = cruise_missile; "балістика", "балістична", "Іскандер", "КН-23" = ballistic_missile; "КАБ", "керовані авіабомби" = guided_bomb; "тактична авіація", "МіГ", "Су-34" = aircraft; nothing said ("ціль", "увага") = unknown.
7. Status only when stated: "збито", "знищено", "мінус", "мінуснули", "приземлили" (of a target) = shot_down; "вибух", "вибухи", "приліт", "влучання" = impact; "втрачено контакт", "зник", "не фіксується" = lost; otherwise in_flight.
8. One entry per target or group, in the order of the post. A count only if written ("2 шахеди", "група з 5", "×3"; "кілька", "група" alone are not a number).
9. Origin: where the post says the target comes from, outside the places above — a direction ("з півночі" = n, "з південного сходу" = se) or a country or area ("з Білорусі", "з території РБ" = belarus; "з Росії", "з Брянщини", "з Курщини", "з боку Бєлгорода" = russia; "з моря", "з акваторії Чорного моря" = sea; "з Криму" = crimea; "з окупованих територій", "з ТОТ" = occupied). A Ukrainian oblast or town it comes from is relation from that place, never an origin.
10. Heading only when the post gives a course as a direction ("курс на захід" = w). A town it flies to is heading_to that town, not a heading.
11. Height, vertical state and speed matter most to the people under a target: give them whenever the post states them, and only for the target they are written for (the same line or paragraph; a height on a line of its own after several targets belongs to the target just above it). Altitude in metres ("висота 2200", "на 1,5 км" = 1500); vertical: "знижується", "спускається", "пікірує", "скидає висоту" = descending; "набирає висоту" = climbing; "низько", "на малій висоті" = low; "високо", "на великій висоті" = high; speed ("швидкість 180 км/год" = 180).
12. Nothing about aerial targets — an official alert message ("Повітряна тривога", "Відбій", "жовтий рівень", "Дронова загроза" with a district: that is an alert, not a target), news, a fundraiser, an advert, the Air Force's morning totals, a warning for the hours or days ahead ("попередження на 24 години щодо застосування балістики", "протягом доби можлива атака": what may come, not a target): targets [].
13. PREVIOUS POSTS are context only. "Далі на X" continues the last target named there; but never copy a fact from them into this post's entry unless this post states it.
14. ON THE MAP NOW lists the targets other posts placed, by their tag (#01, #04…). If one of this post's targets is one of them — the same weapon reported again near the same place, or "Далі на X" continuing it — put its tag in same_as; otherwise "". Such a target is still listed: same_as says which it is.
15. The PARSER READING may be wrong or miss targets. Never copy it; read the post yourself. Where it missed a target the post names, add it; where it misread one, your reading — by the post's words — is the one to give.
16. Unsure? Say so in "uncertain" in one short English sentence ("" when sure), and still give only what is stated.

Answer with the JSON object only — no other text, no code fence."""

ORIGINS = ["belarus", "russia", "sea", "crimea", "occupied"] + DIRS
# the facts a target can carry, and how each is written on the wire when the post does not state it. No field is
# nullable: a nullable field is a "union type" to Anthropic's structured outputs, which take at most 16 of them in
# a schema — and a provider that cannot compile the schema answers "HTTP 400: Provider returned error" (1.50.2).
TEXTS = ("kind_quote", "count_quote", "status_quote", "place_id", "place_quote", "toward_id", "toward_quote", "origin_quote", "heading_quote",
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
        "toward_id": _S, "toward_quote": _S,
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
     ["#04 · drone · at Троєщина · @kyiv_airdef 21:02"],
     {"targets": [_t(kind="unknown", status="shot_down", status_quote="Збито", place_id="c1",
                     place_quote="над Оболонню", relation="at", same_as="#04")], "uncertain": None}),
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
     "c1 | Бортничі | м. Київ\no31 | м. Київ", [], ["#07 · Shahed · heading to Бортничі · @kyiv_airdef 22:10"],
     {"targets": [_t(kind="unknown", place_id="c1", place_quote="на Бортничі", relation="heading_to",
                     vertical="descending", vertical_quote="знижується", same_as="#07")], "uncertain": None}),
    # 1.52: where it is and where it is going, both; the weapon is in the words ("Реактивний БпЛА"), never the 🏍
    (channel_block("kpszsu"), [], "🏍 Реактивний БпЛА на Житомирщині в напрямку Коростеня",
     "c1 | Коростень | Житомирська область\no10 | Житомирська область", ["drone · heading to Коростень"], [],
     {"targets": [_t(kind="jet_drone", kind_quote="Реактивний БпЛА", place_id="o10", place_quote="на Житомирщині",
                     relation="in_oblast", toward_id="c1", toward_quote="в напрямку Коростеня")], "uncertain": None}),
    (channel_block("eRadarrua", None, ["Київська область"]), [], "🛵 Наливайківка\n\n🛵 2 повз Бородянку на Ворзель",
     "c1 | Наливайківка | Київська область\nc2 | Бородянка | Київська область\nc3 | Ворзель | Київська область\no14 | Київська область",
     ["unknown · at Наливайківка", "unknown ×2 · at Бородянка"], [],
     {"targets": [_t(kind="unknown", place_id="c1", place_quote="Наливайківка", relation="at"),
                  _t(kind="unknown", count=2, count_quote="2 повз", place_id="c2", place_quote="повз Бородянку",
                     relation="near", toward_id="c3", toward_quote="на Ворзель")], "uncertain": None}),
    # an official alert message names a district and a threat: it is an alert, not a target
    (channel_block("trevoga_kartaa_noviny"), [], "🚨Повітряна тривога · жовтий рівень🟡\nБучанський р-н\nДронова загроза",
     "o14 | Київська область", [], [], {"targets": [], "uncertain": None}),
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
        kw = "jet drone" if m.get("type") == "drones" and m.get("jet") else _KW.get(m.get("type"), m.get("type") or "?")
        bits = [kw + (f" ×{m['count']}" if (m.get("count") or 1) > 1 else ""), where]
        if (m.get("origin") or {}).get("o"):
            bits.append(f"from {m['origin']['o']}")
        if m.get("status"):
            bits.append({"down": "shot down", "impact": "impact", "lost": "lost"}.get(m["status"], m["status"]))
        if (m.get("alt") or {}).get("m"):
            bits.append(f"{m['alt']['m']} m")
        if (m.get("alt") or {}).get("state"):
            bits.append(m["alt"]["state"])
        if (m.get("speed") or {}).get("kmh"):
            bits.append(f"{m['speed']['kmh']} km/h")
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
    # 1.52: the places the rules' matchers miss — a village they do not read, a slip of spelling ("Пепеяслав") — among
    # the oblasts in play (Kyiv oblast for the Kyiv channels), by the stem of the name, one letter off at most
    play = set(uids) | ({"14"} if {"31", "14"} & set(uids) or home in ("31", "14") else set())
    try:
        names += [k for k in fuzzy_places(geo, t, play) if k not in names]
    except Exception:
        pass
    out, seen = [], set()
    for n in names:
        if n in seen or len(out) >= MAX_CANDIDATES:
            continue
        seen.add(n)
        p = place_of(geo, n)
        if not p:
            continue
        out.append((f"c{len(out) + 1}", n, f"{n} | {oblast_names.get(p[2], p[2])}"))
    for u in dict.fromkeys(uids):
        if u in oblast_names and f"o{u}" not in seen:
            seen.add(f"o{u}")
            out.append((f"o{u}", f"o{u}", oblast_names[u]))
    return out


_END = re.compile(r"(ами|ями|ого|ому|ою|ею|єю|ів|їв|ій|ий|ої|ам|ям|ах|ях|ом|ем|у|ю|а|я|і|ї|и|е|є|о|й|ь)$")
_FUZZ = {}


def _stem(w):
    return " ".join(_END.sub("", x) for x in w.lower().replace("’", "'").replace("ʼ", "'").split())


def _lev1(a, b):
    """True when a and b differ by one letter at most (one changed, added or dropped)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _fuzzy_index(geo):
    if not _FUZZ:
        src = list(dict.items(geo.PLACES)) + list(getattr(geo, "REGIONAL", {}).items()) + list(getattr(geo, "EXTRA_PLACES", {}).items())
        for key, (_, _, uid) in src:
            base = re.sub(r"\s+\d+$", "", key.split(" (")[0])
            st = _stem(base)
            if len(st.replace(" ", "")) >= 4:
                _FUZZ.setdefault(uid, []).append((st, key, len(st.split())))
    return _FUZZ


def fuzzy_places(geo, t, uids, limit=8):
    """1.52: the gazetteer keys (core, regional, extra) of the oblasts `uids` whose name a word of the post — or two
    words, for "Сомкова Долина" — matches by its stem, exactly for a short name, one letter off for a long one."""
    words = [w for w in re.findall(r"[а-яіїєґ'’]+", t.lower()) if len(w) >= 4]
    stop = getattr(geo, "REGIONAL_STOP", frozenset())
    one = {_stem(w) for w in words if w not in stop}
    two = {_stem(f"{a} {b}") for a, b in zip(words, words[1:])}
    idx, out = _fuzzy_index(geo), []
    for uid in uids:
        for st, key, nw in idx.get(uid, ()):
            pool = two if nw == 2 else one if nw == 1 else ()
            if any((w == st) or (len(st) >= 6 and w[:1] == st[:1] and _lev1(w, st)) for w in pool):
                out.append(key)
                if len(out) >= limit:
                    return out
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
        # 1.58.42: a quote of words — an emoji is no weapon (ok() needs two characters of the post's words)
        if t["kind"] not in KINDS or (t["kind"] != "unknown" and not (ok(t["kind_quote"]) and re.search(r"\w{2}", t["kind_quote"] or ""))):
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
        if t["toward_id"] is not None and not (t["toward_id"] in ids and ok(t["toward_quote"]) and t["toward_id"] != t["place_id"]):
            dropped += t["toward_id"] != t["place_id"]
            t["toward_id"], t["toward_quote"] = None, None
        if t["place_id"] is None and t["toward_id"] is not None:      # only where it is going: that is the place
            t["place_id"], t["place_quote"], t["relation"] = t["toward_id"], t["toward_quote"], "heading_to"
            t["toward_id"], t["toward_quote"] = None, None
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
        t["toward"] = ids[t["toward_id"]][1] if t["toward_id"] else None
        res.append(t)
    return res, dropped


# ---- the two readings side by side ---------------------------------------------------------------------------------
def _canon(w):
    """Kyiv itself is the city's region to the rules (a post naming no place in it, geo._city_settle). 1.53: and a
    village is its name — "На Козин" is one place in the post, whichever namesake each reader took ("Козин (Прилуцький
    р-н)", 120 km from the Kyiv one, was drawn as a second target the rules had missed): where the rules placed it stands."""
    w = (w or "").split(" (")[0]
    return "o31" if w == "Київ" else w


def _where_rules(m):
    p = m.get("place") or ""
    if p == "область":
        return "o" + str(m.get("oblast_uid") or "")
    return _canon(p[2:] if p.startswith("→ ") else p)


def place_of(geo, key):
    """(lon, lat, oblast uid) of a candidate place: the gazetteer's (core and regional), or 1.52's extra villages."""
    p = geo.PLACES.get(key) if geo else None
    if p:
        return p
    return getattr(geo, "EXTRA_PLACES", {}).get(key)


def anchors_of(geo, marks, home=None, channel=None):
    """1.53: where a post is about, to choose between namesakes: the rules' marks (their places, a destination too), and
    the channel's own oblast — Kyiv for the Kyiv channels."""
    out = [(m["lon"], m["lat"]) for m in marks or [] if m.get("lon") is not None and m.get("lat") is not None]
    kyiv = home in ("31", "14") or channel in getattr(geo, "_KYIV_CH", ())
    c = (getattr(geo, "_OBL_CENTRE", {}) or {}).get(home) if home and not kyiv else None
    if kyiv and geo and "Київ" in geo.PLACES:
        c = geo.PLACES["Київ"][:2]
    if c:
        out.append((c[0], c[1]))
    return out


def pick_namesakes(targets, cands, geo, anchors=()):
    """1.53: "з Козина на Ходосівку" — the AI took Козин (Прилуцький р-н), 150 km off, for the village by Kyiv the post
    meant. Of several candidates of one name, the one nearest to the other places of the same target, then of the
    post's other targets, then to `anchors` (anchors_of) is kept — whichever the AI chose. Changes `targets` in place."""
    by = {}
    for cid, key, _ in cands:
        if not key.startswith("o"):
            by.setdefault(key.split(" (")[0], []).append((cid, key))

    def pos(k):
        p = place_of(geo, k)
        return (p[0], p[1]) if p else None

    def km(a, b):
        return ((a[0] - b[0]) * 70.7) ** 2 + ((a[1] - b[1]) * 111) ** 2
    sure = [pos(t[f]) for t in targets for f in ("place", "toward") if t.get(f) and len(by.get(t[f].split(" (")[0], [])) < 2]
    for t in targets:
        for fld, idf in (("place", "place_id"), ("toward", "toward_id")):
            k = t.get(fld)
            alts = by.get((k or "").split(" (")[0], [])
            if not k or len(alts) < 2:
                continue
            other = t.get("toward" if fld == "place" else "place")
            anc = ([pos(other)] if other and len(by.get(other.split(" (")[0], [])) < 2 else []) + sure + list(anchors)
            anc = [a for a in anc if a]
            if not anc:
                continue
            best = min(alts, key=lambda a: min(km(pos(a[1]), x) for x in anc) if pos(a[1]) else 1e18)
            t[fld], t[idf] = best[1], best[0]
    return targets


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
                    "alt": f"o{p[2]}" if p and t["relation"] == "side_of" else None,
                    "toward": _canon(t.get("toward") or "") or None})
    return out


def match(targets, wheres, alone):
    """1.51: the AI target that is a given track's — the one at one of its places (`wheres`, canonical), or the only
    target of a post the rules also read as one target (`alone`). None rather than a guess."""
    # 1.53: a check stores only what it found (`f`): a target it found MISSING, or at another place, is not the track's
    if alone and len(targets) == 1 and targets[0].get("f") in (None, "facts", "weapon", "outcome"):
        return targets[0]
    for t in targets:
        w = _canon(t.get("place") or "")
        if (w and w in wheres) or (t.get("toward") and _canon(t["toward"]) in wheres):
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
        if w and w not in rw and a.get("toward") in rw:       # the rules drew it at where it is going
            w = a["toward"]
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


# 1.52.1: the longest answer allowed. Every target is written out field by field with its quotes (the strict schema):
# 600 tokens for a post is usual, and one post in ten of a busy tracker ("По 1 біля Кіптів та Бобровиці. 1 на
# Водосховище…") went past the 1,200 allowed until then — cut off mid-answer, read as "not JSON".
MAX_OUT = 2400


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


# ---- 1.53: the 10-minute check ------------------------------------------------------------------------------------
# The owner (9 Oct 2026): one call a post costs too much at the channels' pace (~150 posts an hour, ~$0.0004 each:
# the month's budget gone in a week). Every `ai_check_minutes` (10) one call reads the posts of those minutes, grouped by
# the oblast they concern, with what the rules drew from each and what the map shows in each oblast — and answers only
# where the rules are wrong or incomplete (FINDINGS), with a short NOTE per oblast. The rules stay the reader; the
# check is the second opinion, ten minutes late at most.
CHECK_VERSION = "6"     # 1.58.42: no emoji is a weapon
FINDINGS = ["missed", "place", "weapon", "outcome", "not_sky", "facts"]
# 1.53.1: 60 posts made answers past 6,000 tokens on a busy night ("cut off at 6000 tokens", 9 Oct): 30 a call, room
# for 12,000, the notes first, and what came complete of an answer cut off is kept (salvage_check)
MAX_CHECK_POSTS = 30          # posts in one call; more in the window → several calls, by oblast
MAX_OUT_CHECK = 12000
CHECK_TEXT = 700              # characters of a post sent (a long post is news; its first lines are what matter)
CHECK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "notes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"oblast": _S, "note": _S}, "required": ["oblast", "note"]}},
        "findings": {"type": "array", "items": None},     # FIND, below
        "uncertain": _S},
    "required": ["notes", "findings", "uncertain"]}
# 1.53.4: a finding is flat and carries only what the map uses — the dashboard (9 Oct) showed 10 checks in 12 cut off at
# 6,000 tokens: a finding in the one-post schema (27 fields, quotes in Cyrillic) cost 600–1,000 tokens. No origin (no
# longer shown), course, side, distance, speed or tag link: 18 fields, a third of the length.
FIND_KEYS = ("kind", "kind_quote", "count", "count_quote", "status", "status_quote", "place_id", "place_quote", "relation",
             "toward_id", "toward_quote", "altitude_m", "altitude_quote", "vertical", "vertical_quote")
FIND = {"type": "object", "additionalProperties": False,
        "properties": {"post": _S, "finding": {"type": "string", "enum": FINDINGS},
                       **{k: TARGET["properties"][k] for k in FIND_KEYS}, "why": _S}}
FIND["required"] = list(FIND["properties"])
CHECK_SCHEMA["properties"]["findings"]["items"] = FIND


def find_target(f):
    """A flat finding as a target in the one-post shape (what `validate` reads): the fields it does not carry, unstated."""
    t = {k: ("" if k in TEXTS else 0 if k in INTS else "none") for k in TARGET["properties"]}
    t.update(kind="unknown", status="in_flight", relation="none")
    t.update({k: f[k] for k in FIND_KEYS if k in f})
    return t

# the reading rules are the same as for one post (1 to 12 of SYSTEM): one text, two prompts
RULES_READ = SYSTEM[SYSTEM.index("1. Never infer."):SYSTEM.index("13. PREVIOUS POSTS")].rstrip()

SYSTEM_CHECK = """You are the second reader of Heimdall, a public air-threat map of Ukraine. People decide whether to take cover from what is drawn. Every few minutes you check the channel posts of those minutes against what Heimdall's deterministic rules drew from each (RULES, under each post) and against the targets ON THE MAP NOW in each oblast. The rules are fast and stay the main reader: you do not repeat what they got right. You report only FINDINGS — where a post's own words show the rules wrong or incomplete — and a short NOTE per oblast on what the posts show together. A target missed is worse than a duplicate: when a post names a place for a target the rules did not draw, report it, even in loose or unusual words. But you never invent: every fact quotes its post, every place is one the post names, from CANDIDATES.

How to read a post:
""" + RULES_READ + """

The check:
13. The posts come grouped by the oblast they concern (=== OBLAST … === blocks), oldest first. Each has its id ([p4]), its time, its channel with the channel's own oblast and the oblasts its last posts named, its text, RULES (what the rules drew from it, one line a target; "set aside" = the server judged it not about the sky and drew nothing) and NAMES (the ids of the CANDIDATES its words match).
14. One finding per target the rules got wrong or missed, with "post" = the post's id and "finding" =
   - "missed": a target the post names that no RULES line of that post has — give the whole target;
   - "place": a RULES line put the target at the wrong place — the target at the right place;
   - "weapon": the right place, the wrong weapon; "outcome": shot down, impact or lost read wrongly or not at all;
   - "facts": the right place, but a stated height, vertical state, count or destination is missing from the RULES line — the target at the rules' place, with them;
   - "not_sky": the rules drew a target from a post that reports none (an official alert message, news, an advert, a fundraiser) — a target of kind "unknown" with no place.
   "why": a few English words. A post the rules read right gets no finding. Be brief: report only what changes what a reader would understand — a target missed or misplaced, a wrong weapon or outcome, a height, descent, origin or destination left out — at most one finding per target, never a count of one or a quote the rules already have.
15. A channel's earlier posts in the check are the context of its later ones ("Далі на X" continues the last target that channel named). Never carry a fact from one post into another post's finding.
16. A finding carries only its own fields — no origin, course, side or speed — and every text field is as short as the post allows: the quote, nothing more.
17. NOTES: for each oblast block with targets, one English sentence on what its posts show together — how many targets, of what kind, where they come in from and where they head, waves, heights, and what the map misses or overstates. Only what the posts and the map show: no forecast, no advice. "oblast" is the block's id (o14).
18. Unsure about something? Say it in "uncertain" ("" when sure).

Answer with the JSON object only — no other text, no code fence."""


def _hm(ts):
    """HH:MM in Kyiv time."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Kyiv")
    except Exception:
        from datetime import timedelta
        tz = timezone(timedelta(hours=3))
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(tz).strftime("%H:%M")
    except Exception:
        return "?"


def check_text(blocks, cand_lines, window=""):
    """The check's message. `blocks`: [(oblast id or "", oblast name, [map lines], [post dicts])], a post dict:
    {label, hm, ch, home, near, text, rules (lines, or None when set aside), names}."""
    out = [f"CHECK OF THE POSTS {window}".rstrip(), "", "CANDIDATES (id | name | oblast):", cand_lines or "(none)", ""]
    for oid, name, lines, posts in blocks:
        out.append(f"=== OBLAST {oid} · {name} ===" if oid else "=== NO OBLAST NAMED ===")
        out.append("ON THE MAP NOW:")
        out += [f"- {x}" for x in lines] or ["(nothing)"]
        out.append("POSTS:")
        for p in posts:
            own = p.get("home") or "none — a country-wide channel"
            out.append(f"[{p['label']}] {p['hm']} @{p['ch']} · CHANNEL'S OBLAST: {own} · OBLASTS ITS LAST POSTS NAMED: "
                       f"{', '.join(p.get('near') or []) or '—'}")
            out.append(p["text"])
            r = p.get("rules")
            out.append("RULES: " + ("set aside — nothing drawn" if r is None else "; ".join(r) if r else "(nothing)"))
            out.append("NAMES: " + (", ".join(p.get("names") or []) or "—"))
            out.append("")
    return "\n".join(out).rstrip()


def _p(label, hm, ch, text, rules, names, home=None, near=()):
    return {"label": label, "hm": hm, "ch": ch, "text": text, "rules": rules, "names": names, "home": home, "near": list(near)}


# one worked check, given as an earlier turn: what to report, and what not to
CHECK_EXAMPLE = (
    check_text([
        ("o14", "Київська область", ["#07 · drone · heading to Бортничі · @kyiv_airdef 22:10"], [
            _p("p1", "22:12", "kyiv_airdef", "Ціль заходить на Бортничі, низько, знижується", [], ["c1", "o31"], "м. Київ", ["м. Київ"]),
            _p("p2", "22:13", "trevoga_kartaa_noviny", "🚨Повітряна тривога · жовтий рівень🟡\nБучанський р-н\nДронова загроза",
               ["drone · in oblast 14"], ["o14"]),
            _p("p3", "22:14", "kpszsu", "2 шахеди з півночі на Бровари", ["drone ×2 · heading to Бровари · from n"], ["c2", "o14"]),
            _p("p4", "22:15", "eRadarrua", "🛵 Наливайківка\n\n🛵 2 повз Бородянку на Ворзель",
               ["unknown · at Наливайківка", "unknown ×2 · at Бородянка"], ["c3", "c4", "c5", "o14"], None, ["Київська область"])]),
        ("o5", "Рівненська область", ["#04 · drone · heading to Сарни · @rivne_radar 22:05"], [
            _p("p5", "22:17", "rivne_radar", "Тепер на Висоцьк", None, ["c6", "c7"], "Рівненська область", ["Рівненська область"])]),
        ("o10", "Житомирська область", [], [
            _p("p6", "22:11", "kpszsu", "🏍 Реактивний БпЛА на Житомирщині в напрямку Коростеня", ["jet drone · heading to Коростень"], ["c8", "o10"]),
            _p("p7", "22:16", "monitor_ukr", "1 реактив над Коростенем\nшвидкість 400 км/год, висота 3 км", ["jet drone · at Коростень"], ["c8", "o10"])])],
        "c1 | Бортничі | м. Київ\nc2 | Бровари | Київська область\nc3 | Наливайківка | Київська область\nc4 | Бородянка | Київська область\n"
        "c5 | Ворзель | Київська область\nc6 | Висоцьк | Рівненська область\nc7 | Висоцьк (Житомирський р-н) | Житомирська область\n"
        "c8 | Коростень | Житомирська область\no5 | Рівненська область\no10 | Житомирська область\no14 | Київська область\no31 | м. Київ",
        "22:10–22:20 Kyiv time"),
    {"findings": [
        {"post": "p1", "finding": "missed", "why": "a tracker's target heading to Bortnychi, descending",
         "target": _t(kind="unknown", place_id="c1", place_quote="на Бортничі", relation="heading_to",
                      vertical="descending", vertical_quote="знижується", same_as="#07")},
        {"post": "p2", "finding": "not_sky", "why": "an official alert message, not a target", "target": _t()},
        {"post": "p4", "finding": "facts", "why": "the course to Vorzel", "target": _t(
            kind="unknown", count=2, count_quote="2 повз", place_id="c4", place_quote="повз Бородянку",
            relation="near", toward_id="c5", toward_quote="на Ворзель")},
        {"post": "p5", "finding": "missed", "why": "the tracker's next point (its own oblast's Vysotsk), set aside by the server",
         "target": _t(kind="unknown", place_id="c6", place_quote="на Висоцьк", relation="heading_to", same_as="#04")},
        {"post": "p7", "finding": "facts", "why": "height", "target": _t(
            kind="jet_drone", kind_quote="реактив", count=1, count_quote="1 реактив", place_id="c8", place_quote="над Коростенем",
            relation="at", speed_kmh=400, speed_quote="швидкість 400 км/год", altitude_m=3000, altitude_quote="висота 3 км")}],
     "notes": [
        {"oblast": "o14", "note": "Two Shaheds from the north toward Brovary, two passing Borodianka toward Vorzel, and #07 descending onto Bortnychi; the yellow-level message for Bucha raion is an alert, not a target."},
        {"oblast": "o5", "note": "#04, heading for Sarny, now goes on toward Vysotsk."},
        {"oblast": "o10", "note": "One jet drone came in toward Korosten and is now over it at 3 km, 400 km/h."}],
     "uncertain": ""})


def wire_check(ans):
    """A check's answer as the model writes it (no field is nullable on the wire; 1.53.4: findings flat, FIND)."""
    one = wire({"targets": [f["target"] for f in ans["findings"]]})["targets"]
    return {"notes": [{"oblast": n["oblast"], "note": n["note"]} for n in ans.get("notes") or []],
            "findings": [{"post": f["post"], "finding": f["finding"], **{k: t[k] for k in FIND_KEYS}, "why": f.get("why") or ""}
                         for f, t in zip(ans["findings"], one)],
            "uncertain": ans.get("uncertain") or ""}


def salvage_check(content):
    """1.53.1: the notes and findings that came complete in a check's answer cut off at the length allowed — the ones
    after the cut are lost, the rest is good. None when nothing came complete."""
    if not isinstance(content, str):
        return None
    dec, out = json.JSONDecoder(), {"notes": [], "findings": [], "uncertain": ""}
    for key in ("notes", "findings"):
        i = content.find(f'"{key}"')
        j = content.find("[", i) if i >= 0 else -1
        if j < 0:
            continue
        k = j + 1
        while True:
            while k < len(content) and content[k] in " \n\r\t,":
                k += 1
            if k >= len(content) or content[k] == "]":
                break
            try:
                obj, k = dec.raw_decode(content, k)
            except ValueError:
                break
            if isinstance(obj, dict):
                out[key].append(obj)
    return out if out["findings"] or out["notes"] else None


def check_messages(text, cache=False):
    out = [{"role": "system", "content": SYSTEM_CHECK},
           {"role": "user", "content": CHECK_EXAMPLE[0]},
           {"role": "assistant", "content": json.dumps(wire_check(CHECK_EXAMPLE[1]), ensure_ascii=False)}]
    if cache:
        out[-1]["content"] = [{"type": "text", "text": out[-1]["content"], "cache_control": {"type": "ephemeral"}}]
    out.append({"role": "user", "content": text})
    return out


# ---- 1.53: the night's report --------------------------------------------------------------------------------------
REPORT_VERSION = "2"     # 1.54: no AI checks to read any more
# 1.58.37, the owner: "some days throw back: Not written: empty answer". The model thinks before it writes and its
# thinking counts against max_tokens: on a busy night 3,000 went on thinking and nothing was left for the report. Room
# to think and write (paid only as used); an answer cut off before any word is asked once more with twice the room.
MAX_OUT_REPORT = 10000
MAX_OUT_PERIOD = 14000
MAX_OUT_RETRY = 24000
REPORT_SYSTEM = """You are the analyst of Heimdall, an unofficial air-threat map of Ukraine built from public Telegram channels and the official alert feed. You are given the complete record of one night (12:00 to 12:00 Kyiv time): the official alerts by oblast, every target Heimdall tagged with the path its reports drew, its heights and where it came from, the reports by hour and oblast, the outcomes reported and the Air Force's figures (a night before 1.54 also has the notes of the AI checks then run every few minutes).

Write the night's report for the owner, in English, plain text with short headed sections:
1. The night in brief — when it started and ended, the waves, the oblasts most concerned, the few figures that matter.
2. Routes — where targets were first reported (entry places), where they went, the longest paths; Kyiv city and oblast in particular. The origins the posts stated are often wrong (a track takes the first one any of its reports gave): use one only where several posts agree.
3. Heights and speeds — what was reported, and the descents.
4. Against the Air Force — what its summary says beside what the channels reported, where both exist.
5. Patterns — what this night shows about how the attack unfolded: timing, routes, mixes of weapons, repeats; only what the record supports.

Only what the record shows: take every figure from it, never invent a number, a place or a weapon; say "reported" (these are channel reports, not a count of drones); no forecast stated as a fact, no advice on sheltering, no names of people. At most 900 words."""

# 1.58.37, the owner: "the main goal is to aggregate as many data as possible to make a report, so we need a wider range
# of dates, not only one day at a time". The record of several nights at once (State.period_summary / period_text).
PERIOD_SYSTEM = """You are the analyst of Heimdall, an unofficial air-threat map of Ukraine built from public Telegram channels and the official alert feed. You are given the record of a period of several nights (each night runs from 12:00 to 12:00 Kyiv time): one line per night (the targets Heimdall tagged and followed, the channel reports, the oblasts under alert, the minutes Kyiv city spent under alert, the Air Force's own figures for the night, the outcomes reported), then the totals over the period — the official alerts by oblast, the reports by oblast and by hour, where tagged targets were first reported, the outcomes, the heights.

Write the period's report for the owner, in English, plain text with short headed sections:
1. The period in brief — the heaviest and the quietest nights, the oblasts most concerned, the few figures that matter.
2. Night by night — how the nights compare: their size, their timing, their mix of weapons; streaks and breaks.
3. Routes and places — where targets were first reported most often, the oblasts and places that recur, Kyiv city and oblast in particular.
4. Timing — the hours the reports cluster in, and whether that moved over the period.
5. Against the Air Force — its launched and shot-down figures beside what the channels reported, night by night where both exist; say plainly that the channels follow only part of what is launched.
6. Patterns — what repeats across the nights: days, hours, routes, mixes; only what the record supports, with the nights it rests on.

Only what the record shows: take every figure from it, never invent a number, a place or a weapon; say "reported" (these are channel reports, not a count of drones); a pattern seen on two or three nights is a hint, not a rule — say how many nights it rests on; no forecast stated as a fact, no advice on sheltering, no names of people. At most 1,400 words."""


# ---- 1.54: the bulletins ------------------------------------------------------------------------------------------
# The owner (9 Oct 2026): "instead of all that on the map, summaries of the activity of the last hour / last 24 hours,
# a bit like a weather bulletin". One call writes the bulletin in the app's three languages, from the server's record of
# the window (State.activity_summary / activity_text) — counts, places and times the rules and the official feed
# recorded, never a post's text.
BULLETIN_VERSION = "3"      # 1.58.30: where the posts put a target, apart from where one was only heading
BULLETIN_KINDS = ("1h", "24h")
# 1.54.8, the owner: more leeway on the token cutoff — three languages of Cyrillic and
# Latin in one JSON answer, and a model that thinks before it writes, ran into 1,200 / 2,400 tokens. Paid only as used.
MAX_OUT_BULLETIN = {"1h": 4000, "24h": 8000}
BULLETIN_CHARS = {"1h": 1100, "24h": 2600}        # per language, at most: past it, cut at the last full sentence
BULLETIN_TIMEOUT = 120                            # seconds; a post's reading keeps 40
BULLETIN_SYSTEM = """You write the bulletins of Heimdall, an unofficial air-threat map of Ukraine built from public Telegram channels and the official alert feed. People read them on a phone, during or after an attack, the way they read a weather bulletin: what happened, where, how much — calm, plain and short.

You are given Heimdall's record of one window, the last hour or the last 24 hours (Kyiv time): the official air-raid alerts by oblast (and their raions), the targets the channels reported (Heimdall's marks — reports, not a count of drones) by oblast, kind and time, the places where the posts put them most (a place a target was only said to be heading for is listed apart), the missiles and carriers reported, the courses the marks carried, the paths of the targets Heimdall followed, the heights and speeds reported, where the posts said the targets came from, the outcomes reported (shot down, explosions) and when, what was on the map when the record was made, the window before it for comparison, and for 24 hours the Air Force's figures and the night's weather. Read all of it; say only what a reader needs.

Write the same bulletin in Ukrainian ("uk"), English ("en") and French ("fr"). Answer with one JSON object: {"uk": "...", "en": "...", "fr": "..."}.

Rules:
1. Only what the record shows. Every number, place, weapon and time comes from the record; never invent or estimate one. These are reports of channels, not radar and not a count of drones: say "reported" ("12 drone reports over Chernihiv oblast"), never "12 drones".
2. Kyiv first — the city, then Kyiv oblast — then the other oblasts by how much was reported. Name at most five oblasts; the rest are "other oblasts".
3. Alerts come only from the official alerts in the record: which oblasts had an air-raid alert and, for the city of Kyiv, when it started and whether it ended. Never say an alert ended unless the record says so.
4. Never say a place is safe or that the danger is over, never advise on shelter, never forecast ("will", "expect", "next"). A trend in the record is a fact and may be said: "fewer reports in the last 20 minutes", "more than in the hour before".
5. Never say where the targets came from or where they are heading — the posts' origins are often wrong, and the record's "where the posts said they came from", "courses" and "reported only by where they were heading" are kept for the record, not for the bulletin. A followed target's path may be told as the places it was reported at, in order: "first reported near Ripky at 19:02, last near Vyshhorod at 20:22".
6. Times in Kyiv time, 24-hour (19:05). Heights in metres, as reported ("reported at 1,800 m").
7. The last hour: at most 90 words a language, one or two short paragraphs, no list. The last 24 hours: at most 220 words a language, at most four short paragraphs — in brief, where, heights and outcomes, and the Air Force's figures when given (the night's weather in one clause, if it matters).
8. Plain text only: no markdown, no emoji, no headings, no channel names, no names of people, no links.
9. Place names in Ukrainian in "uk"; in "en" and "fr" their usual Latin spelling (Київ → Kyiv, Бровари → Brovary, Чернігівська область → Chernihiv oblast / l'oblast de Tchernihiv).
10. When the record shows little, say so in one sentence ("Over the last hour the channels reported 2 drones over Sumy oblast; none near Kyiv.").
11. Never write "unknown", "unidentified" or "unspecified" for a target. A report whose weapon the post did not state is in the record as "probable drone (type not stated)" when no missile was reported in the window — write "probably drones" or "most likely Shahed-type drones"; and as "drone or missile (type not stated)" when missiles or their carriers were reported — write "drones or missiles". Never turn "probably" into a certainty, and never count them as drones in a total of drones."""
BULLETIN_SCHEMA = {"type": "object", "additionalProperties": False,
                   "properties": {"uk": {"type": "string"}, "en": {"type": "string"}, "fr": {"type": "string"}},
                   "required": ["uk", "en", "fr"]}
BULLETIN_LABEL = {"1h": "the last hour", "24h": "the last 24 hours"}
_MD = re.compile(r"^\s*(?:#+|[-*•]|\d+[.)])\s+|\*\*|__|`|\[|\]\([^)]*\)", re.M)
_LINK = re.compile(r"https?://\S+|t\.me/\S+|@\w{4,}")


def bulletin_messages(kind, text, span=""):
    return [{"role": "system", "content": BULLETIN_SYSTEM},
            {"role": "user", "content": f"WINDOW: {BULLETIN_LABEL[kind]}{f' ({span}, Kyiv time)' if span else ''}\n\n{text}\n\n"
                                        f"Write the bulletin of {BULLETIN_LABEL[kind]} as one JSON object {{\"uk\", \"en\", \"fr\"}}."}]


def bulletin_clean(out, kind):
    """The three texts of an answer, cleaned: plain text (no markdown, links or channel names), no card number, no longer
    than BULLETIN_CHARS (cut at the last full sentence). None when a language is missing or empty."""
    if not isinstance(out, dict):
        return None
    res = {}
    for lang in ("uk", "en", "fr"):
        t = out.get(lang)
        if not isinstance(t, str):
            return None
        t = mask(_LINK.sub("", _MD.sub("", t)))
        t = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()
        cap = BULLETIN_CHARS[kind]
        if len(t) > cap:
            cut = t[:cap]
            end = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("! "), cut.rfind("? "))
            t = (cut[:end + 1] if end > cap // 3 else cut.rstrip() + "…").strip()
        if not t:
            return None
        res[lang] = t
    return res


# a post's word for the dashboard, from what the check found in it (the same words as one post's reading)
F_VERDICT = {"not_sky": "rules_only", "place": "place", "weapon": "kind", "outcome": "status", "facts": "facts"}
F_ORDER = ["not_sky", "missed", "place", "weapon", "outcome", "facts"]


def check_verdict(kinds, rules):
    """agree / none when it found nothing; otherwise the weightiest finding's word."""
    if not kinds:
        return "agree" if rules else "none"
    k = min(kinds, key=F_ORDER.index)
    if k == "missed":
        return "place" if rules else "ai_only"
    return F_VERDICT[k]


# ---- the reader --------------------------------------------------------------------------------------------------
class AIReader:
    """The one way to the model: every call within the month's budget (`ai_reader_monthly_usd`, counted from what
    OpenRouter says each call cost) and PER_HOUR an hour; paused 10 minutes when OpenRouter refuses the key or the
    credits, a minute when it says to slow down; off with the dashboard's switch. 1.54: called by the bulletins
    (ask_bulletin) and the night's report (ask_text). read() and check() — the reading of posts for the map, 1.50–1.53 —
    are kept but no longer called: nothing feeds it posts any more."""

    def __init__(self, cfg, store, geo=None, rules_fn=None, oblast_names=None, previous_fn=None, log=print, context_fn=None, map_fn=None):
        self.cfg, self.store, self.geo, self.rules_fn = cfg, store, geo, rules_fn
        oblast_names = oblast_names or {}
        self.oblast_names, self.previous_fn, self.log = oblast_names, previous_fn, log
        self.context_fn = context_fn      # 1.51: (post, candidates) → (lines of the targets on the map, their tags)
        self.map_fn = map_fn              # 1.53: (oblast uids) → ({uid: lines of the targets on the map}, their tags)
        self.checks = 0
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

    def _roll(self):
        m = datetime.now(timezone.utc).strftime("%Y-%m")
        if m != self.month:
            self.month = m
            try:
                self.spent = float(self.store.kv_get(f"ai_usd:{m}") or 0)
            except (TypeError, ValueError):
                self.spent = 0.0

    # -- 1.53, retired in 1.54: the 10-minute check (kept, not called) ---------------------------------------------
    def check(self, items, retry=False):
        """One check of the posts (`items`: the queue's (post, near, home, stored)): grouped by the oblast they concern,
        in calls of at most MAX_CHECK_POSTS posts. Returns the number of calls, or why none was made."""
        why = self._allowed(len(items))
        if why:
            self.skipped[why] = self.skipped.get(why, 0) + len(items)
            return why
        xs = [self._prep(*it) for it in sorted(items, key=lambda it: it[0].get("ts") or "")]
        groups = OrderedDict()
        for x in xs:
            groups.setdefault(x["uid"], []).append(x)
        chunks, cur, size = [], [], 0
        for uid, part in groups.items():
            for i in range(0, len(part), MAX_CHECK_POSTS):
                sl = part[i:i + MAX_CHECK_POSTS]
                if cur and size + len(sl) > MAX_CHECK_POSTS:
                    chunks.append(cur)
                    cur, size = [], 0
                cur.append((uid, sl))
                size += len(sl)
        if cur:
            chunks.append(cur)
        failed = []
        for blocks in chunks:
            if self._check_call(blocks) == "error" and not retry:
                failed += [x["item"] for _, sl in blocks for x in sl]
        if failed:                                        # once more at the next check (a timeout, a busy provider)
            with self.cond:
                self.q.extendleft(reversed(failed))
        return len(chunks)

    def _prep(self, post, near=(), home=None, stored=True):
        ch, full = post["channel"], mask(post["text"])
        home = home if home not in ("", "ua") else None
        cands = candidates(self.geo, full, ch, home, near, self.oblast_names)
        marks = self.rules_fn(ch, full, list(near)) if stored else []
        uids = [m.get("oblast_uid") for m in marks if m.get("oblast_uid")]
        for _, key, _ in cands:
            if key.startswith("o") and key[1:].isdigit():
                uids.append(key[1:])
            else:
                pl = place_of(self.geo, key)
                if pl:
                    uids.append(pl[2])
        uids.append(home)
        uid = next((u for u in uids if u and u in self.oblast_names), "")
        return {"item": (post, near, home, stored), "post": post, "ch": ch, "full": full, "text": full[:CHECK_TEXT],
                "stored": stored, "cands": cands, "marks": marks, "uid": uid,
                "home": self.oblast_names.get(home) if home else None,
                "near": [self.oblast_names[u] for u in dict.fromkeys(near or ()) if u in self.oblast_names]}

    def _check_call(self, blocks):
        gid, lines_c, n = {}, OrderedDict(), 0
        for _, xs in blocks:
            for x in xs:
                n += 1
                x["label"], x["gc"] = f"p{n}", []
                for _, key, lab in x["cands"]:
                    if key.startswith("o") and key[1:].isdigit():
                        g = key
                    else:
                        g = gid.setdefault(key, f"c{len(gid) + 1}")
                    lines_c.setdefault(g, lab)
                    x["gc"].append((g, key, lab))
        uids = [u for u, _ in blocks if u]
        on_map, tags = {}, ()
        if self.map_fn:
            try:
                on_map, tags = self.map_fn(uids)
            except Exception as e:
                self.log("ai reader: no map context:", type(e).__name__)
        allx = [x for _, xs in blocks for x in xs]
        window = f"{_hm(allx[0]['post'].get('ts'))}–{_hm(allx[-1]['post'].get('ts'))} Kyiv time" if allx else ""
        text = check_text([(f"o{u}" if u else "", self.oblast_names.get(u, ""), on_map.get(u, []), [
            _p(x["label"], _hm(x["post"].get("ts")), x["ch"], x["text"], parser_lines(x["marks"]) if x["stored"] else None,
               [g for g, _, _ in x["gc"]], x["home"], x["near"]) for x in xs]) for u, xs in blocks],
            "\n".join(f"{g} | {lab}" for g, lab in sorted(lines_c.items(), key=lambda kv: (kv[0][0] != "c", int(kv[0][1:]) if kv[0][1:].isdigit() else 0))),
            window)
        msgs = check_messages(text, cache=self.model().startswith("anthropic/"))
        t0 = time.time()
        res = self.call(msgs, kind="check")
        ms = int((time.time() - t0) * 1000)
        self.checks += 1
        cid = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{self.checks % 1000:03d}"
        row = {"id": cid, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "first": allx[0]["post"].get("ts"),
               "last": allx[-1]["post"].get("ts"), "posts": len(allx), "oblasts": uids, "model": res.get("model") or self.model(),
               "prompt_v": CHECK_VERSION + ("p" if res.get("way") == 1 else ""), "ms": ms, "tok_in": res.get("tok_in"),
               "tok_out": res.get("tok_out"), "cost": res.get("cost") or 0, "error": res.get("error")}
        if res.get("error"):
            self._save_check(row)
            return "error"
        out = res["out"] if isinstance(res.get("out"), dict) else {}
        by = {}
        for f in out.get("findings") or []:
            if isinstance(f, dict) and f.get("finding") in FINDINGS:
                by.setdefault(str(f.get("post") or ""), []).append(f)
        found = {}
        for x in allx:
            targets, meta, dropped = [], [], 0
            wheres = {_where_rules(m) for m in x["marks"]} - {""}
            for f in by.get(x["label"], []):
                k, why = f["finding"], str(f.get("why") or "")[:200]
                if k == "not_sky":
                    if x["marks"]:
                        meta.append({"f": k, "why": why})
                    else:
                        dropped += 1               # nothing drawn: nothing to set aside
                    continue
                ts, d = validate({"targets": [find_target(f) if "target" not in f else f["target"]]}, x["full"], x["gc"], tags)
                dropped += d
                if not ts:
                    continue
                pick_namesakes(ts, x["gc"], self.geo, anchors_of(self.geo, x["marks"], x["item"][2], x["ch"]))
                t = ts[0]
                if k == "missed" and t.get("place") and _canon(t["place"]) in wheres:
                    k = "facts"                    # the rules have it at that place: what it adds are facts
                t["f"], t["why"] = k, why
                targets.append(t)
                meta.append({"f": k, "why": why, "t": len(targets) - 1})
            kinds = [m["f"] for m in meta]
            for k in kinds:
                found[k] = found.get(k, 0) + 1
            verdict = check_verdict(kinds, x["marks"])
            self._remember(x["post"]["post_id"], targets or None)
            try:
                self.store.ai_save({"post_id": x["post"]["post_id"], "ts": x["post"].get("ts"), "channel": x["ch"], "text": x["full"],
                                    "stored": 1 if x["stored"] else 0, "model": row["model"], "prompt_v": row["prompt_v"],
                                    "ms": None, "tok_in": None, "tok_out": None, "cost": 0, "verdict": verdict,
                                    "rules": summarise_rules(x["marks"]), "ai": {"targets": targets, "findings": meta, "uncertain": None},
                                    "dropped": dropped, "error": None, "chk": cid})
            except Exception as e:
                self.log("ai reader: not saved:", type(e).__name__)
        ok = {f"o{u}" for u in uids}
        found["returned"] = len(out.get("findings") or [])     # 1.53.4: what it gave, before the checks against the posts
        row["findings"] = found
        row["notes"] = [{"oblast": str(n_.get("oblast")), "note": str(n_.get("note") or "").strip()[:600]}
                        for n_ in out.get("notes") or [] if isinstance(n_, dict) and str(n_.get("oblast")) in ok
                        and str(n_.get("note") or "").strip()]
        row["uncertain"] = str(out.get("uncertain") or "")[:400] or None
        if res.get("partial"):                 # 1.53.1: what came complete was kept; say what was lost
            row["uncertain"] = f"answer {res['partial']}: the findings after the cut are lost" + (f" — {row['uncertain']}" if row["uncertain"] else "")
        self._save_check(row)
        return "ok"

    def ask_text(self, system, text, kind="text"):
        """1.53: one request for words (the night's report): {"out": text, …} or {"error": …}. Within the budget.
        1.58.37: `kind` "period" for several nights (more room); an answer cut off before its first word is asked once
        more with MAX_OUT_RETRY, and what both cost is counted."""
        why = self._allowed(0)
        if why:
            return {"error": why}
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": text}]
        res = self._request(msgs, 1, kind)
        if res.get("cut"):
            res2 = self._request(msgs, 1, kind, max_out=MAX_OUT_RETRY)
            res2["cost"] = (res2.get("cost") or 0) + (res.get("cost") or 0)
            return res2
        return res

    def ask_bulletin(self, kind, text, span=""):
        """1.54: one bulletin — {"out": {"uk", "en", "fr"}, "cost", "tok_in", "tok_out", "model"} or {"error": …}. The
        three texts are cleaned (bulletin_clean); an answer without all three is an error."""
        why = self._allowed(0)
        if why:
            return {"error": why}
        res = self.call(bulletin_messages(kind, text, span), "bulletin:" + kind)
        if res.get("error"):
            return res
        out = bulletin_clean(res.get("out"), kind)
        if not out:
            self.last_error = "bulletin: a language missing"
            return dict(res, out=None, error="the answer lacks a language (uk, en, fr)")
        return dict(res, out=out)

    def _save_check(self, row):
        try:
            self.store.ai_check_save(row)
        except Exception as e:
            self.log("ai reader: check not saved:", type(e).__name__)

    # -- one post -----------------------------------------------------------------------------------------------
    def _allowed(self, n=1):
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
            self.n_hour += n
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
        # 1.52: a post the server set aside put nothing on the map — that is the rules' reading of it, not what the parser
        # would have made of it ("rules_only" for an advert the rules never drew was a false alarm about the rules)
        marks = self.rules_fn(ch, text, list(near)) if stored else []
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
        pick_namesakes(targets, cands, self.geo, anchors_of(self.geo, marks, home, ch))
        ai = summarise_ai(targets, getattr(self.geo, "PLACES", None))
        verdict = compare(rules, ai)
        self._save(post, text, stored, ms, res, {"targets": targets, "uncertain": (res["out"] or {}).get("uncertain")},
                   rules, dropped, verdict)
        return verdict

    # How the answer's shape is asked for: 0 — a strict JSON schema the provider enforces; 1 — the prompt and the
    # examples alone (the provider refused the schema: 1.50.2). Either way the server checks every fact (validate).
    WAYS = ("schema", "prompt")
    way = 0

    def call(self, msgs, kind="post"):
        """{"out": dict, "cost", "tok_in", "tok_out"} or {"error": "..."} — the one request to OpenRouter. A provider
        that refuses the request as asked (400) is asked once more the simpler way, which is kept if it works.
        `kind`: "post" (one post's reading) or "check" (1.53)."""
        res = self._request(msgs, self.way, kind)
        if res.get("code") == 400 and self.way == 0:
            res2 = self._request(plain(msgs), 1, kind)
            if not res2.get("error"):
                self.way = 1
                self.log("ai reader: the provider refused the JSON schema —", res["error"], "— answering by the prompt alone")
                return res2
            self.down_until = time.time() + 600       # refused both ways: no point asking again for every post
        elif res.get("code") == 400:
            self.down_until = time.time() + 600
        return res

    def _request(self, msgs, way, kind="post", max_out=None):
        # 1.50.1: only parameters every model that takes a JSON schema accepts. With require_parameters, one the model
        # does not take (claude-haiku-5.5 takes no `temperature`) leaves no provider at all: "HTTP 404: No endpoints".
        # `kind`: "post", "check" (1.50–1.53), "text" (the night's report), "bulletin:1h" / "bulletin:24h" (1.54)
        bk = kind.split(":", 1)[1] if kind.startswith("bulletin:") else None
        mx = MAX_OUT_BULLETIN[bk] if bk else {"check": MAX_OUT_CHECK, "text": MAX_OUT_REPORT, "period": MAX_OUT_PERIOD}.get(kind, MAX_OUT)
        mx = max_out or mx
        body = {"model": self.model(), "max_tokens": mx, "messages": msgs,
                "provider": {"require_parameters": True}, "usage": {"include": True}}
        if way == 0 and kind not in ("text", "period"):
            body["response_format"] = {"type": "json_schema", "json_schema": (
                {"name": "heimdall_bulletin", "strict": True, "schema": BULLETIN_SCHEMA} if bk
                else {"name": "heimdall_check", "strict": True, "schema": CHECK_SCHEMA} if kind == "check"
                else {"name": "heimdall_reading", "strict": True, "schema": SCHEMA})}
        req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={
            "Authorization": "Bearer " + self.key(), "Content-Type": "application/json", "X-Title": "Heimdall"})
        try:
            ctx = getattr(self, "ssl_ctx", None)
            with urllib.request.urlopen(req, timeout=BULLETIN_TIMEOUT * (2 if kind == "period" else 1) if (bk or kind in ("text", "period")) else 40,
                                        context=ctx) as r:
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
        if kind in ("text", "period"):                   # 1.53: the night's report — words, not JSON (1.58.37: a period's too)
            ch = (data.get("choices") or [{}])[0]
            text = (ch.get("message") or {}).get("content")
            if isinstance(text, list):                   # a provider that answers in parts
                text = "".join(p.get("text") or "" for p in text if isinstance(p, dict))
            text = text.strip() if isinstance(text, str) else ""
            if not text:
                # 1.58.37: say why — the thinking ran out the room (cut, asked again with more by ask_text), or the
                # provider stopped for its own reason
                out_n = usage.get("completion_tokens") or 0
                why = ch.get("native_finish_reason") or ch.get("finish_reason")
                cut = ch.get("finish_reason") == "length" or out_n >= mx
                err = (f"empty answer: the model used its {mx} tokens thinking and wrote nothing" if cut
                       else "empty answer" + (f" (the model stopped: {why}, {out_n} tokens out)" if why or out_n else ""))
                self.last_error = err
                return {"error": err, "cost": cost, "cut": cut, "tok_in": usage.get("prompt_tokens"), "tok_out": out_n}
            return {"out": text, "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens"),
                    "model": data.get("model") or self.model(), "way": way}
        try:
            out = _json_of(data["choices"][0]["message"]["content"])
        except Exception:
            # 1.52.1: the answer cut off at the length allowed is not a malformed answer — the dashboard says which
            cut = ((data.get("choices") or [{}])[0].get("finish_reason") == "length"
                   or (usage.get("completion_tokens") or 0) >= mx)
            err = f"cut off at {mx} tokens" if cut else "not JSON"
            raw = (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            part = salvage_check((((data.get("choices") or [{}])[0].get("message") or {}).get("content"))) if cut and kind == "check" else None
            if part:
                self.last_error = None
                return {"out": part, "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens"),
                        "model": data.get("model") or self.model(), "way": way, "partial": err}
            self.last_error = err
            # 1.53.4: how the answer began, for the dashboard — to see why it ran so long
            head = (" — began: " + raw[:300].replace("\n", " ")) if kind == "check" and isinstance(raw, str) and raw else ""
            return {"error": err + head, "cost": cost, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens")}
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
        chk = {}
        try:
            chk = self.store.ai_check_counts(self.month)
        except Exception:
            pass
        bl = {}
        try:
            bl = self.store.bulletin_counts(self.month)
        except Exception:
            pass
        return {"key": bool(self.key()), "enabled": self.enabled(), "reader_on": self.switched_on(), "model": self.model(),
                "prompt_v": BULLETIN_VERSION, "mode": "bulletins",
                **chk, **bl,
                "month": self.month, "usd_month": round(spent, 4), "cap_usd": self.cap(), "queued": len(self.q),
                "paused": time.time() < self.down_until, "last_error": self.last_error, "skipped": dict(self.skipped),
                "format": self.WAYS[self.way],
                **counts}
