"""1.58: the owner's private Telegram channel — a post for each target over Kyiv and Kyiv oblast, with a picture of the
map around it; 1.58.7: a new post for each new report of it, in reply to the one before, and a closing line.

The owner: "a small private Telegram channel that posts alerts like the channels we read, with a 'screenshot' of the
app where the drone is (Kyiv and Kyiv oblast only)"; of the ways asked, "the app's style, drawn on the server"
(app/mapshot.py). 1.58.7: "instead of editing the post, we need to add a screenshot every time — it's better to keep
track of what's going on"; "when the alarm is over, or it exploded or fell, or the threat is no longer here, we should
mark it too"; "no need to say the source of info".

Its rules (docs/SAFETY.md §the channel):
  - it repeats what the map shows and nothing more: the type and the place a post gave, a course only when a post
    stated one (a target town, compass words) — never a course the app worked out from two reports —, the height a
    post gave, "from channel posts, not radar"; not the channel a post came from (the owner: no need);
  - a target's last word is what the map shows of it: the outcome a post reported (shot down / landed, an explosion,
    lost from tracking, the area reported clear), in the app's own words and without the place it happened, or the
    official all-clear of the area it was in, or "no new reports since HH:MM". Never an air-defence position, never
    where a strike landed, and no picture is drawn of an outcome;
  - the official alerts are drawn as the app draws them; an all-clear is said only from the official data, after a
    minute without the alert (a flicker of the feed is no all-clear), and only for an alert this run saw;
  - the bot's token is the owner's: set by scripts/set-telegram-channel.bat into Fly's secrets (TG_BOT_TOKEN,
    TG_CHANNEL_ID), read from the environment, never written to the database, a log or an answer. The server's
    bot only posts in that one channel; it reads nothing (the channels are read as before).
"""
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

try:
    import mapshot
except Exception:  # pragma: no cover
    mapshot = None
try:
    import areas
except Exception:  # pragma: no cover
    areas = None

SCOPE = ("31", "14")                       # Kyiv city, Kyiv oblast
# 1.58.9, the owner: "for the Telegram bot we'll take a single source: t.me/chyste_nebo" — then, @chyste_nebo silent
# from 03:59 while kyiv_airdef and kievinfo_kyiv reported a drone towards Boryspil (1.58.12, his pick): "all the Kyiv
# sources". The channel posts the targets of the three Kyiv live trackers' reports alone — a target whose latest report
# is another channel's (the Air Force, a regional one) waits for theirs — and what became of them by their word (their
# outcomes). The official data (alerts, all-clears) stays the official.
SOURCES = ("chyste_nebo", "kyiv_airdef", "kievinfo_kyiv")
TYPES = ("drones", "ballistic_missiles", "cruise_missiles", "unspecified_missiles", "banderol_missiles",
         "supersonic_missiles", "unknown")
FRESH_S = 5 * 60                           # a report is posted only if it is this recent (no backlog)
UPDATE_EVERY_S = 60                        # 1.58.7: a target's new report is a new post, at most this often
END_AFTER_S = 5 * 60                       # gone from the map this long → its closing line ("no new reports")
CLEAR_AFTER_S = 60                         # an area's alert gone this long → its all-clear (a feed's flicker is not one)
OUTCOME_WINDOW_S = 40 * 60                 # kyiv.html linkStatus: an outcome up to 40 min after the target's report
KEEP_S = 24 * 3600                         # what the store remembers of the posts
BUDGET = 18                                # calls a minute (Telegram allows ~20 messages a minute in one channel)
TICK_S = 5
KV = "chan_posts"
AREA_KM = 35                               # the radius drawn round a target placed only in a part of the oblast
KV_ON = "chan_on"                          # 1.58.3: the dashboard's kill switch ("0" = off; anything else, or unset = on)
MSL_TYPES = ("ballistic_missiles", "cruise_missiles", "supersonic_missiles", "unspecified_missiles")

LABEL = {"drones": ("🛵", "Шахед"), "jet": ("🛩", "Реактивний дрон"), "ballistic_missiles": ("🚀", "Балістична ракета"),
         "cruise_missiles": ("🚀", "Крилата ракета"), "supersonic_missiles": ("🚀", "Надзвукова ракета (Х-22/32)"),
         "unspecified_missiles": ("🚀", "Ракета"), "banderol_missiles": ("🛩", "Бандероль (реактивний дрон)"),
         "unknown_dr": ("❔", "Ймовірно, дрон — тип не вказано"), "unknown": ("❔", "Дрон чи ракета — тип не вказано")}
COMPASS = ("північ", "північний схід", "схід", "південний схід", "південь", "південний захід", "захід", "північний захід")
ALT_STATE = {"low": "низько", "high": "високо", "descending": "знижується", "climbing": "набирає висоту"}
ALT_MAX_S = 4 * 60                         # 1.58.9: a height an earlier report gave, at most this old (i18n.js ALT_MAX_MIN)
# a course the app worked out itself (two reports of a live channel; a destination a later post gave a carried
# mark) is drawn on the map with its own caveat, but the channel says only what a post said
DERIVED = ("bearing between the two latest reports", "the destination a later post named")
WARN = "⚠️ З дописів каналів, не радар. Сирена й офіційна тривога — головне."
# 1.58.7: what became of a target, in the Tactical page's own Ukrainian words (i18n.js st_down … st_clear — tests check)
OUTCOME = {"down": ("⬇️", "Збито / Приземлено"), "impact": ("💥", "Вибух (влучання або перехоплення — невідомо)"),
           "lost": ("❔", "Локаційно втрачено"), "clear": ("✅", "Повідомлено: у районі чисто")}
# the official alert areas a target can be in: Kyiv city, a raion of Kyiv oblast, "14:*" — somewhere in the oblast
AREA_UK = {"kyiv-city": "Київ", "brovary": "Броварський район", "boryspil": "Бориспільський район",
           "bucha": "Бучанський район", "vyshhorod": "Вишгородський район", "obukhiv": "Обухівський район",
           "bila-tserkva": "Білоцерківський район", "fastiv": "Фастівський район", "14:*": "Київщина"}
OBL14 = ("brovary", "boryspil", "bucha", "vyshhorod", "obukhiv", "bila-tserkva", "fastiv")
# kyiv.html's projection (static/kyiv-map.json): kilometres east and south of Kyiv's centre
KM_C, KM_X, KM_Y = (30.52, 50.45), 70.67939956918688, 111.0


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Kyiv")
    except Exception:
        return timezone(timedelta(hours=3))


def parse_ts(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


def hhmm(t):
    return datetime.fromtimestamp(t, _tz()).strftime("%H:%M")


def report_t(m):
    return parse_ts(m.get("pos_ts")) or parse_ts(m.get("ts")) or 0


def eligible(m):
    """A target the channel shows: over Kyiv or Kyiv oblast, at a place a post named — where it is, or the town it is
    heading for ("→ Київ", drawn there by the app as an approach) —, flying: no outcome, no faded or superseded mark,
    no oblast-wide guess, no reading that still waits for its context."""
    if m.get("oblast_uid") not in SCOPE or m.get("lon") is None or m.get("lat") is None:
        return False
    if m.get("channel") not in SOURCES:          # 1.58.9: its sources only (1.58.12: the three Kyiv trackers)
        return False
    if m.get("type") not in TYPES or m.get("status") or m.get("stale") or m.get("superseded_by"):
        return False
    if m.get("needs_context") or m.get("candidates"):
        return False
    if part_of_oblast(m):                       # 1.58.6: "на сході Київщини" — the part the post named, as such
        return True
    place = (m.get("place") or "").strip().lstrip("→").strip()           # "→ Київ": the town it is heading for
    return bool(place) and place.lower() not in ("область", "київщина", "київська область")


QUAD_UK = {"n": "Північ", "s": "Південь", "e": "Схід", "w": "Захід", "ne": "Північний схід", "nw": "Північний захід",
           "se": "Південний схід", "sw": "Південний захід"}


def part_of_oblast(m):
    """The part of Kyiv oblast a post placed it in, with no town ("на сході Київщини") — its key (n, se, …) or None."""
    q = ((m.get("evidence") or {}).get("position") or {}).get("quad")
    return q if m.get("place") == "область" and m.get("oblast_uid") == "14" and q in QUAD_UK else None


def place_text(m):
    q = part_of_oblast(m)
    return QUAD_UK[q] + " Київщини" if q else (m.get("place") or "")


def key_of(m):
    tag = m.get("tag") or {}
    if tag.get("night") and tag.get("id"):
        return f"{tag['night']}{tag['id']}"
    return str(m.get("id"))


def approach(m):
    """Only where it is heading was said ("Балістика на Київ", "шахед на Бровари"): the app draws it at that town."""
    return bool(m.get("approach") or m.get("dest_only") or (m.get("place") or "").strip().startswith("→"))


def stated_course(m):
    """The course a post stated, in words — or None. A target town is said as such; compass words as a direction."""
    if approach(m):
        t = m.get("target") or (m.get("place") or "").strip().lstrip("→").strip()
        return "Курс на " + str(t) if t else None
    if m.get("target"):
        return "Курс на " + str(m["target"])
    ev = (m.get("evidence") or {}).get("heading") or {}
    if m.get("heading") is None or not ev.get("matched") or ev.get("confidence") not in ("high", "medium"):
        return None
    if any(s in (ev.get("method") or "") for s in DERIVED) or (ev.get("method") or "").startswith("derived"):
        return None
    return "Курс: " + COMPASS[int(((m["heading"] % 360) + 22.5) // 45) % 8]


def label_of(m):
    t = m.get("type")
    if t == "drones" and m.get("jet"):
        return LABEL["jet"]
    if t == "unknown":           # kyiv.html's unkKind: a probable drone, unless a missile is on the map near it
        return LABEL["unknown_dr" if m.get("_drone") else "unknown"]
    return LABEL.get(t, LABEL["unknown"])


def stated_alt(m):
    """(the height a post gave, when — None for this report) — this report's, else (1.58.9) the latest an earlier report
    of the same track gave, by one of its sources' word. The owner: "I see the altitude is not shown most of the time":
    @chyste_nebo gives a height in a post of its own ("3800", "Бондарня другий 4600") and its next report names a place
    only, so the height said two minutes ago was dropped from the post. It is carried, with its time — and, as on the
    maps (SAFETY.md "A height is shown for 4 minutes at most", ALT_MAX_MIN), only when it was said at most 4 minutes
    before this report: older, it is probably no longer its height. Never guessed."""
    a = m.get("alt") or {}
    if isinstance(a, dict) and (a.get("m") or a.get("state") in ALT_STATE):
        return a, None
    t = report_t(m)
    for h in reversed(m.get("history") or []):
        if h.get("channel") not in SOURCES:
            continue
        if h.get("alt_m") or h.get("alt_state") in ALT_STATE:
            ht = parse_ts(h.get("ts"))
            if ht is None or not t or t - ht > ALT_MAX_S:
                return None, None                 # the latest height it gave is too old: none
            return {"m": h.get("alt_m"), "state": h.get("alt_state")}, ht
    return None, None


def head_line(m):
    emo, name = label_of(m)
    n = m.get("count")
    return f"{emo} <b>{esc(name)}{' ×' + str(n) if isinstance(n, int) and n > 1 else ''}</b> · {esc(place_text(m))}"


def caption(m, first_t, public_url):
    """A report's post (Telegram HTML): only what the post said. 1.58.7: not the channel it came from (the owner: "no
    need to say the source of info"); a target held off the map (server.State._hold) says so."""
    lines = [head_line(m)]
    c = stated_course(m)
    if c:
        lines.append(f"➡️ {esc(c)} (так у дописі)")
    if approach(m):
        lines.append("📍 Де саме зараз — у дописі не сказано")
    elif part_of_oblast(m):
        lines.append("📍 Точного місця в дописі немає — лише частина області")
    if m.get("held"):
        lines.append("⚪ Офіційної тривоги там поки немає — значка на мапі немає, доки її не оголосять")
    alt, at = stated_alt(m)
    if alt:
        lines.append("↕️ Висота: " + (f"~{int(alt['m'])} м" if alt.get("m") else ALT_STATE[alt["state"]])
                     + (f" (у дописі о {hhmm(at)})" if at else " (у дописі)"))
    t = report_t(m)
    when = hhmm(t) if t else "?"
    if first_t and t and hhmm(first_t) != when:
        when += f" (перший допис {hhmm(first_t)})"
    lines.append(f"🕒 {when}")
    lines.append(WARN)
    lines.append(f'🗺 <a href="{esc(public_url.rstrip("/"))}/m">Мапа Heimdall</a>')
    return "\n".join(lines)[:1024]


def end_text(m, end):
    """1.58.7: a target's closing line, in reply to its last post — what became of it, as the map shows it.
    `end`: {"k": "quiet", "t": its last report} | {"k": "outcome", "status": …, "t": the outcome's report}."""
    if end.get("k") == "outcome" and end.get("status") in OUTCOME:
        emo, word = OUTCOME[end["status"]]
        first = f"{emo} <b>{esc(word)}</b> — так у дописі о {hhmm(end['t'])}"
    else:
        first = f"⏹ Нових дописів після {hhmm(end['t'])} немає"
    return first + "\n" + head_line(m)


def allclear_text(area, t):
    """1.58.7: the official all-clear of an area the channel had a target in — the official data's, never a post's."""
    return f"✅ <b>Відбій тривоги</b> о {hhmm(t)} · {esc(AREA_UK.get(area, area))} (офіційно)"


def signature(m):
    """What a new post is for: a new place, a new course, a new count or height, held or drawn — not a new id of the
    same report."""
    alt = stated_alt(m)[0] or {}
    hist = [(round(h.get("lon") or 0, 3), round(h.get("lat") or 0, 3)) for h in (m.get("history") or [])[-6:]]
    return json.dumps([round(m["lon"], 3), round(m["lat"], 3), m.get("place"), stated_course(m), m.get("count"),
                       m.get("type"), m.get("jet"), alt.get("m") or alt.get("state"), hist,
                       int(report_t(m) // 60), bool(m.get("held"))], ensure_ascii=False)


def area_of(m):
    """The official alert area a channel target is in, for its all-clear: "kyiv-city", a raion of Kyiv oblast, "14:*"
    for a target placed only in a part of the oblast — or None (no area of Kyiv or its oblast)."""
    if m.get("lon") is None or m.get("lat") is None:
        return None
    if part_of_oblast(m):
        return "14:*"
    a = areas.area_at(m["lon"], m["lat"]) if areas else None
    if not a:
        return None
    if a[0] == "31":
        return "kyiv-city"
    return a[1] if a[0] == "14" and a[1] in AREA_UK else None


def area_on(area, fills):
    """Is this area (a raion key of Kyiv oblast, "14:*" for the whole oblast) under an official alert in `fills`?
    1.58.24: a hromada's alert ("hr:14:<id>", 1.58.16) keeps its raion on — the raion's own alert ending while one of
    its hromadas stays under alert is no all-clear for the raion."""
    on = set(fills)
    for k in fills:
        if k.startswith("hr:14:"):
            r = areas.hromada_raion("14", k[6:]) if areas else None
            on.add(r or "14:hr")                      # no outline known: still somewhere in Kyiv oblast
    if area == "14:*":
        return any(k in on for k in OBL14 + ("14:hr",))
    return area in on


def _km(m):
    return ((m["lon"] - KM_C[0]) * KM_X, -(m["lat"] - KM_C[1]) * KM_Y)


def link_outcomes(marks, extra=()):
    """kyiv.html's linkStatus, the same rules: each outcome a post reported (down, impact, lost, clear) closes the one
    target it most plausibly ends — same family, reported 2 min before to 40 min after the target's report, within
    60 km and (with a course, beyond 8 km) roughly ahead of it, "clear" within 25 km; the nearest and soonest.
    `extra`: (key, mark) of targets the channel posted that the map no longer has (gone, or faded out). → {key: outcome}"""
    tracks = {}
    for m in marks:
        if not m.get("status") and m.get("lon") is not None and m.get("lat") is not None:
            k = key_of(m)
            if k not in tracks or (parse_ts(m.get("ts")) or 0) > (parse_ts(tracks[k].get("ts")) or 0):
                tracks[k] = m
    for k, m in extra:
        if k not in tracks and m.get("lon") is not None and m.get("lat") is not None:
            tracks[k] = m
    ended = {}
    for s_ in marks:
        if s_.get("status") not in OUTCOME or s_.get("lon") is None or s_.get("lat") is None:
            continue
        st = parse_ts(s_.get("ts"))
        if st is None:
            continue
        sx, sy = _km(s_)
        best = None
        for k, t in tracks.items():
            tt = parse_ts(t.get("ts"))
            if k in ended or tt is None:
                continue
            dt = (st - tt) / 60
            if dt < (0 if s_.get("status") == "lost" else -2) or dt > 40:      # 1.58.29: reported after "lost": found again
                continue
            if (t.get("type") == "drones") != (s_.get("type") == "drones"):
                continue
            tx, ty = _km(t)
            d = math.hypot(sx - tx, sy - ty)
            if d > 60:
                continue
            if t.get("heading") is not None and d > 8:
                b = (math.degrees(math.atan2(sx - tx, -(sy - ty))) + 360) % 360
                if abs(((t["heading"] - b) + 540) % 360 - 180) > 55:
                    continue
            if s_.get("status") == "clear" and d > 25:
                continue
            score = d + dt * 0.5
            if best is None or score < best[0]:
                best = (score, k)
        if best:
            ended[best[1]] = s_
    return ended


class TgError(Exception):
    def __init__(self, code, desc, retry_after=None):
        super().__init__(f"{code} {desc}")
        self.code, self.desc, self.retry_after = code, desc, retry_after


class BotAPI:
    """The few Bot API calls the channel needs. The token is in the URL Telegram asks for: it is never logged, and
    every error leaving this class carries the method's name and Telegram's description, never the URL."""
    BASE = "https://api.telegram.org"

    def __init__(self, token, ssl_ctx=None, timeout=30):
        self._token, self.ssl_ctx, self.timeout = token, ssl_ctx, timeout

    def call(self, method, fields, files=None):
        if files:
            body, ctype = _multipart(fields, files)
        else:
            body, ctype = json.dumps(fields).encode(), "application/json"
        req = urllib.request.Request(f"{self.BASE}/bot{self._token}/{method}", data=body,
                                     headers={"Content-Type": ctype, "User-Agent": "heimdall-channel/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_ctx) as r:
                out = json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                out = json.loads(e.read() or b"{}")
            except ValueError:
                out = {"ok": False, "error_code": e.code, "description": "HTTP error"}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TgError(0, f"{method}: network — {type(e).__name__}") from None
        if not out.get("ok"):
            ra = (out.get("parameters") or {}).get("retry_after")
            raise TgError(out.get("error_code") or 0, f"{method}: {out.get('description') or 'failed'}", ra)
        return out.get("result")


def _multipart(fields, files):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode() + v.encode() + b"\r\n")
    for k, (name, data, ctype) in files.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                     f"Content-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


class ChannelPoster(threading.Thread):
    """Every few seconds: the marks of the moment → a post for a new target, a new post (in reply to its last one) for
    a target reported again, a closing line for a target that came down or is gone, an all-clear for its area."""

    def __init__(self, state, token, chat_id, public_url, api=None, shot=None, log=print, clock=time.time,
                 kv=None, ssl_ctx=None, sat=None):
        super().__init__(daemon=True, name="channel")
        self.state, self.chat_id, self.public_url = state, chat_id, public_url
        self.api = api or BotAPI(token, ssl_ctx)
        self.log, self.clock = log, clock
        self.kv = kv or getattr(state, "store", None)
        if shot is None and mapshot is not None and mapshot.Image is not None:
            try:
                shot = mapshot.MapShot(sat=sat)       # 1.58.2: over the app's satellite picture
            except Exception as e:
                log("channel: no map picture —", type(e).__name__, e)
                shot = None
        self.shot = shot
        self.calls = []                    # times of the last minute's calls
        self.missiles = []                 # (lon, lat) of the missiles on the map, this pass
        self.cur = {}                      # the targets the channel shows, this pass (key → mark)
        # 1.58.7: the areas under an official alert this run has seen with a channel target in them (area → keys), and
        # since when an area's alert has been gone. Kept in memory only: after a restart an area must be seen under
        # alert again before its all-clear is said — the first passes after a start have no alerts read yet
        self.watch = {}
        self.clear_since = {}
        self.pause_until = 0.0
        self.stats = {"posted": 0, "updates": 0, "closed": 0, "allclear": 0, "errors": 0, "last_error": None,
                      "last_post": None, "failing": False}
        self.posts = self._load()

    # ---- the store -----------------------------------------------------------------------------------------------
    def _load(self):
        try:
            raw = self.kv.kv_get(KV) if self.kv else None
            posts = json.loads(raw) if raw else {}
        except (ValueError, TypeError, AttributeError):
            posts = {}
        cut = self.clock() - KEEP_S
        return {k: v for k, v in posts.items() if isinstance(v, dict) and (v.get("seen") or 0) >= cut}

    def _save(self):
        if self.kv:
            try:
                self.kv.kv_set(KV, json.dumps(self.posts, ensure_ascii=False))
            except Exception as e:
                self.log("channel: could not save its posts —", type(e).__name__)

    # ---- the budget ----------------------------------------------------------------------------------------------
    def _room(self):
        now = self.clock()
        self.calls = [t for t in self.calls if now - t < 60]
        return now >= self.pause_until and len(self.calls) < BUDGET

    def _call(self, method, fields, files=None):
        self.calls.append(self.clock())
        try:
            r = self.api.call(method, fields, files)
        except TgError as e:
            if e.retry_after:
                self.pause_until = self.clock() + float(e.retry_after) + 1
            self.stats.update(errors=self.stats["errors"] + 1, last_error=e.desc[:200], failing=True)
            self.log("channel:", e.desc[:200])
            raise
        self.stats["failing"] = False
        return r

    def health(self):
        """The dashboard's row (/api/health → official): working or not, and what it did — counts only."""
        st = self.stats
        ok = not st["failing"]                # the last call to Telegram worked (or none was needed yet)
        return {"name": "telegram channel (posting)", "ok": ok, "last": st["last_post"],
                "error": None if ok else st["last_error"],
                "note": ("switched OFF on the dashboard · " if not self.enabled() else "")
                        + f"targets {st['posted']} · new reports {st['updates']} · closed {st['closed']}"
                        + f" · all-clears {st['allclear']}"
                        + ("" if self.shot else " · text only (no Pillow)")}

    # ---- one pass ------------------------------------------------------------------------------------------------
    def marks(self):
        return self.state.markers_now()

    def active(self):
        try:
            return self.state.snapshot().get("active") or []
        except Exception:
            return []

    def picture(self, m, active):
        if not self.shot:
            return None
        try:
            k = key_of(m)
            # 1.58.5: what else is in the sky — as the map shows it (a target held off the map is not drawn)
            others = [o for kk, o in (self.cur or {}).items() if kk != k and not o.get("held")]
            if part_of_oblast(m):                 # 1.58.6: a part of the oblast is an area, not a point
                m = dict(m, place=place_text(m), _area_km=AREA_KM)
            if m.get("held"):                     # 1.58.7: no silhouette at a place it has not been seen at
                m = dict(m, _held=True)
            alt, at = stated_alt(m)               # 1.58.9: a height an earlier report gave, with its time
            if alt and at:
                m = dict(m, alt=alt, _alt_t=hhmm(at))
            return self.shot.render(m, active, hhmm(report_t(m) or self.clock()),
                                    ray=stated_course(m) is not None and not approach(m), missiles=self.missiles,
                                    others=others)
        except Exception as e:
            self.log("channel: picture failed —", type(e).__name__, e)
            return None

    def enabled(self):
        """The dashboard's switch (Live tab): off, the channel makes no call at all — no post, no closing line, no
        all-clear. Read on every pass, so it takes effect within one (5 s). Unreadable: on, as before the switch existed."""
        try:
            return (self.kv.kv_get(KV_ON) if self.kv else None) != "0"
        except Exception:
            return True

    def tick(self):
        if not self.enabled():
            self.watch, self.clear_since = {}, {}   # switched on again: no all-clear of an alert that ended meanwhile
            return
        now = self.clock()
        marks = self.marks() or []
        self.missiles = [(m["lon"], m["lat"]) for m in marks if m.get("type") in MSL_TYPES and not m.get("status")
                         and m.get("lon") is not None and m.get("lat") is not None]
        cur = {}
        for m in marks:
            if eligible(m):
                k = key_of(m)
                if k not in cur or report_t(m) > report_t(cur[k]):
                    cur[k] = m
        for k, m in cur.items():
            if m.get("type") == "unknown":
                cur[k] = dict(m, _drone=mapshot.as_drone(m, self.missiles) if mapshot else True)
        self.cur = cur
        # what the map says became of the targets: the outcomes, linked as kyiv.html links them, the channel's
        # targets the map no longer has included (their last report, kept with the post)
        extra = [(k, p["m"]) for k, p in self.posts.items() if k not in cur and (p.get("m") or {}).get("lon") is not None
                 and now - (p.get("last") or 0) <= OUTCOME_WINDOW_S + 120]
        outcomes = link_outcomes([m for m in marks if m.get("channel") in SOURCES], extra)   # 1.58.9: their word only
        active = self.active()
        fills = mapshot.alert_fill(active) if mapshot else {}
        changed = False
        # 1. new targets first, the most recent report first — not one the map already shows as ended
        for k, m in sorted(cur.items(), key=lambda kv: -report_t(kv[1])):
            p = self.posts.get(k)
            if p and not p.get("ended"):
                p["seen"] = now
                continue
            if p and p.get("ended") and report_t(m) <= (p.get("last") or 0):
                continue                               # the same report, already closed
            if k in outcomes or now - report_t(m) > FRESH_S or not self._room():
                continue
            if self._send(k, m, active, reply_to=(p or {}).get("mid")):
                changed = True
        # 2. what became of them: an outcome a post reported (once, even after "no new reports")
        for k, s_ in outcomes.items():
            p = self.posts.get(k)
            if not p or p.get("outcome") or (p.get("ended") and (p.get("end") or {}).get("k") != "quiet"):
                continue
            if not self._room():
                break
            if self._end(k, p, {"k": "outcome", "status": s_.get("status"), "t": parse_ts(s_.get("ts")) or now}):
                changed = True
        # 3. the official all-clear of an area a target was in
        if self._allclears(now, fills):
            changed = True
        # 4. targets reported again: a new post, in reply to the last one, at most every UPDATE_EVERY_S
        for k, m in sorted(cur.items(), key=lambda kv: (self.posts.get(kv[0]) or {}).get("sent") or 0):
            p = self.posts.get(k)
            if not p or p.get("ended") or k in outcomes or p.get("sig") == signature(m):
                continue
            if now - (p.get("sent") or 0) < UPDATE_EVERY_S or now - report_t(m) > FRESH_S:
                continue
            if not self._room():
                break
            if self._send(k, m, active, reply_to=p.get("mid"), update=True):
                changed = True
        # 5. targets gone from the map: "no new reports since"
        for k, p in list(self.posts.items()):
            if p.get("ended") or k in cur or now - (p.get("seen") or 0) < END_AFTER_S:
                continue
            if not self._room():
                break
            if self._end(k, p, {"k": "quiet", "t": p.get("last") or p.get("first") or now}):
                changed = True
        cut = now - KEEP_S
        for k in [k for k, p in self.posts.items() if (p.get("seen") or 0) < cut]:
            del self.posts[k]
            changed = True
        if changed:
            self._save()

    def _allclears(self, now, fills):
        """An area under an official alert with a channel target in it is watched; a minute after its alert is gone
        (the official data), one line says so, in reply to the last post of a target there, and the targets still open
        there are closed by it."""
        changed = False
        for k, p in self.posts.items():
            a = p.get("area")
            if a and not p.get("ended") and area_on(a, fills):
                self.watch.setdefault(a, set()).add(k)
        for a in list(self.watch):
            if area_on(a, fills):
                self.clear_since.pop(a, None)
                continue
            t0 = self.clear_since.setdefault(a, now)
            if now - t0 < CLEAR_AFTER_S:
                continue
            keys = [k for k in self.watch[a] if k in self.posts]
            if keys:
                if not self._room():
                    continue
                last = max(keys, key=lambda k: self.posts[k].get("sent") or 0)
                try:
                    r = self._call("sendMessage", self._reply({"chat_id": self.chat_id, "text": allclear_text(a, t0),
                                                               "parse_mode": "HTML",
                                                               "link_preview_options": {"is_disabled": True}},
                                                              self.posts[last].get("mid")))
                except TgError:
                    continue
                self.stats["allclear"] += 1
                for k in keys:
                    p = self.posts[k]
                    if not p.get("ended") and p.get("area") == a:
                        p.update(ended=True, end={"k": "allclear", "t": t0, "area": a})
                        self.stats["closed"] += 1
                if (r or {}).get("message_id"):
                    self.posts[last]["mid"] = r["message_id"]
            del self.watch[a]
            self.clear_since.pop(a, None)
            changed = True
        return changed

    @staticmethod
    def _reply(fields, mid):
        if mid:
            fields["reply_parameters"] = {"message_id": mid, "allow_sending_without_reply": True}
        return fields

    def _send(self, k, m, active, reply_to=None, update=False):
        """A post for this report of the target — 1.58.7: always a new one, never an edit of the last (the owner:
        "better to keep track of what's going on"), in reply to the target's last post."""
        t = report_t(m)
        p = self.posts.get(k) if update else None
        first = (p or {}).get("first") or t
        cap = caption(m, first, self.public_url)
        png = self.picture(m, active)
        try:
            if png:
                r = self._call("sendPhoto", self._reply({"chat_id": self.chat_id, "caption": cap, "parse_mode": "HTML"},
                                                        reply_to), {"photo": ("map.jpg", png, "image/jpeg")})
            else:
                r = self._call("sendMessage", self._reply({"chat_id": self.chat_id, "text": cap, "parse_mode": "HTML",
                                                           "link_preview_options": {"is_disabled": True}}, reply_to))
        except TgError:
            return False
        now = self.clock()
        mid = (r or {}).get("message_id")
        if update:
            p.update(mid=mid or p.get("mid"), sig=signature(m), last=t, seen=now, sent=now, m=_slim(m),
                     area=area_of(m), n=(p.get("n") or 1) + 1)
            self.stats["updates"] += 1
        else:
            self.posts[k] = {"mid": mid, "first_mid": mid, "sig": signature(m), "first": t, "last": t, "seen": now,
                             "sent": now, "m": _slim(m), "area": area_of(m), "n": 1}
            self.stats["posted"] += 1
        self.stats["last_post"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        return True

    def _end(self, k, p, end):
        """Its closing line, in reply to its last post: what the map shows became of it. An outcome after a quiet
        close is said too, once."""
        try:
            r = self._call("sendMessage", self._reply({"chat_id": self.chat_id, "text": end_text(p.get("m") or {}, end),
                                                       "parse_mode": "HTML",
                                                       "link_preview_options": {"is_disabled": True}}, p.get("mid")))
        except TgError:
            return False
        if not p.get("ended"):
            self.stats["closed"] += 1
        p.update(ended=True, end=end, mid=(r or {}).get("message_id") or p.get("mid"))
        if end.get("k") == "outcome":
            p["outcome"] = True
        return True

    def run(self):
        self.log(f"channel: posting the targets over Kyiv and Kyiv oblast ({'with' if self.shot else 'without'} the map picture)")
        while True:
            try:
                self.tick()
            except Exception as e:                    # the channel never stops the rest of the server
                self.stats.update(errors=self.stats["errors"] + 1, failing=True,
                                  last_error=f"{type(e).__name__}: {str(e)[:160]}")
                self.log("channel: tick failed —", type(e).__name__, str(e)[:160])
            time.sleep(TICK_S)


def _slim(m):
    """What a closing line and the outcome's link need of a mark, kept with the post (no text of the post, no evidence
    beyond the course and the part of the oblast)."""
    keep = ("type", "jet", "_drone", "count", "place", "target", "dest_only", "approach", "heading", "alt", "ts",
            "pos_ts", "lon", "lat", "oblast_uid", "held")
    out = {k: m.get(k) for k in keep if m.get(k) is not None}
    ev = m.get("evidence") or {}
    hv, pv = ev.get("heading"), ev.get("position") or {}
    if hv or pv.get("quad"):
        out["evidence"] = {}
        if hv:
            out["evidence"]["heading"] = {k: hv.get(k) for k in ("matched", "method", "confidence")}
        if pv.get("quad"):
            out["evidence"]["position"] = {"quad": pv["quad"]}
    return out


def configured(env=None):
    env = os.environ if env is None else env
    return bool(env.get("TG_BOT_TOKEN") and env.get("TG_CHANNEL_ID"))


def start(state, log=print, ssl_ctx=None, env=None, sat=None):
    """Called by app/server.py's main(): the channel runs only when the owner has set both secrets."""
    env = os.environ if env is None else env
    if not configured(env):
        return None
    url = env.get("PUBLIC_URL") or "https://kyiv-air-watch-gb.fly.dev"
    p = ChannelPoster(state, env["TG_BOT_TOKEN"], env["TG_CHANNEL_ID"], url, log=log, ssl_ctx=ssl_ctx, sat=sat)
    p.start()
    return p
