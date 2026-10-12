"""1.58: the owner's private Telegram channel — one post per target over Kyiv and Kyiv oblast, with a picture of the
map around it, edited as new reports of the same target come in.

The owner: "a small private Telegram channel that posts alerts like the channels we read, with a 'screenshot' of the
app where the drone is (Kyiv and Kyiv oblast only)"; of the ways asked, "one post per target, updated" and "the app's
style, drawn on the server" (app/mapshot.py).

Its rules (docs/SAFETY.md §the channel):
  - it repeats what the map shows and nothing more: the type and the place a post gave, a course only when a post
    stated one (a target town, compass words) — never a course the app worked out from two reports —, the height a
    post gave, the channel it came from, "from channel posts, not radar";
  - it never publishes an outcome (shot down, an explosion, a hit) nor where one happened, and never an air-defence
    position: a target leaves the channel with "no new reports since HH:MM", whatever became of it;
  - the official alerts are drawn as the app draws them; the channel never says that an alert starts or ends;
  - the bot's token is the owner's: set by scripts/set-telegram-channel.bat into Fly's secrets (TG_BOT_TOKEN,
    TG_CHANNEL_ID), read from the environment, never written to the database, a log or an answer. The server's
    bot only posts and edits in that one channel; it reads nothing (the channels are read as before).
"""
import json
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

SCOPE = ("31", "14")                       # Kyiv city, Kyiv oblast
TYPES = ("drones", "ballistic_missiles", "cruise_missiles", "unspecified_missiles", "banderol_missiles",
         "supersonic_missiles", "unknown")
FRESH_S = 5 * 60                           # a target is posted only if its report is this recent (no backlog)
EDIT_EVERY_S = 45                          # a post is redrawn at most this often
END_AFTER_S = 5 * 60                       # gone from the map this long → its post is closed ("no new reports")
KEEP_S = 24 * 3600                         # what the store remembers of the posts
BUDGET = 18                                # calls a minute (Telegram allows ~20 messages a minute in one channel)
TICK_S = 5
KV = "chan_posts"
MSL_TYPES = ("ballistic_missiles", "cruise_missiles", "supersonic_missiles", "unspecified_missiles")

LABEL = {"drones": ("🛵", "Шахед"), "jet": ("🛩", "Реактивний дрон"), "ballistic_missiles": ("🚀", "Балістична ракета"),
         "cruise_missiles": ("🚀", "Крилата ракета"), "supersonic_missiles": ("🚀", "Надзвукова ракета (Х-22/32)"),
         "unspecified_missiles": ("🚀", "Ракета"), "banderol_missiles": ("🛩", "Бандероль (реактивний дрон)"),
         "unknown_dr": ("❔", "Ймовірно, дрон — тип не вказано"), "unknown": ("❔", "Дрон чи ракета — тип не вказано")}
COMPASS = ("північ", "північний схід", "схід", "південний схід", "південь", "південний захід", "захід", "північний захід")
ALT_STATE = {"low": "низько", "high": "високо", "descending": "знижується", "climbing": "набирає висоту"}
# a course the app worked out itself (two reports of a live channel; a destination a later post gave a carried
# mark) is drawn on the map with its own caveat, but the channel says only what a post said
DERIVED = ("bearing between the two latest reports", "the destination a later post named")
WARN = "⚠️ З дописів каналів, не радар. Сирена й офіційна тривога — головне."


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
    if m.get("type") not in TYPES or m.get("status") or m.get("stale") or m.get("superseded_by"):
        return False
    if m.get("needs_context") or m.get("candidates"):
        return False
    place = (m.get("place") or "").strip().lstrip("→").strip()           # "→ Київ": the town it is heading for
    return bool(place) and place.lower() not in ("область", "київщина", "київська область")


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


def caption(m, first_t, public_url, ended_t=None):
    """The post's text (Telegram HTML). Only what the post said; nothing about what became of it."""
    emo, name = label_of(m)
    n = m.get("count")
    head = f"{emo} <b>{esc(name)}{' ×' + str(n) if isinstance(n, int) and n > 1 else ''}</b> · {esc(m.get('place'))}"
    lines = []
    if ended_t:
        lines.append(f"⏹ Нових дописів після {hhmm(ended_t)} немає")
    lines.append(head)
    c = stated_course(m)
    if c:
        lines.append(f"➡️ {esc(c)} (так у дописі)")
    if approach(m):
        lines.append("📍 Де саме зараз — у дописі не сказано")
    alt = m.get("alt") or {}
    if isinstance(alt, dict) and (alt.get("m") or alt.get("state") in ALT_STATE):
        lines.append("↕️ Висота: " + (f"~{int(alt['m'])} м" if alt.get("m") else ALT_STATE[alt["state"]]) + " (у дописі)")
    t = report_t(m)
    when = hhmm(t) if t else "?"
    if first_t and t and hhmm(first_t) != when:
        when += f" (перший допис {hhmm(first_t)})"
    ch = m.get("channel")
    lines.append(f"🕒 {when}" + (f" · за @{esc(ch)}" if ch else ""))
    lines.append(WARN)
    lines.append(f'🗺 <a href="{esc(public_url.rstrip("/"))}/m">Мапа Heimdall</a>')
    return "\n".join(lines)[:1024]


def signature(m):
    """What a redraw is for: a new place, a new course, a new count or height — not a new id of the same report."""
    alt = m.get("alt") or {}
    hist = [(round(h.get("lon") or 0, 3), round(h.get("lat") or 0, 3)) for h in (m.get("history") or [])[-6:]]
    return json.dumps([round(m["lon"], 3), round(m["lat"], 3), m.get("place"), stated_course(m), m.get("count"),
                       m.get("type"), m.get("jet"), alt.get("m") if isinstance(alt, dict) else None, hist,
                       int(report_t(m) // 60)], ensure_ascii=False)


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
    """Every few seconds: the marks of the moment → a new post for a new target, a redraw for a target reported
    again, a closing line for a target gone from the map."""

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
        self.pause_until = 0.0
        self.stats = {"posted": 0, "edited": 0, "closed": 0, "errors": 0, "last_error": None, "last_post": None,
                      "failing": False}
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
            if "message is not modified" not in (e.desc or ""):
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
                "note": f"posted {st['posted']} · redrawn {st['edited']} · closed {st['closed']}"
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
            return self.shot.render(m, active, hhmm(report_t(m) or self.clock()),
                                    ray=stated_course(m) is not None and not approach(m), missiles=self.missiles)
        except Exception as e:
            self.log("channel: picture failed —", type(e).__name__, e)
            return None

    def tick(self):
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
        active = None
        changed = False
        # 1. new targets first, the most recent report first
        for k, m in sorted(cur.items(), key=lambda kv: -report_t(kv[1])):
            p = self.posts.get(k)
            if p and not p.get("ended"):
                p["seen"] = now
                continue
            if p and p.get("ended") and report_t(m) <= (p.get("last") or 0):
                continue                               # the same report, already closed
            if now - report_t(m) > FRESH_S or not self._room():
                continue
            active = self.active() if active is None else active
            if self._send(k, m, active):
                changed = True
        # 2. targets reported again: their post redrawn, at most every EDIT_EVERY_S
        for k, m in cur.items():
            p = self.posts.get(k)
            if not p or p.get("ended") or p.get("sig") == signature(m) or now - (p.get("edited") or 0) < EDIT_EVERY_S:
                continue
            if not self._room():
                break
            active = self.active() if active is None else active
            if self._edit(k, m, active):
                changed = True
        # 3. targets gone from the map: closed, without a word on what became of them
        for k, p in list(self.posts.items()):
            if p.get("ended") or k in cur or now - (p.get("seen") or 0) < END_AFTER_S:
                continue
            if not self._room():
                break
            if self._close(k, p):
                changed = True
        cut = now - KEEP_S
        for k in [k for k, p in self.posts.items() if (p.get("seen") or 0) < cut]:
            del self.posts[k]
            changed = True
        if changed:
            self._save()

    def _send(self, k, m, active):
        t = report_t(m)
        cap = caption(m, t, self.public_url)
        png = self.picture(m, active)
        try:
            if png:
                r = self._call("sendPhoto", {"chat_id": self.chat_id, "caption": cap, "parse_mode": "HTML"},
                               {"photo": ("map.jpg", png, "image/jpeg")})
            else:
                r = self._call("sendMessage", {"chat_id": self.chat_id, "text": cap, "parse_mode": "HTML",
                                               "link_preview_options": {"is_disabled": True}})
        except TgError:
            return False
        now = self.clock()
        self.posts[k] = {"mid": (r or {}).get("message_id"), "photo": bool(png), "sig": signature(m), "first": t,
                         "last": t, "seen": now, "edited": now, "m": _slim(m)}
        self.stats["posted"] += 1
        self.stats["last_post"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        return True

    def _edit(self, k, m, active):
        p = self.posts[k]
        cap = caption(m, p.get("first"), self.public_url)
        png = self.picture(m, active) if p.get("photo") else None
        try:
            if p.get("photo") and png:
                self._call("editMessageMedia", {"chat_id": self.chat_id, "message_id": p["mid"],
                                                "media": {"type": "photo", "media": "attach://photo", "caption": cap,
                                                          "parse_mode": "HTML"}},
                           {"photo": ("map.jpg", png, "image/jpeg")})
            elif p.get("photo"):
                self._call("editMessageCaption", {"chat_id": self.chat_id, "message_id": p["mid"], "caption": cap,
                                                  "parse_mode": "HTML"})
            else:
                self._call("editMessageText", {"chat_id": self.chat_id, "message_id": p["mid"], "text": cap,
                                               "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}})
        except TgError as e:
            if "message is not modified" in (e.desc or ""):
                p.update(sig=signature(m), edited=self.clock())
                return True
            if "not found" in (e.desc or "") or "can't be edited" in (e.desc or ""):
                p["ended"] = True                     # deleted by the owner, or too old: left alone
                return True
            return False
        p.update(sig=signature(m), last=report_t(m), seen=self.clock(), edited=self.clock(), m=_slim(m))
        self.stats["edited"] += 1
        return True

    def _close(self, k, p):
        m = p.get("m") or {}
        cap = caption(m, p.get("first"), self.public_url, ended_t=p.get("last") or p.get("first"))
        try:
            if p.get("photo"):
                self._call("editMessageCaption", {"chat_id": self.chat_id, "message_id": p["mid"], "caption": cap,
                                                  "parse_mode": "HTML"})
            else:
                self._call("editMessageText", {"chat_id": self.chat_id, "message_id": p["mid"], "text": cap,
                                               "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}})
        except TgError as e:
            if not any(s in (e.desc or "") for s in ("not found", "can't be edited", "message is not modified")):
                return False
        p["ended"] = True
        self.stats["closed"] += 1
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
    """What a closing line needs of a mark, kept with the post (no text of the post, no evidence beyond the course)."""
    keep = ("type", "jet", "_drone", "count", "place", "target", "dest_only", "approach", "heading", "alt", "channel", "ts",
            "pos_ts")
    out = {k: m.get(k) for k in keep if m.get(k) is not None}
    hv = (m.get("evidence") or {}).get("heading")
    if hv:
        out["evidence"] = {"heading": {k: hv.get(k) for k in ("matched", "method", "confidence")}}
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
