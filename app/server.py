#!/usr/bin/env python3
"""
UA Alerts — local air-raid alert tracker for Ukraine.

Polls official / semi-official sources, keeps a local history (SQLite),
serves a live dashboard on http://localhost:8642 and pushes events to it (SSE).

Sources (all optional except at least one alert source):
  * alerts.in.ua API           — primary, needs token   (config.alerts_in_ua_token)
  * api.ukrainealarm.com API   — official app backend, needs key (config.ukrainealarm_key)
  * ubilling.net.ua mirror     — keyless fallback, oblast-level only
  * Telegram public mirrors    — t.me/s/<channel>, e.g. Air Force (kpszsu) for threat details

Standard library only. Optional: `pip install plyer` for OS desktop notifications.
"""
import argparse
import bisect
import collections
import gzip
import hashlib
import html
import json
import math
import os
import re
import selectors
import socket
import sqlite3
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # sibling modules, however the file is launched

try:
    import geo
except Exception:  # pragma: no cover
    geo = None
try:
    import push as _push
except Exception:
    _push = None
try:
    import translate as _tr
except Exception:  # pragma: no cover
    _tr = None


def to_en(text):
    if not _tr or not text:
        return text
    try:
        return _tr.translate(text)
    except Exception:
        return text

BASE = os.path.dirname(os.path.abspath(__file__))
# the code lives in app/, everything else (config, database, static assets) at the repository root
ROOT = os.path.dirname(BASE) if os.path.basename(BASE) == "app" else BASE
CONFIG_PATH = os.environ.get("CONFIG_PATH") or os.path.join(ROOT, "config.json")
DB_PATH = os.environ.get("DB_PATH") or os.path.join(ROOT, "alerts.sqlite")
# 1.47: the satellite layer's tiles — an MBTiles file next to the database (on the volume), built once by
# scripts/build_imagery.py and put there by scripts/upload-imagery.bat. Without it the layer is simply not offered.
SAT_PATH = os.environ.get("SAT_TILES") or os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "sat-ua.mbtiles")
STATIC = os.path.join(ROOT, "static")

DEFAULT_CONFIG = {
    "port": 8642,
    "bind": "0.0.0.0",
    "marker_ttl_minutes": 45,
    "track_stale_minutes": 5,
    "alerts_in_ua_token": "",
    "ukrainealarm_key": "",
    "use_ubilling_fallback": True,
    "use_siren_proxy": True,
    "telegram_api_channels": ["chyste_nebo"],   # read through the Telegram API (web preview off); needs TG_* secrets
    "deepl_key": "",                  # machine translation of the feed (EN/FR); or env DEEPL_KEY
    "google_translate_key": "",       # alternative: Google Cloud Translation; or env GOOGLE_TRANSLATE_KEY
    "ai_key": "",                     # written summaries of each night / week on the dashboard; or env ANTHROPIC_API_KEY
    "ai_model": "claude-sonnet-5",    # the model that writes them; or env AI_MODEL
    "digest_hour": 9,                 # Kyiv hour after which last night is written up (the Air Force summary is out by then)          # keyless proxy of the official API (siren.pp.ua) — raion-level alerts without a key
    "poll_ukrainealarm_seconds": 10,
    "telegram_channels": ["kyiv_airdef", "chyste_nebo", "kievinfo_kyiv", "war_monitor", "eRadarrua", "kpszsu"],   # informational: AUTHORITATIVE_CHANNELS is what is read
    "favourites": ["31", "14"],
    "poll_alerts_seconds": 15,
    "poll_ubilling_seconds": 30,
    "poll_telegram_seconds": 30,
    "poll_telegram_missile_seconds": 10,
    "history_backfill_hours": 6,
    "desktop_notifications": True,
    "access_key": "",
    "esri_key": "",                   # 1.48: Esri World Imagery for the closest zooms; or env ESRI_KEY (set-esri-key.bat)
    "esri_monthly_tiles": 1800000,    # its cap: under the 2 M free tiles a month; a tenth of it a day at most
    "demo": False,
}

# ---------------------------------------------------------------------------
# Oblast table (alerts.in.ua UIDs) — order = /iot/active_air_raid_alerts_by_oblast.json
# ---------------------------------------------------------------------------
OBLASTS = [
    ("29", "Автономна Республіка Крим", "Crimea"),
    ("8", "Волинська область", "Volyn"),
    ("4", "Вінницька область", "Vinnytsia"),
    ("9", "Дніпропетровська область", "Dnipropetrovsk"),
    ("28", "Донецька область", "Donetsk"),
    ("10", "Житомирська область", "Zhytomyr"),
    ("11", "Закарпатська область", "Zakarpattia"),
    ("12", "Запорізька область", "Zaporizhzhia"),
    ("13", "Івано-Франківська область", "Ivano-Frankivsk"),
    ("31", "м. Київ", "Kyiv city"),
    ("14", "Київська область", "Kyiv oblast"),
    ("15", "Кіровоградська область", "Kirovohrad"),
    ("16", "Луганська область", "Luhansk"),
    ("27", "Львівська область", "Lviv"),
    ("17", "Миколаївська область", "Mykolaiv"),
    ("18", "Одеська область", "Odesa"),
    ("19", "Полтавська область", "Poltava"),
    ("5", "Рівненська область", "Rivne"),
    ("30", "м. Севастополь", "Sevastopol"),
    ("20", "Сумська область", "Sumy"),
    ("21", "Тернопільська область", "Ternopil"),
    ("22", "Харківська область", "Kharkiv"),
    ("23", "Херсонська область", "Kherson"),
    ("3", "Хмельницька область", "Khmelnytskyi"),
    ("24", "Черкаська область", "Cherkasy"),
    ("26", "Чернівецька область", "Chernivtsi"),
    ("25", "Чернігівська область", "Chernihiv"),
]
UID_BY_UK = {uk: uid for uid, uk, _ in OBLASTS}
NAME_BY_UID = {uid: (uk, en) for uid, uk, en in OBLASTS}


OBLAST_EN = {uid: en for uid, _, en in OBLASTS}


def norm_uk(s):
    """Loose match of an oblast name in Ukrainian (handles 'Київська', 'м. Київ', 'Крим'...)."""
    s = (s or "").strip().lower()
    for uid, uk, _ in OBLASTS:
        if s == uk.lower():
            return uid
    stem = re.sub(r"\s*(область|обл\.?)\s*$", "", s)
    for uid, uk, _ in OBLASTS:
        ukl = uk.lower()
        if stem and (ukl.startswith(stem) or stem.startswith(ukl.replace(" область", ""))):
            return uid
    if "крим" in s:
        return "29"
    if s in ("київ", "м. київ", "м.київ", "kyiv"):
        return "31"
    if "севастополь" in s:
        return "30"
    return None


# ---------------------------------------------------------------------------
# Threat keyword tagging for Telegram feed
# ---------------------------------------------------------------------------
FEED_TAGS = [
    ("drones", re.compile(r"бпла|шахед|дрон|безпілотн|мопед|реактив|\bбп\b", re.I)),
    # "Кинджал" is how the Air Force and war_monitor write it (1.33): read as "a missile" it lost the ballistic
    # banner — for an aeroballistic missile that reaches Kyiv in minutes
    ("ballistic_missiles", re.compile(r"баліст|іскандер|кінжал|к[иі]нджал|х-?47|kn-?23|балістич", re.I)),
    ("banderol_missiles", re.compile(r"бандерол", re.I)),
    ("cruise_missiles", re.compile(r"крилат|калібр|калиб|х-?101|х-?555|х-?59|х-?69|х-?22|х-?32|ракет", re.I)),
    # the channels decline it and drop the hyphen ("Мігну31к в небе"), so міг/миг/mig then 31 within three letters
    ("mig31k_departure", re.compile(r"м[іи]г\w{0,3}\s?-?\s?31|mig\w{0,3}\s?-?\s?31", re.I)),
    ("strategic_aircraft_activity", re.compile(r"ту-?95|ту-?160|ту-?22|стратегічн", re.I)),
    ("tactic_aircraft_activity", re.compile(r"тактичн|су-?34|су-?35|су-?25|су-?24", re.I)),
    ("guided_aerial_bombs", re.compile(r"каб|керован.*бомб", re.I)),
    ("air_defense", re.compile(r"ппо|протиповітрян|збит|знищен", re.I)),
    ("clear", re.compile(r"відбій|загроза минула|небезпека минула|\bчисто\b|посадк|приземл", re.I)),
    ("impact", re.compile(r"вибух|приліт|влучанн|уражен", re.I)),
    ("alert", re.compile(r"тривог|укритт|небезпек|загроз|сирен", re.I)),
]
THREAT_TAGS = {n for n, _ in FEED_TAGS}


# The only Telegram channels this app reads, for Kyiv and the oblasts around it.
#
# This is deliberately in code and not in config.json. The config on each machine already lists thirty-odd
# channels, and a config-level whitelist would change nothing until someone edited every deployed config by
# hand — the old list would keep running silently. Here, the list IS the behaviour: anything else in the
# config is ignored and logged once at start.
#
# kyiv_airdef, chyste_nebo and kievinfo_kyiv are the fast live trackers; war_monitor and eRadarrua the wider
# picture; kpszsu is the Air Force itself. None of them sets an alert's colour — see OFFICIAL_ALERTS_FROM_TELEGRAM.
AUTHORITATIVE_CHANNELS = ["kyiv_airdef", "chyste_nebo", "kievinfo_kyiv", "war_monitor", "eRadarrua", "kpszsu",
                          # 1.43: one live tracker per oblast — Chernihiv, Odesa, Cherkasy, Kharkiv, Dnipro
                          "chernihiv_nebo", "monitoringodesa", "chyste_nebocherkasy", "radar_kharkov", "RadarDnepr",
                          # 1.44: Sumy, Mykolaiv, Poltava, Vinnytsia, Zhytomyr
                          "kabusumy", "air_alert_mk", "PoltavaRadar", "vinnytsiappo", "zt_radar",
                          # 1.45: Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne, Lviv, Volyn
                          "kherson_monitoring", "controlkrop", "radarhmel", "radarofternopil", "rivne_radar", "ppoualviv",
                          "lutsk_radar"]

# 1.43: the dashboard groups the channels by the oblast they speak for, and switches an oblast on or off as a whole.
# "31" is Kyiv — the city and its oblast, always on; "ua" the channels that cover the whole country. A channel's
# home oblast is also how its posts are read: its villages, its city districts (geo.CHANNEL_HOME).
CHANNEL_HOME_DEFAULT = {"kyiv_airdef": "31", "chyste_nebo": "31", "kievinfo_kyiv": "31",
                        "war_monitor": "ua", "eRadarrua": "ua", "kpszsu": "ua",
                        "chernihiv_nebo": "25", "monitoringodesa": "18", "chyste_nebocherkasy": "24",
                        "radar_kharkov": "22", "RadarDnepr": "9",
                        "kabusumy": "20", "air_alert_mk": "17", "PoltavaRadar": "19", "vinnytsiappo": "4", "zt_radar": "10",
                        "kherson_monitoring": "23", "controlkrop": "15", "radarhmel": "3", "radarofternopil": "21",
                        "rivne_radar": "5", "ppoualviv": "27", "lutsk_radar": "8"}
# The preview of the "Чисте небо" network's channels is switched off: with the Telegram API configured, read that way.
# 1.44: so is @kabusumy's (Sumy).
CHANNEL_VIA_DEFAULT = {"chyste_nebocherkasy": "api", "kabusumy": "api"}

# Whether a Telegram post may start or end an alert. It may not. The colour of the alert — red, yellow,
# green — comes only from the official «Повітряна тривога» data (alerts.in.ua / ukrainealarm, or the ubilling
# mirror of it). A channel writing "відбій" or "чисто" turned the band green while the government app was still
# red; the one thing this app must never do is tell somebody it is over before the state does.
OFFICIAL_ALERTS_FROM_TELEGRAM = False

LIVE_TAGS = {"drones", "ballistic_missiles", "cruise_missiles", "banderol_missiles", "unspecified_missiles",
             "mig31k_departure", "strategic_aircraft_activity", "tactic_aircraft_activity", "guided_aerial_bombs", "clear"}
# Mixed channels: live tracking at night, city news in the day. Only short posts that read as a threat are kept.
NEWS_CHANNELS = {"kyiv_times_official", "eRadarrua", "kievinfo_kyiv", "RadarDnepr"}


def is_relevant(text, tags, channel=None):
    """Keep only posts about the air situation: a threat / alert / outcome keyword, a parsed position, or an
    official alert message. Everything else (news, fundraising, culture, ads) is dropped before storage."""
    if "af_summary" in tags or "retract" in tags:
        return True
    if channel in NEWS_CHANNELS:
        if channel == "eRadarrua" and "◦" in text:
            return True
        return bool(LIVE_TAGS & set(tags) or "geo" in tags) and len(text) <= 350
    if geo and channel in geo.OFFICIAL_PARSERS and geo.OFFICIAL_PARSERS[channel][0] == "etryvoga":
        return not text.lower().startswith("мапа тривог")    # nationwide raion alerts: everything except the hourly summary
    if THREAT_TAGS & set(tags) or "geo" in tags:
        return True
    if geo and channel in geo.OFFICIAL_PARSERS:
        kind = geo.OFFICIAL_PARSERS[channel][0]
        try:
            r = {"koda": geo.parse_koda, "kmda": geo.parse_kmda, "etryvoga": geo.parse_etryvoga, "eradar_alert": geo.parse_eradar_alert}.get(kind, geo.parse_city_siren)(text)
        except Exception:
            r = None
        return bool(r)
    return False
KYIV_RE = re.compile(r"київ|столиц|бровар|бориспіл|бучан|фастів|вишгород|обух|біла церкв", re.I)
# oblasts around Kyiv: Zhytomyr 10, Chernihiv 25, Sumy 20, Poltava 19, Cherkasy 24, Vinnytsia 4
REGION_UIDS = {"14", "31", "10", "25", "20", "19", "24", "4"}
# 1.43: the oblasts the map covers. Kyiv and the six around it, as before, and the three with a tracker of their own —
# Odesa 18, Kharkiv 22, Dnipro 9. The dashboard switches any oblast on or off (State.region_set); this set is what
# in_scope reads, updated in place. 1.44: Mykolaiv 17, with its tracker. 1.45: Kherson 23, Kirovohrad 15, Khmelnytskyi 3,
# Ternopil 21, Rivne 5, Lviv 27, Volyn 8 — each with its tracker.
DEFAULT_SCOPE = REGION_UIDS | {"18", "22", "9", "17", "23", "15", "3", "21", "5", "27", "8"}
SCOPE_UIDS = set(DEFAULT_SCOPE)
# channels that speak for one surrounding oblast (their posts are "region", not "kyiv", unless Kyiv is named)
REGION_CHANNELS = {"cherkasy_alerts", "cherkasy_monitor", "poltavskaODA", "zhytomyrskaODA", "chernihiv_alert", "Zhytomyr_alert", "sumy_alert", "sumy_alerts"}
REGION_RE = re.compile(r"житомир|чернігів|чернигов|сум(и|ськ|щин)|полтав|черкас|вінниц|ніжин|прилук|конотоп|шостк|охтир|ромн|кременчу|лубн|миргород|умань|уман[сь]|золотонош|бердич|коростен|звягел|гайсин|жмерин|тульчин", re.I)


SCOPE_KM = 330          # Kyiv to the far edge of Sumy or Vinnytsia oblast


def in_scope(m):
    uid = m.get("oblast_uid")
    if uid is not None:
        return str(uid) in SCOPE_UIDS
    if m.get("lat") is None or m.get("lon") is None:
        return True          # an outcome with no place of its own is resolved against its track later
    return haversine_km(50.45, 30.52, m["lat"], m["lon"]) <= SCOPE_KM


# nightly / daily *assessments* ("Загальна оцінка загроз на ніч…", "#обстановка", "може відбутись у будь-який момент") describe
# what MIGHT happen — they must never light the ballistic / MiG strip or place a marker. They keep only 'forecast' + 'alert'.
FORECAST_RX = re.compile(r"оцінка\s+загроз|загальна\s+оцінка|прогноз\s+(?:на|загроз)|#обстановка|на\s+ніч\s+\d|може\s+відбутись\s+у\s+будь-який\s+момент|впродовж\s+ночі\s+(?:ймовірн|можлив)|(?:ймовірн|можлив)\w*\s+(?:додаткові\s+)?запуск|"
                         # 1.41.2: what the enemy is said to plan ("ворог планує запустити … до 40 балістичних ракет") — geo.PLAN_RX
                         r"(?:ворог|противник|рф|росі\w*|окупант\w*)\s+план\w*|план\w*\s+(?:запустити|атакувати|завдати|застосувати)", re.I)


# 1.42.1: a channel taking a missile report back. On 7 Oct 2026 at 01:14 the channels relayed a ballistic launch "towards
# Kyiv" that the military's own system had shown by mistake ("швидкість 6000 була, ймовірно лаг системи"); the
# retraction was not even kept (no threat word), and the warning stood until it aged out. A retraction says the system
# glitched or the report was not confirmed, about something missile-shaped (a speed, a launch, a rocket). "Хибна ціль"
# is NOT one: that is a decoy drone, which flies.
# A glitch of the system ("лаг системи", "хибне спрацювання") is one on its own; "not confirmed" only about something
# missile-shaped — "Вибух у Броварах не підтвердився" must not end a ballistic warning.
RETRACT_RX = re.compile(r"(?:лаг\w*|збій|збої)\s+(?:\S+\s+)?(?:систем|радар|ПРО|ППО)\w*|(?:хибн|помилков)\w*\s+спрацюв\w*", re.I)
RETRACT_WEAK_RX = re.compile(r"(?:хибн|помилков)\w*\s+(?:тривог|інформац|відмітк)\w*|не\s+підтверд(?:и|ж)\w*", re.I)
RETRACT_CTX_RX = re.compile(r"баліст|ракет|швидк|пуск|м[іи]г|кинджал|кінжал|іскандер", re.I)


def is_retraction(text):
    t = text or ""
    return bool(RETRACT_RX.search(t) or (RETRACT_WEAK_RX.search(t) and RETRACT_CTX_RX.search(t)))


def tag_feed_text(text, channel=None, near=None):
    # 1.32: the Air Force's summary of a night or a day. It was being read as news (dropped, so the statistics lost
    # every summary from 25 Sep); it is also not a live threat — "балістичними ракетами" in a morning summary must
    # never light the ballistic banner. It is kept, with this one tag.
    if channel in AF_SUMMARY_CHANNELS and parse_af_report(text):
        return ["af_summary"]
    # 1.43: a post in Russian is tagged by its Ukrainian reading — the same words the parser reads (geo.prepare)
    if geo:
        text = geo.prepare(text, channel)
        # 1.43.1: what a post says about our own drones and aircraft is no threat — "Акустика нашего БпЛА над Харьковом"
        text = geo.drop_friendly(text)
        if not text:
            return []
    # a retraction carries no threat of its own — "балістика була хибною відміткою" is not a ballistic warning
    if is_retraction(text):
        return ["retract"] + (["kyiv"] if KYIV_RE.search(text) else [])
    tags = [name for name, rx in FEED_TAGS if rx.search(text)]
    if FORECAST_RX.search(text) and not re.search(r"\bпуск\b|зафіксовано\s+пуск|швидкісн\w*\s+ціл|зліт\s+міг|злетів|у\s+повітрі\s+міг", text, re.I):
        return [t for t in tags if t == "alert"] + ["forecast"]
    # An article is tagged as one and nothing else. Its threat words used to become threat tags, and a
    # ballistic_missiles tag on a news item is what lit "БАЛІСТИЧНА ЗАГРОЗА — НЕГАЙНО В УКРИТТЯ" on the page.
    # After the forecast check on purpose: a nightly assessment is a forecast, which says more than "news".
    if geo and geo.looks_like_news(geo._norm(text)):
        return ["news"]
    if KYIV_RE.search(text):
        tags.append("kyiv")
    if REGION_RE.search(text):
        tags.append("region")
    if geo:
        try:
            ms = geo.parse_for_channel(channel, text, near) if channel else geo.parse_post(text)
        except Exception:
            ms = []
        for m in ms:
            if m["type"] not in tags:
                tags.append(m["type"])
            if m.get("oblast_uid") in ("14", "31") and "kyiv" not in tags:
                tags.append("kyiv")
            if m.get("oblast_uid") in REGION_UIDS and "region" not in tags:     # the oblasts around Kyiv, for the feed filter
                tags.append("region")
        if ms and "geo" not in tags:
            tags.append("geo")
    # A Banderol post says "ракета" too, and the keyword pass tags that as a cruise missile. Once the post has been
    # read as a Banderol, the vaguer tag goes — otherwise the feed shows a "cruise missiles" chip on it.
    if "banderol_missiles" in tags:
        tags = [t for t in tags if t not in ("cruise_missiles", "unspecified_missiles")]
    if OFFICIAL_ALERTS_FROM_TELEGRAM and channel and geo and channel in geo.OFFICIAL_PARSERS:
        tags.append("official")
    if geo and channel in geo.OFFICIAL_PARSERS and geo.OFFICIAL_PARSERS[channel][0] == "city" and geo.OFFICIAL_PARSERS[channel][1] not in REGION_UIDS:
        tags.append("ua")
        if "kyiv" in tags and not KYIV_RE.search(text):
            tags.remove("kyiv")
    if geo and channel in geo.OFFICIAL_PARSERS and geo.OFFICIAL_PARSERS[channel][0] in ("etryvoga", "eradar_alert") and "region" not in tags and "kyiv" not in tags:
        tags.append("ua")
    if channel in REGION_CHANNELS:
        if "region" not in tags:
            tags.append("region")
        if "kyiv" in tags and not KYIV_RE.search(text):
            tags.remove("kyiv")
    return tags


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


BUILD_FILES = ("static/kyiv.html", "static/light.html", "static/light-map.json", "static/glyphs.js", "static/i18n.js", "static/live.js",
               "static/nuke.js", "static/sw.js", "app/server.py", "app/geo.py", "app/push.py",
               "static/light-map-x.json", "data/regional_places.json", "static/map-ua.json")


def build_id():
    """A short id that changes whenever the front end or the service changes. An open page compares it with
    the one it loaded and offers a reload — that is how someone running for three days on an old build finds out.

    It hashes the CONTENT of those files, not their timestamps. Timestamps change on every container build even
    when nothing did, and are different on two machines holding identical code — so the same id here and in
    production means the same code here and in production, and that is a question worth being able to answer
    without guessing at a screenshot."""
    h = hashlib.sha1()
    for rel in BUILD_FILES:
        try:
            with open(os.path.join(ROOT, rel), "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(b"?")
        h.update(b"\0")
    return h.hexdigest()[:8]


# The version the front end shows in its footer, kept here too so /api/version can answer "what is actually
# running" without anybody reading it off a screenshot. tests/test_version.py pins the two to each other.
APP_VERSION = "1.48"
APP_NAME = "Heimdall"
BUILD = None    # filled at startup


# ---------------------------------------------------------------------------
# Usage counters — aggregates only.
#
# The people using this app include police and soldiers during attacks. Nothing here identifies anybody:
# no IP is stored, no path history, no location, no per-device timeline. A device is counted once per day
# through a hash of (IP + user-agent + a salt that is thrown away and regenerated every day), so the same
# person cannot be followed from one day to the next, and the hash cannot be turned back into an address.
# Kept: a daily row of totals. That is enough to see whether the app is being used, and nothing more.
class Usage:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.day = None
        self.salt = None
        self.seen = set()          # hashes seen today, in memory only, dropped at midnight
        # Pings are counted in memory and written in batches. During a ballistic alert every client pings once
        # a second: one committed transaction per ping would put thousands of writes a second through a single
        # SQLite connection and stall the alert path itself — a counter is never allowed to do that.
        self.pending = 0
        self.flushed = 0.0
        with store.lock:
            store.conn.execute("""CREATE TABLE IF NOT EXISTS usage(
                day TEXT PRIMARY KEY, devices INTEGER, loads INTEGER, pings INTEGER,
                lang TEXT, pwa INTEGER, lite INTEGER)""")
            # The day's salt and the hashes seen under it have to OUTLIVE THE PROCESS. They used to be a
            # fresh random salt and an empty set at every start, so every deploy, every crash and every
            # auto-stop/start counted the same three people again — 62 "devices" out of a handful of readers.
            # A counter that inflates itself is a counter that says nothing, and this one sits on a dashboard
            # next to figures that are carefully honest about what they count.
            store.conn.execute("CREATE TABLE IF NOT EXISTS usage_seen(day TEXT, h TEXT, PRIMARY KEY(day,h))")
            store.conn.commit()

    def _roll(self):
        d = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")
        if d != self.day:
            if self.day is not None and self.pending:
                self._flush(self.day, self.pending)          # yesterday's tail is not thrown away
                self.pending = 0
            self.day = d
            self.salt = self._salt_for(d)
            self.seen = self._seen_for(d)
        return d

    def _salt_for(self, day):
        """One salt per day, kept only for that day. New day, new salt: nobody can be followed across days."""
        import binascii
        k = f"usage_salt:{day}"
        cur = self.store.kv_get(k)
        if cur:
            try:
                return binascii.unhexlify(cur)
            except Exception:
                pass
        salt = os.urandom(16)
        self.store.kv_set(k, binascii.hexlify(salt).decode())
        with self.store.lock:
            # yesterday's salt and hashes are destroyed, which is what makes the daily hash un-followable
            self.store.conn.execute("DELETE FROM kv WHERE k LIKE 'usage_salt:%' AND k<>?", (k,))
            self.store.conn.execute("DELETE FROM usage_seen WHERE day<>?", (day,))
            self.store.conn.commit()
        return salt

    def _seen_for(self, day):
        with self.store.lock:
            try:
                rows = self.store.conn.execute("SELECT h FROM usage_seen WHERE day=?", (day,)).fetchall()
            except sqlite3.OperationalError:
                return set()
        return {r[0] for r in rows}

    def _flush(self, day, n):
        with self.store.lock:
            c = self.store.conn
            c.execute("INSERT OR IGNORE INTO usage(day,devices,loads,pings,lang,pwa,lite) VALUES(?,0,0,0,'{}',0,0)", (day,))
            c.execute("UPDATE usage SET pings=pings+? WHERE day=?", (n, day))
            c.commit()

    def hit(self, ip, ua, kind, lang=None, pwa=False, lite=False):
        try:
            import hashlib
            due = 0
            with self.lock:
                day = self._roll()
                h = hashlib.blake2s(self.salt + (ip or "").encode() + (ua or "")[:120].encode(), digest_size=8).hexdigest()
                new = h not in self.seen
                if new:
                    self.seen.add(h)
                    try:
                        with self.store.lock:
                            self.store.conn.execute("INSERT OR IGNORE INTO usage_seen(day,h) VALUES(?,?)", (day, h))
                            self.store.conn.commit()
                    except Exception:
                        pass
                if kind != "load":
                    self.pending += 1
                    now = time.time()
                    due = self.pending if (self.pending >= 200 or now - self.flushed > 20) else 0
                    if due:
                        self.pending, self.flushed = 0, now
            if kind != "load" and not new:
                if due:
                    self._flush(day, due)
                return                    # the common case writes nothing at all
            with self.store.lock:
                c = self.store.conn
                c.execute("INSERT OR IGNORE INTO usage(day,devices,loads,pings,lang,pwa,lite) VALUES(?,0,0,0,'{}',0,0)", (day,))
                if new:
                    c.execute("UPDATE usage SET devices=devices+1 WHERE day=?", (day,))
                if kind == "load":
                    c.execute("UPDATE usage SET loads=loads+1 WHERE day=?", (day,))
                    if pwa:
                        c.execute("UPDATE usage SET pwa=pwa+1 WHERE day=?", (day,))
                    if lite:
                        c.execute("UPDATE usage SET lite=lite+1 WHERE day=?", (day,))
                    if lang in ("en", "uk", "fr"):
                        row = c.execute("SELECT lang FROM usage WHERE day=?", (day,)).fetchone()
                        d = json.loads(row[0] or "{}") if row else {}
                        d[lang] = d.get(lang, 0) + 1
                        c.execute("UPDATE usage SET lang=? WHERE day=?", (json.dumps(d), day))
                elif due:
                    c.execute("UPDATE usage SET pings=pings+? WHERE day=?", (due, day))   # `due` already counts this one
                c.commit()
        except Exception:
            pass       # counting must never get in the way of an alert

    def report(self, days=30):
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT day,devices,loads,pings,lang,pwa,lite FROM usage ORDER BY day DESC LIMIT ?", (days,)).fetchall()
        out = [{"day": r[0], "devices": r[1], "loads": r[2], "pings": r[3],
                "lang": json.loads(r[4] or "{}"), "pwa": r[5], "lite": r[6]} for r in rows]
        with self.lock:
            live, day, tail = len(self.seen), self.day, self.pending
        if tail:                                   # pings counted but not yet written
            for r in out:
                if r["day"] == day:
                    r["pings"] += tail
                    break
        return {"days": out, "today_devices": live,
                "push_subs": len(self.store.push_all()),
                "generated": now_iso()}


def _clean_post(text):
    """What the reader sees: the warning without the channel's ad tail ("Купуємо контент | ❤️")."""
    if not _tr:
        return text
    try:
        return _tr.strip_promo(text)
    except Exception:
        return text


# How long a missile report stays on the map at all. Past this the last position tells you nothing useful even
# as an uncertainty circle: a cruise missile has covered 150 km, a ballistic one has already arrived.
MISSILE_TTL_MIN = 12

# 1.43.1: how long a regional tracker's report of a drone stays — the Kyiv channels report a target every minute, the
# Chernihiv, Odesa or Kharkiv ones every five to twenty. Shown as "location not updated" after the first, gone after
# the second; an unspecified threat ("Придніпровськ – уважно") goes after the first. The oblast's all-clear ends them.
REGIONAL_STALE_MIN = 10
REGIONAL_GONE_MIN = 25
# 1.45: how long the oblast a regional channel named stays the context its next bare names are read in (geo `near`)
NEAR_CTX_MIN = 30

AF_SUMMARY_CHANNELS = {"kpszsu", "war_monitor", "monitor_ukr"}   # the Air Force summary and the channels that re-post it verbatim
_AF_NUM = r"(\d{1,3})(?:-?[а-яіїєґ']{1,3})?"
_AF_ATTACK_RX = re.compile(r"(?:противник|ворог|росі\w+|рф)\s+(?:масовано\s+|знову\s+)?атакув\w+", re.I)
_AF_DRONES_RX = re.compile(_AF_NUM + r"\s+(?:ударн\w+\s+|розвідувальн\w+\s+)?(?:БпЛА|безпілотник\w*|дрон\w*)", re.I)
_AF_MISSILE_RX = re.compile(_AF_NUM + r"\s+(?:[а-яіїєґ'\-/]+\s+){0,4}?ракет\w*", re.I)
_AF_DOWN_RX = re.compile(r"(?:збито|знищено|подавлен\w+|збито/подавлено|збито\s*/\s*подавлено)\s+" + _AF_NUM, re.I)


def parse_af_summary(text):
    """Air Force summary → {'drones','missiles','down'} (totals, per the Air Force), or None. Kept for the callers that
    want totals; the type-by-type reading is parse_af_report. Banderol is a jet drone, never a missile: not in either."""
    rep = parse_af_report(text)
    if not rep:
        return None
    la, dn = rep.get("launched") or {}, rep.get("down") or {}
    missiles = af_missiles(la)
    if not la.get("drones") and not missiles and not dn.get("total"):
        return None
    return {"drones": la.get("drones", 0), "missiles": min(missiles, 400), "down": dn.get("total", 0)}

# ---- the Air Force's summaries, in full (1.32) ------------------------------------------------------------------
# "У ніч на 28 вересня противник атакував 165 ударними БпЛА (79 із них - реактивні) … збито/подавлено 112 …
#  Зафіксовано влучання … на 14 локаціях, а також падіння збитих (уламки) на 7 локаціях." Each weapon type is read
# on its own, launched and shot down, and a type named without a number ("балістичними ракетами Іскандер-М") is
# recorded as used, never as zero. Nothing is inferred: what the summary does not say stays unknown.
AF_TYPES = (
    ("aeroballistic", r"аеробалістичн\w*(?:\s+ракет\w*)?"),
    ("ballistic", r"(?<!аеро)балістичн\w*(?:\s+ракет\w*)?"),
    ("cruise", r"крилат\w*(?:\s+ракет\w*)?"),
    ("antiship", r"протикорабельн\w*\s+ракет\w*"),
    ("guided", r"керован\w*\s+(?:авіаційн\w*\s+)?ракет\w*"),
    ("banderol", r"[«\"“„']?\s*бандерол\w*"),
    ("decoys", r"(?:дрон\w*|безпілотник\w*)[\s-]*імітатор\w*"),
    ("drones", r"(?:ворож\w+\s+)?(?:ударн\w+\s+|розвідувальн\w+\s+)?(?:БпЛА|безпілотник\w*|дрон\w*(?![\s-]*імітатор))"),
    ("missiles", r"ракет\w*"),                  # "13 ракетами" — a total, broken down by type elsewhere or not at all
)
AF_MISSILE_TYPES = ("cruise", "ballistic", "aeroballistic", "antiship", "guided")


def af_missiles(counts):
    """Missiles in a launched / shot-down dict: the stated total when there is one, else the sum of the types."""
    return counts.get("missiles") or sum(counts.get(k, 0) for k in AF_MISSILE_TYPES)
_AF_TYPE_RX = [(k, re.compile(r"(?<![\d.,])(\d{1,4})(?:-?[а-яіїєґ']{1,3})?\s+(?:[а-яіїєґА-ЯІЇЄҐ'\-]+\s+){0,2}?" + rx, re.I)) for k, rx in AF_TYPES]
_AF_MENTION_RX = [(k, re.compile(rx, re.I)) for k, rx in AF_TYPES]
_AF_JET_RX = re.compile(r"\(\s*(?:понад\s+)?(\d{1,4})\s+(?:із|з)\s+них\s*[-–—]\s*реактивн", re.I)
_AF_MONTHS = {"січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
              "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12}
_AF_MODELS = re.compile(r"Іскандер[\s-]*[МК]?|С-400|KN-23|Калібр|Циркон|Онікс|Кинджал|Х-?\s?(?:101|555|22|32|59|69|31|35)", re.I)


def _af_counts(seg):
    got, used = {}, set()
    work = seg
    for k, rx in _AF_TYPE_RX:
        for m in rx.finditer(work):
            got[k] = got.get(k, 0) + int(m.group(1))
        work = rx.sub(" ", work)                          # counted once, by the most specific type
    for k, rx in _AF_MENTION_RX:
        if rx.search(seg):
            used.add(k)
    return got, used


def parse_af_report(text, ts=None):
    """An Air Force summary (night or day) → what it says, type by type; None for anything else."""
    if not text:
        return None
    low = text.lower()
    m = _AF_ATTACK_RX.search(text)
    if not m or "атакува" not in low:
        return None
    body = re.sub(r"[ \t]+", " ", text)
    m = _AF_ATTACK_RX.search(body)
    rest = body[m.end():]
    cut = re.search(r"Повітряний напад відбивал|За попередніми даними|Станом на|підтверджено|протиповітрян\w+\s+обороною|"
                    r"збит\w*\s*/\s*подавл|Основн\w*\s+напрям", rest, re.I)
    attack = rest[:cut.start()] if cut else rest[:1200]
    attack_nb = re.sub(r"\([^)]*\)", " ", attack)                # "(79 із них - реактивні)" itemises, it is not a type
    launched, used = _af_counts(attack_nb)
    if "missiles" in launched:
        # "13 ракетами (9 крилатих … та 4 балістичні …)" or "35 ракетами: 6 балістичних, 29 крилатих": the total is the
        # total; the types after it are its breakdown, read from the brackets as well — never added to it
        paren = " ".join(re.findall(r"\(([^)]*)\)", attack))
        more, _ = _af_counts(paren)
        for k in AF_MISSILE_TYPES:
            if k in more and k not in launched:
                launched[k] = more[k]
    used.discard("missiles")
    jm = _AF_JET_RX.search(attack)
    if jm:
        launched["jet"] = int(jm.group(1))
    elif re.search(r"в\s+т\.?\s*ч\.?\s+реактивн|реактивн", attack, re.I):
        used.add("jet")
    down = {}
    dm = re.search(r"(?:протиповітрян\w+\s+обороною\s+(?:протягом\s+вказаного\s+періоду\s+)?)?збито\s*/\s*подавлено|протиповітрян\w+\s+обороною\s+збито|"
                   r"збито\s+та\s+подавлено|збиття\s*/\s*подавлення", rest, re.I)
    if dm:
        dseg = rest[dm.end():]
        dend = re.search(r"Зафіксовано|Атака триває|Станом на \d|Не ігноруйте|Тримаймо", dseg)
        dseg = dseg[:dend.start()] if dend else dseg[:900]
        tot = re.match(r"\s*(\d{1,4})\s+(?:ціл|ворожих\s+ціл)", dseg)
        dm_nb = re.sub(r"\([^)]*\)", " ", dseg)
        down, _ = _af_counts(dm_nb)
        down.pop("decoys", None)
        down.pop("missiles", None)
        jd = _AF_JET_RX.search(dseg)
        if jd:
            down["jet"] = int(jd.group(1))
        down["total"] = int(tot.group(1)) if tot else sum(v for k, v in down.items() if k not in ("jet", "total"))
    head = re.search(r"ЗБИТО\s*/\s*ПОДАВЛЕНО\s+(\d{1,4})", text)
    if head and not down.get("total"):
        down["total"] = int(head.group(1))
    if not launched and not down:
        return None
    # which period, and which date it is about (Kyiv): "у ніч на 28 вересня" / "протягом дня 28 вересня"
    period, date = "other", None
    pm = re.search(r"(?:у|в)\s+ніч\s+на\s+(\d{1,2})\s+([а-яіїє]+)", body, re.I)
    if pm:
        period = "night"
    else:
        pm = re.search(r"(?:протягом|впродовж)\s+(?:дня|доби)\s+(\d{1,2})\s+([а-яіїє]+)", body, re.I) or \
            re.search(r"(\d{1,2})\s+([а-яіїє]+)\s+\d{4}\s+року\s+\(\s*(?:із|з)", body, re.I)
        if pm:
            period = "day"
    posted = parse_iso(ts) if ts else None
    if pm and pm.group(2).lower() in _AF_MONTHS:
        mon, dd = _AF_MONTHS[pm.group(2).lower()], int(pm.group(1))
        yr = (posted.astimezone(kyiv_tz()).year if posted else datetime.now(timezone.utc).year)
        if posted and mon - posted.astimezone(kyiv_tz()).month > 6:
            yr -= 1                                            # a January post about 31 December
        try:
            date = f"{yr:04d}-{mon:02d}-{dd:02d}"
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            date = None
    if not date and posted:
        date = posted.astimezone(kyiv_tz()).strftime("%Y-%m-%d")
    out = {"period": period, "date": date, "launched": launched, "used": sorted(used - set(launched)),
           "down": down}
    im = re.search(r"влучання[^.]*?на\s+(\d{1,4})\s+локаці", body, re.I)
    if im:
        out["impacts"] = int(im.group(1))
    de = re.search(r"падіння\s+збитих[^.]*?на\s+(\d{1,4})\s+локаці", body, re.I)
    if de:
        out["debris"] = int(de.group(1))
    am = re.search(r"(?:із|з)\s+напрямк\w*\s*:\s*([^.\n]+)", re.sub(r"\bрф\.", "рф", body), re.I)
    if am:
        areas = []
        for part in re.split(r",|;|\s+та\s+|\s[-–—]\s", am.group(1)):
            p = re.sub(r"(?<![\w-])(?:ТОТ|АР\s+Крим|рф|РФ)(?![\w-])\.?", " ", part)
            p = re.sub(r"\s+", " ", p).strip(" .–—-")
            if p and len(p) <= 40:
                areas.append({"Донецької": "Донецьк"}.get(p, p))
        out["areas"] = list(dict.fromkeys(a for a in areas if a))
    dirm = re.search(r"Основн\w*\s+напрям\w*\s+удар\w*\s*[-–—:]\s*([^!.\n]+)", body, re.I)
    if dirm:
        out["directions"] = [x.strip(" .!") for x in re.split(r",|\s+та\s+|\s+і\s+", dirm.group(1)) if x.strip(" .!")]
    models = sorted({re.sub(r"\s+", "", x).replace("-", "-") for x in _AF_MODELS.findall(body)})
    if models:
        out["models"] = models
    return out


# ---------------------------------------------------------------------------
# 1.33: the aircraft that carry the missiles — take-offs, launches, stand-downs
# ---------------------------------------------------------------------------
# The channels announce the carriers before the missiles: "Зафіксовано зліт МіГ-31К", "Відмічено зліт 4х бортів
# Ту-95мс з ае «Оленья»", "Борт Ту-22м3 в районі Криму", then "Проведено пуски КР «Калібр»", "Ворог ймовірно
# виконав перші пуски крилатих ракет повітряного базування Х-101", "Відбій загрози МіГ-31К". Each post is read
# for what it says happened — a carrier up, a launch, a stand-down — sentence by sentence, so that a sentence
# about what MAY come ("Якщо будуть пуски КР…", "Загроза пусків Х-22") never counts as a report. Kept in
# air_reports; the sorties and the delay from take-off to launch are computed from them (State.air_sorties).
# Statistics only: none of this places a mark or raises anything.
AIR_KINDS = ("mig31k", "strategic", "tu22", "kalibr")
_AIR_KIND_RX = {
    "mig31k": re.compile(r"м[іи]г\w{0,3}\s?-?\s?31|mig\w{0,3}\s?-?\s?31", re.I),
    "strategic": re.compile(r"ту-?\s?95|ту-?\s?160|стратегічн\w*\s+(?:бомбардувальник|авіац|борт)|стратавіа", re.I),
    "tu22": re.compile(r"ту-?\s?22", re.I),
}
_AIR_SENT = re.compile(r"[.!?;\n]+")
# said as possible, expected, conditional or as a threat: not a report that anything happened
_AIR_IF = re.compile(r"\bмож(?:е|уть)\b|можлив|імітаці|якщо|чи\s+будуть|у\s+разі|очіку|загроз|імовірн\w*\s+застосуванн|ймовірн\w*\s+застосуванн|"
                     r"буде\s+надходит|надходить\s+інформаці|по\s+фактичн|прогноз|попередження\s+на|на\s+вечір|на\s+ніч\b|найближчими\s+днями", re.I)
_AIR_UP = re.compile(r"\bзліт\b|злет[іи]в|злетіл|\bвиліт\b|вилетіл|(?:в|у)\s+повітрі|(?:в|у)\s+повітряному\s+просторі|здійснюють\s+політ|"
                     r"\d+\s*(?:-?(?:ти|х|x|×))?\s*борт|борт\w*\s+(?:да\s+)?(?:ту|стратав)|в\s+акваторії|(?:в|у)\s+напрямку|в\s+районі|"
                     r"на\s+(?:північ|південь|схід|захід)", re.I)
_AIR_NOT_UP = re.compile(r"не\s+активн|тихо\b|посадк|приземл|відбі|повернул|залишают|зворотн|готов\w*\s+до|присутніст", re.I)
# a whole post about moving aircraft between airfields is not a sortie
_AIR_REDEPLOY = re.compile(r"передислок|перебазув|переміщ", re.I)
# a report written after the attack ("Застосовано …") is a tally, not a launch as it happens
_AIR_TALLY = re.compile(r"застосовано|застосував|вибухи\s+лунали|за\s+добу|(?:у|в)\s+ніч\s+(?:на|з)\s+\d|уночі\s+\d|уранці\s+\d|"
                        r"цієї\s+ночі|знищено\s+\d|збито\s+\d|за\s+даними\s+пс", re.I)
_AIR_LAUNCH = re.compile(r"\b(?:за)?пуск\w*", re.I)
_AIR_MISSILE = re.compile(r"крилат|\bкр\b|х-?\s?101|х-?\s?555|ракет", re.I)
_AIR_STRAT_LAUNCH = re.compile(r"повітряного\s+базування|х-?\s?101|х-?\s?555", re.I)
_AIR_KALIBR = re.compile(r"калібр|калибр", re.I)
_AIR_X22 = re.compile(r"х-?\s?(?:22|32)\b", re.I)
_AIR_X22_COUNT = re.compile(r"\d+\s*[хx×]\s*(?:пкр\s+|кр\s+)?х-?\s?(?:22|32)\b", re.I)
_AIR_KINZHAL = re.compile(r"к[иі]нджал|кінжал|х-?\s?47", re.I)
_AIR_KINZHAL_GO = re.compile(r"вектор|курс|напрям|\bна\s+[А-ЯІЇЄҐ]|\bпуск|\d+\s*[хx×]", re.I)
_AIR_MIG_END = re.compile(r"відбі\w*\s+(?:\S+\s+){0,3}?м[іи]г|посадк\w*\s+(?:\S+\s+){0,1}?м[іи]г|м[іи]г\S*\s+(?:\S+\s+){0,2}?(?:приземл|сів|сіли|посадк)", re.I)
_AIR_TU22_END = re.compile(r"чисто\s+по\s+х-?\s?22|залишают\w*\s+пускові|(?:у|в)\s+зворотному\s+напрямку", re.I)


def parse_air_report(text):
    """A post → what it reports about the carriers: a list of (kind, phase), phase "up" (airborne), "launch"
    or "end" (stood down, landed). [] when it reports none of it."""
    if not text or parse_af_report(text):
        return []                                   # the Air Force's summary of a night: a tally, not a report
    found = []
    redeploy = bool(_AIR_REDEPLOY.search(text))
    tally = bool(_AIR_TALLY.search(text))
    strat_post = bool(_AIR_KIND_RX["strategic"].search(text))     # "В повітрі … Ту-95МС. Імовірно здійснили пуски КР!"

    def add(kind, phase):
        if (kind, phase) not in found:
            found.append((kind, phase))
    for sent in _AIR_SENT.split(text):
        sent = sent.strip()
        if not sent:
            continue
        kinds = [k for k, rx in _AIR_KIND_RX.items() if rx.search(sent)]
        hedged = bool(_AIR_IF.search(sent))
        # stood down / landed
        if _AIR_MIG_END.search(sent):
            add("mig31k", "end")
            continue
        if _AIR_TU22_END.search(sent) and ("tu22" in kinds or _AIR_X22.search(sent)):
            add("tu22", "end")
            continue
        # launches, as reported (the Air Force's "імовірно здійснено пуски" included: it reads them from the aircraft)
        if not hedged and not tally:
            if _AIR_LAUNCH.search(sent) and _AIR_KALIBR.search(sent):
                add("kalibr", "launch")
            elif _AIR_LAUNCH.search(sent) and _AIR_MISSILE.search(sent) and ("strategic" in kinds or strat_post or _AIR_STRAT_LAUNCH.search(sent)) \
                    and not _AIR_X22.search(sent):
                add("strategic", "launch")
            if (_AIR_LAUNCH.search(sent) and _AIR_X22.search(sent)) or _AIR_X22_COUNT.search(sent):
                add("tu22", "launch")
            if _AIR_KINZHAL.search(sent) and _AIR_KINZHAL_GO.search(sent) and not re.search(r"носі", sent, re.I):
                add("mig31k", "launch")
        # a carrier in the air
        if kinds and not hedged and not redeploy and not tally and not _AIR_NOT_UP.search(sent) and _AIR_UP.search(sent):
            for k in kinds:
                if k == "strategic" and ("strategic", "launch") in found and not re.search(r"(?:в|у)\s+повітрі", sent, re.I):
                    continue                        # "пуски … з Ту-95" names the carrier of the launch, not a new take-off
                add(k, "up")
    return found


# How long a sortie stays open after its last report, and how long after the take-off a launch still belongs to it
# (minutes). A MiG-31K flight lasts under an hour and is called off ("Відбій загрози МіГ-31К"); Tu-95/Tu-160 fly to
# their launch lines for hours and launch before dawn; a Tu-22M3 sortie over the Black Sea is a few hours.
AIR_OPEN = {"mig31k": 90, "strategic": 12 * 60, "tu22": 6 * 60, "kalibr": 120}


def air_sorties(reports):
    """Reports (dicts with ts, kind, phase, channel, h — oldest first) → sorties: {kind, start (first "up"),
    launch (first launch report), end (first stand-down), reports, channels}. Several channels reporting the
    same take-off are one sortie; the same text from the same channel again within 45 minutes counts once;
    a take-off more than 10 minutes after a stand-down is a new sortie. A launch with no take-off on record
    (the Kalibr ships, or a take-off nobody posted) is a sortie with no start: it has no delay."""
    out, cur, seen = [], {}, {}
    for r in reports:
        t = parse_iso(r["ts"])
        if not t:
            continue
        k, ph = r["kind"], r["phase"]
        key = (r.get("channel"), r.get("h"), ph)
        if r.get("h") and key in seen and (t - seen[key]).total_seconds() < 45 * 60:
            continue                        # the same words again within minutes: a repost, an edit, or a reply
                                            # stored with the message it answered (before 1.33) — not a new take-off
        seen[key] = t
        s = cur.get(k)
        if s and ((t - s["_last"]).total_seconds() / 60 > AIR_OPEN.get(k, 120)
                  or (ph == "up" and s["end"] and (t - s["end"]).total_seconds() > 600)
                  or (ph == "launch" and k == "kalibr" and s["launch"] and (t - s["launch"]).total_seconds() / 60 > AIR_OPEN["kalibr"])):
            s = None
        if s is None:
            if ph == "end":
                continue                                   # a stand-down with no take-off on record
            s = {"kind": k, "start": None, "launch": None, "end": None, "reports": 0, "channels": set(), "_last": t}
            cur[k] = s
            out.append(s)
        s["reports"] += 1
        s["channels"].add(r.get("channel"))
        if ph != "end":
            s["_last"] = t
        if ph == "up" and not s["start"] and not s["launch"]:
            s["start"] = t
        elif ph == "launch" and not s["launch"]:
            s["launch"] = t
        elif ph == "end" and not s["end"]:
            s["end"] = t
    res = []
    for s in out:
        d = {"kind": s["kind"], "reports": s["reports"], "channels": sorted(c for c in s["channels"] if c)}
        for f in ("start", "launch", "end"):
            d[f] = s[f].isoformat().replace("+00:00", "Z") if s[f] else None
        d["delay_min"] = round((s["launch"] - s["start"]).total_seconds() / 60) if s["start"] and s["launch"] else None
        d["up_min"] = round((s["end"] - s["start"]).total_seconds() / 60) if s["start"] and s["end"] else None
        res.append(d)
    return res


# ---------------------------------------------------------------------------
# 1.34: the Dnipro bridges in Kyiv
# ---------------------------------------------------------------------------
# From 1 October 2026 the bridges are the targets: the Southern bridge was hit five times in two days, the
# Northern bridge on 3 and 4 October, by Shaheds and jet drones, by day, with cars on them. A bridge is a place
# somebody drives onto without thinking and cannot leave quickly — so the app says, bridge by bridge, when a target
# was reported on or near one. Each crossing as the line it draws over the water, from OpenStreetMap (1.34: the
# roadway's two ends; 1.38: a polyline where the crossing bends, read off the OpenStreetMap map at street zoom).
# North to south. 1.38 adds the Kyiv HPP dam at Vyshhorod (the road on the dam), the Petrivskyi railway bridge and the
# Podilsko-Voskresenskyi crossing (Podil — Rybalskyi — the arch over the Dnipro — Trukhaniv island — Raiduzhnyi).
BRIDGES = [
    {"id": "ges", "uk": "Дамба Київської ГЕС", "en": "Kyiv HPP dam", "fr": "barrage de la centrale de Kyiv",
     "pts": ((30.5010, 50.5905), (30.5100, 50.5887), (30.5155, 50.5875), (30.5221, 50.5862), (30.5300, 50.5854))},
    {"id": "pivnichnyi", "uk": "Північний міст", "en": "Northern Bridge", "fr": "pont Nord", "pts": ((30.53082, 50.48923), (30.54096, 50.49218))},
    {"id": "petrivskyi", "uk": "Петрівський залізничний міст", "en": "Petrivskyi Railway Bridge", "fr": "pont ferroviaire Petrivskyi",
     "pts": ((30.5380, 50.4837), (30.5575, 50.4837))},
    {"id": "podilskyi", "uk": "Подільсько-Воскресенський міст", "en": "Podilskyi Bridge", "fr": "pont de Podil",
     "pts": ((30.5248, 50.4749), (30.5300, 50.4747), (30.5400, 50.4716), (30.5457, 50.4715), (30.5555, 50.4738),
             (30.5609, 50.4755), (30.5713, 50.4795), (30.5754, 50.4813))},
    {"id": "metro", "uk": "Міст Метро", "en": "Metro Bridge", "fr": "pont du Métro", "pts": ((30.55998, 50.44132), (30.56888, 50.44397))},
    {"id": "paton", "uk": "Міст Патона", "en": "Paton Bridge", "fr": "pont Paton", "pts": ((30.57212, 50.42440), (30.59198, 50.43015))},
    {"id": "darnytskyi", "uk": "Дарницький міст", "en": "Darnytskyi Bridge", "fr": "pont de Darnytsia", "pts": ((30.57219, 50.41222), (30.59725, 50.41850))},
    {"id": "pivdennyi", "uk": "Південний міст", "en": "Southern Bridge", "fr": "pont Sud", "pts": ((30.55467, 50.40097), (30.59796, 50.39435))},
]
BRIDGE_BY_PLACE = {b["uk"]: b["id"] for b in BRIDGES}
# "at": the place the post named is the bridge or its ends. "near": a Shahed covers 3.5 km in about a minute; a jet
# drone or a missile 6 km in well under one, and is drawn 6 km out for that reason.
BRIDGE_AT_KM, BRIDGE_NEAR_KM, BRIDGE_NEAR_FAST_KM = 1.2, 3.5, 6.0
# 1.38: what makes "hit reported" — a post that names the bridge and says it was hit or damaged. Never "вибух" (an
# explosion is most often an interception), never "уражено" (the Air Force's word for a drone taken down).
BRIDGE_HIT_RX = re.compile(r"влучан|влучил|влучення|пошкоджен|зруйнован|\bприл[іеь]?[іо]т|\bприльот", re.I)
# A post that names only the city, or a bank of the river, is placed at a point 2–4 km from several bridges.
# That is not a report near any of them.
BRIDGE_VAGUE = {"Київ", "м. Київ", "Столиця", "Лівий берег", "Правий берег", "область"}
# The bridge named in a post's own words — for the posts that are placed somewhere else ("Повз лівий берег на
# Південний міст", "ТЕЦ-5/південний міст") or on the city header ("Київ: 🔻Зниження міст метро").
BRIDGE_NAME_RX = {
    "pivnichnyi": re.compile(r"\bпівнічн\w{0,3}\s+м[іо]ст|\bсеверн\w{0,3}\s+мост", re.I),
    "ges": re.compile(r"\b(?:дамб|гребл)\w{0,2}\s+(?:київськ\w{0,3}\s+)?гес\b|\bм[іо]ст\w{0,2}\s+(?:на\s+|через\s+|біля\s+)?(?:київськ\w{0,3}\s+)?гес\b"
                     r"|\bдамб\w{0,2}\s+(?:киевск\w{0,3}\s+)?гэс\b", re.I),
    "petrivskyi": re.compile(r"\bпетрівськ\w{0,3}\s+(?:залізничн\w{0,3}\s+)?м[іо]ст|\bрибальськ\w{0,3}\s+залізничн\w{0,3}\s+м[іо]ст"
                            r"|\bпетровск\w{0,3}\s+(?:железнодорожн\w{0,3}\s+)?мост", re.I),
    "podilskyi": re.compile(r"\bподільсько-воскресенськ\w{0,3}\s+м[іо]ст|\bподільськ\w{0,3}\s+(?:мостов\w{0,3}\s+перех[оі]д|м[іо]ст)"
                           r"|\bвоскресенськ\w{0,3}\s+м[іо]ст|\bподольск\w{0,3}\s+мост", re.I),
    "metro": re.compile(r"\bм[іо]ст\w{0,2}\s+метро|\bметро\s*-?\s*м[іо]ст", re.I),
    "paton": re.compile(r"\bм[іо]ст\w{0,2}\s+(?:ім\.?\s*|імені\s+|им\.?\s*|имени\s+)?патона", re.I),
    "darnytskyi": re.compile(r"\bдарни[цч]\w{0,4}\s+(?:залізнично-автомобільн\w{0,3}\s+|залізничн\w{0,3}\s+)?м[іо]ст", re.I),
    "pivdennyi": re.compile(r"\bпівденн\w{0,3}\s+м[іо]ст|\bюжн\w{0,3}\s+мост", re.I),
}


def bridge_km(lon, lat, br):
    """Distance in km from a point to a bridge's line over the water (a polyline; flat projection — a few km in Kyiv)."""
    kx, ky = 111.32 * math.cos(math.radians(50.45)), 110.57
    best = None
    for (ax, ay), (bx, by) in zip(br["pts"], br["pts"][1:]):
        px, py, vx, vy = (lon - ax) * kx, (lat - ay) * ky, (bx - ax) * kx, (by - ay) * ky
        t = max(0.0, min(1.0, (px * vx + py * vy) / (vx * vx + vy * vy)))
        d = math.hypot(px - t * vx, py - t * vy)
        best = d if best is None or d < best else best
    return best


def bridges_named(text):
    return [k for k, rx in BRIDGE_NAME_RX.items() if rx.search(text or "")]


def kyiv_tz():
    """Kyiv's own time, summer and winter. Without the zone data (a bare container) the summer offset stands in."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Kyiv")
    except Exception:
        return timezone(timedelta(hours=3))


def _union_minutes(spans):
    """Minutes covered by a set of (start, end) intervals, overlaps counted once."""
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(spans):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += (cur_e - cur_s).total_seconds() / 60
            cur_s, cur_e = s, e
        elif e > cur_e:
            cur_e = e
    if cur_e is not None:
        tot += (cur_e - cur_s).total_seconds() / 60
    return round(tot)


COMPASS8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# The written summary. Its one job is to put into words numbers this app already has — nothing else. A model that
# "explains" an attack invents intentions, targets and forecasts; a model asked to describe a table does not.
AI_SYSTEM = """You write the summary of one period of air-raid activity over Kyiv city and Kyiv oblast for the operator \
of Heimdall, a volunteer warning app. You are given the facts as JSON.

Rules — follow all of them:
- Use ONLY the facts in the JSON. Every number and every place you write must be in it.
- Never predict, forecast or estimate anything. Never guess intentions, targets, causes, weapons or damage that the
  facts do not state. No advice about safety.
- "reports" are posts of monitoring channels read by the app, not a count of drones or missiles; say "reports".
- The Air Force figures are official and cover all of Ukraine; say so when you use them.
- If something is missing or zero, say plainly that nothing was recorded; do not fill the gap.
- Calm, plain, short. No markdown headings, no emojis.

Write it twice, in English and in Ukrainian (natural Ukrainian, not a word-for-word translation). Each version:
4 to 7 sentences of prose, then a line "Key figures:" (Ukrainian: "Ключові цифри:") and 3 to 6 lines starting with "• ".

Answer with a JSON object only: {"en": "...", "uk": "..."}"""


def ai_summary(cfg, facts, kind):
    """(text_en, text_uk, model, error) — the written summary of `facts`, or the error that prevented it."""
    key, model = cfg.get("ai_key"), cfg.get("ai_model") or "claude-sonnet-5"
    if not key:
        return None, None, None, "no ANTHROPIC_API_KEY"
    body = json.dumps({"model": model, "max_tokens": 1800, "system": AI_SYSTEM,
                       "messages": [{"role": "user", "content": f"Period: {kind}\nFacts:\n" + json.dumps(facts, ensure_ascii=False, indent=1)}]}).encode("utf-8")
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as r:
            out = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, None, model, f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except Exception as e:
        return None, None, model, str(e)[:200]
    text = "".join(b.get("text", "") for b in out.get("content") or [] if b.get("type") == "text").strip()
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        en, uk = (d.get("en") or "").strip(), (d.get("uk") or "").strip()
        if en or uk:
            return en or None, uk or None, out.get("model") or model, None
    except Exception:
        pass
    return (text or None), None, out.get("model") or model, ("the answer was not the JSON asked for" if text else "empty answer")


_GZ = {}


def _gzipped(path, body):
    """gzip of a static file, kept until the file changes."""
    k = (path, len(body), hashlib.md5(body).digest())
    if k not in _GZ:
        if len(_GZ) > 64:
            _GZ.clear()
        _GZ[k] = gzip.compress(body, 6)
    return _GZ[k]


# One TLS context for every outgoing request. urlopen() without one builds a new context each call and loads the
# system's ~150 root certificates into it again: 15–25 ms of CPU per request, ~90 % of the process's CPU while the
# channels are read every 5–10 s on an attack night (1.46 audit, py-spy: 10 % of a core → 1.6 %).
_SSL_CTX = ssl.create_default_context()


def http_get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "ua-alerts-local/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        return r.status, dict(r.headers), r.read()


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


# A subscription used to carry the exact coordinates of somebody's village, next to the address their phone
# can be reached at. That is the only row in this database that would say where a person sleeps, and the app
# does not need it: proximity alerts ask "is anything within N km", and N is never smaller than 10. The point
# is snapped to a ~10 km grid and the name is dropped — the alerts behave the same, and the row no longer
# points at a house.
HOME_CELL_KM = 10.0
HOME_CELL_LAT = HOME_CELL_KM / 111.0
HOME_CELL_LON = HOME_CELL_KM / 71.0          # at ~50°N, the latitudes this app covers


def coarse_home(home):
    """{lat, lon, radius} snapped to the grid, and nothing else. Anything unrecognised is dropped."""
    if not isinstance(home, dict):
        return {}
    try:
        lat, lon = float(home["lat"]), float(home["lon"])
    except (KeyError, TypeError, ValueError):
        return {}
    out = {"lat": round(round(lat / HOME_CELL_LAT) * HOME_CELL_LAT, 4),
           "lon": round(round(lon / HOME_CELL_LON) * HOME_CELL_LON, 4),
           "cell_km": HOME_CELL_KM}
    try:
        r = float(home.get("radius") or 0)
        if r > 0:
            out["radius"] = min(100.0, max(HOME_CELL_KM, r))
    except (TypeError, ValueError):
        pass
    return out


# ---------------------------------------------------------------------------
# State + storage
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        # 1.46: with WAL, NORMAL syncs at checkpoints instead of at every commit — safe against a crash of the process,
        # and a power cut can lose at most the last commits, never corrupt the file
        self.conn.execute("PRAGMA synchronous=NORMAL")
        c = self.conn
        c.execute("""CREATE TABLE IF NOT EXISTS alerts(
            key TEXT PRIMARY KEY, source TEXT, location_uid TEXT, location_title TEXT, location_title_en TEXT,
            location_type TEXT, oblast_uid TEXT, alert_type TEXT, alert_level TEXT,
            started_at TEXT, finished_at TEXT, notes TEXT, threats TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, key TEXT, location_uid TEXT,
            location_title TEXT, alert_type TEXT, oblast_uid TEXT, detail TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS feed(
            post_id TEXT PRIMARY KEY, channel TEXT, ts TEXT, text TEXT, tags TEXT)""")
        cols = [r[1] for r in c.execute("PRAGMA table_info(feed)").fetchall()]
        if "text_en" not in cols:
            c.execute("ALTER TABLE feed ADD COLUMN text_en TEXT")
        if "text_fr" not in cols:
            c.execute("ALTER TABLE feed ADD COLUMN text_fr TEXT")
        if "en_mt" not in cols:     # 1 = the English came from a machine translator, not the offline glossary
            c.execute("ALTER TABLE feed ADD COLUMN en_mt INTEGER")
        c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS push_subs(endpoint TEXT PRIMARY KEY, sub TEXT, home TEXT, created TEXT, last_ok TEXT)")
        # 1.34: what a phone asked for besides its own area ("bridges"), and the language to say it in
        for col in ("topics TEXT", "lang TEXT"):
            try:
                c.execute("ALTER TABLE push_subs ADD COLUMN " + col)
            except sqlite3.OperationalError:
                pass
        # 1.34: each time a target was reported on or near a Kyiv bridge (the rising edges, for the dashboard)
        c.execute("""CREATE TABLE IF NOT EXISTS bridge_events(
            ts TEXT, bridge TEXT, lvl TEXT, km REAL, type TEXT, jet INTEGER, place TEXT, channel TEXT, how TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_brg_ts ON bridge_events(ts)")
        # ---- the record of what the app itself said -------------------------------------------------
        # Markers were recomputed from the feed on every request, and the feed prunes. So "what did the map
        # show at 02:14 last Tuesday" had no answer, the lead time over the official siren could not be
        # measured, and a wrong reading could only be studied while the post that caused it was still there.
        # Each marker is written once, as computed, with the evidence that produced it.
        c.execute("""CREATE TABLE IF NOT EXISTS marker_log(
            id TEXT PRIMARY KEY, ts TEXT, post_id TEXT, channel TEXT, type TEXT, status TEXT,
            place TEXT, oblast_uid TEXT, lon REAL, lat REAL, heading REAL, count INTEGER,
            jet INTEGER, pos_conf TEXT, evidence TEXT)""")
        # Outcomes were derived from the feed every time they were asked for, which made them as short-lived
        # as the posts. They are the app's most-cited numbers; they get a table.
        c.execute("""CREATE TABLE IF NOT EXISTS outcomes(
            id TEXT PRIMARY KEY, ts TEXT, post_id TEXT, channel TEXT, status TEXT, type TEXT,
            place TEXT, oblast_uid TEXT, lon REAL, lat REAL, count INTEGER, pos_conf TEXT)""")
        # Which channels earn being believed first: posts seen, how many the app could read, how many were
        # flagged as wrong afterwards. Counters only — no post text, nothing about any reader.
        c.execute("""CREATE TABLE IF NOT EXISTS channel_stats(
            day TEXT, channel TEXT, posts INTEGER DEFAULT 0, with_marker INTEGER DEFAULT 0,
            outcomes INTEGER DEFAULT 0, flagged INTEGER DEFAULT 0, PRIMARY KEY(day, channel))""")
        # Each night and each week: the numbers computed once, and the written summary of them (dashboard only).
        c.execute("""CREATE TABLE IF NOT EXISTS digests(
            id TEXT PRIMARY KEY, kind TEXT, period_start TEXT, period_end TEXT, facts TEXT,
            summary_en TEXT, summary_uk TEXT, model TEXT, created TEXT, error TEXT)""")
        # The Air Force's summaries, read type by type (parse_af_report), one row per post — kept for good: they are
        # the official series every trend is measured against, and a summary lost is a night missing from it.
        c.execute("""CREATE TABLE IF NOT EXISTS af_reports(
            post_id TEXT PRIMARY KEY, channel TEXT, ts TEXT, period TEXT, date TEXT, data TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_af_date ON af_reports(date)")
        # 1.33: what the posts reported about the carriers (parse_air_report), and the weather of each night
        c.execute("""CREATE TABLE IF NOT EXISTS air_reports(
            post_id TEXT, kind TEXT, phase TEXT, channel TEXT, ts TEXT, h TEXT, PRIMARY KEY(post_id, kind, phase))""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_air_ts ON air_reports(ts)")
        c.execute("""CREATE TABLE IF NOT EXISTS weather(
            date TEXT, place TEXT, data TEXT, PRIMARY KEY(date, place))""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_alerts_started ON alerts(started_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_feed_ts ON feed(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_mlog_ts ON marker_log(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_mlog_obl ON marker_log(oblast_uid, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_out_ts ON outcomes(ts)")
        c.commit()

    def af_save(self, post_id, channel, ts, rep):
        with self.lock:
            cur = self.conn.execute("INSERT OR IGNORE INTO af_reports(post_id,channel,ts,period,date,data) VALUES(?,?,?,?,?,?)",
                                    (post_id, channel, ts, rep.get("period"), rep.get("date"), json.dumps(rep, ensure_ascii=False)))
            self.conn.commit()
        return bool(cur.rowcount)

    def af_reports(self, since_date="0000"):
        """One report per (date, period): the Air Force's own post over a re-post, then the fullest, then the latest."""
        with self.lock:
            rows = self.conn.execute("SELECT post_id,channel,ts,period,date,data FROM af_reports WHERE date>=? ORDER BY ts",
                                     (since_date,)).fetchall()
        best = {}
        for pid, ch, ts, period, date, data in rows:
            try:
                rep = json.loads(data)
            except Exception:
                continue
            size = len(rep.get("launched") or {}) + len(rep.get("down") or {}) + len(rep.get("used") or [])
            key = (date, period)
            score = (ch == "kpszsu", size, ts)
            if key not in best or score >= best[key][0]:
                best[key] = (score, dict(rep, post=pid, channel=ch, ts=ts))
        return [v[1] for _, v in sorted(best.items())]

    def air_save(self, post_id, channel, ts, items, text):
        """The carriers a post reported (parse_air_report). `h` fingerprints the text: the same words from the same
        channel again are a repost or an edit, not a second take-off."""
        if not items:
            return 0
        h = hashlib.sha1(re.sub(r"\W+", "", (text or "").lower()).encode("utf-8")).hexdigest()[:12]
        with self.lock:
            n = 0
            for kind, phase in items:
                n += self.conn.execute("INSERT OR IGNORE INTO air_reports(post_id,kind,phase,channel,ts,h) VALUES(?,?,?,?,?,?)",
                                       (post_id, kind, phase, channel, ts, h)).rowcount
            self.conn.commit()
        return n

    def air_reports(self, since_iso):
        with self.lock:
            rows = self.conn.execute("SELECT post_id,kind,phase,channel,ts,h FROM air_reports WHERE ts>=? ORDER BY ts", (since_iso,)).fetchall()
        return [dict(zip(("post", "kind", "phase", "channel", "ts", "h"), r)) for r in rows if self.mode_of(r[3]) == "map"]

    def weather_save(self, nights):
        with self.lock:
            for (date, place), d in nights.items():
                self.conn.execute("INSERT OR REPLACE INTO weather(date,place,data) VALUES(?,?,?)", (date, place, json.dumps(d)))
            self.conn.commit()
        return len(nights)

    def weather(self, since_date):
        with self.lock:
            rows = self.conn.execute("SELECT date,place,data FROM weather WHERE date>=?", (since_date,)).fetchall()
        out = {}
        for d, pl, data in rows:
            out.setdefault(d, {})[pl] = json.loads(data)
        return out

    def kv_get(self, k):
        with self.lock:
            r = self.conn.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r[0] if r else None

    def kv_set(self, k, v):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, v))
            self.conn.commit()

    PUSH_TOPICS = ("bridges",)

    def push_add(self, sub, home, topics=None, lang=None):
        topics = [t for t in (topics or []) if t in self.PUSH_TOPICS]
        lang = lang if lang in ("uk", "en", "fr") else None
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO push_subs(endpoint,sub,home,created,last_ok,topics,lang) VALUES(?,?,?,?,?,?,?)",
                              (sub["endpoint"], json.dumps(sub), json.dumps(coarse_home(home)), now_iso(), now_iso(),
                               ",".join(topics), lang))
            self.conn.commit()

    def bridge_event(self, bid, e):
        with self.lock:
            self.conn.execute("INSERT INTO bridge_events(ts,bridge,lvl,km,type,jet,place,channel,how) VALUES(?,?,?,?,?,?,?,?,?)",
                              (now_iso(), bid, e.get("lvl"), e.get("km"), e.get("type"), 1 if e.get("jet") else 0, e.get("place"),
                               e.get("ch"), e.get("how")))
            self.conn.commit()

    def coarsen_homes(self):
        """Rewrite every stored home through the grid, once, at startup. Rows written before this existed
        hold an exact village; leaving them would mean the change only protected new subscribers."""
        with self.lock:
            rows = self.conn.execute("SELECT endpoint,home FROM push_subs").fetchall()
        n = 0
        for ep, raw in rows:
            try:
                h = json.loads(raw or "{}")
            except Exception:
                h = {}
            c = coarse_home(h)
            if c != h:
                with self.lock:
                    self.conn.execute("UPDATE push_subs SET home=? WHERE endpoint=?",
                                      (json.dumps(c), ep))
                    self.conn.commit()
                n += 1
        return n

    def push_remove(self, endpoint):
        with self.lock:
            self.conn.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))
            self.conn.commit()

    def push_all(self):
        with self.lock:
            rows = self.conn.execute("SELECT endpoint,sub,home,topics,lang FROM push_subs").fetchall()
        return [{"endpoint": r[0], "sub": json.loads(r[1]), "home": json.loads(r[2] or "{}"),
                 "topics": [t for t in (r[3] or "").split(",") if t], "lang": r[4] or "uk"} for r in rows]

    # -- flagged readings ---------------------------------------------------
    # The map is read by people who know the ground far better than any parser does. When one of them sees a
    # marker that is wrong, the cheapest possible way to capture it is a button on the marker itself — a
    # workflow that needs a terminal is a workflow that never happens during a raid. What is stored is the
    # post, the reading, and what the person said was wrong with it. Never who they are: no address, no
    # location, and the daily hash that rate-limits them is the same throwaway one the usage counter uses.
    def flag_add(self, row):
        with self.lock:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS flags(
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, post_id TEXT, channel TEXT, marker_id TEXT,
                place TEXT, kind TEXT, reason TEXT, note TEXT, day_hash TEXT, text TEXT, done INTEGER DEFAULT 0)""")
            n_today = self.conn.execute(
                "SELECT COUNT(*) FROM flags WHERE day_hash=? AND ts>=?",
                (row.get("day_hash") or "", row["ts"][:10])).fetchone()[0]
            if n_today >= 40:                      # one device cannot flood it; 40 a day is far past honest use
                return False
            self.conn.execute(
                "INSERT INTO flags(ts,post_id,channel,marker_id,place,kind,reason,note,day_hash,text) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (row["ts"], row.get("post_id"), row.get("channel"), row.get("marker_id"), row.get("place"),
                 row.get("kind"), row.get("reason"), (row.get("note") or "")[:400], row.get("day_hash"),
                 (row.get("text") or "")[:1500]))
            self.conn.commit()
        # a reader saying "this reading is wrong" is the strongest signal a channel has about itself
        try:
            self.bump_channel(row["ts"][:10], row.get("channel"), flagged=1)
        except Exception:
            pass
        return True

    def flags(self, limit=200, include_done=False):
        with self.lock:
            try:
                q = ("SELECT id,ts,post_id,channel,marker_id,place,kind,reason,note,text,done FROM flags "
                     + ("" if include_done else "WHERE done=0 ") + "ORDER BY id DESC LIMIT ?")
                rows = self.conn.execute(q, (limit,)).fetchall()
            except sqlite3.OperationalError:
                return []                          # nobody has flagged anything yet
        keys = ("id", "ts", "post_id", "channel", "marker_id", "place", "kind", "reason", "note", "text", "done")
        return [dict(zip(keys, r)) for r in rows]

    # -- corpus review verdicts ---------------------------------------------
    # The corpus itself is a repo file, shipped inside the image and read-only here: anything written to it on
    # a deployed machine would vanish on the next release. So the verdicts live on the volume instead, and get
    # merged back into the repo by `corpus.py pull`. That keeps the reviewing where the reviewer actually is —
    # a phone, in a browser — without pretending the container is the source of truth.
    def corpus_review(self, case_id, state, note=""):
        with self.lock:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS corpus_reviews(
                case_id TEXT PRIMARY KEY, state TEXT, note TEXT, ts TEXT)""")
            self.conn.execute("INSERT OR REPLACE INTO corpus_reviews(case_id,state,note,ts) VALUES(?,?,?,?)",
                              (case_id, state, (note or "")[:300], now_iso()))
            self.conn.commit()

    def corpus_reviews(self):
        with self.lock:
            try:
                rows = self.conn.execute("SELECT case_id,state,note,ts FROM corpus_reviews").fetchall()
            except sqlite3.OperationalError:
                return {}
        return {r[0]: {"state": r[1], "note": r[2], "ts": r[3]} for r in rows}

    def flag_done(self, ids):
        with self.lock:
            self.conn.executemany("UPDATE flags SET done=1 WHERE id=?", [(int(i),) for i in ids])
            self.conn.commit()

    def upsert_alert(self, a):
        with self.lock:
            self.conn.execute("""INSERT INTO alerts(key,source,location_uid,location_title,location_title_en,location_type,
                oblast_uid,alert_type,alert_level,started_at,finished_at,notes,threats)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET finished_at=excluded.finished_at, alert_level=excluded.alert_level,
                threats=excluded.threats, notes=excluded.notes, source=excluded.source""",
                (a["key"], a["source"], a["location_uid"], a["location_title"], a.get("location_title_en"),
                 a["location_type"], a["oblast_uid"], a["alert_type"], a.get("alert_level"),
                 a["started_at"], a.get("finished_at"), a.get("notes"), json.dumps(a.get("threats") or [], ensure_ascii=False)))
            self.conn.commit()

    def finish_alert(self, key, finished_at):
        with self.lock:
            self.conn.execute("UPDATE alerts SET finished_at=? WHERE key=? AND finished_at IS NULL", (finished_at, key))
            self.conn.commit()

    def add_event(self, ev):
        with self.lock:
            self.conn.execute("INSERT INTO events(ts,kind,key,location_uid,location_title,alert_type,oblast_uid,detail) VALUES(?,?,?,?,?,?,?,?)",
                              (ev["ts"], ev["kind"], ev.get("key"), ev.get("location_uid"), ev.get("location_title"),
                               ev.get("alert_type"), ev.get("oblast_uid"), json.dumps(ev.get("detail") or {}, ensure_ascii=False)))
            self.conn.commit()


    _seen_ids = None

    def has_post(self, post_id):
        with self.lock:
            if self._seen_ids is None:
                self._seen_ids = {r[0] for r in self.conn.execute("SELECT post_id FROM feed ORDER BY ts DESC LIMIT 5000")}
            return post_id in self._seen_ids

    def mark_seen(self, post_id):
        with self.lock:
            if self._seen_ids is None:
                self._seen_ids = set()
            self._seen_ids.add(post_id)
            if len(self._seen_ids) > 20000:
                self._seen_ids = set(list(self._seen_ids)[-8000:])

    def add_feed(self, posts):
        new = []
        with self.lock:
            if self._seen_ids is None:
                self._seen_ids = set()
            for p in posts:
                self._seen_ids.add(p["post_id"])
                cur = self.conn.execute("INSERT OR IGNORE INTO feed(post_id,channel,ts,text,tags,text_en,en_mt) VALUES(?,?,?,?,?,?,?)",
                                        (p["post_id"], p["channel"], p["ts"], p["text"], json.dumps(p["tags"]), p.get("text_en"),
                                         0 if p.get("en_fallback") else 1))
                if cur.rowcount:
                    new.append(p)
            self.conn.commit()
        # Which channel earns being read first. Counted here because this is the one place a post is known to
        # be NEW — counting in markers() would count the same post again every time the window is recomputed.
        for p in new:
            try:
                day = (p.get("ts") or now_iso())[:10]
                got = 0
                if geo:
                    try:
                        got = 1 if geo.parse_for_channel(p["channel"], _clean_post(p["text"])) else 0
                    except Exception:
                        got = 0
                self.bump_channel(day, p["channel"], posts=1, with_marker=got)
            except Exception:
                pass
        return new

    _fc = (0.0, 0)

    def feed_count(self):
        """Asked by every page's ping, every 1–15 s: counted at most every 3 s."""
        if time.time() - self._fc[0] < 3:
            return self._fc[1]
        with self.lock:
            n = self.conn.execute("SELECT COUNT(*) FROM feed").fetchone()[0]
        self._fc = (time.time(), n)
        return n

    # -- the record of what the app said ------------------------------------------------------------
    def log_markers(self, markers):
        """Write each marker once, the way it was computed. INSERT OR IGNORE on the marker id: markers() is
        called many times a minute and recomputes the same ids, so only the first sighting is kept."""
        if not markers:
            return 0
        rows = []
        for m in markers:
            ev = m.get("evidence") or {}
            rows.append((m.get("id"), m.get("ts"), str(m.get("id", "")).split("#")[0], m.get("channel"),
                         m.get("type"), m.get("status"), m.get("place"), m.get("oblast_uid"),
                         m.get("lon"), m.get("lat"), m.get("heading"), m.get("count"),
                         1 if m.get("jet") else 0,
                         ((ev.get("position") or {}).get("confidence")),
                         json.dumps(ev, ensure_ascii=False)[:4000]))
        with self.lock:
            cur = self.conn.executemany(
                "INSERT OR IGNORE INTO marker_log(id,ts,post_id,channel,type,status,place,oblast_uid,"
                "lon,lat,heading,count,jet,pos_conf,evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            n = cur.rowcount
            out = [r for r in rows if r[5] in ("impact", "down", "fire", "damage")]
            if out:
                self.conn.executemany(
                    "INSERT OR IGNORE INTO outcomes(id,ts,post_id,channel,status,type,place,oblast_uid,"
                    "lon,lat,count,pos_conf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(r[0], r[1], r[2], r[3], r[5], r[4], r[6], r[7], r[8], r[9], r[11], r[13]) for r in out])
            self.conn.commit()
        return max(0, n)

    def bump_channel(self, day, channel, **counts):
        """Counters per channel per day. Nothing about any reader, nothing about any post's content."""
        if not channel:
            return
        fields = [k for k in ("posts", "with_marker", "outcomes", "flagged") if counts.get(k)]
        if not fields:
            return
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO channel_stats(day,channel) VALUES(?,?)", (day, channel))
            self.conn.execute("UPDATE channel_stats SET " + ", ".join(f"{f}={f}+?" for f in fields)
                              + " WHERE day=? AND channel=?", [int(counts[f]) for f in fields] + [day, channel])
            self.conn.commit()

    def channel_report(self, days=30):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self.lock:
            rows = self.conn.execute(
                "SELECT channel, SUM(posts), SUM(with_marker), SUM(outcomes), SUM(flagged) "
                "FROM channel_stats WHERE day>=? GROUP BY channel ORDER BY SUM(posts) DESC", (since,)).fetchall()
        return [{"channel": r[0], "posts": r[1] or 0, "with_marker": r[2] or 0,
                 "outcomes": r[3] or 0, "flagged": r[4] or 0} for r in rows]

    def markers_between(self, start, end, oblast_uid=None, only_live=True):
        """What the app had on the map in a window — used to measure how far ahead of the siren it was."""
        q = "SELECT ts,type,status,place,oblast_uid,channel FROM marker_log WHERE ts>=? AND ts<=?"
        a = [start, end]
        if oblast_uid:
            q += " AND oblast_uid=?"
            a.append(oblast_uid)
        if only_live:
            q += " AND status IS NULL"
        with self.lock:
            rows = self.conn.execute(q + " ORDER BY ts", a).fetchall()
        return [{"ts": r[0], "type": r[1], "status": r[2], "place": r[3], "oblast_uid": r[4], "channel": r[5]}
                for r in rows]

    def outcomes_between(self, start, end, oblast_uid=None):
        q = "SELECT ts,status,type,place,oblast_uid,count FROM outcomes WHERE ts>=? AND ts<=?"
        a = [start, end]
        if oblast_uid:
            q += " AND oblast_uid=?"
            a.append(oblast_uid)
        with self.lock:
            rows = self.conn.execute(q + " ORDER BY ts", a).fetchall()
        return [{"ts": r[0], "status": r[1], "type": r[2], "place": r[3], "oblast_uid": r[4], "count": r[5]}
                for r in rows]

    _DG = ("id", "kind", "period_start", "period_end", "facts", "summary_en", "summary_uk", "model", "created", "error")

    def digest_save(self, d):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO digests(" + ",".join(self._DG) + ") VALUES(" + ",".join("?" * len(self._DG)) + ")",
                              [json.dumps(d[k], ensure_ascii=False) if k == "facts" else d.get(k) for k in self._DG])
            self.conn.commit()

    def digest_get(self, did):
        with self.lock:
            r = self.conn.execute("SELECT " + ",".join(self._DG) + " FROM digests WHERE id=?", (did,)).fetchone()
        return self._dg(r) if r else None

    def digests(self, limit=30):
        with self.lock:
            rows = self.conn.execute("SELECT " + ",".join(self._DG) + " FROM digests ORDER BY period_end DESC, kind LIMIT ?", (limit,)).fetchall()
        return [self._dg(r) for r in rows]

    def _dg(self, r):
        d = dict(zip(self._DG, r))
        d["facts"] = json.loads(d["facts"] or "{}")
        return d

    def prune_log(self, days=120):
        cut = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self.lock:
            self.conn.execute("DELETE FROM marker_log WHERE ts<?", (cut,))
            self.conn.commit()

    def feed_find(self, channel, text):
        """The stored post a corpus case was harvested from: its id (so the review panel can link to it on
        Telegram) and the English text that was translated once, when it arrived. Matched on the exact text,
        because that is the only thing a corpus case keeps. Returns (post_id, text_en) or (None, None)."""
        text = (text or "").strip()
        if not text:
            return (None, None)
        with self.lock:
            row = self.conn.execute(
                "SELECT post_id,text_en FROM feed WHERE channel=? AND text=? ORDER BY ts DESC LIMIT 1",
                (channel, text)).fetchone()
        return (row[0], row[1]) if row else (None, None)

    # How each channel is used (State.channel_mode, 1.31): "map" feeds the marks, the banners and every count;
    # "trial" only shows its posts in the feed, flagged; "off" is not read and not shown. Set by State.
    mode_of = staticmethod(lambda ch: "map")
    # 1.43: the oblast a regional channel speaks for ("" for Kyiv and the country-wide ones). Set by State.
    home_of = staticmethod(lambda ch: "")

    def feed_since(self, minutes, limit=200, translate=True):
        """The posts the marks, the banners, the statistics and the summaries are computed from: only channels
        on the map. A channel on trial or switched off never reaches them."""
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        with self.lock:
            rows = self.conn.execute("SELECT post_id,channel,ts,text,tags,text_en FROM feed WHERE ts>=? ORDER BY ts DESC LIMIT ?", (since, limit)).fetchall()
        rows = [r for r in rows if self.mode_of(r[1]) == "map"]
        # Never a network call here: this runs inside the marks' computation. It used to call the machine
        # translator for any post without an English text — one call per post, each up to 6 s, on every request
        # for the marks — and during an attack the pages' requests piled up behind it until the server froze.
        return [{"post_id": r[0], "channel": r[1], "ts": r[2], "text": _clean_post(r[3]), "tags": json.loads(r[4]),
                 "text_en": r[5] or (_tr.translate_offline(r[3]) if (translate and _tr) else None)} for r in rows]

    def feed_between(self, start, end):
        """1.42 (replay): the posts of a past window, oldest first — only channels on the map, never a network call."""
        with self.lock:
            rows = self.conn.execute("SELECT post_id,channel,ts,text,tags FROM feed WHERE ts>=? AND ts<=? ORDER BY ts", (start, end)).fetchall()
        return [{"post_id": r[0], "channel": r[1], "ts": r[2], "text": _clean_post(r[3]), "tags": json.loads(r[4])}
                for r in rows if self.mode_of(r[1]) == "map"]

    def alert_events_between(self, start, end):
        """1.42 (replay): every official start and end of the window, in order. The alerts table cannot answer "what
        was on at 02:14": it keeps one row per region and alert type, so a region's second alert overwrites its first."""
        with self.lock:
            return self.conn.execute(
                "SELECT ts,kind,key,location_uid,location_title,alert_type,oblast_uid FROM events "
                "WHERE ts>=? AND ts<=? AND kind IN ('start','end') ORDER BY ts, id", (start, end)).fetchall()

    def alert_meta(self):
        """key -> (location type, last level, English title) for every alert ever stored."""
        with self.lock:
            rows = self.conn.execute("SELECT key,location_type,alert_level,location_title_en FROM alerts").fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def feed(self, limit=80):
        """The feed as the pages show it. A channel switched off is left out; a channel on trial is shown with its
        place tags only and "trial" — no threat tag, so nothing on the page is raised by it."""
        with self.lock:
            rows = self.conn.execute("SELECT post_id,channel,ts,text,tags,text_en,text_fr,en_mt FROM feed ORDER BY ts DESC LIMIT ?", (limit + 60,)).fetchall()
        out = []
        for r in rows:
            mode = self.mode_of(r[1])
            if mode == "off":
                continue
            tags = json.loads(r[4])
            if mode == "trial":
                tags = [t for t in tags if t in ("kyiv", "region", "ua")] + ["trial"]
            item = {"post_id": r[0], "channel": r[1], "ts": r[2], "text": _clean_post(r[3]), "tags": tags,
                    "text_en": r[5] or (_tr.translate_offline(r[3]) if _tr else r[3]), "text_fr": r[6], "en_mt": bool(r[7])}
            home = self.home_of(r[1])
            if home and home not in ("31", "ua"):
                item["home"] = home          # a regional channel's warning is for the readers of that oblast (1.43)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def set_translation(self, post_id, lang, text):
        with self.lock:
            if lang == "en":
                self.conn.execute("UPDATE feed SET text_en=?, en_mt=1 WHERE post_id=?", (text, post_id))
            elif lang == "fr":
                self.conn.execute("UPDATE feed SET text_fr=? WHERE post_id=?", (text, post_id))
            self.conn.commit()

    def history(self, hours=24, oblast_uids=None):
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = "SELECT key,source,location_uid,location_title,location_title_en,location_type,oblast_uid,alert_type,alert_level,started_at,finished_at,notes,threats FROM alerts WHERE (finished_at IS NULL OR finished_at>=?)"
        args = [since]
        if oblast_uids:
            q += " AND oblast_uid IN (%s)" % ",".join("?" * len(oblast_uids))
            args += list(oblast_uids)
        q += " ORDER BY started_at DESC LIMIT 2000"
        with self.lock:
            rows = self.conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows]

    def events(self, limit=200):
        with self.lock:
            rows = self.conn.execute("SELECT ts,kind,key,location_uid,location_title,alert_type,oblast_uid,detail FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": r[0], "kind": r[1], "key": r[2], "location_uid": r[3], "location_title": r[4],
                 "alert_type": r[5], "oblast_uid": r[6], "detail": json.loads(r[7])} for r in rows]

    @staticmethod
    def _row(r):
        return {"key": r[0], "source": r[1], "location_uid": r[2], "location_title": r[3], "location_title_en": r[4],
                "location_type": r[5], "oblast_uid": r[6], "alert_type": r[7], "alert_level": r[8],
                "started_at": r[9], "finished_at": r[10], "notes": r[11], "threats": json.loads(r[12] or "[]")}


def normalize_channel(s):
    """'@kyiv_airdef', 't.me/kyiv_airdef', 'https://t.me/s/kyiv_airdef' → 'kyiv_airdef'; anything else → None."""
    s = (s or "").strip()
    s = re.sub(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?", "", s, flags=re.I).lstrip("@").split("/")[0].split("?")[0]
    return s if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", s) else None


def canonical_host(cfg):
    """The app's own address once it has one (e.g. heimdall.com.ua). Pages opened anywhere else show a banner that
    sends the reader there, settings included (1.29). Unset: nothing is shown."""
    h = (os.environ.get("CANONICAL_HOST") or cfg.get("canonical_host") or "").strip().lower()
    return h if re.fullmatch(r"[a-z0-9.-]{3,253}", h) else None


def _canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(text):
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def _alert_id(a):
    return f"{a.get('location_uid')}|{a.get('alert_type')}"


def _keyed(items, idf):
    """A list of dicts as the stream hub diffs it: ids in order, each entry's canonical JSON, and a hash of both."""
    ids, strs = [], {}
    for it in items:
        i = idf(it)
        ids.append(i)
        strs[i] = _canon(it)
    return {"h": _hash("\n".join(f"{i}\t{strs[i]}" for i in ids)), "ids": ids, "strs": strs, "items": items,
            "dup": len(strs) != len(ids)}


def _list_delta(prev, cur):
    """What a page showing `prev` needs to show `cur`, as small as it can be said:
      - the same ids in the same order: only the entries that changed (`set`);
      - new entries at the head and the oldest dropped at the tail — a new post, a new alert: `pre` (the new
        ones), `n` (the new length) and the kept entries that changed;
      - otherwise the ids in order (`ids`) and the entries that changed.
    `all` when there is nothing to diff against (or an id is duplicated): the page replaces the whole list."""
    if not prev or prev["dup"] or cur["dup"]:
        return {"b": prev["h"] if prev else None, "h": cur["h"], "all": cur["items"]}
    pi, ci = prev["ids"], cur["ids"]
    d = {"b": prev["h"], "h": cur["h"]}
    if ci == pi:
        d["set"] = [it for it, i in zip(cur["items"], ci) if prev["strs"].get(i) != cur["strs"][i]]
        return d
    known = prev["strs"]
    k = 0
    while k < len(ci) and ci[k] not in known:
        k += 1
    if k and ci[k:] == pi[:len(ci) - k]:
        d["pre"] = cur["items"][:k]
        d["n"] = len(ci)
        d["set"] = [it for it, i in zip(cur["items"][k:], ci[k:]) if known.get(i) != cur["strs"][i]]
        return d
    d["ids"] = ci
    d["set"] = [it for it, i in zip(cur["items"], ci) if known.get(i) != cur["strs"][i]]
    return d


def _state_delta(prev, cur):
    """The alerts state: `active` as a list (see _list_delta), the dicts keyed by oblast (`oblasts`, `sources`)
    by the keys that changed (`sub`, `unset`), anything else whole (`set`)."""
    if not prev or prev["dup"] or cur["dup"]:
        return {"b": prev["h"] if prev else None, "h": cur["h"], "all": {k: v for k, v in cur["obj"].items() if k != "h"}}
    d = {"b": prev["h"], "h": cur["h"]}
    for k, v in cur["rest"].items():
        if prev["rest"].get(k) == v:
            continue
        pd, cd = prev["restd"].get(k), cur["restd"].get(k)
        if pd is not None and cd is not None:
            ch = {sk: cur["obj"][k][sk] for sk, sv in cd.items() if pd.get(sk) != sv}
            gone = [sk for sk in pd if sk not in cd]
            if ch:
                d.setdefault("sub", {})[k] = ch
            if gone:
                d.setdefault("unset", {})[k] = gone
        else:
            d.setdefault("set", {})[k] = cur["obj"][k]
    if prev["ids"] != cur["ids"] or any(prev["strs"].get(i) != cur["strs"][i] for i in cur["ids"]):
        d["act"] = _list_delta(prev, cur)
        d["act"].pop("b", None); d["act"].pop("h", None)
    return d


class State:
    """In-memory current picture + SSE fan-out."""

    def __init__(self, store, cfg):
        self.store = store
        self.cfg = cfg
        self.esri = EsriTiles(cfg, store)      # 1.48: the closest zooms of the satellite layer
        self.lock = threading.Lock()
        self.active = {}            # key -> alert dict
        self.sources = {}           # name -> {ok, last, error, ...}
        self.subscribers = []       # list of queues (lists + condition)
        self.cond = threading.Condition()
        self.seq = 0
        self.notifier = Notifier(cfg)
        # caches are per State: two States (the tests) must never see each other's answers
        self._resp, self._resp_locks, self._stats_res, self._entries = {}, {}, {}, {}
        try:
            self.notice = json.loads(store.kv_get("notice") or "null")
        except Exception:
            self.notice = None
        try:
            self.nuke = json.loads(store.kv_get("nuke") or "null")
        except Exception:
            self.nuke = None
        self._nuke_arm = None
        self._channels_load()
        store.mode_of = self.channel_mode
        store.home_of = self.channel_home

    # -- the Telegram channels read (1.31) -------------------------------------------------------------------------
    # The channels in AUTHORITATIVE_CHANNELS are the defaults, in code. The dashboard can switch any of them to trial
    # or off, send one through the Telegram API, and add others — stored in kv "channels", so they survive a restart
    # and a deploy. A channel added from the dashboard starts on TRIAL: its posts appear in the feed, flagged, but put
    # nothing on the map, raise no banner and send no alert until it is switched to the map. A channel nobody vetted
    # must not be able to put a drone over somebody's house.
    #
    # 1.43: every channel belongs to a compartment — the oblast it speaks for ("home"), Kyiv ("31"), or the whole
    # country ("ua") — and the dashboard switches a compartment on or off as a whole (kv "regions"). An oblast switched
    # off leaves the map (SCOPE_UIDS) and its channels are not read; Kyiv cannot be switched off.
    CHANNEL_MODES = ("map", "trial", "off")
    MAX_CHANNELS = 40
    LOCKED_REGIONS = {"31"}

    def _channels_load(self):
        try:
            saved = json.loads(self.store.kv_get("channels") or "null") or {}
        except Exception:
            saved = {}
        api = {c.lower() for c in (self.cfg.get("telegram_api_channels") or [])}
        tga = TelegramAPI.configured(self.cfg)
        by = {e["name"].lower(): e for e in saved.get("list", []) if isinstance(e, dict) and e.get("name")}
        out = []
        for c in AUTHORITATIVE_CHANNELS:
            e = by.pop(c.lower(), {})
            dflt_via = "api" if (c.lower() in api or (tga and CHANNEL_VIA_DEFAULT.get(c) == "api")) else "web"
            out.append({"name": c, "builtin": True, "mode": e.get("mode") if e.get("mode") in self.CHANNEL_MODES else "map",
                        "via": e.get("via") if e.get("via") in ("web", "api") else dflt_via,
                        "home": self._home_ok(e.get("home")) or CHANNEL_HOME_DEFAULT.get(c, "")})
        for e in by.values():
            out.append({"name": e["name"], "builtin": False, "mode": e.get("mode") if e.get("mode") in self.CHANNEL_MODES else "trial",
                        "via": e.get("via") if e.get("via") in ("web", "api") else "web", "added": e.get("added"),
                        "home": self._home_ok(e.get("home")) or ""})
        self.channel_list = out
        self._deleted = {k: v for k, v in (saved.get("deleted") or {}).items()}
        self._regions_load()
        self._apply_channels()

    def _regions_load(self):
        try:
            r = json.loads(self.store.kv_get("regions") or "null") or {}
        except Exception:
            r = {}
        self._regions_off = {x for x in (r.get("off") or []) if self._home_ok(x) and x not in self.LOCKED_REGIONS}
        self._regions_on = {x for x in (r.get("on") or []) if self._home_ok(x) and x != "ua"}

    @staticmethod
    def _home_ok(h):
        """A compartment id: "ua", "31", or an oblast uid the map knows (not Kyiv oblast — it is part of "31")."""
        h = str(h or "")
        return h if (h == "ua" or h == "31" or (h in OBLAST_EN and h != "14")) else ""

    def region_on(self, rid):
        if rid in self.LOCKED_REGIONS:
            return True
        if rid in self._regions_off:
            return False
        if rid == "ua" or rid in self._regions_on:
            return True
        return rid in DEFAULT_SCOPE

    def scope_uids(self):
        return {"31", "14"} | {u for u in OBLAST_EN if u not in ("31", "14") and self.region_on(u)}

    def _apply_channels(self):
        """Everything that follows from the list and the switches: each channel's effective mode, the oblasts the map
        keeps, and the home oblast each regional channel's posts are read against."""
        self._modes = {}
        homes = {}
        for e in self.channel_list:
            h = e.get("home") or ""
            self._modes[e["name"].lower()] = "off" if (h and not self.region_on(h)) else e["mode"]
            if h and h not in ("31", "ua"):
                homes[e["name"]] = h
        sc = self.scope_uids()
        SCOPE_UIDS.clear()
        SCOPE_UIDS.update(sc)
        if geo:
            geo.CHANNEL_HOME.clear()
            geo.CHANNEL_HOME.update(homes)
        self._health_res = None

    def _channels_save(self):
        builtin = {c.lower(): c for c in AUTHORITATIVE_CHANNELS}
        api = {c.lower() for c in (self.cfg.get("telegram_api_channels") or [])}
        tga = TelegramAPI.configured(self.cfg)
        keep = []
        for e in self.channel_list:
            if e["builtin"]:
                dflt_via = "api" if (e["name"].lower() in api or (tga and CHANNEL_VIA_DEFAULT.get(e["name"]) == "api")) else "web"
                if e["mode"] == "map" and e["via"] == dflt_via and e.get("home", "") == CHANNEL_HOME_DEFAULT.get(e["name"], ""):
                    continue            # a default left as it is: nothing to store
            keep.append({k: e[k] for k in ("name", "mode", "via", "added", "home") if k in e})
        cut = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        self._deleted = {k: v for k, v in self._deleted.items() if v >= cut and k not in builtin}
        self.store.kv_set("channels", json.dumps({"list": keep, "deleted": self._deleted}, ensure_ascii=False))
        self.store.kv_set("regions", json.dumps({"off": sorted(self._regions_off), "on": sorted(self._regions_on)}))
        self._apply_channels()
        self._marker_cache.clear()                      # the posts are read against the homes and the scope just set
        self._impact_cache.clear()
        self._impact_res.clear()
        self.publish({"kind": "channels", "ts": now_iso()})       # the feed, the marks and the pages follow at once

    def channel_mode(self, ch):
        """map / trial / off. A channel removed from the dashboard stays off for the hours its posts could still
        count; a channel never registered (an old post, the demo) counts as before 1.31. A channel whose oblast is
        switched off is off (1.43)."""
        k = (ch or "").lower()
        m = self._modes.get(k)
        if m:
            return m
        return "off" if k in self._deleted else "map"

    def channel_home(self, ch):
        e = next((x for x in self.channel_list if x["name"].lower() == (ch or "").lower()), None)
        return (e or {}).get("home") or CHANNEL_HOME_DEFAULT.get(ch or "", "")

    def channels_read(self, via):
        return [e["name"] for e in self.channel_list if self.channel_mode(e["name"]) != "off" and e["via"] == via]

    def region_set(self, rid, on):
        """The dashboard's switch for a whole oblast (1.43). Returns (ok, message)."""
        rid = self._home_ok(rid)
        if not rid:
            return False, "not an oblast"
        if rid in self.LOCKED_REGIONS:
            return False, "Kyiv is always on"
        with self.lock:
            if on:
                self._regions_off.discard(rid)
                if rid != "ua" and rid not in DEFAULT_SCOPE:
                    self._regions_on.add(rid)
            else:
                self._regions_on.discard(rid)
                self._regions_off.add(rid)
        self._channels_save()
        return True, "ok"

    def regions(self):
        """For the dashboard: every compartment, on or off, with what is in it."""
        homes = {}
        for e in self.channel_list:
            homes.setdefault(e.get("home") or "", []).append(e["name"])
        out = [{"id": "31", "name": "м. Київ і Київська область", "en": "Kyiv city and oblast", "on": True, "locked": True,
                "channels": homes.get("31", [])},
               {"id": "ua", "name": "Уся Україна", "en": "All Ukraine", "on": self.region_on("ua"), "locked": False,
                "channels": homes.get("ua", [])}]
        for uid, uk, en in OBLASTS:
            if uid in ("31", "14"):
                continue
            out.append({"id": uid, "name": uk, "en": en, "on": self.region_on(uid), "locked": False,
                        "default": uid in DEFAULT_SCOPE, "channels": homes.get(uid, [])})
        if homes.get(""):
            out.append({"id": "", "name": "Без області", "en": "No oblast", "on": True, "locked": True, "channels": homes[""]})
        return out

    def channel_update(self, action, name, mode=None, via=None, home=None):
        """The dashboard's changes. Returns (ok, message)."""
        name = normalize_channel(name)
        if not name:
            return False, "not a Telegram channel name"
        e = next((x for x in self.channel_list if x["name"].lower() == name.lower()), None)
        with self.lock:
            if action == "add":
                if e:
                    return False, "already in the list"
                if len(self.channel_list) >= self.MAX_CHANNELS:
                    return False, f"at most {self.MAX_CHANNELS} channels"
                self.channel_list.append({"name": name, "builtin": False, "mode": "trial",
                                          "via": via if via in ("web", "api") else "web", "added": now_iso(),
                                          "home": self._home_ok(home)})
                self._deleted.pop(name.lower(), None)
            elif not e:
                return False, "not in the list"
            elif action == "set":
                if mode in self.CHANNEL_MODES:
                    e["mode"] = mode
                if via in ("web", "api"):
                    e["via"] = via
                if home is not None:
                    e["home"] = self._home_ok(home)
            elif action == "delete":
                if e["builtin"]:
                    return False, "a default channel can be switched off, not deleted"
                self.channel_list.remove(e)
                self._deleted[name.lower()] = now_iso()
            else:
                return False, "unknown action"
        self._channels_save()
        return True, "ok"

    # -- the admin's message to every reader (1.29) --------------------------------------------------------------
    # One message at a time, in up to three languages, shown as a banner on both pages until it expires or is
    # cleared. It is part of the alerts state (`notice`), so the live stream and /api/state both carry it.
    def notice_now(self):
        n = self.notice
        if n and n.get("until"):
            u = parse_iso(n["until"])
            if u and u <= datetime.now(timezone.utc):
                self.set_notice(None)
                return None
        return n

    # -- a nuclear event (1.32) -----------------------------------------------------------------------------------
    # The one message that covers the map: the radiation symbol, pulsing, and what to do. Behind two locks, because a
    # false one would be the worst thing this app could ever show: the dashboard must first ARM (the server hands back
    # a one-time code valid for two minutes), then FIRE with that code and the phrase typed in full. Ending it is one
    # step. Every change is logged. It travels in the alerts state (`nuke`), like the admin's message.
    NUKE_PHRASE = "NUCLEAR EVENT"
    # 1.42.2: the phrase in Ukrainian too — an admin on a Ukrainian keyboard could not type the English one
    NUKE_PHRASES = ("NUCLEAR EVENT", "ЯДЕРНА ПОДІЯ")

    def nuke_arm(self):
        import secrets
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        self._nuke_arm = (code, time.time() + 120)
        # 1.42.2: kept in the database too. The arming lived in the process only, and the process restarted often
        # (every release, and in the crashes of the shared-CPU nights): an arming made a minute before a restart was
        # gone, and the fire answered "not armed". Still one attempt, still two minutes.
        self.store.kv_set("nuke_arm", json.dumps({"code": code, "until": self._nuke_arm[1]}))
        log("NUKE: armed from the dashboard (code valid 2 min)")
        return code

    @staticmethod
    def _nuke_norm(s):
        # case and spacing never matter: "nuclear  event" is the phrase
        return re.sub(r"\s+", " ", (s or "").strip().upper())

    def nuke_fire(self, code, phrase, text):
        arm, self._nuke_arm = self._nuke_arm, None           # one attempt per arming, right or wrong
        if not arm:
            try:
                kv = json.loads(self.store.kv_get("nuke_arm") or "null")
                arm = (kv["code"], float(kv["until"])) if kv else None
            except Exception:
                arm = None
        self.store.kv_set("nuke_arm", "")
        if not arm or time.time() > arm[1]:
            return False, "not armed, or the arming expired — arm again"
        if (code or "").strip().upper() != arm[0]:
            return False, "wrong code — arm again"
        if self._nuke_norm(phrase) not in self.NUKE_PHRASES:
            return False, f"type the phrase exactly: {self.NUKE_PHRASE} (or {self.NUKE_PHRASES[1]})"
        self.nuke = {"id": f"k{int(time.time() * 1000)}", "since": now_iso(), "text": text}
        self.store.kv_set("nuke", json.dumps(self.nuke, ensure_ascii=False))
        log("NUKE: nuclear event ACTIVATED from the dashboard")
        self.publish({"kind": "nuke", "ts": now_iso(), "nuke": self.nuke})
        return True, "active"

    def nuke_end(self):
        was = self.nuke
        self.nuke, self._nuke_arm = None, None
        self.store.kv_set("nuke", "")
        self.store.kv_set("nuke_arm", "")
        if was:
            log("NUKE: nuclear event ended from the dashboard")
        self.publish({"kind": "nuke", "ts": now_iso(), "nuke": None})

    def set_notice(self, n):
        self.notice = n
        self.store.kv_set("notice", json.dumps(n, ensure_ascii=False) if n else "")
        self.publish({"kind": "notice", "ts": now_iso(), "notice": n})

    # -- fan-out --------------------------------------------------------
    def publish(self, event):
        with self.cond:
            self.seq += 1
            event["seq"] = self.seq
            for q in self.subscribers:
                q.append(event)
            self.cond.notify_all()
        cb = self.on_publish
        if cb:
            cb()

    on_publish = None       # the stream hub's wake-up (StreamHub.wake)

    def subscribe(self):
        q = []
        with self.cond:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.cond:
            if q in self.subscribers:
                self.subscribers.remove(q)

    # -- source status --------------------------------------------------
    def set_source(self, name, ok, **kw):
        with self.lock:
            self.sources[name] = {"ok": ok, "last": now_iso(), **kw}

    # -- reconciling a full snapshot from a source ----------------------
    eradar = None   # latest @eRadarrua per-oblast group counts: {"ts":…, "counts": {uid: {drones, jet, missiles}}}

    def set_eradar(self, ts, counts):
        with self.lock:
            if self.eradar and self.eradar["ts"] >= ts:
                return
            self.eradar = {"ts": ts, "counts": counts}
        self.publish({"kind": "eradar", "ts": ts, "counts": counts})

    def apply_snapshot(self, source, alerts, authoritative_levels, scope=None):
        """alerts: list of normalised alerts currently active according to `source`.
        authoritative_levels: set of location_type values this source is authoritative for
        (a keyless oblast-only source must not close raion-level alerts it cannot see)."""
        ts = now_iso()
        events = []
        with self.lock:
            incoming = {a["key"]: a for a in alerts}
            # starts / updates
            for key, a in incoming.items():
                old = self.active.get(key)
                if old is None:
                    self.active[key] = a
                    events.append({"kind": "start", "ts": ts, "alert": a})
                else:
                    changed = False
                    if (old.get("threats") or []) != (a.get("threats") or []):
                        old_types = {t.get("threat_type") for t in old.get("threats") or []}
                        for t in a.get("threats") or []:
                            if t.get("threat_type") not in old_types:
                                events.append({"kind": "threat", "ts": ts, "alert": a, "threat": t})
                        changed = True
                    if old.get("alert_level") != a.get("alert_level"):
                        changed = True
                    if changed:
                        self.active[key] = a
                        events.append({"kind": "update", "ts": ts, "alert": a})
            # ends
            for key in list(self.active.keys()):
                a = self.active[key]
                if key in incoming:
                    continue
                # close only what this source is allowed to see: its own alerts, or
                # any alert at a level it is authoritative for
                if a["source"] != source and (a["location_type"] not in authoritative_levels or (scope and a["oblast_uid"] not in scope)):
                    continue
                a = dict(a, finished_at=ts)
                del self.active[key]
                events.append({"kind": "end", "ts": ts, "alert": a})
        # persist + notify
        for ev in events:
            a = ev["alert"]
            if ev["kind"] == "end":
                self.store.finish_alert(a["key"], ev["ts"])
            else:
                self.store.upsert_alert(a)
            self.store.add_event({"ts": ev["ts"], "kind": ev["kind"], "key": a["key"], "location_uid": a["location_uid"],
                                  "location_title": a["location_title"], "alert_type": a["alert_type"],
                                  "oblast_uid": a["oblast_uid"], "detail": ev.get("threat") or {}})
            self.publish(ev)
            self.notifier.maybe(ev, self.cfg.get("favourites") or [])
            if getattr(self, "pusher", None):
                try:
                    self.pusher.on_event(ev)
                except Exception as e:
                    log("push:", e)
        if events:
            log(f"[{source}] {len(events)} event(s):", ", ".join(f"{e['kind']}:{e['alert']['location_title']}" for e in events[:8]))

    _marker_cache = {}
    _named_cache = {}        # 1.46: post id → the oblasts its text names (geo.oblasts_named)
    _ev_cache = {}
    _impact_cache = {}
    _impact_res = {}

    def markers(self):
        ttl = int(self.cfg.get("marker_ttl_minutes", 45))
        if not geo:
            return []
        kyiv_ends = self.kyiv_city_all_clears(ttl)
        out = self._marks_from_posts(sorted(self.store.feed_since(ttl), key=lambda p: p["ts"]), kyiv_ends, self._marker_cache)
        # Kyiv, its oblast, the five oblasts around it, and Sumy — the corridor most Shaheds into Kyiv arrive
        # through. Everything else is dropped here rather than hidden in the page, so a raid over Odesa never
        # reaches the Kyiv map, the counts, the proximity pushes or the light page. A mark with no oblast is kept
        # only if it sits close enough to still be about Kyiv.
        out = [m for m in out if in_scope(m)]
        out = self._chain_and_prune(out, ttl, kyiv_ends)
        out.sort(key=lambda m: m["ts"], reverse=True)
        # Keep what the app decided, not just what it was told. INSERT OR IGNORE keyed on the marker id, so
        # recomputing the same window many times a minute writes each marker exactly once.
        try:
            self.store.log_markers(out)
        except Exception as e:
            log(f"marker log failed: {e}")
        if len(self._marker_cache) > 2000:
            self._marker_cache.clear()
            self._ev_cache.clear()
            self._named_cache.clear()
        return out

    def _marks_from_posts(self, posts, kyiv_ends, cache, evidence=True):
        """Posts (oldest first) → the marks they place, each read in the context of the channel's previous post.
        The live map (markers) and the replay (1.42) read posts through this one function, so a replayed night is
        read exactly the way the map reads a live one — with today's rules."""
        out = []
        seen = []
        # channel -> (when its position was reported, marker, that time as text) — for the live-tracking channels'
        # bare lines ("Видубичі", "На Таращу", "Вибух"). 1.38: the clock is the POSITION's. A line that only says
        # where the target is going, or what happened to it, is placed at the channel's last reported position — and
        # used to restart that position's clock, so on 5 October a target destroyed at Vydubychi at 20:25 stood
        # there, "1 min ago", until 20:37, carried by lines about another target 100 km south.
        last_by_channel = {}
        # 1.44.1: the weapon each channel last named (from its posts' tags) — "Пуски КАБів в нашому напрямку" names no
        # place, and the reports after it ("Пролітають …", "Впали") name no weapon
        weapon_by_channel = {}
        near_by_channel = {}     # 1.45: the oblasts each channel named (or reported in) lately — geo's `near`
        for p in posts:
            pts = parse_iso(p["ts"])
            ms = cache.get(p["post_id"])
            if ms is None:
                near = [u for t_, u in reversed(near_by_channel.get(p["channel"], ()))
                        if pts and t_ and 0 <= (pts - t_).total_seconds() <= NEAR_CTX_MIN * 60]
                try:
                    ms = geo.parse_for_channel(p["channel"], p["text"], near or None)
                except Exception:
                    ms = []
                cache[p["post_id"]] = ms
            if pts:
                nb = near_by_channel.setdefault(p["channel"], [])
                # 1.46: read once per post — recomputed on every pass it was ~40 % of the time spent building the marks
                named = self._named_cache.get(p["post_id"])
                if named is None:
                    named = self._named_cache[p["post_id"]] = geo.oblasts_named(p["text"], p["channel"])
                nb.extend((pts, u) for u in named)
                nb.extend((pts, m["oblast_uid"]) for m in ms if m.get("oblast_uid") and m.get("lon") is not None)
                del nb[:-12]
            ctx = last_by_channel.get(p["channel"])
            # the official all-clear for Kyiv city ends every position a channel holds inside the city: whatever is
            # said after it is about another target, or about nothing
            if ctx and pts and ctx[1].get("oblast_uid") == "31" and any(ctx[0] < e <= pts for e in kyiv_ends):
                ctx = None
                last_by_channel.pop(p["channel"], None)
            fixed = []
            for m in ms:
                m = dict(m)
                if m.get("candidates"):
                    # 1.43: a name several villages of the oblast share ("Ивановка", "Троицкое"). The one within 60 km of
                    # this channel's report of the last half hour is the one it means; with no such report, the clear
                    # default the parser chose (raion centre, city district, by far the largest) — or nothing at all.
                    pick = None
                    if ctx and pts and (pts - ctx[0]).total_seconds() <= 30 * 60:
                        here = (ctx[1]["lon"], ctx[1]["lat"])
                        best = min(m["candidates"], key=lambda c: geo._km((c[1], c[2]), here))
                        if geo._km((best[1], best[2]), here) <= geo._REG_KM:
                            pick = best
                    if pick is None and m.get("ambiguous"):
                        continue
                    if pick is not None:
                        key, plon, plat, puid = pick
                        dest = bool(m.get("dest_only"))
                        m.update(lon=round(plon, 3), lat=round(plat, 3), oblast_uid=puid,
                                 place=("→ " + key) if dest else key)
                        if dest:
                            m["target"] = key
                        elif m.get("target") in geo.PLACES and m.get("heading") is not None:
                            tl, tt, _ = geo.PLACES[m["target"]]
                            m["heading"] = round(geo.bearing(plon, plat, tl, tt))
                        ev = dict(m.get("evidence") or {})
                        ev["position"] = dict(ev.get("position") or {}, place=key, confidence="medium",
                                              method=f"several villages are called {key.split(' (')[0]} — the one nearest this channel's previous report")
                        m["evidence"] = ev
                    m.pop("candidates", None)
                    m.pop("ambiguous", None)
                if m.get("needs_context"):
                    if ctx and pts and (pts - ctx[0]).total_seconds() <= 8 * 60:
                        m.update(lon=ctx[1]["lon"], lat=ctx[1]["lat"], place=ctx[1]["place"], oblast_uid=ctx[1].get("oblast_uid"), pos_ts=ctx[2])
                        wpn = weapon_by_channel.get(p["channel"])
                        kab = ctx[1].get("type") == "guided_aerial_bombs" or (
                            wpn and wpn[1] == "guided_aerial_bombs" and (pts - wpn[0]).total_seconds() <= 15 * 60)
                        if kab and m.get("status") == "down":
                            # 1.44: "Впали" after a guided-bomb report (@kabusumy) — the bombs hit the ground; nothing was
                            # shot down
                            m.update(status="impact", type="guided_aerial_bombs")
                        ev = dict(m.get("evidence") or {}); ev["position"] = dict(ev.get("position") or {}, matched=ctx[1].get("place"), place=ctx[1].get("place"))
                        m["evidence"] = ev
                    else:
                        continue
                elif m.get("dest_only"):
                    # "Два йдуть на Васильків": only where it is going. The target this channel reported last (within
                    # 8 min) is the one going there: it stays where that report put it, turned toward the destination.
                    # Without one it stays drawn at the destination, as an approach — never moved on past it.
                    if ctx and pts and (pts - ctx[0]).total_seconds() <= 8 * 60 and m.get("target") in geo.PLACES:
                        dlon, dlat, _ = geo.PLACES[m["target"]]
                        if math.hypot((dlon - ctx[1]["lon"]) * 70.7, (dlat - ctx[1]["lat"]) * 111) >= 0.4:
                            m.update(lon=ctx[1]["lon"], lat=ctx[1]["lat"], place=ctx[1]["place"], oblast_uid=ctx[1].get("oblast_uid"),
                                     approach=False, dest_only=False, pos_ts=ctx[2],
                                     heading=round(geo.bearing(ctx[1]["lon"], ctx[1]["lat"], dlon, dlat)))
                            ev = dict(m.get("evidence") or {})
                            ev["position"] = {"matched": ctx[1].get("place"), "place": ctx[1].get("place"), "confidence": "medium",
                                              "method": "this channel's previous report — the post only said where it is going"}
                            ev["heading"] = {"matched": f"{ctx[1].get('place')} → {m['target']}", "confidence": "medium",
                                             "method": "from the previous report toward the destination the post named"}
                            m["evidence"] = ev
                elif m.get("live"):
                    if ctx and pts and (pts - ctx[0]).total_seconds() <= 8 * 60 and m.get("heading") is None:
                        d = math.hypot((m["lon"] - ctx[1]["lon"]) * 70.7, (m["lat"] - ctx[1]["lat"]) * 111)
                        if d >= 0.4:
                            m["heading"] = round(geo.bearing(ctx[1]["lon"], ctx[1]["lat"], m["lon"], m["lat"]))
                            ev = dict(m.get("evidence") or {}); ev["heading"] = {"matched": f"{ctx[1].get('place')} → {m.get('place')}", "method": "bearing between the two latest reports of this live-tracking channel", "confidence": "medium"}
                            m["evidence"] = ev
                if m.get("lon") is not None and not m.get("status") and not m.get("approach"):
                    # a carried position keeps the time it was reported at; only a newly named place resets the clock
                    last_by_channel[p["channel"]] = ctx if (m.get("pos_ts") and ctx) else (pts, m, p["ts"])
                fixed.append(m)
            ms = fixed
            if pts:
                said = geo.prepare(p.get("text") or "", p["channel"]).lower()
                wpn = next((n for n, rx in geo.TYPE_RX if rx.search(said)), None)
                if wpn:
                    weapon_by_channel[p["channel"]] = (pts, wpn)
            # the channel said the target fell, was destroyed, is lost, or that the sky is clear: its position ends here
            if any(m.get("status") in ("down", "lost", "clear") for m in ms) or "clear" in (p.get("tags") or []):
                last_by_channel.pop(p["channel"], None)
            # one post, one marker per place: identical (type, position, status) items collapse (counts add up);
            # official administrations never place a target at an oblast centre; a missile needs a named place or a heading
            official_kind = geo.OFFICIAL_PARSERS.get(p["channel"], (None,))[0]
            merged = []
            for m in ms:
                if m.get("lon") is None:
                    merged.append(m); continue
                if m.get("place") == "область":
                    if official_kind in ("koda", "kmda") or ("missile" in m["type"] and m.get("heading") is None and not m.get("status")):
                        continue
                same = next((x for x in merged if x.get("type") == m.get("type") and x.get("status") == m.get("status") and x.get("lon") is not None
                             and abs(x["lon"] - m["lon"]) < 0.005 and abs(x["lat"] - m["lat"]) < 0.005), None)
                if same:
                    if m.get("count") and same.get("count"):
                        same["count"] = same["count"] + m["count"]
                    continue
                merged.append(m)
            ms = merged
            for i, m in enumerate(ms):
                dup = False
                for (t2, ty2, st2, ch2, lo2, la2) in seen:
                    if ch2 != p["channel"] and ty2 == m["type"] and st2 == m.get("status") and abs(lo2 - m["lon"]) < 0.08 and abs(la2 - m["lat"]) < 0.06 and pts and abs((pts - t2).total_seconds()) < 300:
                        dup = True   # the same report relayed by another channel
                        break
                if dup:
                    continue
                seen.append((pts, m["type"], m.get("status"), p["channel"], m["lon"], m["lat"]))
                ev = m.get("evidence")
                if not evidence:
                    out.append(dict(m, id=f"{p['post_id']}#{i}", ts=p["ts"], channel=p["channel"]))
                    continue
                if ev and _tr:
                    ck = (p["post_id"], i)
                    cached = self._ev_cache.get(ck)
                    if cached is None:
                        # evidence fragments use the fast offline glossary (no network per request)
                        ev = dict(ev, segment_en=_tr.translate_offline(ev.get("segment") or ""))
                        for k in ("type", "position", "heading", "count"):
                            v = ev.get(k)
                            if v:
                                v = dict(v, method=_tr.translate_offline(v.get("method") or ""))
                                if isinstance(v.get("matched"), str):
                                    v["matched_en"] = _tr.translate_offline(v["matched"])
                                ev[k] = v
                        self._ev_cache[ck] = ev
                    else:
                        ev = cached
                out.append(dict(m, id=f"{p['post_id']}#{i}", ts=p["ts"], text=p["text"], text_en=p.get("text_en"), channel=p["channel"], tags=p["tags"], evidence=ev))
        return self._drop_retracted(out, posts)

    @staticmethod
    def _drop_retracted(out, posts):
        """1.42.1: a ballistic or supersonic mark reported in the 20 minutes before a channel's retraction is gone."""
        rts = [t for t in (parse_iso(p["ts"]) for p in posts if "retract" in (p.get("tags") or [])) if t]
        if not rts:
            return out
        fast = ("ballistic_missiles", "supersonic_missiles")

        def taken_back(m):
            t = parse_iso(m.get("ts"))
            return m.get("type") in fast and not m.get("status") and t and any(0 <= (r - t).total_seconds() <= 1200 for r in rts)
        return [m for m in out if not taken_back(m)]

    # -- one computation for everybody --------------------------------------------------------------------------
    # 25 Sep 2026, during an attack: every new post made EVERY open page ask for the marks, the feed and the
    # state at the same moment, and each request recomputed them from scratch — the marks from 45 minutes of
    # posts, the feed with its offline translation, each serialised on its own. With the pages that reconnect
    # after a restart on top, the one shared CPU never caught up and the server stopped answering. Now each
    # answer is built once per change (and at most every `ttl` seconds), by one thread while the others wait for
    # it, serialised and compressed once, and the same bytes go to every page.
    _resp = {}
    _resp_locks = {}
    _resp_guard = threading.Lock()

    def cached(self, name, ttl, build, ver=None):
        """(built_at, body, gzipped body or None, object) for `build()`; rebuilt when `ver` changes or `ttl`
        seconds have passed, never by two threads at once."""
        hit = self._resp.get(name)
        if hit and hit[4] == ver and time.time() - hit[0] < ttl:
            return hit
        with self._resp_guard:
            lk = self._resp_locks.setdefault(name, threading.Lock())
        with lk:
            hit = self._resp.get(name)
            if hit and hit[4] == ver and time.time() - hit[0] < ttl:
                return hit
            obj = build()
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            hit = (time.time(), body, gzip.compress(body, 5) if len(body) > 1400 else None, obj, ver)
            self._resp[name] = hit
            return hit

    _bridges_res = None
    BRIDGE_RANK = {"hit": 1, "near": 2, "at": 3}

    def bridges_now(self):
        """{bridge id: {} or {lvl, km, type, jet, place, ts, ch, n, how}} — what was reported on or near each bridge
        now. "at" / "near" from a live, positioned mark (never a stale one, never a closed track, never one placed
        at a vague point, never an outcome); "at" also when a post of the last 5 minutes names the bridge and says
        nothing happened to the target; "hit" only when a post of the last 30 minutes names the bridge AND says the
        bridge was hit (влучання, пошкоджено, приліт). 1.38: an explosion is not a hit. On 5 October a bare "Вибух"
        — an interception, placed at the tracker's last position, Vydubychi — made "Darnytskyi Bridge: hit reported"
        and "Southern Bridge: hit reported" for half an hour; nobody had reported a hit. And nothing posted before
        the official all-clear for Kyiv city counts after it. Cached 3 s."""
        if self._bridges_res and time.time() - self._bridges_res[0] < 3:
            return self._bridges_res[1]
        now = datetime.now(timezone.utc)
        out = {b["id"]: {} for b in BRIDGES}
        rank = self.BRIDGE_RANK
        ends = self.kyiv_city_all_clears(35)

        def offer(bid, cand):
            cur = out[bid]
            if not cur or (rank[cand["lvl"]], -(cand.get("km") if cand.get("km") is not None else 99), cand["ts"]) > \
                    (rank[cur["lvl"]], -(cur.get("km") if cur.get("km") is not None else 99), cur["ts"]):
                cand["n"] = cur.get("n", 0) + (cand["lvl"] != "hit")
                out[bid] = cand
            elif cand["lvl"] != "hit":
                cur["n"] = cur.get("n", 0) + 1
        for m in self.markers_now():
            if m.get("lat") is None or m.get("lon") is None or m.get("oblast_uid") not in ("31", "14"):
                continue
            place = (m.get("place") or "").replace("→", "").strip()
            if place in BRIDGE_VAGUE or m.get("stale") or m.get("endedBy"):
                continue
            t = parse_iso(m.get("pos_ts") or m.get("ts"))
            if not t or any(t < e <= now for e in ends):
                continue
            age = (now - t).total_seconds() / 60
            if m.get("status") or age > 30:
                continue                     # an outcome (shot down, an explosion, lost) is no target on a bridge
            fast = bool(m.get("jet") or m.get("fast") or "missile" in (m.get("type") or ""))
            for b in BRIDGES:
                d = 0.0 if BRIDGE_BY_PLACE.get(place) == b["id"] else bridge_km(m["lon"], m["lat"], b)
                lvl = "at" if d <= BRIDGE_AT_KM else "near" if d <= (BRIDGE_NEAR_FAST_KM if fast else BRIDGE_NEAR_KM) else None
                if lvl:
                    offer(b["id"], {"lvl": lvl, "km": round(d, 1), "type": m.get("type"), "jet": bool(m.get("jet")), "place": place,
                                    "ts": m.get("ts"), "ch": m.get("channel"), "how": "mark"})
        for p in self.store.feed_since(31, limit=200, translate=False):
            tags = set(p.get("tags") or [])
            t = parse_iso(p.get("ts"))
            if not t or tags & {"clear", "forecast", "news", "trial", "af_summary"} or any(t < e <= now for e in ends):
                continue
            text = p.get("text") or ""
            if geo and geo.looks_like_news(geo._norm(text)):
                continue
            named = bridges_named(text)
            if not named:
                continue
            if BRIDGE_HIT_RX.search(text):
                lvl = "hit"                          # the post says the bridge itself was hit
            elif (now - t).total_seconds() <= 300 and not (geo and any(rx.search(text) for _, rx in geo.STATUS_RX)):
                lvl = "at"                           # names the bridge, and nothing happened to the target yet
            else:
                continue
            for bid in named:
                if not out[bid] or rank[out[bid]["lvl"]] < rank[lvl] or (lvl == "hit" and out[bid]["lvl"] != "at"):
                    offer(bid, {"lvl": lvl, "km": None, "type": None, "jet": False, "place": None, "ts": p["ts"],
                                "ch": p.get("channel"), "how": "named"})
        self._bridges_res = (time.time(), out)
        return out

    def kyiv_city_all_clears(self, minutes):
        """When the official air-raid alert over Kyiv city ended within the last `minutes` — an end that left no other
        source's alert over the city running. Telegram never ends an alert; this is the official one."""
        try:
            rows = self.store.history(hours=minutes / 60 + 0.5, oblast_uids=["31"])
        except Exception:
            return []
        spans = [(parse_iso(a["started_at"]), parse_iso(a["finished_at"]) if a.get("finished_at") else None) for a in rows
                 if (a.get("alert_type") or "air_raid") == "air_raid" and parse_iso(a.get("started_at"))]
        return sorted(e for i, (s_, e) in enumerate(spans)
                      if e and not any(j != i and s2 <= e and (e2 is None or e2 > e) for j, (s2, e2) in enumerate(spans)))

    def bridges_busy(self):
        """A live threat within 12 km of a bridge: the Kyiv trackers are then read as often as in a missile threat."""
        for m in self.markers_now():
            if m.get("lat") is None or m.get("status") or m.get("stale") or m.get("oblast_uid") not in ("31", "14"):
                continue
            if min(bridge_km(m["lon"], m["lat"], b) for b in BRIDGES) <= 12:
                return True
        return False

    def markers_now(self):
        """The marks as the pages see them — the cached computation, never a private recomputation."""
        return self.cached("markers", 10, self._markers_obj, ver=self.seq)[3]["markers"]

    # 1.29: every cached answer the live stream sends in pieces carries `h`, a hash of its content, and the
    # build keeps each entry's serialisation (`_entries`) so the stream hub can say what changed since the
    # last message without serialising anything twice. A page knows which version it shows by its `h`.
    _entries = {}

    def _markers_obj(self):
        ms = self.markers()
        e = _keyed(ms, lambda m: str(m.get("id")))
        self._entries["markers"] = e
        return {"now": now_iso(), "ttl_minutes": int(self.cfg.get("marker_ttl_minutes", 45)),
                "stale_minutes": int(self.cfg.get("track_stale_minutes", 5)), "markers": ms, "h": e["h"]}

    def _state_obj(self):
        snap = self.snapshot()
        e = _keyed(snap["active"], _alert_id)
        e["rest"] = {k: _canon(v) for k, v in snap.items() if k not in ("now", "active")}
        e["restd"] = {k: {sk: _canon(sv) for sk, sv in v.items()} for k, v in snap.items()
                      if k not in ("now", "active") and isinstance(v, dict)}
        e["h"] = _hash(e["h"] + "".join(f"\n{k}\t{e['rest'][k]}" for k in sorted(e["rest"])))
        e["obj"] = snap
        self._entries["state"] = e
        snap["h"] = e["h"]
        return snap

    def state_now(self):
        return self.cached("state", 5, self._state_obj, ver=self.seq)

    def _feed_obj(self, limit):
        f = self.store.feed(limit)
        e = _keyed(f, lambda p: p["post_id"])
        self._entries[f"feed:{limit}"] = e
        return {"feed": f, "h": e["h"]}

    def feed_now(self, limit):
        return self.cached(f"feed:{limit}", 15, lambda: self._feed_obj(limit), ver=self.seq)

    # -- the dashboard's analytics (1.32): how the attacks change, week after week ----------------------------------
    # Three records, each for what it can say, never mixed:
    #   - the Air Force's summaries (af_reports): what was launched over Ukraine and shot down, type by type, the
    #     launch areas, the main directions, the missile models, the hits — the official series;
    #   - the official alerts (alerts): minutes under alert over Kyiv city and the oblast, and when alerts start;
    #   - the marks this app placed (marker_log), Kyiv city + oblast: reports by type, by hour, their stated courses
    #     — a volume of REPORTS read from channels, never a count of targets.
    def analytics(self, days=30):
        tz = kyiv_tz()
        now = datetime.now(timezone.utc)
        today = now.astimezone(tz).date()
        start_d = today - timedelta(days=days - 1)
        dates = [(start_d + timedelta(days=i)).isoformat() for i in range(days)]
        # 1. the Air Force, per date (night + day of the same date added up)
        af = {d: {"date": d, "launched": {}, "down": {}, "used": [], "impacts": 0, "debris": 0, "periods": []} for d in dates}
        areas, dirs, models = collections.Counter(), collections.Counter(), collections.Counter()
        for r in self.store.af_reports(start_d.isoformat()):
            row = af.get(r.get("date"))
            if not row:
                continue
            row["periods"].append(r.get("period"))
            if r.get("period") == "night" and (r.get("launched") or {}).get("drones") is not None:
                row["night_drones"] = r["launched"]["drones"]
            for k, v in (r.get("launched") or {}).items():
                row["launched"][k] = row["launched"].get(k, 0) + v
            for k, v in (r.get("down") or {}).items():
                row["down"][k] = row["down"].get(k, 0) + v
            row["used"] = sorted(set(row["used"]) | set(r.get("used") or []))
            row["impacts"] += r.get("impacts", 0)
            row["debris"] += r.get("debris", 0)
            areas.update(r.get("areas") or [])
            dirs.update(r.get("directions") or [])
            models.update(r.get("models") or [])
        # 2. the official alerts over Kyiv city (31) and the oblast (14): minutes per day, and when they start
        t0 = datetime(start_d.year, start_d.month, start_d.day, tzinfo=tz).astimezone(timezone.utc)
        with self.store.lock:
            # by oblast_uid, whatever the level: the city is one unit (31); "the oblast" is any raion of 14 under alert
            al = self.store.conn.execute(
                "SELECT oblast_uid, location_type, alert_level, started_at, finished_at FROM alerts WHERE (finished_at IS NULL OR finished_at>=?) "
                "AND oblast_uid IN ('31','14') AND alert_type='air_raid'", (t0.isoformat(),)).fetchall()
        spans = {"31": [], "14": []}
        starts = [[0] * 24 for _ in range(7)]
        for uid, _lt, _lvl, sa, fa in al:
            a, b = parse_iso(sa), parse_iso(fa) or now
            if not a or (not fa and (now - a).days > 3):
                continue                            # left open by a restart, not an alert of three days
            spans[uid].append((max(a, t0), b))
            if uid == "31" and a >= t0:
                k = a.astimezone(tz)
                starts[k.weekday()][k.hour] += 1
        kyiv = []
        for d in dates:
            dd = datetime.fromisoformat(d).replace(tzinfo=tz)
            lo, hi = dd.astimezone(timezone.utc), (dd + timedelta(days=1)).astimezone(timezone.utc)
            row = {"date": d}
            for uid, key in (("31", "city_min"), ("14", "oblast_min")):
                row[key] = _union_minutes([(max(a, lo), min(b, hi)) for a, b in spans[uid] if a < hi and b > lo])
            row["city_alerts"] = len({a for a, _ in spans["31"] if lo <= a < hi})
            kyiv.append(row)
        # 3. the marks placed over Kyiv city + oblast: reports by type per 24 h (18:00 → 18:00, named by the morning
        #    date, like the Air Force's nights), by hour of day, and the courses the posts stated
        with self.store.lock:
            ml = self.store.conn.execute("SELECT ts, type, status, heading, jet FROM marker_log WHERE ts>=? AND oblast_uid IN ('31','14')",
                                         (t0.isoformat(),)).fetchall()
        rep = {d: {"date": d} for d in dates}
        hours = [0] * 24
        heads = [0] * 8
        for ts, typ, status, heading, jet in ml:
            k = parse_iso(ts)
            if not k:
                continue
            k = k.astimezone(tz)
            d = (k + timedelta(hours=6)).date().isoformat()
            row = rep.get(d)
            if row is None:
                continue
            key = status if status in ("down", "impact") else ("jet" if (typ == "drones" and jet) else (typ or "unknown"))
            row[key] = row.get(key, 0) + 1
            if not status:
                hours[k.hour] += 1
                if typ == "drones" and heading is not None:
                    heads[int(((float(heading) % 360) + 22.5) // 45) % 8] += 1
        return {"days": days, "from": dates[0], "to": dates[-1], "generated": now_iso(),
                "af": [af[d] for d in dates], "af_areas": areas.most_common(15), "af_directions": dirs.most_common(12),
                "af_models": models.most_common(12), "kyiv": kyiv, "starts": starts,
                "reports": [rep[d] for d in dates], "hours": hours, "headings": heads,
                "weather": self._an_weather(dates), "approach": self._an_approach(t0, dates),
                "air": self._an_air(t0, dates), "obl": self._an_oblasts(t0, dates),
                "places": self.drone_heat(days)["points"][:25], "bridges": self._an_bridges(t0, dates),
                "weather_status": getattr(self, "weather_status", None)}

    # -- 1.33: the weather, the approach sides, the carriers, and the time under alert oblast by oblast ---------------
    def _an_bridges(self, t0, dates):
        """1.34: each time a target was reported on or near a Kyiv bridge (bridge_events), per date (24 h from 18:00)."""
        tz = kyiv_tz()
        with self.store.lock:
            rows = self.store.conn.execute("SELECT ts, bridge, lvl, km, type, jet, place, channel, how FROM bridge_events WHERE ts>=? ORDER BY ts",
                                           (t0.isoformat(),)).fetchall()
        per = {d: {b["id"]: 0 for b in BRIDGES} for d in dates}
        tot = {b["id"]: {"at": 0, "near": 0} for b in BRIDGES}
        for ts, bid, lvl, *_ in rows:
            k = parse_iso(ts)
            if not k or bid not in tot:
                continue
            d = (k.astimezone(tz) + timedelta(hours=6)).date().isoformat()
            if d in per:
                per[d][bid] += 1
            if lvl in tot[bid]:
                tot[bid][lvl] += 1
        recent = [dict(zip(("ts", "bridge", "lvl", "km", "type", "jet", "place", "channel", "how"), r)) for r in rows[-30:]][::-1]
        return {"names": {b["id"]: {"uk": b["uk"], "en": b["en"]} for b in BRIDGES}, "per_date": [dict(per[d], date=d) for d in dates],
                "totals": tot, "recent": recent}

    def _an_weather(self, dates):
        wx = self.store.weather(dates[0])
        out = []
        for d in dates:
            w = wx.get(d) or {}
            launch = [w[k] for k in WEATHER_LAUNCH if k in w]
            row = {"date": d, "kyiv": w.get("kyiv")}
            if launch:
                def avg(f):
                    v = [x[f] for x in launch if x.get(f) is not None]
                    return round(sum(v) / len(v), 1) if v else None
                row["launch"] = {"wind": avg("wind"), "gust": max((x["gust"] for x in launch if x.get("gust") is not None), default=None),
                                 "cloud": avg("cloud"), "precip": avg("precip"), "tmin": min((x["tmin"] for x in launch if x.get("tmin") is not None), default=None),
                                 "points": len(launch)}
            out.append(row)
        return out

    APPROACH_KM = (20, 130)

    def _an_approach(self, t0, dates):
        """Where the channels placed drones around Kyiv: the side of Kyiv (8 sectors), 20–130 km out, in Kyiv oblast,
        per 24 h from 18:00. Positions the posts stated (a town, high or medium confidence); a post counts once per
        side. Nothing is extrapolated."""
        tz = kyiv_tz()
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT ts, post_id, lon, lat FROM marker_log WHERE ts>=? AND oblast_uid='14' AND type='drones' AND status IS NULL "
                "AND lon IS NOT NULL AND lat IS NOT NULL AND pos_conf IN ('high','medium')", (t0.isoformat(),)).fetchall()
        by = {d: [0] * 8 for d in dates}
        seen = set()
        lo, hi = self.APPROACH_KM
        for ts, pid, lon, lat in rows:
            k = parse_iso(ts)
            if not k:
                continue
            dist = haversine_km(50.45, 30.52, lat, lon)
            if not lo <= dist <= hi:
                continue
            sec = int(((geo.bearing(30.52, 50.45, lon, lat) if geo else 0) + 22.5) // 45) % 8
            d = (k.astimezone(tz) + timedelta(hours=6)).date().isoformat()
            if d not in by or (pid, sec) in seen:
                continue
            seen.add((pid, sec))
            by[d][sec] += 1
        return [{"date": d, "s": by[d]} for d in dates]

    def _an_air(self, t0, dates):
        tz = kyiv_tz()
        sorties = air_sorties(self.store.air_reports((t0 - timedelta(hours=14)).isoformat()))
        keep, per = [], {d: {k: 0 for k in AIR_KINDS} for d in dates}
        for so in sorties:
            first = parse_iso(so["start"] or so["launch"])
            if not first or first < t0:
                continue
            d = (first.astimezone(tz) + timedelta(hours=6)).date().isoformat()
            if d in per:
                per[d][so["kind"]] += 1
            keep.append(so)

        def q(v, f):                                    # a quantile, interpolated (the median of 3 and 50 is 26)
            v = sorted(v)
            if not v:
                return None
            i = f * (len(v) - 1)
            lo = int(i)
            hi = min(lo + 1, len(v) - 1)
            return round(v[lo] + (v[hi] - v[lo]) * (i - lo))
        stats = {}
        for k in AIR_KINDS:
            ss = [x for x in keep if x["kind"] == k]
            dl = [x["delay_min"] for x in ss if x["delay_min"] is not None]
            up = [x["up_min"] for x in ss if x["up_min"] is not None]
            stats[k] = {"sorties": len(ss), "with_takeoff": sum(1 for x in ss if x["start"]),
                        "launched": sum(1 for x in ss if x["launch"]), "stood_down": sum(1 for x in ss if x["end"] and not x["launch"]),
                        "delay_median": q(dl, .5), "delay_p25": q(dl, .25), "delay_p75": q(dl, .75), "delays": len(dl),
                        "up_median": q(up, .5)}
        return {"per_date": [dict(per[d], date=d) for d in dates], "stats": stats, "sorties": keep[-60:][::-1]}

    def _alert_spans(self, t0):
        """Air-raid alert time per oblast since t0 — in any part of it (the oblast's own alert, a raion's, a
        hromada's). A row still open counts to now only while that alert is active: one a restart left open does not."""
        now = datetime.now(timezone.utc)
        with self.lock:
            live = set(self.active)
        with self.store.lock:
            rows = self.store.conn.execute("SELECT key, oblast_uid, started_at, finished_at FROM alerts WHERE alert_type='air_raid' "
                                           "AND (finished_at IS NULL OR finished_at>=?)", (t0.isoformat(),)).fetchall()
        spans = collections.defaultdict(list)
        for key, uid, sa, fa in rows:
            a = parse_iso(sa)
            b = parse_iso(fa) if fa else (now if key in live else None)
            if not uid or not a or not b or b <= t0 or a >= now:
                continue
            spans[uid].append((max(a, t0), min(b, now)))
        return spans

    def _an_oblasts(self, t0, dates):
        """Hours under an air-raid alert, oblast by oblast, per week (per day for two weeks or less)."""
        tz = kyiv_tz()
        spans = self._alert_spans(t0)
        edges = [datetime.fromisoformat(d).replace(tzinfo=tz).astimezone(timezone.utc) for d in dates]
        last = datetime.fromisoformat(dates[-1]).replace(tzinfo=tz) + timedelta(days=1)
        edges.append(last.astimezone(timezone.utc))
        by_week = len(dates) > 14
        cols, col_of = [], []
        for d in dates:
            key = (datetime.fromisoformat(d) - timedelta(days=datetime.fromisoformat(d).weekday())).date().isoformat() if by_week else d
            if not cols or cols[-1]["from"] != key:
                cols.append({"from": key, "days": 0})
            cols[-1]["days"] += 1
            col_of.append(len(cols) - 1)
        rows = []
        for uid, uk, en in OBLASTS:
            per_day = collections.defaultdict(list)
            for a, b in spans.get(uid, []):
                i = max(0, bisect.bisect_right(edges, a) - 1)
                while i < len(dates) and edges[i] < b:
                    per_day[i].append((max(a, edges[i]), min(b, edges[i + 1])))
                    i += 1
            mins = [0] * len(cols)
            for i, sp in per_day.items():
                mins[col_of[i]] += _union_minutes(sp)
            tot = sum(mins)
            if tot:
                rows.append({"uid": uid, "uk": uk, "en": en, "h": [round(m / 60, 1) for m in mins], "total_h": round(tot / 60, 1)})
        rows.sort(key=lambda r: -r["total_h"])
        return {"by": "week" if by_week else "day", "cols": cols, "rows": rows}

    def drone_heat(self, days):
        """The heat layer (1.34, public): where drones and unidentified targets were reported, as the posts placed
        them — one point per place with the number of posts that named it. Town- and district-level positions only
        (never an oblast's centre, never "Kyiv" alone or a bank of the river). Shoot-downs and hits are not counted:
        they would show where the air defence works, not where drones go."""
        t0 = datetime.now(timezone.utc) - timedelta(days=days)
        with self.store.lock:
            rows = self.store.conn.execute(
                "SELECT post_id, place, lon, lat, oblast_uid FROM marker_log WHERE ts>=? AND type IN ('drones','unknown','banderol_missiles') "
                "AND status IS NULL AND lon IS NOT NULL AND lat IS NOT NULL AND pos_conf IN ('high','medium')", (t0.isoformat(),)).fetchall()
        agg, seen = {}, set()
        for pid, place, lon, lat, uid in rows:
            pl = (place or "").replace("→", "").strip()
            if not pl or pl in BRIDGE_VAGUE:
                continue
            k = (pl, round(lon, 3), round(lat, 3))
            if (pid, k) in seen:
                continue
            seen.add((pid, k))
            a = agg.setdefault(k, [round(lon, 4), round(lat, 4), 0, pl, uid])
            a[2] += 1
        pts = sorted(agg.values(), key=lambda a: -a[2])
        return {"days": days, "generated": now_iso(), "reports": sum(a[2] for a in pts), "points": pts}

    # -- the dashboard: is every source alive, is every channel still posting, how early was the map ---------
    _health_res = None

    def health(self):
        if self._health_res and time.time() - self._health_res[0] < 60:
            return self._health_res[1]
        now = datetime.now(timezone.utc)
        with self.lock:
            sources = {k: dict(v) for k, v in self.sources.items()}
        since24 = (now - timedelta(hours=24)).isoformat()
        with self.store.lock:
            c = self.store.conn
            f24 = {r[0]: r[1] for r in c.execute("SELECT channel, COUNT(*) FROM feed WHERE ts>=? GROUP BY channel", (since24,))}
            m24 = {r[0]: r[1] for r in c.execute(
                "SELECT channel, COUNT(*) FROM marker_log WHERE ts>=? AND status IS NULL GROUP BY channel", (since24,))}
            last = {r[0]: r[1] for r in c.execute("SELECT channel, MAX(ts) FROM feed GROUP BY channel")}
        week = {r["channel"]: r for r in self.store.channel_report(7)}
        listed = [e["name"] for e in self.channel_list]
        low = {c.lower() for c in listed}
        names = listed + [ch for ch in list(f24) + list(week) if ch.lower() not in low]
        reg = {e["name"].lower(): e for e in self.channel_list}
        channels = []
        for ch in dict.fromkeys(names):
            src = sources.get(f"tga:{ch}") or sources.get(f"tg:{ch}") or {}
            w = week.get(ch) or {}
            channels.append({"channel": ch, "posts_24h": f24.get(ch, 0), "marks_24h": m24.get(ch, 0), "last_post": last.get(ch),
                             "posts_7d": w.get("posts", 0), "read_7d": w.get("with_marker", 0), "outcomes_7d": w.get("outcomes", 0),
                             "flagged_7d": w.get("flagged", 0), "ok": src.get("ok"), "checked": src.get("last"),
                             "error": src.get("error"), "via": "api" if f"tga:{ch}" in sources else ("preview" if src else None),
                             "mode": self.channel_mode(ch), "listed": ch.lower() in reg, "builtin": bool(reg.get(ch.lower(), {}).get("builtin")),
                             "read_via": reg.get(ch.lower(), {}).get("via"), "added": reg.get(ch.lower(), {}).get("added"),
                             "home": reg.get(ch.lower(), {}).get("home", "") if ch.lower() in reg else None})
        official = [{"name": k, **v} for k, v in sorted(sources.items()) if not k.startswith(("tg:", "tga:"))]
        tr = {"available": [], "paused": {}}
        if _tr:
            try:
                tr["available"] = [n for n, _ in _tr.backends()]
                tr["paused"] = {n: int(u - time.time()) for n, u in _tr._DOWN.items() if u > time.time()}
            except Exception:
                pass
        out = {"generated": now_iso(), "official": official, "channels": channels, "translation": tr, "lead": self.lead_times(30),
               "tg_api": TelegramAPI.configured(self.cfg), "max_channels": self.MAX_CHANNELS, "regions": self.regions(),
               "imagery": {"sat": dict(zip(("version", "maxzoom"), SAT.info())), "esri": self.esri.stats()}}
        self._health_res = (time.time(), out)
        return out

    def lead_times(self, days=30):
        """How long before each official air-raid alert over Kyiv or Kyiv oblast the map already showed a threat
        there (a live mark in the hour before it). Alerts that start within 30 min of another are one wave, counted
        once. A wave with nothing on the map in the hour before it counts as no warning — never as a zero lead."""
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        starts = sorted(st for st in (parse_iso(a["started_at"]) for a in self.store.history(days * 24, ["31", "14"])
                                      if (a.get("alert_type") or "air_raid") == "air_raid") if st and st >= since)
        marks = sorted(parse_iso(m["ts"]) for m in self.store.markers_between((since - timedelta(hours=1)).isoformat(), now.isoformat())
                       if m.get("oblast_uid") in ("31", "14"))
        marks = [m for m in marks if m]
        leads, waves, prev = [], 0, None
        for st in starts:
            if prev and (st - prev).total_seconds() < 1800:
                prev = st
                continue
            prev = st
            waves += 1
            i = bisect.bisect_left(marks, st - timedelta(hours=1))
            if i < len(marks) and marks[i] <= st:
                leads.append((st - marks[i]).total_seconds() / 60)
        leads.sort()

        def q(f):
            return round(leads[min(len(leads) - 1, int(f * len(leads)))]) if leads else None
        return {"days": days, "waves": waves, "warned": len(leads), "median_min": q(.5), "p25_min": q(.25), "p75_min": q(.75)}

    # -- nights and weeks, as numbers and in words ---------------------------------------------------------------
    def digest_facts(self, start, end, kind="night"):
        """Everything this app recorded over Kyiv and Kyiv oblast between two UTC datetimes: the official alerts,
        what the channels reported (marks), the outcomes, and the Air Force's own figures. Counts only — no post
        text, no reader, nobody."""
        tz = kyiv_tz()
        now = datetime.now(timezone.utc)

        def loc(d):
            return d.astimezone(tz).strftime("%d.%m %H:%M")
        hours = int((now - start).total_seconds() / 3600) + 2
        al = [a for a in self.store.history(hours, ["31", "14"]) if (a.get("alert_type") or "air_raid") == "air_raid"]
        spans = []
        for a in al:
            s, e = parse_iso(a["started_at"]), parse_iso(a["finished_at"]) if a["finished_at"] else now
            if not s or s >= end or (e and e <= start):
                continue
            spans.append((a, max(s, start), min(e or end, end)))
        city = [(s, e) for a, s, e in spans if a["oblast_uid"] == "31"]
        units = {}
        for a, s, e in spans:
            if a["oblast_uid"] == "14":
                units.setdefault(a["location_title"], []).append((s, e))
        longest = max(((e - s).total_seconds() / 60 for a, s, e in spans if a["oblast_uid"] == "31"), default=None)
        starts = sorted(s for a, s, e in spans if parse_iso(a["started_at"]) >= start)
        waves, prev = [], None
        for s in starts:
            if not prev or (s - prev).total_seconds() >= 1800:
                waves.append(s)
            prev = s
        with self.store.lock:
            mk = self.store.conn.execute(
                "SELECT ts,type,place,heading,jet,count,channel FROM marker_log WHERE ts>=? AND ts<? AND status IS NULL "
                "AND oblast_uid IN ('31','14')", (start.isoformat(), end.isoformat())).fetchall()
            oc = self.store.conn.execute(
                "SELECT ts,status,type,place FROM outcomes WHERE ts>=? AND ts<? AND oblast_uid IN ('31','14')",
                (start.isoformat(), end.isoformat())).fetchall()
        kinds = collections.Counter(("jet_drones" if r[4] else "drones") if r[1] == "drones" else r[1] for r in mk)
        places = collections.Counter((r[2] or "").replace("→ ", "") for r in mk if r[2] and r[2] != "область")
        course = collections.Counter(COMPASS8[int(((r[3] % 360) + 22.5) // 45) % 8] for r in mk if r[3] is not None)
        hours_k = collections.Counter(parse_iso(r[0]).astimezone(tz).strftime("%H:00") for r in mk if parse_iso(r[0]))
        marks_ts = sorted(t for t in (parse_iso(r[0]) for r in mk) if t)
        lead = []
        for w in waves:
            before = [t for t in marks_ts if w - timedelta(hours=1) <= t <= w]
            if before:
                lead.append(round((w - before[0]).total_seconds() / 60))
        outc = collections.Counter(r[1] for r in oc)
        oplaces = collections.Counter((r[3] or "") for r in oc if r[1] in ("down", "impact") and r[3] and r[3] != "область")
        # the Air Force's figures (all of Ukraine): the summaries kept in af_reports (1.32: type by type, and the
        # ones the backfill recovered) posted over the period, or — for a night — the morning summary after it
        af_to = min(now, end + timedelta(hours=4)) if kind == "night" else end
        af = {}
        for r in self.store.af_reports((start.astimezone(tz).date() - timedelta(days=1)).isoformat()):
            pt = parse_iso(r.get("ts"))
            if not pt or pt < start or pt > af_to:
                continue
            la, dn = r.get("launched") or {}, r.get("down") or {}
            af[f"{r.get('date', '')[8:10]}.{r.get('date', '')[5:7]} {r.get('period')}"] = {
                "drones": la.get("drones", 0), "missiles": af_missiles(la), "down": dn.get("total", 0),
                "launched": la, "down_by_type": {k: v for k, v in dn.items() if k != "total"},
                "used_number_not_given": r.get("used") or [], "hit_locations": r.get("impacts", 0),
                "debris_locations": r.get("debris", 0), "main_directions": r.get("directions") or []}
        facts = {
            "period": {"kind": kind, "from": loc(start), "to": loc(end), "timezone": "Kyiv"},
            "official_alerts": {
                "kyiv_city_minutes_under_alert": _union_minutes(city),
                "kyiv_city_alerts": len(city),
                "kyiv_city_longest_alert_minutes": round(longest) if longest else 0,
                "alert_waves_kyiv_and_oblast": len(waves),
                "alerts_by_level": dict(collections.Counter((a.get("alert_level") or "not given") for a, s, e in spans)),
                "kyiv_oblast_units_minutes_under_alert": dict(sorted(((k, _union_minutes(v)) for k, v in units.items()), key=lambda x: -x[1])[:10]),
            },
            "channel_reports": {
                "reports": len(mk), "by_type": dict(kinds.most_common()), "most_named_places": dict(places.most_common(10)),
                "reported_course": dict(course.most_common()), "busiest_hours": dict(hours_k.most_common(4)),
                "first_report": loc(marks_ts[0]) if marks_ts else None, "last_report": loc(marks_ts[-1]) if marks_ts else None,
                "note": "posts of monitoring channels read by the app — reports, not a count of drones or missiles",
            },
            "outcomes_reported": {"by_kind": dict(outc.most_common()), "places": dict(oplaces.most_common(8)),
                                  "note": "shoot-downs ('down') and explosions ('impact') as reported by channels"},
            "map_ahead_of_alert": {"waves_with_a_mark_before": len(lead), "median_minutes_ahead": sorted(lead)[len(lead) // 2] if lead else None},
            "air_force_all_ukraine": af or None,
        }
        return facts

    def digest_totals(self, start, end):
        """The few numbers a week is compared on."""
        f = self.digest_facts(start, end, "week")
        return {"kyiv_city_minutes_under_alert": f["official_alerts"]["kyiv_city_minutes_under_alert"],
                "alert_waves": f["official_alerts"]["alert_waves_kyiv_and_oblast"], "reports": f["channel_reports"]["reports"],
                "shoot_downs_reported": f["outcomes_reported"]["by_kind"].get("down", 0),
                "explosions_reported": f["outcomes_reported"]["by_kind"].get("impact", 0)}


    # -- statistics of past attacks (cached 5 min) ---------------------------
    _stats_res = {}

    def stats(self, days=14):
        days = max(1, min(int(days), 30))
        ck = self._stats_res.get(days)
        if ck and time.time() - ck[0] < 300:
            return ck[1]
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        kyiv_tz = timezone(timedelta(hours=3))
        # 1. alerts (Kyiv city + oblast-wide) → per day count / minutes, hour-of-day histogram, longest
        al = [a for a in self.store.history(days * 24, ["31", "14"]) if a["location_type"] in ("oblast", "city")]
        by_day = {}
        hours = [0] * 24
        longest = None
        tot_min = 0
        for a in al:
            st = parse_iso(a["started_at"]); en = parse_iso(a["finished_at"]) if a["finished_at"] else now
            if not st:
                continue
            st = max(st, since)
            mins = max(0, (en - st).total_seconds() / 60)
            d = st.astimezone(kyiv_tz).strftime("%Y-%m-%d")
            by_day.setdefault(d, {"alerts": 0, "minutes": 0, "impacts": 0, "down": 0, "drone_posts": 0, "missile_posts": 0})
            if a["oblast_uid"] == "31" or True:
                by_day[d]["alerts"] += 1
                by_day[d]["minutes"] += mins
            tot_min += mins if a["oblast_uid"] == "31" else 0
            if a["oblast_uid"] == "31" and (longest is None or mins > longest[0]):
                longest = (mins, a["started_at"], a["finished_at"])
            t = st
            while t < en and t < now:
                hours[t.astimezone(kyiv_tz).hour] += 1
                t += timedelta(hours=1)
        # 2. feed: impacts / shoot-downs (parsed, named towns only, region + Kyiv), drone / missile posts about Kyiv
        imp = self.impacts(min(days * 24, 96)) if geo else []
        by_obl = {}
        for m in imp:
            d = (parse_iso(m["ts"]) or now).astimezone(kyiv_tz).strftime("%Y-%m-%d")
            by_day.setdefault(d, {"alerts": 0, "minutes": 0, "impacts": 0, "down": 0, "fires": 0, "damage": 0, "drone_posts": 0, "missile_posts": 0})
            b = {"impact": "impacts", "down": "down", "fire": "fires", "damage": "damage"}.get(m["status"], "impacts")
            by_day[d].setdefault(b, 0)
            by_day[d][b] += 1
            ou = m.get("oblast_uid") or "?"
            by_obl.setdefault(ou, {"impacts": 0, "down": 0, "fires": 0, "damage": 0})
            by_obl[ou].setdefault(b, 0)
            by_obl[ou][b] += 1
        # 3. launches: Air Force morning summaries ("противник атакував N ударними БпЛА ... та M ракетами") give the
        #    official count of what was launched over Ukraine; per-day max (the summary is sometimes re-posted / corrected).
        #    Reports: every monitoring post tagged drones / missiles, all of Ukraine — a volume of reporting, not a count of targets.
        empty = {"alerts": 0, "minutes": 0, "impacts": 0, "down": 0, "fires": 0, "damage": 0, "drone_posts": 0, "missile_posts": 0,
                 "drone_reports": 0, "missile_reports": 0, "launched_drones": 0, "launched_missiles": 0, "af_down": 0}
        for k in by_day.values():
            for kk, v in empty.items():
                k.setdefault(kk, v)
        windows = {w: {"drone_reports": 0, "missile_reports": 0, "launched_drones": 0, "launched_missiles": 0,
                       "af_down": 0, "summaries": 0} for w in (1, 7, 30)}
        for p in self.store.feed_since(30 * 24 * 60, limit=60000, translate=False):
            tg = set(p.get("tags") or [])
            pts = parse_iso(p["ts"]) or now
            age_d = (now - pts).total_seconds() / 86400
            d = pts.astimezone(kyiv_tz).strftime("%Y-%m-%d")
            in_series = pts >= since
            if in_series:
                by_day.setdefault(d, dict(empty))
            is_d = "drones" in tg
            is_m = bool(tg & {"ballistic_missiles", "cruise_missiles", "unspecified_missiles"})
            if not (is_d or is_m):
                continue
            for w, acc in windows.items():
                if age_d <= w:
                    if is_d: acc["drone_reports"] += 1
                    if is_m: acc["missile_reports"] += 1
            if not in_series:
                continue
            if is_d:
                by_day[d]["drone_reports"] += 1
            if is_m:
                by_day[d]["missile_reports"] += 1
            if "kyiv" in tg:
                if is_d:
                    by_day[d]["drone_posts"] += 1
                if is_m:
                    by_day[d]["missile_posts"] += 1
        # 3b. the Air Force's own figures, type by type (af_reports: one report per night / day, its own post over a
        #     re-post). Summed per window; a type the summary named without a number is listed as "used", never 0.
        reps = self.store.af_reports((now - timedelta(days=31)).astimezone(kyiv_tz).strftime("%Y-%m-%d"))
        for w, acc in windows.items():
            acc["af"] = {"launched": {}, "down": {}, "used": [], "impacts": 0, "debris": 0}
        for r in reps:
            age_d = (now - (parse_iso(r["ts"]) or now)).total_seconds() / 86400
            la, dn = r.get("launched") or {}, r.get("down") or {}
            if r.get("date") in by_day:
                row = by_day[r["date"]]
                row["launched_drones"] += la.get("drones", 0)
                row["launched_missiles"] += af_missiles(la)
                row["af_down"] += dn.get("total", 0)
            for w, acc in windows.items():
                if age_d > w:
                    continue
                acc["summaries"] += 1
                acc["launched_drones"] += la.get("drones", 0)
                acc["launched_missiles"] += af_missiles(la)
                acc["af_down"] += dn.get("total", 0)
                af = acc["af"]
                for k, v in la.items():
                    af["launched"][k] = af["launched"].get(k, 0) + v
                for k, v in dn.items():
                    af["down"][k] = af["down"].get(k, 0) + v
                af["used"] = sorted(set(af["used"]) | set(r.get("used") or []))
                af["impacts"] += r.get("impacts", 0)
                af["debris"] += r.get("debris", 0)
        for acc in windows.values():
            af = acc["af"]
            # counted in some summaries, named without a number in others: the sum is a floor ("8+"), not a total
            af["partial"] = [k for k in af["used"] if k in af["launched"]]
            af["used"] = [k for k in af["used"] if k not in af["launched"]]
        # Explosions and confirmed shoot-downs come from parsed posts, and that parsing covers at most 96 h —
        # so they are reported for 24 h and 72 h only. Reporting them "per 30 days" would be a number that is
        # simply missing most of its days.
        # fires are counted apart and never folded into the explosion total: a warehouse burning after a strike
        # is not a second explosion, and a fire nobody tied to a strike is not an explosion at all
        imp_windows = {1: {"impacts": 0, "down": 0, "fires": 0, "damage": 0}, 3: {"impacts": 0, "down": 0, "fires": 0, "damage": 0}}
        _bucket = {"impact": "impacts", "down": "down", "fire": "fires", "damage": "damage"}
        for m in imp:
            age_d = (now - (parse_iso(m["ts"]) or now)).total_seconds() / 86400
            for w, acc in imp_windows.items():
                if age_d <= w:
                    acc[_bucket.get(m["status"], "impacts")] += 1
        daysl = [(since + timedelta(days=i)).astimezone(kyiv_tz).strftime("%Y-%m-%d") for i in range(days + 1)]
        series = [{"day": d, **by_day.get(d, empty)} for d in daysl]
        out = {"days": days, "since": since.isoformat(), "series": series, "hours": hours, "kyiv_minutes": round(tot_min),
               "kyiv_alerts": sum(1 for a in al if a["oblast_uid"] == "31"), "longest": longest, "by_oblast": by_obl,
               "impacts_total": sum(1 for m in imp if m["status"] == "impact"), "down_total": sum(1 for m in imp if m["status"] == "down"),
               "fires_total": sum(1 for m in imp if m["status"] == "fire"),
               "damage_total": sum(1 for m in imp if m["status"] == "damage"),
               "impact_window_h": min(days * 24, 96), "windows": {str(k): v for k, v in windows.items()},
               "imp_windows": {str(k): v for k, v in imp_windows.items()}, "imp_max_h": min(days * 24, 96),
               # the Stats tab shows only these: the Air Force's own summaries, one row per night / day, newest first
               "af_days": [{"day": r.get("date"), "period": r.get("period"), "post": r.get("post"),
                            "drones": (r.get("launched") or {}).get("drones", 0),
                            "missiles": af_missiles(r.get("launched") or {}),
                            "down": (r.get("down") or {}).get("total", 0),
                            **{k: r[k] for k in ("launched", "down_by", "used", "impacts", "debris", "areas", "directions", "models") if k in r},
                            "down_by": r.get("down") or {}}
                           for r in sorted(reps, key=lambda r: (r.get("date") or "", r.get("period") != "night", r.get("ts") or ""), reverse=True)]}
        self._stats_res[days] = (time.time(), out)
        return out


    # -- missile mode -----------------------------------------------------
    # A level, not a flag, because the two missile families leave you different amounts of time:
    #   0  nothing flying   → clients ping every 15 s, Telegram every 30 s
    #   1  cruise / MiG-31K → clients every 5 s, Telegram every 10 s
    #   2  ballistic open   → clients every second, Telegram and the alert APIs every 5 s
    # A ballistic missile covers ~35 km a minute: from the moment a post exists, every second the app
    # spends not knowing about it is roughly half a kilometre of someone's warning. Level 2 is rare and
    # short (the whole event is minutes), which is what makes a one-second cadence affordable at all.
    MSL_NONE, MSL_CRUISE, MSL_BALLISTIC = 0, 1, 2
    _missile_res = (0, 0)

    def missile_active(self):
        """0 / 1 / 2 — truthy exactly when something missile-shaped is up, so old call sites still work."""
        t0, v = self._missile_res
        if time.time() - t0 < 4:
            return v
        v = self._missile_active()
        self._missile_res = (time.time(), v)
        return v

    def _missile_active(self):
        fav = set(self.cfg.get("favourites") or [])
        bal = {"ballistic_missiles"}
        kinds = {"ballistic_missiles", "cruise_missiles", "banderol_missiles", "mig31k_departure"}
        level = self.MSL_NONE
        with self.lock:
            for a in self.active.values():
                if fav and a.get("oblast_uid") not in fav:
                    continue
                for t in a.get("threats") or []:
                    ty = t.get("threat_type") if isinstance(t, dict) else t
                    if ty in bal:
                        return self.MSL_BALLISTIC          # nothing outranks this, stop looking
                    if ty in kinds:
                        level = self.MSL_CRUISE
        for p in self.store.feed_since(10, limit=60, translate=False):      # newest first
            tags = set(p.get("tags") or [])
            if "retract" in tags:
                break                                  # what was reported before a retraction no longer counts
            if bal & tags:
                return self.MSL_BALLISTIC
            if kinds & tags:
                level = self.MSL_CRUISE
        return level

    # -- impact / shoot-down history (24/48/72 h) ---------------------------
    # "impact / explosion" and confirmed "shot down" outcome markers, parsed from every post of the window (cached per post,
    # result cached 60 s per window). Same-place relays from other channels within 5 min are merged.
    def impacts(self, hours):
        hours = max(1, min(int(hours), 168))      # the report offers 7 days; the map never asks for more than 24 h
        if not geo:
            return []
        now = time.time()
        ck = self._impact_res.get(hours)
        if ck and now - ck[0] < 60:
            return ck[1]
        out, seen = [], []
        for p in sorted(self.store.feed_since(hours * 60, limit=6000, translate=False), key=lambda p: p["ts"]):
            ms = self._impact_cache.get(p["post_id"])
            if ms is None:
                try:
                    # only impacts pinned to a named town (no oblast-centre approximations in a history layer);
                    # long news / summary posts are not live impact reports
                    ms = [] if len(p["text"]) > 400 else [m for m in geo.parse_for_channel(p["channel"], p["text"])
                          if m.get("status") in ("impact", "down", "fire", "damage") and m.get("lon") is not None and m.get("place") != "область"
                          and ((m.get("evidence") or {}).get("position") or {}).get("confidence") == "high"]
                except Exception:
                    ms = []
                self._impact_cache[p["post_id"]] = ms
            if not ms:
                continue
            pts = parse_iso(p["ts"])
            for i, m in enumerate(ms):
                if any(st == m["status"] and abs(lo - m["lon"]) < 0.08 and abs(la - m["lat"]) < 0.06 and pts and abs((pts - t).total_seconds()) < 300 for (t, lo, la, st) in seen):
                    continue
                seen.append((pts, m["lon"], m["lat"], m["status"]))
                out.append({"id": f"{p['post_id']}#i{i}", "type": m["type"], "status": m["status"], "lon": m["lon"], "lat": m["lat"], "place": m.get("place"),
                            "count": m.get("count"), "ts": p["ts"], "text": p["text"], "text_en": p.get("text_en"), "channel": p["channel"], "oblast_uid": m.get("oblast_uid")})
        out.sort(key=lambda m: m["ts"], reverse=True)
        if len(self._impact_cache) > 20000:
            self._impact_cache.clear()
        self._impact_res[hours] = (now, out)
        return out

    # -- replay (1.42) ---------------------------------------------------------------------------------------------
    # A past window — at most 26 hours, within the last 7 days — for the time bar in Tactical: the official alerts as
    # intervals and the targets as tracks of reported positions. The targets are read from the stored posts with
    # today's rules (the same _marks_from_posts and _chain as the live map), so a reading fixed since is fixed in the
    # replay too. Nothing is extrapolated: a target stands where a post put it, until the next post moved it or its
    # time ran out. Outcomes (explosions, shoot-downs) are not part of it.
    REPLAY_MAX_H = 26
    REPLAY_DAYS = 7
    _replay_parse = {}
    _replay_keys = []

    def replay_cached(self, t0, t1):
        """The cached answer for one window: a window wholly in the past is built once an hour, one that reaches now
        once a minute. At most twelve windows are kept."""
        name = f"replay:{t0}:{t1}"
        if name not in self._replay_keys:
            self._replay_keys.append(name)
            while len(self._replay_keys) > 12:
                self._resp.pop(self._replay_keys.pop(0), None)
        past = t1 < time.time() - 600
        return self.cached(name, 3600 if past else 60, lambda: self.replay(t0, t1))

    def replay(self, t0, t1):
        start = datetime.fromtimestamp(t0, timezone.utc)
        end = datetime.fromtimestamp(t1, timezone.utc)
        alerts = self._replay_alerts(start, end)
        tracks = self._replay_tracks(start, end, alerts)
        if len(self._replay_parse) > 30000:
            self._replay_parse.clear()
        return {"from": t0, "to": t1, "now": int(time.time()), "alerts": alerts, "tracks": tracks}

    def _replay_alerts(self, start, end):
        """Official alert intervals overlapping [start, end], rebuilt from the start / end events.

        A restart loses the alerts the process held without writing an end: the first reading after it writes a
        start for everything still on, and nothing for what ended while it was down. So a restart — recorded since
        1.41 ("boots"), and before that seen as a start for a region already on — closes every interval that is not
        started again within five minutes of it, at the moment of the restart."""
        look = start - timedelta(days=3)
        rows = self.store.alert_events_between(look.isoformat(), end.isoformat())
        meta = self.store.alert_meta()
        evs = [(parse_iso(r[0]), r) for r in rows]
        evs = [(t, r) for t, r in evs if t]
        starts = collections.defaultdict(list)
        open_, boots = set(), []
        for t, r in evs:
            if r[1] == "start":
                starts[r[2]].append(t)
                if r[2] in open_:
                    boots.append(t)
                open_.add(r[2])
            else:
                open_.discard(r[2])
        try:
            for b in json.loads(self.store.kv_get("boots") or "[]"):
                bt = parse_iso(b.get("ts"))
                if bt and look <= bt <= end:
                    boots.append(bt)
        except Exception:
            pass
        B = []
        for b in sorted(boots):
            if not B or (b - B[-1]).total_seconds() > 90:
                B.append(b)

        def again(key, b):
            ts = starts.get(key) or ()                  # in time order: the first start at or after b - 5 s
            i = bisect.bisect_left(ts, b - timedelta(seconds=5))
            return i < len(ts) and ts[i] <= b + timedelta(seconds=300)
        cur, iv, bi = {}, [], 0
        for t, r in evs:
            while bi < len(B) and B[bi] <= t:
                for key in [k for k in cur if not again(k, B[bi])]:
                    s0, r0 = cur.pop(key)
                    iv.append((s0, B[bi], r0))
                bi += 1
            if r[1] == "start":
                if r[2] not in cur:
                    cur[r[2]] = (t, r)
            elif r[2] in cur:
                s0, r0 = cur.pop(r[2])
                iv.append((s0, t, r0))
        for b in B[bi:]:
            for key in [k for k in cur if not again(k, b)]:
                s0, r0 = cur.pop(key)
                iv.append((s0, b, r0))
        for s0, r0 in cur.values():
            iv.append((s0, None, r0))
        # what is on now and began before the look-back (an occupied oblast's alert of many months)
        seen = {r[2] for _, r in evs}
        with self.lock:
            act = [dict(a) for a in self.active.values()]
        for a in act:
            if a["key"] not in seen:
                iv.append((look, None, (None, "start", a["key"], a["location_uid"], a["location_title"], a["alert_type"], a["oblast_uid"])))
        uar = ua_regions()

        def raion_key(uid):
            rid = uid[3:] if (uid or "").startswith("ua-") else None
            if not rid:
                return None
            d = uar["districts"].get(rid)
            if not d:
                c = uar["communities"].get(rid) or {}
                d = uar["districts"].get(c.get("d") or "")
            return (d or {}).get("key")
        out = []
        for s0, e0, r in iv:
            if s0 >= end or (e0 is not None and e0 <= start):
                continue
            lt, lv, _en = meta.get(r[2], (None, None, None))
            out.append({"k": r[3], "o": r[6], "lt": lt or ("oblast" if (r[3] or "") == r[6] else "raion"), "rk": raion_key(r[3]),
                        "lv": lv, "at": r[5] or "air_raid", "ti": r[4], "s": int(s0.timestamp()),
                        "e": int(e0.timestamp()) if e0 else None})
        out.sort(key=lambda a: a["s"])
        return out

    def _replay_tracks(self, start, end, alerts):
        """The targets of the window as tracks: each one's reported positions, oldest first."""
        if not geo:
            return []
        lead = start - timedelta(minutes=30)
        # the official all-clears for Kyiv city in the window: what a channel said before one is not carried past it
        city = [(a["s"], a["e"]) for a in alerts if a["o"] == "31" and a["at"] == "air_raid"]
        kyiv_ends = sorted(datetime.fromtimestamp(e, timezone.utc) for i, (s_, e) in enumerate(city)
                           if e and not any(j != i and s2 <= e and (e2 is None or e2 > e) for j, (s2, e2) in enumerate(city)))
        posts = self.store.feed_between(lead.isoformat(), end.isoformat())
        ms = self._marks_from_posts(posts, kyiv_ends, self._replay_parse, evidence=False)
        ms = [m for m in ms if not m.get("status") and m.get("lon") is not None and in_scope(m)]
        ms = self._chain(ms)
        out = []
        for m in ms:
            if m.get("superseded_by") or m.get("absorbed") or m.get("status"):
                continue
            pts = [(h["ts"], h["lon"], h["lat"], h.get("place")) for h in m.get("history") or []] + [(m["ts"], m["lon"], m["lat"], m.get("place"))]
            pts = [[int(parse_iso(t).timestamp()), round(lo, 3), round(la, 3), pl] for t, lo, la, pl in pts if parse_iso(t)]
            if not pts or pts[-1][0] < lead.timestamp():
                continue
            hev = ((m.get("evidence") or {}).get("heading") or {})
            stated = m.get("heading") is not None and hev.get("confidence") not in (None, "none")
            out.append({"ty": m["type"], "jet": 1 if m.get("jet") else 0, "n": m.get("count") or 1,
                        "ap": 1 if m.get("approach") else 0, "h": round(m["heading"]) if stated else None,
                        "ch": m.get("channel"), "p": pts})
        out.sort(key=lambda x: x["p"][0][0])
        return out

    # -- track lifecycle ------------------------------------------------
    # A target must be *re-reported* to stay on the map. Each new report is matched to the most plausible
    # earlier report of the same family (same channel preferred): dt ≤ 30 min, distance ≤ max_speed·dt + 25 km,
    # roughly ahead of the earlier heading. The earlier report is then superseded (kept only as history).
    # A report that is neither updated within `stale_minutes` nor closed by an outcome is dropped, and every
    # report in an oblast whose air-raid alert has ended is dropped once the alert has been over for 3 min.
    @staticmethod
    def _chain(ms):
        """Each report of a target is matched to the most plausible earlier report of the same family, which it
        then supersedes (keeping it as history). Returns the reports oldest first. Shared by the live map and the
        replay (1.42)."""
        ms = sorted(ms, key=lambda m: m["ts"])
        tracks = [m for m in ms if not m.get("status")]
        for m in tracks:
            m["superseded_by"] = None
            m["history"] = []
        def km(a, b):
            return math.hypot((a["lon"] - b["lon"]) * 70.7, (a["lat"] - b["lat"]) * 111)
        def fam(m):
            # Banderol is its own family. It used to share "missile" with cruise missiles because its type name
            # contains the word, so a Banderol track could be continued by a later "ракета" report from another
            # channel — and the later, vaguer report is what named the track. A Banderol never becomes a cruise
            # missile by being chained to one.
            if m["type"] == "banderol_missiles":
                return "banderol"
            return "drone" if m["type"] == "drones" else ("missile" if "missile" in m["type"] else m["type"])

        def vague(m):
            return (m.get("place") or "") == "область"      # "БпЛА на Харківщині": the oblast, no town named
        for i, m in enumerate(tracks):
            t1 = parse_iso(m["ts"])
            best = None
            for pm in tracks[:i]:
                if pm["superseded_by"] or fam(pm) != fam(m):
                    continue
                dt = (t1 - parse_iso(pm["ts"])).total_seconds() / 60
                same = pm["channel"] == m["channel"]
                # 1.43.1: another channel's report continues a track only within 15 minutes. With the regional trackers
                # on the map, the Kyiv channels — a report a minute — were taking over every Odesa, Chernihiv and
                # Kharkiv report within half an hour and hundreds of kilometres: "Перший район Ніжина" became the
                # history of a target at Vasylkiv, and nothing of Odesa was ever drawn.
                if dt <= 0 or dt > (30 if same else 15):
                    continue
                # A report naming no town never takes over one that named a place (it would move the target to the
                # middle of the oblast), and a destination is never handed to one: "на Зміїв" stays a mark of its own.
                if (vague(m) and not vague(pm)) or (m.get("approach") and vague(pm)):
                    continue
                # an unspecified threat is a target of unknown speed: from its own channel it may be anything, but
                # two channels' bare place names are only one target at the speed of a drone
                vmax = 7.0 if fam(m) == "drone" or (fam(m) == "unknown" and not same) else 15.0
                d = km(pm, m)
                # an approach mark stands at the town the target is heading to, not where it is: it may be further
                if d > (80 if m.get("approach") else vmax * dt + 25):
                    continue
                if pm.get("heading") is not None and d > 12:
                    b = (math.degrees(math.atan2((m["lon"] - pm["lon"]) * 70.7, (m["lat"] - pm["lat"]) * 111)) + 360) % 360
                    diff = abs(((pm["heading"] - b) + 540) % 360 - 180)
                    if diff > 60:
                        continue
                score = d + dt * 0.8 + (0 if pm["channel"] == m["channel"] else 10) + (0 if (pm.get("count") or 1) == (m.get("count") or 1) else 5)
                if best is None or score < best[0]:
                    best = (score, pm)
            if best:
                pm = best[1]
                if m.get("approach") and not pm.get("approach"):
                    # "…на Васильків" about a target already on the map: where it is going, not where it now is.
                    # The track keeps its reported position and takes the destination; the approach mark goes.
                    m["absorbed"] = True
                    pm["target"] = pm.get("target") or m.get("target")
                    if pm.get("heading") is None and m.get("target") in geo.PLACES:
                        dlon, dlat, _ = geo.PLACES[m["target"]]
                        pm["heading"] = round(geo.bearing(pm["lon"], pm["lat"], dlon, dlat))
                        ev = dict(pm.get("evidence") or {})
                        ev["heading"] = {"matched": m.get("place"), "confidence": "medium",
                                         "method": f"toward {m['target']}, the destination a later post named"}
                        pm["evidence"] = ev
                    continue
                pm["superseded_by"] = m["id"]
                # each earlier report keeps the height ITS post stated (if any): two stated heights in a row are a
                # descent the posts reported, not one this app worked out — 2200 m, then 1600 m, then 800 m
                # an approach mark's point is a destination, not a place it was: it is no step of the track
                m["history"] = pm["history"] + ([] if pm.get("approach") or vague(pm) else [{"id": pm["id"], "lon": pm["lon"], "lat": pm["lat"], "ts": pm["ts"], "channel": pm["channel"],
                                                 "place": pm.get("place"), "alt_m": (pm.get("alt") or {}).get("m"),
                                                 "alt_state": (pm.get("alt") or {}).get("state")}])
        return ms

    def _chain_and_prune(self, ms, ttl, kyiv_ends=()):
        stale = int(self.cfg.get("track_stale_minutes", 5))
        now = datetime.now(timezone.utc)
        obl_status = {}
        with self.lock:
            # any alert in the oblast keeps its reports alive: with alerts by raion, an oblast whose three raions
            # are under alert has no oblast-wide alert at all, and its drones must not vanish after 3 minutes
            for a in self.active.values():
                obl_status[a["oblast_uid"]] = "A"
        ms = self._chain(ms)
        keep = []
        for m in ms:
            if m.get("superseded_by") or m.get("absorbed"):
                continue
            # 1.38: a position carried from an earlier line is as old as that line, not as the line that carried it
            tp = parse_iso(m.get("pos_ts") or m["ts"])
            age = (now - tp).total_seconds() / 60 if tp else 0
            if m.get("status"):
                if age <= 25:
                    keep.append(m)
                continue
            # A missile is not a drone and must not be aged like one. A Shahed does ~3 km a minute, so a
            # five-minute-old dot is still worth something. A cruise missile does ~13, a ballistic one ~35: a
            # position two minutes old is already tens of kilometres wrong, and a grey dot left on the map would
            # be a lie with a precise pin in it. So missiles keep no "stale" flag at all — the client turns them
            # into a growing circle of where they could now be — and they are dropped sooner.
            if "missile" in (m.get("type") or ""):
                if age > MISSILE_TTL_MIN:
                    continue
                m["fast"] = True
                keep.append(m)
                continue
            # 1.43.1: a regional tracker reports a target every five to twenty minutes, not every minute like the Kyiv
            # channels: its last report is the latest anyone said, and it keeps longer — as "location not updated"
            # after REGIONAL_STALE_MIN, gone after REGIONAL_GONE_MIN (and still at once when the oblast's alert ends)
            # (1.44.1: never a guided bomb — it glides for minutes, whoever reports it)
            reg = bool(geo and geo.CHANNEL_HOME.get(m.get("channel"))) and m.get("type") != "guided_aerial_bombs"
            st_min = max(stale, REGIONAL_STALE_MIN) if reg else stale
            if reg:
                m["slow"] = True                  # the page fades it on the same longer clock
            if age > st_min:
                # An unspecified threat ("Васильків увага") says where, not what. It is a loud red sign while it
                # is fresh, and then it is simply gone — no grey ghost fading for ten more minutes, because there
                # is nothing to keep half-alive: nobody ever said what it was.
                if m.get("type") == "unknown":
                    continue
                if age > (REGIONAL_GONE_MIN if reg else max(stale * 3, 15)):
                    continue                      # nothing for 15 min (a regional tracker: 25) → gone
                m["stale"] = round(age)           # not re-reported for > stale min: kept as "? location not updated"
            ou = m.get("oblast_uid")
            if ou and obl_status and ou not in obl_status and age > 3:
                # its oblast has no active alert any more → the threat has left or was resolved
                continue
            if ou == "31" and "31" not in obl_status and tp and any(tp < e <= now for e in kyiv_ends):
                continue                          # reported in Kyiv city before the official all-clear there
            keep.append(m)
        return keep

    def snapshot(self):
        with self.lock:
            merged = {}
            for a in self.active.values():
                k = (a["location_uid"], a["alert_type"])
                if k in merged:
                    b = merged[k]
                    m = dict(b if b["source"] in ("alerts_in_ua", "ukrainealarm", "ukrainealarm_proxy") else a)
                    m["started_at"] = min(a["started_at"] or "9", b["started_at"] or "9")
                    thr = list(b.get("threats") or [])
                    for t in a.get("threats") or []:
                        if t not in thr:
                            thr.append(t)
                    m["threats"] = thr
                    m["alert_level"] = "red" if "red" in (a.get("alert_level"), b.get("alert_level")) else (a.get("alert_level") or b.get("alert_level"))
                    merged[k] = m
                else:
                    merged[k] = dict(a)
            active = sorted(merged.values(), key=lambda a: a["started_at"], reverse=True)
            sources = dict(self.sources)
        by_oblast = {}
        for uid, uk, en in OBLASTS:
            by_oblast[uid] = {"uid": uid, "uk": uk, "en": en, "status": "N", "types": [], "level": None, "since": None, "threats": []}
        for a in active:
            o = by_oblast.get(a["oblast_uid"])
            if not o:
                continue
            if a["location_type"] == "oblast":
                o["status"] = "A"
                if a.get("since_known", True):   # a mirror alert with no start time has no "since"
                    o["since"] = a["started_at"] if not o["since"] or a["started_at"] < o["since"] else o["since"]
            elif o["status"] != "A":
                o["status"] = "P"
            if a["alert_type"] not in o["types"]:
                o["types"].append(a["alert_type"])
            if a.get("alert_level") == "red" or (a.get("alert_level") == "yellow" and o["level"] != "red"):
                o["level"] = a.get("alert_level")
            for t in a.get("threats") or []:
                if t not in o["threats"]:
                    o["threats"].append(t)
        try:
            bridges = self.bridges_now()
        except Exception as e:                       # never at the cost of the alerts themselves
            log("bridges:", e)
            bridges = {b["id"]: {} for b in BRIDGES}
        # 1.46: the pages show a source as working or not, and nothing more. Its time of last reading changed on every
        # poll, so every reader was sent the whole table again at each beat of the live line — ~80 % of what the line
        # carried. The details (last read, counts, errors) are the dashboard's: /api/health.
        sources = {k: {"ok": bool(v.get("ok"))} for k, v in sources.items()}
        sv, sz = SAT.info()                          # 1.48: the imagery file's own version and deepest zoom
        return {"now": now_iso(), "active": active, "oblasts": by_oblast, "sources": sources, "eradar": self.eradar,
                "notice": self.notice_now(), "nuke": self.nuke, "bridges": bridges, "scope": sorted(SCOPE_UIDS, key=int),
                "favourites": self.cfg.get("favourites") or [], "config": {"demo": bool(self.cfg.get("demo")), "canonical": canonical_host(self.cfg),
                "has_token": bool(self.cfg.get("alerts_in_ua_token")), "channels": self.cfg.get("telegram_channels"),
                "sat": SAT.available(), "sat_v": sv, "sat_z": sz, "esri": self.esri.enabled()}}


# ---------------------------------------------------------------------------
# Desktop notifications (optional plyer)
# ---------------------------------------------------------------------------
class SatTiles:
    """The satellite layer (1.47): Ukraine from the ESA WorldCover Sentinel-2 composite of 2021, WebP tiles in an
    MBTiles file, read-only — zoom 5–12 in the first build, 5–13 at the full 10 m since 1.48. Served by this server
    and nobody else: no map provider learns which part of the country a reader looks at. A new file put in place
    (scripts/upload-imagery.bat) is picked up on the next request — no restart.

    1.48: the page is told the file's own version and deepest zoom (its metadata), not a number written in the page:
    the tiles are kept a year under their address, and a page that asked for the new zoom or the new version before
    the new file was on the volume would have kept the old pictures under the new address."""
    ATTRIBUTION = "ESA WorldCover 2021 · contains modified Copernicus Sentinel data (2021)"

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.conn = None
        self.sig = None
        self.checked = 0.0
        self.meta = {}

    def _db(self):
        now = time.monotonic()
        if now - self.checked < 10 and (self.conn or self.sig == "missing"):
            return self.conn
        self.checked = now
        try:
            st = os.stat(self.path)
        except OSError:
            if self.conn:
                self.conn.close()
            self.conn, self.sig = None, "missing"
            return None
        sig = (st.st_ino, st.st_mtime, st.st_size)
        if sig != self.sig:
            if self.conn:
                self.conn.close()
            self.meta = {}
            try:
                self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
                self.conn.execute("SELECT 1 FROM tiles LIMIT 1").fetchone()
                try:
                    self.meta = dict(self.conn.execute("SELECT name, value FROM metadata").fetchall())
                except sqlite3.Error:
                    pass
            except sqlite3.Error as e:
                log("satellite tiles unreadable:", e)
                self.conn = None
            self.sig = sig
        return self.conn

    def available(self):
        with self.lock:
            return self._db() is not None

    def info(self):
        """(version, deepest zoom) of the file in place — what the page asks for, and under which address."""
        with self.lock:
            if self._db() is None:
                return None, None
            m = self.meta
        try:
            z = max(5, min(16, int(m.get("maxzoom") or 12)))
        except ValueError:
            z = 12
        return re.sub(r"[^\w.-]", "", str(m.get("version") or ""))[:12] or "1", z

    def tile(self, z, x, y):
        if not (0 <= z <= 20 and 0 <= x < (1 << z) and 0 <= y < (1 << z)):
            return None
        with self.lock:
            c = self._db()
            if not c:
                return None
            try:
                row = c.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                                (z, x, (1 << z) - 1 - y)).fetchone()
            except sqlite3.Error:
                return None
        return row[0] if row else None


SAT = SatTiles(SAT_PATH)

# 1.48: closer than Sentinel's 10 m — Esri World Imagery (ArcGIS Location Platform), zoom 14 and closer, Ukraine only
ESRI_URL = "https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_BBOX = (22.0, 44.2, 40.4, 52.5)       # lon, lat — the tiles asked for must touch it


class EsriTiles:
    """The closest zooms of the satellite layer (1.48): a street, a building — what 10 m Sentinel pixels cannot show.
    The key is the owner's (ESRI_KEY, a Fly secret set with scripts/set-esri-key.bat) and stays on this server: the
    page asks /tiles/esri/…, this server asks Esri. Nothing is kept here — Esri's terms forbid storing its tiles; the
    browser keeps what Esri's own cache headers let it.

    Every tile is paid for past the free tier, so they are counted and capped: `esri_monthly_tiles` a month (under the
    2 M free tiles), never more than a tenth of them in one day (one busy night cannot spend the month), PER_IP_HOUR
    for one reader. Past a cap the page is told (state.config.esri) and shows the Sentinel picture alone. Only tiles
    over Ukraine, zoom ZMIN–ZMAX, are ever asked for."""
    ATTRIBUTION = "Powered by Esri · Esri, Maxar, Earthstar Geographics, and the GIS User Community"
    ZMIN, ZMAX = 14, 18
    PER_IP_HOUR = 3000
    SAVE_EVERY = 200

    def __init__(self, cfg, store=None):
        self.cfg, self.store = cfg, store
        self.lock = threading.Lock()
        self.gate = threading.BoundedSemaphore(12)       # requests to Esri at once
        self.month = self.day = None
        self.n_month = self.n_day = self.unsaved = 0
        self.hour, self.by_ip = None, {}
        self.salt = os.urandom(16)
        self.down_until = 0.0
        self.refused = None

    def cap(self):
        try:
            return max(0, int(self.cfg.get("esri_monthly_tiles", 1800000)))
        except (TypeError, ValueError):
            return 0

    def _roll(self):
        now = datetime.now(timezone.utc)
        m, d = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
        if m != self.month:
            self._save()
            self.month, self.n_month = m, 0
            if self.store:
                try:
                    self.n_month = int(self.store.kv_get(f"esri_tiles:{m}") or 0)
                except (TypeError, ValueError):
                    pass
        if d != self.day:
            self.day, self.n_day = d, 0
            if self.store:
                try:
                    self.n_day = int(self.store.kv_get(f"esri_tiles_day:{d}") or 0)
                except (TypeError, ValueError):
                    pass

    def _save(self):
        if self.store and self.month and self.unsaved:
            self.store.kv_set(f"esri_tiles:{self.month}", str(self.n_month))
            self.store.kv_set(f"esri_tiles_day:{self.day}", str(self.n_day))
        self.unsaved = 0

    def _spent(self):
        cap = self.cap()
        return self.n_month >= cap or self.n_day >= max(1, cap // 10)

    def enabled(self):
        if not self.cfg.get("esri_key") or not self.cap():
            return False
        with self.lock:
            self._roll()
            return not self._spent() and time.monotonic() >= self.down_until

    def stats(self):
        with self.lock:
            self._roll()
            return {"key": bool(self.cfg.get("esri_key")), "month": self.month, "tiles_month": self.n_month,
                    "tiles_today": self.n_day, "cap_month": self.cap(), "cap_day": self.cap() // 10,
                    "paused": time.monotonic() < self.down_until, "refused": self.refused}

    @staticmethod
    def over_ukraine(z, x, y):
        n = 1 << z
        lon0, lon1 = x / n * 360 - 180, (x + 1) / n * 360 - 180
        lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
        w, s, e, nn = ESRI_BBOX
        return lon1 > w and lon0 < e and lat1 > s and lat0 < nn

    def fetch(self, z, x, y, ip=""):
        """(HTTP status, body, content type, cache header) for the page."""
        if not (self.ZMIN <= z <= self.ZMAX and 0 <= x < (1 << z) and 0 <= y < (1 << z)) or not self.over_ukraine(z, x, y):
            return 404, b"", None, "public, max-age=86400"
        key = self.cfg.get("esri_key")
        if not key or not self.cap():
            return 404, b"", None, "no-store"
        h = hashlib.sha256(self.salt + (ip or "").encode()).hexdigest()[:16]    # in memory, for the hour, never stored
        with self.lock:
            self._roll()
            if self._spent():
                return 429, b"", None, "no-store"
            if time.monotonic() < self.down_until:
                return 503, b"", None, "no-store"
            hr = int(time.time() // 3600)
            if hr != self.hour:
                self.hour, self.by_ip = hr, {}
            if self.by_ip.get(h, 0) >= self.PER_IP_HOUR:
                return 429, b"", None, "no-store"
            self.by_ip[h] = self.by_ip.get(h, 0) + 1
            self.n_month += 1
            self.n_day += 1
            self.unsaved += 1
            if self.unsaved >= self.SAVE_EVERY:
                self._save()
        if not self.gate.acquire(timeout=10):
            return 503, b"", None, "no-store"
        try:
            url = ESRI_URL.format(z=z, x=x, y=y) + "?blankTile=false&token=" + quote(key, safe="")
            req = urllib.request.Request(url, headers={"User-Agent": f"Heimdall/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
                body, ctype, cc = r.read(), r.headers.get("Content-Type") or "", r.headers.get("Cache-Control")
        except urllib.error.HTTPError as e:
            # never e.url or str(e) of the request: the address carries the key
            if e.code in (401, 403, 498, 499):
                self._refused(f"HTTP {e.code}")
                return 503, b"", None, "no-store"
            return (404 if e.code == 404 else 502), b"", None, ("public, max-age=86400" if e.code == 404 else "no-store")
        except Exception as e:
            log("esri tiles:", type(e).__name__)
            return 502, b"", None, "no-store"
        finally:
            self.gate.release()
        if not ctype.startswith("image/"):
            # a refused key comes back as 200 and a JSON error
            code = None
            try:
                code = (json.loads(body).get("error") or {}).get("code")
            except Exception:
                pass
            self._refused(f"error {code}" if code else "not an image")
            return 503, b"", None, "no-store"
        # the reader's browser keeps it as long as Esri says; no shared cache does
        cc = cc if cc and "no-store" not in cc else "max-age=86400"
        return 200, body, ctype, ", ".join(["private"] + [p.strip() for p in cc.split(",") if p.strip() not in ("", "public", "private")])

    def _refused(self, why):
        """Esri refused the key (wrong, expired, out of credits): ask again in 5 minutes, not on every tile."""
        log("esri tiles refused:", why, "— paused 5 min")
        with self.lock:
            self.refused, self.down_until = why, time.monotonic() + 300


class Notifier:
    def __init__(self, cfg):
        self.enabled = bool(cfg.get("desktop_notifications", True))
        self.impl = None
        if self.enabled:
            try:
                from plyer import notification  # type: ignore
                self.impl = notification
            except Exception:
                self.impl = None

    def maybe(self, ev, favourites):
        if not self.impl:
            return
        a = ev["alert"]
        if a["oblast_uid"] not in favourites:
            return
        if ev["kind"] == "start":
            title, msg = f"🔴 Alert — {a.get('location_title_en') or a['location_title']}", a["alert_type"]
        elif ev["kind"] == "end":
            title, msg = f"🟢 All clear — {a.get('location_title_en') or a['location_title']}", "alert ended"
        elif ev["kind"] == "threat":
            t = ev.get("threat") or {}
            title, msg = f"⚠️ {t.get('threat_type')} — {a.get('location_title_en') or a['location_title']}", t.get("source_message") or ""
        else:
            return
        try:
            self.impl.notify(title=title, message=msg[:200], app_name="UA Alerts", timeout=8)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Source pollers
# ---------------------------------------------------------------------------
def poll_gap(state, interval, rush=5):
    """Seconds to wait before the next round.

    While a ballistic threat is open everything upstream is read at `rush` instead. Serving a client every
    second is theatre if the server itself last looked fifteen seconds ago — the app can only ever be as
    fresh as the slowest link, and that link is the source poll, not the browser. Ballistic windows are
    measured in minutes, so the extra requests cost little and stop the moment the alert clears.
    """
    try:
        return rush if state.missile_active() >= 2 else interval
    except Exception:
        return interval


class AlertsInUa(threading.Thread):
    NAME = "alerts_in_ua"

    def __init__(self, state, cfg):
        super().__init__(daemon=True)
        self.state, self.cfg = state, cfg
        self.token = cfg["alerts_in_ua_token"]
        self.last_modified = None
        self.backfilled = False

    @staticmethod
    def normalise(a):
        return {
            "key": f"aiu:{a['id']}",
            "source": "alerts_in_ua",
            "location_uid": str(a.get("location_uid")),
            "location_title": a.get("location_title"),
            "location_title_en": a.get("location_title_en"),
            "location_type": a.get("location_type") or "unknown",
            "oblast_uid": str(a.get("location_oblast_uid") or norm_uk(a.get("location_oblast")) or a.get("location_uid")),
            "alert_type": a.get("alert_type") or "air_raid",
            "alert_level": a.get("alert_level"),
            "started_at": a.get("started_at"),
            "finished_at": a.get("finished_at"),
            "notes": a.get("notes"),
            "threats": a.get("threats") or [],
        }

    def run(self):
        interval = max(10, int(self.cfg.get("poll_alerts_seconds", 15)))
        while True:
            try:
                self.poll()
                if not self.backfilled:
                    self.backfilled = True
                    threading.Thread(target=self.backfill, daemon=True).start()
            except urllib.error.HTTPError as e:
                if e.code == 304:
                    self.state.set_source(self.NAME, True, note="304 not modified")
                elif e.code == 429:
                    self.state.set_source(self.NAME, False, error="429 rate limited — slowing down")
                    time.sleep(60)
                else:
                    self.state.set_source(self.NAME, False, error=f"HTTP {e.code}")
                    log("alerts.in.ua HTTP", e.code)
            except Exception as e:
                self.state.set_source(self.NAME, False, error=str(e)[:200])
                log("alerts.in.ua error:", e)
            time.sleep(poll_gap(self.state, interval))

    def poll(self):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified
        status, hdrs, body = http_get("https://api.alerts.in.ua/v1/alerts/active.json", headers)
        self.last_modified = hdrs.get("Last-Modified")
        data = json.loads(body.decode("utf-8"))
        alerts = [self.normalise(a) for a in data.get("alerts", []) if a.get("finished_at") is None]
        self.state.set_source(self.NAME, True, count=len(alerts), disclaimer=data.get("disclaimer"))
        self.state.apply_snapshot(self.NAME, alerts, {"oblast", "raion", "city", "hromada", "unknown"})

    def backfill(self):
        """Month history for favourite regions (rate limit 2/min on this endpoint)."""
        for uid in self.cfg.get("favourites") or []:
            try:
                status, hdrs, body = http_get(f"https://api.alerts.in.ua/v1/regions/{uid}/alerts/month_ago.json",
                                              {"Authorization": f"Bearer {self.token}"})
                data = json.loads(body.decode("utf-8"))
                n = 0
                for a in data.get("alerts", []):
                    self.state.store.upsert_alert(self.normalise(a))
                    n += 1
                log(f"backfilled {n} alerts for {NAME_BY_UID.get(uid, (uid,))[0]}")
            except Exception as e:
                log("backfill error", uid, e)
            time.sleep(35)


# The raion table: official region id → oblast, parent raion, and the raion's shape on the map.
# Built by scripts/build_geo.py from the ukrainealarm region list; read once.
REGIONS_PATH = os.path.join(ROOT, "data", "ua_regions.json")
_UAR = None


def ua_regions():
    global _UAR
    if _UAR is None:
        try:
            with open(REGIONS_PATH, encoding="utf-8") as f:
                _UAR = json.load(f)
        except Exception as e:
            log("ua_regions.json:", e)
            _UAR = {"states": {}, "districts": {}, "communities": {}}
    return _UAR


def _iso_s(t):
    """'2026-09-24T14:11:44.399859Z' (any number of decimals) → '2026-09-24T14:11:44Z', the form used everywhere else."""
    if not t:
        return None
    d = parse_iso(re.sub(r"\.\d+", "", t))
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


class UkraineAlarm(threading.Thread):
    """The official «Повітряна тривога» data, down to the raion and the hromada.

    api.ukrainealarm.com is the backend of the government app. With a key (config ukrainealarm_key, or env
    UKRAINEALARM_KEY) this reads it directly. Without one it reads siren.pp.ua, a keyless read-only proxy that
    serves the same API responses — the source the Home Assistant integration falls back to.

    This is the source that knows WHICH raion. The ubilling mirror only says "something in Kyiv oblast is under
    alert": it turned the whole oblast red, and a person in Boryspil raion saw red ten minutes after the
    government app had lifted their alert. A raion here comes as a bare numeric id; data/ua_regions.json turns
    it into its oblast and its shape on the map.

    Each alert also carries the government app's own danger level (since 11 Sep 2026): red — massed drone,
    missile or drone-and-missile threat; yellow — drone threat. Both are air-raid alerts. The official reason
    text ("Дронова загроза (жовтий рівень)") is kept as the alert's note, word for word.
    """
    TYPE_MAP = {"AIR": "air_raid", "ARTILLERY": "artillery_shelling", "URBAN_FIGHTS": "urban_fights",
                "CHEMICAL": "chemical", "NUCLEAR": "nuclear", "INFO": "info"}
    LEVEL_MAP = {"State": "oblast", "District": "raion", "Community": "hromada"}

    def __init__(self, state, cfg):
        super().__init__(daemon=True)
        self.state, self.cfg = state, cfg
        self.key = cfg.get("ukrainealarm_key") or ""
        if self.key:
            self.NAME, self.base = "ukrainealarm", "https://api.ukrainealarm.com/api/v3"
        else:
            self.NAME, self.base = "ukrainealarm_proxy", (cfg.get("siren_proxy_url") or "https://siren.pp.ua/api/v3").rstrip("/")
        self.primary = not cfg.get("alerts_in_ua_token")
        self.last_action = None
        self.last_full = 0.0
        self.last_ok = 0.0
        self.born = time.time()
        self.unknown = set()

    def healthy(self, within=90):
        """Answered in the last `within` seconds — or still starting up (the mirror must not jump in during
        the first seconds of a boot and paint whole oblasts that this source then has to take back)."""
        now = time.time()
        return now - self.last_ok < within or (not self.last_ok and now - self.born < within)

    def run(self):
        interval = max(8, int(self.cfg.get("poll_ukrainealarm_seconds", 10)))
        while True:
            try:
                self.poll()
                self.last_ok = time.time()
            except Exception as e:
                self.state.set_source(self.NAME, False, error=str(e)[:200])
                log(f"{self.NAME} error:", e)
            time.sleep(poll_gap(self.state, interval))

    def poll(self):
        h = {"Accept": "application/json"}
        if self.key:
            h["Authorization"] = self.key
        _, _, body = http_get(self.base + "/alerts/status", h)
        action = json.loads(body.decode()).get("lastActionIndex")
        # Unchanged index: skip the full list — but never for long. A change of level on an alert that is already
        # on (yellow → red) must not wait on the index moving, so the full list is read at least every 30 s.
        if action is not None and action == self.last_action and time.time() - self.last_full < 30:
            self.state.set_source(self.NAME, True, note="unchanged")
            return
        _, _, body = http_get(self.base + "/alerts", h)
        alerts = self.normalise(json.loads(body.decode()))
        self.last_action, self.last_full = action, time.time()
        self.state.set_source(self.NAME, True, count=len(alerts))
        if self.primary:
            self.state.apply_snapshot(self.NAME, alerts, {"oblast", "raion", "hromada", "city", "unknown"})

    def place(self, rid, rtype, r):
        """Where an official region id is. None only for the API's own test region."""
        uar = ua_regions()
        if rid in (uar.get("ignore") or []):
            return None
        if rtype == "State":
            uid = uar["states"].get(rid)
            if uid:
                return {"type": "oblast", "obl": uid, "name": NAME_BY_UID.get(uid, (r.get("regionName"),))[0]}
        if rtype == "District":
            d = uar["districts"].get(rid)
            if d:
                return {"type": "raion", "obl": d["obl"], "name": d["name"], "raion_uid": rid, "raion_key": d["key"], "raion_title": d["name"]}
        c = uar["communities"].get(rid)
        if c:   # a hromada — including a city the API lists at the top level ("м. Харків та … громада")
            d = uar["districts"].get(c.get("d") or "") or {}
            return {"type": "hromada", "obl": c.get("obl") or d.get("obl") or "?", "name": c["name"],
                    "raion_uid": c.get("d"), "raion_key": d.get("key"), "raion_title": d.get("name")}
        # An id the table does not know yet (a new hromada, a renamed raion). The alert is kept — an alert is
        # never dropped for being hard to place — as precisely as its name allows, and logged once.
        if rid not in self.unknown:
            self.unknown.add(rid)
            log(f"{self.NAME}: region id {rid} ({rtype}) not in ua_regions.json — rebuild it with scripts/build_geo.py")
        name = r.get("regionName") if str(r.get("regionId")) == rid else f"#{rid}"
        return {"type": self.LEVEL_MAP.get(rtype, "unknown"), "obl": norm_uk(name) or "?", "name": name}

    def normalise(self, regions):
        out = {}
        for r in regions or []:
            for a in r.get("activeAlerts") or []:
                # an entry can carry its parent's alert too (a hromada listing its raion's): each alert names its own region
                rid = str(a.get("regionId") or r.get("regionId") or "")
                rtype = a.get("regionType") or r.get("regionType")
                p = self.place(rid, rtype, r)
                if not p:
                    continue
                atype = self.TYPE_MAP.get(a.get("type"), str(a.get("type") or "air_raid").lower())
                levels = a.get("activeAlertLevels") or []
                names = [x.get("alertLevel") for x in levels]
                level = "red" if "Red" in names else ("yellow" if "Yellow" in names else None)
                times = [s for s in [_iso_s(a.get("lastUpdate"))] + [_iso_s(x.get("createdAt")) for x in levels] if s]
                reason = next((x.get("reason") for x in sorted(levels, key=lambda x: x.get("alertLevel") != "Red") if x.get("reason")), None)
                key = f"ua:{rid}:{atype}"
                out[key] = {"key": key, "source": self.NAME, "location_uid": f"ua-{rid}", "location_title": p["name"],
                            "location_title_en": r.get("regionEngName") if str(r.get("regionId")) == rid else None,
                            "location_type": p["type"], "oblast_uid": p["obl"], "alert_type": atype, "alert_level": level,
                            "started_at": min(times) if times else now_iso(), "finished_at": None, "notes": reason, "threats": [],
                            "raion_uid": p.get("raion_uid"), "raion_key": p.get("raion_key"), "raion_title": p.get("raion_title")}
        return list(out.values())


class Ubilling(threading.Thread):
    """Keyless mirror: one on/off per OBLAST, nothing finer, and usually no start time.

    It lights an oblast as soon as any raion in it is under alert, so it can only be a fallback: it stands in
    when no raion-level source answers (`detail` unhealthy), and otherwise just reports its own health.
    """
    NAME = "ubilling_mirror"

    def __init__(self, state, cfg, primary, detail=None):
        super().__init__(daemon=True)
        self.state, self.cfg, self.primary, self.detail = state, cfg, primary, detail

    def run(self):
        interval = max(20, int(self.cfg.get("poll_ubilling_seconds", 30)))
        while True:
            try:
                st, _, body = http_get("https://ubilling.net.ua/aerialalerts/?json=true")
                data = json.loads(body.decode("utf-8"))
                alerts = []
                for name, v in (data.get("states") or {}).items():
                    uid = norm_uk(name)
                    if not uid:
                        continue
                    if v.get("alertnow"):
                        changed = v.get("changed")
                        started = changed.replace(" ", "T") if changed else now_iso()
                        if "+" not in started and not started.endswith("Z"):
                            started += "+03:00"  # mirror reports Kyiv local time
                        d = parse_iso(started)
                        known = bool(d and d.year >= 2022)
                        if not known:
                            # the mirror reports epoch 0: the start time is unknown. The time it is first seen is kept
                            # for ordering only — shown as "since", it was the moment the server rebooted.
                            started = now_iso()
                        uk, en = NAME_BY_UID[uid]
                        alerts.append({"key": f"ub:{uid}", "source": self.NAME, "location_uid": uid,
                                       "location_title": uk, "location_title_en": en, "location_type": "oblast",
                                       "oblast_uid": uid, "alert_type": "air_raid", "alert_level": None,
                                       "started_at": started, "finished_at": None, "notes": "keyless mirror — oblast level only",
                                       "threats": [], "since_known": known})
                standing_in = self.primary and not (self.detail and self.detail.healthy())
                self.state.set_source(self.NAME, True, count=len(alerts), cached_at=data.get("cachedat"),
                                      note="standing in: oblast level only" if standing_in and self.detail else None)
                if standing_in:
                    self.state.apply_snapshot(self.NAME, alerts, {"oblast"})
            except Exception as e:
                self.state.set_source(self.NAME, False, error=str(e)[:200])
                log("ubilling error:", e)
            time.sleep(interval)


class Translations(threading.Thread):
    """Machine translation of feed posts, off the alert path.

    A post is stored and shown the moment it is read, with the offline English glossary. A machine translation
    (DeepL, Google — see translate.py) replaces it afterwards, from here, so a slow or refusing translator can
    never hold a drone report back. Only for a language somebody is reading: a page in English or French asks
    for the feed with ?lang=, and for an hour after that, new posts are translated into that language too.
    Nobody reading French, no French translated — a key's monthly allowance goes to what is read."""
    DEMAND_S = 3600

    def __init__(self, state):
        super().__init__(daemon=True, name="translations")
        self.state = state
        self.q = collections.deque()
        self.queued = set()
        self.cond = threading.Condition()
        self.seen = {}

    def want(self, lang):
        if lang in ("en", "fr"):
            self.seen[lang] = time.time()

    def wanted(self, lang):
        return time.time() - self.seen.get(lang, 0) < self.DEMAND_S

    def add(self, posts, lang, front=False):
        if not (_tr and _tr.backends()):
            return            # nothing here can do better than what is stored
        with self.cond:
            items = [p for p in posts if (p["post_id"], lang) not in self.queued]
            for p in (reversed(items) if front else items):
                self.queued.add((p["post_id"], lang))
                (self.q.appendleft if front else self.q.append)((p["post_id"], p["text"], lang))
            self.cond.notify()

    def run(self):
        while True:
            with self.cond:
                while not self.q:
                    self.cond.wait()
                pid, text, lang = self.q.popleft()
            try:
                out, ok = _tr.translate_to(text, lang)
                if ok and out:
                    self.state.store.set_translation(pid, lang, out)
                    self.state.publish({"kind": "tr", "ts": now_iso(), "post_id": pid, "lang": lang})
                elif not _tr.backends():
                    with self.cond:           # every translator is resting: drop the queue, the next page view refills it
                        self.q.clear()
                        self.queued.clear()
            except Exception as e:
                log("translate:", e)
            finally:
                with self.cond:
                    self.queued.discard((pid, lang))


# A reply on t.me/s/ carries the message it answers first, in a div of the same class
# ("tgme_widget_message_text js-message_reply_text"), then its own ("… js-message_text"). The reader took the first
# one: the Air Force's "📢 Відбій небезпеки по МіГ-31К", posted as a reply to its take-off message, was stored as
# "Зафіксовано зліт МіГ-31К" — a second take-off at the very minute the danger was called off (1.33).
_TG_TEXT_RX = re.compile(r'<div class="tgme_widget_message_text(?![^"]*reply)[^"]*"[^>]*>(.*?)</div>', re.S)


def tg_post_text(block):
    """The text of one t.me/s/ message block — its own, not the quoted message of a reply — as HTML, or None."""
    m = _TG_TEXT_RX.search(block)
    return m.group(1) if m else None


class Telegram(threading.Thread):
    """Reads public channel previews at t.me/s/<channel> (no API key)."""
    NAME = "telegram"
    TAG_RE = re.compile(r"<br\s*/?>", re.I)
    STRIP_RE = re.compile(r"<[^>]+>")

    def __init__(self, state, cfg):
        super().__init__(daemon=True)
        self.state, self.cfg = state, cfg
        extra = [c for c in (cfg.get("telegram_channels") or []) if c not in AUTHORITATIVE_CHANNELS]
        if extra:
            log(f"telegram: {len(extra)} channel(s) in config ignored — the list is the defaults plus the dashboard's")
        self.official = OfficialAlerts(state)
        self.seen_channels = set()
        self.api_channels = set()   # channels TelegramAPI is reading right now — this poller leaves them alone
        self._near_ctx = {}         # 1.45: channel → [(time, oblast uid)] the oblasts its last posts named

    def run(self):
        interval = max(30, int(self.cfg.get("poll_telegram_seconds", 45)))
        fast = max(8, int(self.cfg.get("poll_telegram_missile_seconds", 10)))
        # Ballistic only. A one-second client is pointless if the server itself last looked ten seconds ago:
        # the client can only be as fresh as the source behind it.
        rush = max(5, int(self.cfg.get("poll_telegram_ballistic_seconds", 5)))
        import concurrent.futures as _cf
        pool = _cf.ThreadPoolExecutor(max_workers=4, thread_name_prefix="tg")
        def one(ch):
            try:
                self.poll(ch)
            except Exception as e:
                self.state.set_source(f"tg:{ch}", False, error=str(e)[:200])
                log(f"telegram {ch} error:", e)
        while True:
            lvl = self.state.missile_active()
            try:
                busy = self.state.bridges_busy()     # 1.34: a threat within 12 km of a Kyiv bridge
            except Exception:
                busy = False
            # the dashboard's list, read afresh each round: a channel added, switched or removed takes effect here
            chans = self.state.channels_read("web") + [c for c in self.state.channels_read("api") if c not in self.api_channels]
            list(pool.map(one, chans))   # 4 channels at a time, ~1 round trip each
            time.sleep(rush if lvl >= 2 else fast if (lvl or busy) else interval)

    def poll(self, ch):
        if ch in self.api_channels:
            return            # read through the Telegram API (TelegramAPI) — its preview is switched off
        st, _, body = http_get(f"https://t.me/s/{ch}", {"Accept-Language": "uk,en"})
        page = body.decode("utf-8", "replace")
        if 'tgme_widget_message_wrap' not in page:
            # The owner has switched the web preview off: t.me/s/ shows the landing page and no posts at all.
            # Reported as a failed source, not a quiet one — "no drones reported" and "we cannot read this
            # channel" must never look the same in the sources panel.
            self.state.set_source(f"tg:{ch}", False, error="web preview disabled by the channel — cannot be read via t.me/s/")
            return
        raw_posts = []
        for part in page.split('<div class="tgme_widget_message_wrap')[1:]:
            mid = re.search(r'data-post="([^"]+)"', part)
            mtxt = tg_post_text(part)
            mdt = re.search(r'<time[^>]*datetime="([^"]+)"', part)
            if not (mid and mtxt and mdt):
                continue
            text = html.unescape(self.STRIP_RE.sub("", self.TAG_RE.sub("\n", mtxt))).strip()
            raw_posts.append((mid.group(1), mdt.group(1), text))
        self.ingest(ch, raw_posts, f"tg:{ch}")

    def ingest(self, ch, raw_posts, source):
        """Everything a channel post goes through, whichever way it was read (web preview or Telegram API):
        raw_posts is a list of (post_id "channel/123", ISO time, text)."""
        posts = []
        for post_id, dt, text in sorted(raw_posts, key=lambda r: r[1] or ""):
            text = re.sub(r"[ \t]+", " ", (text or "").strip())
            if not text:
                continue
            if self.state.store.has_post(post_id):
                continue          # already stored (and translated) on an earlier poll
            if ch in AF_SUMMARY_CHANNELS:
                rep = parse_af_report(text, dt)
                if rep:
                    self.state.store.af_save(post_id, ch, dt, rep)
            self.state.store.air_save(post_id, ch, dt, parse_air_report(text), text)
            # 1.44: tagged as the reader sees it — without the channel's signature ("💪 Телеграм канал ППО Вінниця")
            # 1.45: and in the light of the oblasts the channel named in its last 30 minutes (geo.parse_for_channel)
            ctx = self._near_ctx.setdefault(ch, [])
            pt = parse_iso(dt)
            near = [u for t_, u in reversed(ctx) if pt and t_ and 0 <= (pt - t_).total_seconds() <= NEAR_CTX_MIN * 60]
            tags = tag_feed_text(_clean_post(text), ch, near or None)
            if geo:
                ctx.extend((pt, u) for u in geo.oblasts_named(text, ch))
                del ctx[:-12]
            if not is_relevant(text, tags, ch):
                self.state.store.mark_seen(post_id)
                continue          # news, fundraising, culture… — not an air-threat post, not stored
            # The offline glossary, instantly. A machine translation replaces it later, off this path (Translations):
            # on the server the free translator refuses every call, and each refusal cost ~3 s per post — a burst
            # of ten posts held the drone reports in them back by half a minute.
            en, fb = (_tr.translate_offline(text), True) if _tr else (text, True)
            posts.append({"post_id": post_id, "channel": ch, "ts": dt, "text": text, "tags": tags, "text_en": en, "en_fallback": fb})
        new = self.state.store.add_feed(posts)
        self.state.set_source(source, True, count=len(posts), new=len(new))
        if ch == "eRadarrua" and geo:
            for p in sorted(posts, key=lambda p: p["ts"], reverse=True):
                summ = geo.parse_eradar_summary(p["text"]) if "◦" in p["text"] else None
                if summ:
                    self.state.set_eradar(p["ts"], summ)
                    break
        home = self.state.channel_home(ch)
        for p in sorted(new, key=lambda p: p["ts"]):
            if self.state.channel_mode(ch) == "trial":
                p = dict(p, tags=["trial"])       # on trial: shown in the feed, raises nothing (no toast, no banner)
            if home and home not in ("31", "ua"):
                p = dict(p, home=home)            # 1.43: a regional channel's warnings are for that oblast's readers
            self.state.publish({"kind": "feed", "ts": p["ts"], "post": p})
        tr = getattr(self.state, "tr", None)
        if tr and new:
            for lang in ("en", "fr"):
                if tr.wanted(lang):
                    tr.add(sorted(new, key=lambda p: p["ts"], reverse=True), lang, front=True)
        if OFFICIAL_ALERTS_FROM_TELEGRAM and geo and ch in geo.OFFICIAL_PARSERS:
            self.official.ingest(ch, sorted(new, key=lambda p: p["ts"]), initial=ch not in self.seen_channels)
        self.seen_channels.add(ch)
        return new


class AFBackfill(threading.Thread):
    """The Air Force summaries the app did not keep (1.32).

    From 25 Sep the summaries were read as news and dropped, so the statistics lost them. At start, and once a day,
    this looks for nights of the last 14 days with no summary on record — first in the posts already stored, then,
    if any is still missing, in @kpszsu's public page history (t.me/s/kpszsu?before=…), a page every second, at most
    240 pages (the channel posts ~15 pages a day), stopping as soon as no night is missing. It only reads summaries; nothing else from that history is stored."""
    DAYS, MAX_PAGES = 14, 240

    def __init__(self, state):
        super().__init__(daemon=True, name="af-backfill")
        self.state = state

    def missing(self):
        tz = kyiv_tz()
        today = datetime.now(tz).date()
        have = {r["date"] for r in self.state.store.af_reports((today - timedelta(days=self.DAYS)).isoformat()) if r.get("period") == "night"}
        return [(today - timedelta(days=i)).isoformat() for i in range(1, self.DAYS) if (today - timedelta(days=i)).isoformat() not in have]

    def from_feed(self):
        st = self.state.store
        with st.lock:
            rows = st.conn.execute("SELECT post_id,channel,ts,text FROM feed WHERE channel IN (%s)" % ",".join("?" * len(AF_SUMMARY_CHANNELS)),
                                   tuple(AF_SUMMARY_CHANNELS)).fetchall()
        n = 0
        for pid, ch, ts, text in rows:
            rep = parse_af_report(text or "", ts)
            if rep and st.af_save(pid, ch, ts, rep):
                n += 1
        return n

    def from_history(self):
        oldest = (datetime.now(timezone.utc) - timedelta(days=self.DAYS)).isoformat()
        before, n = None, 0
        for page_no in range(self.MAX_PAGES):
            body = None
            for attempt in range(3):
                try:
                    _, _, body = http_get("https://t.me/s/kpszsu" + (f"?before={before}" if before else ""), {"Accept-Language": "uk,en"}, timeout=20)
                    break
                except Exception as e:
                    log("af backfill:", e)
                    time.sleep(5 * (attempt + 1))
            if body is None:
                return n
            if page_no % 10 == 9 and not self.missing():
                return n
            page = body.decode("utf-8", "replace")
            ids, last_ts = [], None
            for blk in page.split('<div class="tgme_widget_message_wrap')[1:]:
                m = re.search(r'data-post="kpszsu/(\d+)"', blk)
                if not m:
                    continue
                ids.append(int(m.group(1)))
                tm = tg_post_text(blk)
                dt = re.search(r'<time[^>]*datetime="([^"]+)"', blk)
                if not (tm and dt):
                    continue
                last_ts = dt.group(1)
                text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", tm)))
                rep = parse_af_report(text, dt.group(1))
                if rep and self.state.store.af_save(f"kpszsu/{m.group(1)}", "kpszsu", dt.group(1), rep):
                    n += 1
                self.state.store.air_save(f"kpszsu/{m.group(1)}", "kpszsu", dt.group(1), parse_air_report(text), text)
            if not ids or (last_ts and last_ts < oldest):
                break
            before = min(ids)
            time.sleep(1)
        return n

    AIR_VERSION = "1"                        # bump when parse_air_report changes: the stored feed is read again

    def air_from_feed(self):
        """The carriers in every post already stored (1.33): once, and again whenever the parser changes."""
        st = self.state.store
        if st.kv_get("air_parsed") == self.AIR_VERSION:
            return 0
        n, last = 0, 0
        while True:
            with st.lock:
                rows = st.conn.execute("SELECT rowid,post_id,channel,ts,text FROM feed WHERE rowid>? ORDER BY rowid LIMIT 2000", (last,)).fetchall()
            if not rows:
                break
            for rid, pid, ch, ts, text in rows:
                last = rid
                n += st.air_save(pid, ch, ts, parse_air_report(text or ""), text)
            time.sleep(0.05)
        st.kv_set("air_parsed", self.AIR_VERSION)
        log(f"air: {n} carrier reports read from the stored posts")
        return n

    def run(self):
        time.sleep(60)                       # after the start's own work
        try:
            self.air_from_feed()
        except Exception as e:
            log("air backfill:", e)
        while True:
            try:
                n = self.from_feed()
                if self.missing():
                    n += self.from_history()
                if n:
                    log(f"af backfill: {n} Air Force summaries recovered; nights still missing: {len(self.missing())}")
                    self.state._stats_res = {}
            except Exception as e:
                log("af backfill:", e)
            time.sleep(24 * 3600)


# 1.33: the weather of each night where the drones are launched from, and over Kyiv — to see whether the volume of
# an attack follows the wind, the cloud or the rain. Open-Meteo (free, no key); only these fixed points are asked
# for, nothing about anybody. A night is 18:00 the day before to 06:00 on `date`, Kyiv time — the Air Force's night.
WEATHER_POINTS = [("kyiv", "Київ", 50.45, 30.52), ("orel", "Орел", 52.97, 36.06), ("kursk", "Курськ", 51.73, 36.19),
                  ("bryansk", "Брянськ", 53.24, 34.36), ("shatalovo", "Шаталово", 54.34, 32.47),
                  ("millerovo", "Міллерово", 48.92, 40.40), ("primorsko", "Приморсько-Ахтарськ", 46.05, 38.17)]
WEATHER_LAUNCH = [k for k, *_ in WEATHER_POINTS if k != "kyiv"]


def parse_open_meteo(data, now=None):
    """Open-Meteo's hourly series (one per point, in WEATHER_POINTS order, Kyiv local time) → {(date, place):
    {wind, gust, cloud, precip, tmin}} for every complete night: mean wind at 10 m (km/h), strongest gust, mean
    cloud cover (%), rain over the night (mm), lowest temperature (°C)."""
    if isinstance(data, dict):
        data = [data]
    now_local = (now or datetime.now(timezone.utc)).astimezone(kyiv_tz()).replace(tzinfo=None)
    out = {}
    for (key, *_), d in zip(WEATHER_POINTS, data or []):
        h = (d or {}).get("hourly") or {}
        nights = {}
        for i, tm in enumerate(h.get("time") or []):
            try:
                t = datetime.fromisoformat(tm)
            except ValueError:
                continue
            if t.hour >= 18:
                nights.setdefault((t + timedelta(days=1)).date(), []).append(i)
            elif t.hour < 6:
                nights.setdefault(t.date(), []).append(i)
        for nd, idx in nights.items():
            if len(idx) < 12 or datetime(nd.year, nd.month, nd.day, 6) > now_local:
                continue                                   # not over yet, or cut at the start of the series

            def col(k):
                v = h.get(k) or []
                return [v[i] for i in idx if i < len(v) and v[i] is not None]
            w, g, c, pr, tt = col("wind_speed_10m"), col("wind_gusts_10m"), col("cloud_cover"), col("precipitation"), col("temperature_2m")
            if not w:
                continue
            out[(nd.isoformat(), key)] = {"wind": round(sum(w) / len(w), 1), "gust": round(max(g), 1) if g else None,
                                         "cloud": round(sum(c) / len(c)) if c else None, "precip": round(sum(pr), 1) if pr else None,
                                         "tmin": round(min(tt), 1) if tt else None}
    return out


class Weather(threading.Thread):
    """Every 6 h: the last nights' weather at WEATHER_POINTS (92 days the first time)."""
    URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m,wind_gusts_10m,"
           "cloud_cover,precipitation,temperature_2m&past_days={days}&forecast_days=1&timezone=Europe%2FKyiv")

    def __init__(self, state):
        super().__init__(daemon=True, name="weather")
        self.state = state

    def fetch(self, days=None):
        st = self.state.store
        if days is None:
            days = 10 if st.weather((datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()) else 92
        url = self.URL.format(lat=",".join(str(p[2]) for p in WEATHER_POINTS), lon=",".join(str(p[3]) for p in WEATHER_POINTS), days=days)
        _, _, body = http_get(url, timeout=30)
        n = st.weather_save(parse_open_meteo(json.loads(body.decode("utf-8"))))
        self.state.weather_status = {"ok": True, "last": now_iso(), "nights": n}   # the dashboard's, not a page's source
        return n

    def run(self):
        time.sleep(90)
        while True:
            wait = 6 * 3600
            try:
                self.fetch()
            except Exception as e:
                # Open-Meteo limits calls per address and per day ("Daily API request limit exceeded" on a shared
                # address): try again in an hour, not in six
                log("weather:", e)
                self.state.weather_status = {"ok": False, "last": now_iso(), "error": str(e)[:160]}
                wait = 3600
            time.sleep(wait)


class TelegramAPI(threading.Thread):
    """Reads the channels whose web preview is switched off — chyste_nebo — through the Telegram client API.

    chyste_nebo is the channel that states drone heights most often, and its owner switched t.me/s/ off, so the
    preview reader sees nothing. A user session (api_id / api_hash from my.telegram.org, and a one-time sign-in
    with scripts/telegram-login.bat) reads it the way the Telegram app does. That session is a key to a whole
    Telegram account: it lives only in Fly secrets (TG_SESSION) — never in config.json, the logs or the repository.

    It READS the channel — the last 20 posts every 15 s, every 8 s while a missile is in the air — and does not
    subscribe to updates. 25 Sep 2026: with updates on, the session (a personal account) received the update stream
    of every chat and channel it is in; on the 256 MB server that took the whole process down within minutes of
    the first sign-in — pages, the official alert reader, everything stopped answering. Every post goes through
    the same Telegram.ingest() as the preview reader, so nothing downstream knows or cares how it was read."""
    POLL_S, POLL_MISSILE_S = 15, 8
    NAME = "tgapi"

    def __init__(self, state, cfg, tg):
        super().__init__(daemon=True, name="tgapi")
        self.state, self.cfg, self.tg = state, cfg, tg
        self.channels = []          # the channels open right now; which ones is the dashboard's list (State.channels_read)

    @staticmethod
    def configured(cfg):
        return bool(cfg.get("tg_api_id") and cfg.get("tg_api_hash") and cfg.get("tg_session"))

    @staticmethod
    def raw_of(ch, msg):
        """A Telethon message → the (post_id, time, text) the preview reader produces for the same post."""
        return (f"{ch}/{msg.id}", msg.date.astimezone(timezone.utc).isoformat(), msg.message or "")

    def _status(self, ok, **kw):
        for ch in self.channels:
            self.state.set_source(f"tga:{ch}", ok, via="Telegram API", **kw)

    def run(self):
        try:
            import asyncio

            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except Exception as e:
            self._status(False, error="telethon is not installed")
            log("telegram api: telethon not available —", e)
            return
        while True:
            try:
                asyncio.run(self._session(TelegramClient, StringSession))
                return            # stopped for good (session revoked)
            except Exception as e:
                self.tg.api_channels -= set(self.channels)     # let the preview reader report the channel again
                self._status(False, error=str(e)[:160])
                log("telegram api error:", e)
                time.sleep(30)

    async def _session(self, TelegramClient, StringSession):
        import asyncio
        try:
            sess = StringSession(self.cfg["tg_session"])
        except ValueError:
            self._status(False, error="TG_SESSION is not a Telegram session — run scripts\\telegram-login.bat again")
            log("telegram api: TG_SESSION is not a valid session string")
            return
        client = TelegramClient(sess, int(self.cfg["tg_api_id"]), self.cfg["tg_api_hash"],
                                device_model="Clear Sky server", app_version=APP_VERSION, receive_updates=False)
        await client.connect()
        if not await client.is_user_authorized():
            self._status(False, error="Telegram session no longer valid — run scripts\\telegram-login.bat again")
            log("telegram api: session not authorised — run scripts/telegram-login.bat")
            await client.disconnect()
            return
        ents, retry = {}, {}
        try:
            while client.is_connected():
                # the dashboard's list, read afresh each round (1.31): a channel switched to the API, or off, or added
                want = self.state.channels_read("api")
                for ch in [c for c in ents if c not in want]:
                    ents.pop(ch)
                    self.tg.api_channels.discard(ch)
                    log("telegram api: no longer reading @" + ch)
                for ch in [c for c in want if c not in ents and retry.get(c, 0) <= time.time()]:
                    try:
                        ents[ch] = await client.get_entity(ch)
                        self.tg.api_channels.add(ch)
                        with self.state.lock:
                            self.state.sources.pop(f"tg:{ch}", None)       # no longer a failed preview source
                        log("telegram api: reading @" + ch)
                    except Exception as ex:
                        retry[ch] = time.time() + 300                        # not every 15 s: Telegram limits this
                        self.state.set_source(f"tga:{ch}", False, via="Telegram API", error=("cannot open this channel: " + str(ex))[:160])
                self.channels = list(ents)
                for ch, e in list(ents.items()):
                    try:
                        msgs = await client.get_messages(e, limit=20)
                        # the parsing and the database work run off this thread's event loop
                        await asyncio.to_thread(self.tg.ingest, ch, [self.raw_of(ch, m) for m in reversed(msgs) if m.message], f"tga:{ch}")
                    except Exception as ex:
                        wait = getattr(ex, "seconds", None)       # FloodWaitError: Telegram says how long to wait
                        self.state.set_source(f"tga:{ch}", False, via="Telegram API", error=str(ex)[:160])
                        if wait:
                            await asyncio.sleep(min(int(wait), 600))
                await asyncio.sleep(self.POLL_MISSILE_S if (self.state.missile_active() or self.state.bridges_busy()) else self.POLL_S)
        finally:
            self.tg.api_channels -= set(ents)
            await client.disconnect()
        raise ConnectionError("disconnected from Telegram")


class Digests(threading.Thread):
    """The record of each night and each week (dashboard only).

    Once the night is over — 18:00 to 08:00 Kyiv time, written up after `digest_hour` so the Air Force's morning
    summary is in it — its numbers are computed (`State.digest_facts`) and stored, and, when ANTHROPIC_API_KEY is
    set, put into words in English and Ukrainian. The same every Monday for the week before. The numbers are kept
    with the text, so every sentence can be checked against them. The model gets counts and place names only — no
    post, no reader, nobody — and is told to describe them and nothing else: no forecasts, no guessed targets.

    Never in a request path: the dashboard's "now" button only asks this thread."""
    NIGHT_H = (18, 8)

    def __init__(self, state, cfg):
        super().__init__(daemon=True, name="digests")
        self.state, self.cfg = state, cfg
        self.hour = int(cfg.get("digest_hour", 9))
        self.cond = threading.Condition()
        self.asked = []

    def ask(self, kind):
        with self.cond:
            if kind not in self.asked:
                self.asked.append(kind)
            self.cond.notify()

    def last_night(self, now=None):
        tz = kyiv_tz()
        local = (now or datetime.now(timezone.utc)).astimezone(tz)
        d = local.date() if local.hour >= self.hour else local.date() - timedelta(days=1)
        end = datetime(d.year, d.month, d.day, self.NIGHT_H[1], 0, tzinfo=tz)
        return end - timedelta(hours=24 - self.NIGHT_H[0] + self.NIGHT_H[1]), end

    def last_week(self, now=None):
        s, e = self.last_night(now)
        e = e - timedelta(days=e.weekday())               # the Monday 08:00 at or before the last night's end
        return e - timedelta(days=7), e

    def make(self, kind, force=False):
        start, end = self.last_night() if kind == "night" else self.last_week()
        did = f"{kind}:{end.date().isoformat()}"
        if not force and self.state.store.digest_get(did):
            return None
        su, eu = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        facts = self.state.digest_facts(su, eu, kind)
        if kind == "week":
            facts["previous_week"] = self.state.digest_totals(su - timedelta(days=7), su)
        en, uk, model, err = ai_summary(self.cfg, facts, kind)
        d = {"id": did, "kind": kind, "period_start": su.isoformat(), "period_end": eu.isoformat(), "facts": facts,
             "summary_en": en, "summary_uk": uk, "model": model, "created": now_iso(), "error": err}
        self.state.store.digest_save(d)
        log(f"digest {did}: " + ("written" if en or uk else f"figures only ({err})"))
        return d

    def run(self):
        time.sleep(20)
        while True:
            with self.cond:
                asked, self.asked = self.asked, []
            for kind in ("night", "week"):
                try:
                    self.make(kind, force=kind in asked)
                except Exception as e:
                    log(f"digest {kind} error:", e)
            with self.cond:
                if not self.asked:
                    self.cond.wait(300)


class Vitals(threading.Thread):
    """1.41: is the server itself well? "The app goes off sometimes" can be four different things, and each needs a
    different answer: a new version being deployed (a start with a new build), a crash or an out-of-memory kill (a
    start with the same build), the host taking the CPU away (on a shared Fly vCPU, past its baseline the machine is
    throttled: the guest sees it as "steal" time and every request waits), or one slow piece of work holding the rest.
    Every 10 s this records the process's own CPU, the steal, the memory and how late its own clock woke it; every
    request over 2 s is noted (path and time only — never who); every start is kept with its build. All of it is on
    the dashboard (Live), so the next time it happens the cause is on screen instead of guessed."""
    INTERVAL, SLOW_MS = 10, 2000

    def __init__(self, state):
        super().__init__(daemon=True, name="vitals")
        self.state = state
        self.samples = collections.deque(maxlen=360)        # one hour
        self.slow = collections.deque(maxlen=60)
        self.started = now_iso()
        self._t0 = time.monotonic()
        self._prev = None
        self.boots = self._record_boot()

    def _record_boot(self):
        try:
            b = json.loads(self.state.store.kv_get("boots") or "[]")
        except Exception:
            b = []
        b = (b + [{"ts": self.started, "build": BUILD, "app": APP_VERSION}])[-100:]
        try:
            self.state.store.kv_set("boots", json.dumps(b))
        except Exception:
            pass
        return b

    @staticmethod
    def read():
        """(process CPU seconds, all-CPU jiffies, steal jiffies, RSS MB, available MB, total MB) — Linux only."""
        out = [None] * 6
        try:
            with open("/proc/self/stat") as f:
                fs = f.read().rsplit(")", 1)[1].split()
            out[0] = (int(fs[11]) + int(fs[12])) / os.sysconf("SC_CLK_TCK")
        except Exception:
            pass
        try:
            with open("/proc/stat") as f:
                v = [int(x) for x in f.readline().split()[1:9]]
            out[1], out[2] = sum(v), v[7]
        except Exception:
            pass
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        out[3] = round(int(line.split()[1]) / 1024)
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        out[4] = round(int(line.split()[1]) / 1024)
                    elif line.startswith("MemTotal:"):
                        out[5] = round(int(line.split()[1]) / 1024)
        except Exception:
            pass
        return out

    def sample(self):
        now, r = time.monotonic(), self.read()
        p, self._prev = self._prev, (now, r)
        if not p:
            return
        dt = now - p[0]
        cpu = round(100 * (r[0] - p[1][0]) / dt, 1) if r[0] is not None and p[1][0] is not None and dt > 0 else None
        tot = (r[1] - p[1][1]) if r[1] is not None and p[1][1] is not None else 0
        steal = round(100 * (r[2] - p[1][2]) / tot, 1) if tot > 0 else None
        self.samples.append({"ts": now_iso(), "cpu": cpu, "steal": steal, "rss": r[3], "avail": r[4], "total": r[5],
                             "late": round(max(0.0, dt - self.INTERVAL), 1)})

    def run(self):
        while True:
            try:
                self.sample()
            except Exception as e:
                log("vitals:", e)
            time.sleep(self.INTERVAL)

    def note(self, path, ms):
        if ms >= self.SLOW_MS and not path.startswith("/api/stream"):
            self.slow.append({"ts": now_iso(), "path": path[:60], "ms": int(ms)})

    def report(self):
        s = list(self.samples)

        def col(k):
            return [x[k] for x in s if x.get(k) is not None]

        def stat(v):
            return {"now": v[-1], "avg": round(sum(v) / len(v), 1), "max": max(v)} if v else None
        hour = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent = [b for b in self.boots if b["ts"] >= week]
        same = sum(1 for i, b in enumerate(self.boots) if i and b["ts"] >= week and self.boots[i - 1]["build"] == b["build"])
        return {"started": self.started, "uptime_s": int(time.monotonic() - self._t0), "build": BUILD, "app": APP_VERSION,
                "cpu": stat(col("cpu")), "steal": stat(col("steal")), "late": stat(col("late")),
                "rss": stat(col("rss")), "avail_min": min(col("avail")) if col("avail") else None,
                "mem_total": (col("total") or [None])[-1],
                "slow_1h": [x for x in self.slow if x["ts"] >= hour][-10:], "slow_1h_n": sum(1 for x in self.slow if x["ts"] >= hour),
                "starts_7d": len(recent), "restarts_same_build_7d": same, "boots": self.boots[-12:]}


class Watchdog(threading.Thread):
    """A service people take shelter by must never hang in silence.

    25 Sep 2026: the process stopped answering — pages, the version ping, the official alert reader — while
    /healthz still said "ok", and nothing restarted it. Every 20 s this checks that the database and the alert
    state can be had within 15 s, and that the process itself is not starved (its own 20 s sleep did not take a
    minute). A held lock writes every thread's stack to the log, which says exactly where it is stuck; a lock held
    through five checks in a row (about two minutes) and the process exits: Fly starts it again in seconds. A
    starved process is only logged — that is load, and a restart under load would bring every page back at once."""
    INTERVAL, WAIT, MISSES = 20, 15, 5

    def __init__(self, state):
        super().__init__(daemon=True, name="watchdog")
        self.state, self.misses, self.last = state, 0, None

    def check(self):
        why = []
        for name, lk in (("database", self.state.store.lock), ("alert state", self.state.lock)):
            if lk.acquire(timeout=self.WAIT):
                lk.release()
            else:
                why.append(f"{name} lock held for more than {self.WAIT} s")
        now = time.monotonic()
        if self.last is not None and now - self.last > self.INTERVAL * 3 + self.WAIT * 2:
            why.append(f"the process was starved: a {self.INTERVAL} s sleep took {round(now - self.last)} s")
        self.last = now
        return why

    def run(self):
        while True:
            time.sleep(self.INTERVAL)
            why = self.check()
            if not why:
                self.misses = 0
                continue
            locked = any("lock held" in w for w in why)
            # starvation alone is load, not a deadlock: logged, never a restart (a restart under load brings
            # every page back at once and makes it worse)
            self.misses = self.misses + 1 if locked else 0
            log(f"WATCHDOG ({self.misses}/{self.MISSES}): " + "; ".join(why))
            if not locked:
                continue
            names = {t.ident: t.name for t in threading.enumerate()}
            for ident, frame in sys._current_frames().items():
                log(f"--- thread {names.get(ident, ident)}\n" + "".join(traceback.format_stack(frame)[-8:]))
            if self.misses >= self.MISSES:
                log("WATCHDOG: the server is not answering — exiting so that Fly restarts it")
                os._exit(3)


class OfficialAlerts:
    """Turns posts of official administration channels (Kyiv oblast / Kyiv city) into alerts.
    Raion-level alerts are authoritative from here; oblast/city-level ones get merged with keyed sources."""
    NAME = "tg_official"

    def __init__(self, state):
        self.state = state
        self.active = {}   # key -> alert
        self.lock = threading.Lock()

    def ingest(self, channel, posts, initial=False):
        kind, oblast_uid, fixed_name = geo.OFFICIAL_PARSERS[channel]
        changed = False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
        with self.lock:
            for p in posts:
                pts = parse_iso(p["ts"])
                if initial and pts and pts < cutoff:
                    continue
                if kind == "koda":
                    rs = [geo.parse_koda(p["text"])]
                elif kind == "kmda":
                    rs = [geo.parse_kmda(p["text"])]
                elif kind == "etryvoga":
                    rs = geo.parse_etryvoga(p["text"]) or []
                elif kind == "eradar_alert":
                    rs = geo.parse_eradar_alert(p["text"]) or []
                else:
                    r0 = geo.parse_city_siren(p["text"])
                    rs = [dict(r0, name=fixed_name, type="raion")] if r0 else []
                for r in rs:
                    if not r:
                        continue
                    if self._apply(r, kind, oblast_uid, channel, p):
                        changed = True
            stale = datetime.now(timezone.utc) - timedelta(hours=4)
            for k in [k for k, a in self.active.items() if (parse_iso(a["started_at"]) or stale) < stale]:
                self.active.pop(k, None)
                changed = True
            alerts = [dict(a, threats=list(a["threats"])) for a in self.active.values()]
        self.state.set_source(self.NAME, True, count=len(alerts))
        if changed or initial:
            self.state.apply_snapshot(self.NAME, alerts, {"raion"})

    def _apply(self, r, kind, oblast_uid, channel, p):
        """Apply one parsed alert change to self.active (lock held). Returns True when something changed."""
        changed = False
        if True:
            if True:
                if kind == "kmda" or (kind in ("etryvoga", "eradar_alert") and r.get("type") == "city"):
                    key = "tgo:31"
                    if r["kind"] == "end":
                        self.active.pop(key, None)
                        changed = True
                    elif r["kind"] == "start":
                        a = self.active.get(key) or {"key": key, "source": self.NAME, "location_uid": "31", "location_title": "м. Київ",
                                                     "location_title_en": "Kyiv city", "location_type": "oblast", "oblast_uid": "31",
                                                     "alert_type": "air_raid", "alert_level": r["level"], "started_at": p["ts"], "finished_at": None,
                                                     "notes": "@" + channel, "threats": []}
                        a["alert_level"] = "red" if "red" in (a.get("alert_level"), r["level"]) else r["level"]
                        for t in r["threats"]:
                            t = dict(t, started_at=p["ts"])
                            if not any(x["threat_type"] == t["threat_type"] for x in a["threats"]):
                                a["threats"].append(t)
                        self.active[key] = a
                        changed = True
                    elif r["kind"] == "threat":
                        a = self.active.get(key)
                        if a:
                            for t in r["threats"]:
                                t = dict(t, started_at=p["ts"])
                                if not any(x["threat_type"] == t["threat_type"] for x in a["threats"]):
                                    a["threats"].append(t)
                            changed = True
                    return changed
                # raion / oblast alerts (koda-format channels, єТривога, city sirens)
                ouid = r.get("oblast_uid") or oblast_uid
                name = r["name"]
                uid = ouid if r["type"] == "oblast" else ouid + ":" + re.sub(r"\s+", "_", name.lower())
                key = f"tgo:{uid}"
                if r["kind"] == "start":
                    a = self.active.get(key) or {"key": key, "source": self.NAME, "location_uid": uid, "location_title": name,
                                                 "location_title_en": None, "location_type": r["type"], "oblast_uid": ouid,
                                                 "alert_type": "air_raid", "alert_level": r["level"], "started_at": p["ts"], "finished_at": None,
                                                 "notes": "@" + channel, "threats": []}
                    a["alert_level"] = r["level"]
                    if a["notes"] != "@" + channel and "@" + channel not in a["notes"]:
                        a["notes"] += " @" + channel
                    for t in r["threats"]:
                        t = dict(t, started_at=p["ts"])
                        if not any(x["threat_type"] == t["threat_type"] for x in a["threats"]):
                            a["threats"].append(t)
                    self.active[key] = a
                elif r["kind"] == "threat":
                    a = self.active.get(key)
                    if not a:
                        a = {"key": key, "source": self.NAME, "location_uid": uid, "location_title": name, "location_title_en": None,
                             "location_type": r["type"], "oblast_uid": ouid, "alert_type": "air_raid", "alert_level": "yellow",
                             "started_at": p["ts"], "finished_at": None, "notes": "@" + channel, "threats": []}
                        self.active[key] = a
                    for t in r["threats"]:
                        t = dict(t, started_at=p["ts"])
                        if not any(x["threat_type"] == t["threat_type"] for x in a["threats"]):
                            a["threats"].append(t)
                else:
                    self.active.pop(key, None)
                changed = True
        return changed


class Demo(threading.Thread):
    """Fake alert generator so the dashboard can be tested without keys."""
    NAME = "demo"

    def __init__(self, state, cfg):
        super().__init__(daemon=True)
        self.state, self.cfg = state, cfg

    def run(self):
        import random
        active = {}
        threats_pool = [("drones", "yellow", "Загроза застосування ударних БпЛА"), ("ballistic_missiles", "red", "Загроза застосування балістичного озброєння"),
                        ("mig31k_departure", "red", "Зліт МіГ-31К"), ("cruise_missiles", "red", "Пуски крилатих ракет")]
        while True:
            uid = random.choice([o[0] for o in OBLASTS] + ["31", "14", "31"])
            if uid in active and random.random() < 0.5:
                del active[uid]
            else:
                uk, en = NAME_BY_UID[uid]
                t = random.sample(threats_pool, k=random.randint(1, 2))
                active[uid] = {"key": f"demo:{uid}", "source": "demo", "location_uid": uid, "location_title": uk,
                               "location_title_en": en, "location_type": "oblast", "oblast_uid": uid, "alert_type": "air_raid",
                               "alert_level": t[0][1], "started_at": now_iso(), "finished_at": None, "notes": "DEMO",
                               "threats": [{"threat_type": a, "level": b, "started_at": now_iso(), "source_message": c} for a, b, c in t]}
            self.state.set_source(self.NAME, True, count=len(active))
            self.state.apply_snapshot(self.NAME, list(active.values()), {"oblast", "raion", "city", "hromada", "unknown"})
            dtext = random.choice(["🛵 Ударні БпЛА на Київщині ➡️ курсом на Київ", "Загроза застосування балістики з півдня", "Зліт МіГ-31К з аеродрому Саваслейка", "Відбій загрози балістики",
                                                       "🛵 Ударні БпЛА на Чернігівщині в р-ні Добрянки курс південний", "🏍 Реактивний БпЛА в р-ні Володарки (Київщина) курс північний.",
                                                       "🛵 Група ударних БпЛА на Сумщині курсом на Полтавщину", "🚀 Швидкісна ціль на Дніпропетровщині курсом на Павлоград!",
                                                       "🛵 БпЛА в районі Кременчуцького водосховища, курс північно-західний.", "💣 КАБи на Донеччину.", "🛵 Ударні БпЛА на півночі Чернігівщини на/повз Ріпки ➡️ у південно-західному напрямку.",
                                                       "🛵 Харківщина: ударні БпЛА ➡️ курсом на Богодухів.", "🛵 Житомирщина - БпЛА поряд н.п. Ємільчине курсом на Рівненську область.", "🏍 Реактивний БпЛА на Білу Церкву з півдня",
                                                       "🛵 Ударні БпЛА на Черкащині повз Канів курсом на Бориспіль", "🚀 Крилаті ракети з Чорного моря курсом на Одесу",
                                                       "🏍 Реактивний БпЛА в р-ні Козельця курсом на Бровари", "🛵 Ударні БпЛА на Київщині повз Іванків курсом на Вишгород", "🛵 2х БпЛА від Фастова на Васильків",
                                                       "🛵 БпЛА над Обуховом курсом на столицю", "🅿️ 1х реактив від Ніжина у напрямку Києва", "🟡 Броварський район — повітряна тривога, жовтий рівень: Дронова загроза (жовтий рівень)",
                                                       "1х зниження Троєщина.", "🅿️ БпЛА збито в районі Василькова", "По реактивам довкола Києва та Броварів чисто.", "Вибух у Бортничах, попередньо ППО"])
            dpost = {"post_id": f"demo/{int(time.time())}", "channel": "demo", "ts": now_iso(), "text": dtext, "tags": tag_feed_text(dtext), "text_en": to_en(dtext)}
            self.state.store.add_feed([dpost])
            self.state.publish({"kind": "feed", "ts": now_iso(), "post": dpost})
            time.sleep(random.randint(8, 20))


# ---------------------------------------------------------------------------
# Web Push (phone notifications even with the page closed)
# ---------------------------------------------------------------------------
RAION_STEMS = [("бровар", "brovary"), ("бориспіл", "boryspil"), ("бучан", "bucha"), ("вишгород", "vyshhorod"), ("обухів", "obukhiv"), ("білоцерків", "bila-tserkva"), ("фастів", "fastiv")]


class Pusher:
    """Sends Web Push notifications for Kyiv events: city / oblast-wide starts, ends and threats, raion events
    of the subscriber's priority raion, and MiG-31K / ballistic warnings. One background worker takes the
    notifications in order, deduped; each goes to all its phones at once (push.Sender)."""
    def __init__(self, store):
        self.store = store
        self.enabled = bool(_push and _push.AVAILABLE)
        self.priv = self.pub = None
        if self.enabled:
            self.priv, self.pub = store.kv_get("vapid_priv"), store.kv_get("vapid_pub")
            if not (self.priv and self.pub):
                self.priv, self.pub = _push.generate_vapid()
                store.kv_set("vapid_priv", self.priv); store.kv_set("vapid_pub", self.pub)
        self.q = []
        self.cond = threading.Condition()
        self.recent = {}
        self.last_fanout = None
        self.sender = _push.Sender(self.priv, self.pub) if self.enabled else None
        if self.enabled:
            threading.Thread(target=self._run, daemon=True, name="push").start()

    def on_event(self, ev):
        if not self.enabled:
            return
        a = ev["alert"]; kind = ev["kind"]
        ou = a.get("oblast_uid")
        title = body = None; tag = "alert"
        thr = ev.get("threat") or {}
        tt = thr.get("threat_type")
        # A MiG-31K take-off is not a Kyiv event. The Air Force declares an alert over the whole country for
        # it, because the aircraft can turn toward anywhere before it fires, and the channels post it as
        # "тривога по усій території країни". Gating it on the Kyiv oblast uid meant a subscriber in Kharkiv
        # got nothing at all for the one warning that comes an hour ahead of the missile.
        if kind == "threat" and tt == "mig31k_departure":
            title = "✈ MiG-31K airborne — ballistic risk, country-wide"
            body = (thr.get("source_message") or "")[:120]; tag = "threat"
        elif kind == "threat" and tt == "ballistic_missiles" and ou in ("31", "14"):
            # Still oblast-gated: a ballistic launch concerns a region, and a subscription stores a coarse
            # home cell with no region on it. Positioned ballistic markers are already covered region-wide by
            # proximity_watch; the rest waits for the subscriber's own region to be a stored thing.
            title = "🚀 Ballistic threat — shelter now"
            body = (thr.get("source_message") or "")[:120]; tag = "threat"
        # Siren-start and all-clear pushes are gone. "Kyiv oblast — alert" says nothing a person can act on:
        # not what, not where, not how far — the siren itself already said that much, louder. A push that
        # cannot be acted on still wakes somebody at 3 a.m., and after enough of those the ones that matter
        # get swiped away too. What is left is what is specific: a MiG-31K or ballistic launch, above, and a
        # target actually near the reader, in proximity_watch.
        if not title:
            return
        self._queue(title, body, tag)

    def _queue(self, title, body, tag, raion=None):
        k = (title, raion); now = time.time()
        if now - self.recent.get(k, 0) < 90:
            return
        self.recent[k] = now
        with self.cond:
            self.q.append({"title": title, "body": body, "tag": tag, "raion": raion, "ts": now_iso()})
            self.cond.notify()

    def queue_all(self, title, body, tag):
        """Every subscribed phone, no deduplication: the admin's message, sent on purpose."""
        with self.cond:
            self.q.append({"title": title, "body": body, "tag": tag, "raion": None, "ts": now_iso()})
            self.cond.notify()

    def queue_direct(self, title, body, tag, endpoint):
        """One device only — used by the proximity watcher, which does its own deduplication."""
        with self.cond:
            self.q.append({"title": title, "body": body, "tag": tag, "raion": None, "only": endpoint, "ts": now_iso()})
            self.cond.notify()

    def queue_topic(self, texts, tag, topic):
        """The phones that asked for `topic` (1.34: "bridges"), each in its own language: texts = {lang: (title, body)}."""
        with self.cond:
            self.q.append({"texts": texts, "tag": tag, "topic": topic, "raion": None, "ts": now_iso()})
            self.cond.notify()

    def send_test(self, endpoint=None):
        with self.cond:
            self.q.append({"title": APP_NAME, "body": "Push notifications are on for this phone.", "tag": "test", "raion": None, "only": endpoint, "ts": now_iso()})
            self.cond.notify()

    def _run(self):
        while True:
            with self.cond:
                while not self.q:
                    self.cond.wait()
                n = self.q.pop(0)
            subs = [s_ for s_ in self.store.push_all()
                    if not (n.get("only") and s_["endpoint"] != n["only"])
                    and not (n.get("raion") and (s_["home"] or {}).get("raion") != n["raion"])
                    and not (n.get("topic") and n["topic"] not in s_.get("topics", []))]
            if not subs:
                continue
            t0 = time.time()
            try:
                if n.get("texts"):
                    res = [None] * len(subs)
                    for lang in {s_.get("lang") or "uk" for s_ in subs}:
                        idx = [i for i, s_ in enumerate(subs) if (s_.get("lang") or "uk") == lang]
                        title, body = n["texts"].get(lang) or n["texts"]["uk"]
                        part = self.sender.send_many([subs[i]["sub"] for i in idx], {"title": title, "body": body, "tag": n["tag"],
                                                                                    "ts": n["ts"], "url": "/m"})
                        for i, r in zip(idx, part):
                            res[i] = r
                else:
                    res = self.sender.send_many([s_["sub"] for s_ in subs], {"title": n["title"], "body": n["body"], "tag": n["tag"],
                                                                            "ts": n["ts"], "url": "/m"})
            except Exception as e:
                log("push error:", e); continue
            ok = 0
            for s_, (_, code, gone) in zip(subs, res):
                ok += 200 <= code < 300
                if gone:
                    self.store.push_remove(s_["endpoint"])
            self.last_fanout = {"ts": now_iso(), "phones": len(subs), "ok": ok, "seconds": round(time.time() - t0, 2)}
            if len(subs) >= 20:
                log(f"push: {ok}/{len(subs)} phones in {time.time() - t0:.1f} s")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# Notifications by distance from the subscriber's own position.
#
# The rules exist because a false alert at 3 a.m. costs more than a missed one here: the official siren is the
# primary warning, this is the detail on top of it.
#   - only live targets: never a stale one, never a closed track, never an outcome marker;
#   - each target notifies a given device once (30 min memory), so a target re-reported every minute is one push;
#   - at most one push per device every 2 minutes;
#   - the distance sent is the distance to where the post said the target was, and the text says so.
BRIDGE_PUSH_GAP = 600  # one push per bridge per 10 minutes — except when a "near" becomes an "at"
BRIDGE_TXT = {
    "uk": {"at": "🌉 {n}: ціль біля мосту", "near": "🌉 {n}: ціль за {km} км", "body": "{what} · {t} · з дописів каналів, не радар. Не заїжджайте на міст, якщо можете.",
           "drone": "БпЛА", "jet": "Реактивний БпЛА", "missile": "Ракета", "target": "Ціль"},
    "en": {"at": "🌉 {n}: target at the bridge", "near": "🌉 {n}: target {km} km away", "body": "{what} · {t} · from channel posts, not radar. Avoid the bridge if you can.",
           "drone": "Drone", "jet": "Jet drone", "missile": "Missile", "target": "Target"},
    "fr": {"at": "🌉 {n} : cible au pont", "near": "🌉 {n} : cible à {km} km", "body": "{what} · {t} · d'après les chaînes, pas un radar. Évitez le pont si vous le pouvez.",
           "drone": "Drone", "jet": "Drone à réaction", "missile": "Missile", "target": "Cible"},
}


def bridge_push_texts(b, e):
    out = {}
    for lang, T in BRIDGE_TXT.items():
        what = T["jet"] if e.get("jet") else T["missile"] if "missile" in (e.get("type") or "") else T["drone"] if e.get("type") == "drones" else T["target"]
        km = str(e.get("km") or "").replace(".", "," if lang != "en" else ".")
        out[lang] = (T[e["lvl"]].format(n=b[lang] if lang != "fr" else b["fr"][0].upper() + b["fr"][1:], km=km),
                     T["body"].format(what=what, t=fmt_kyiv(e["ts"])))
    return out


def bridge_watch(state, interval=5):
    """Every 5 s: a bridge whose state rose (nothing → near → at) is written to bridge_events, and pushed to the phones
    that asked for the bridges — at most once per bridge every 10 minutes, a "near" turning "at" excepted."""
    prev, pushed = {}, {}
    while True:
        time.sleep(interval)
        try:
            cur = state.bridges_now()
            rank = state.BRIDGE_RANK
            for b in BRIDGES:
                c, p = cur.get(b["id"]) or {}, prev.get(b["id"]) or {}
                if not c or c["lvl"] == "hit" or rank[c["lvl"]] <= rank.get(p.get("lvl"), 0):
                    continue
                state.store.bridge_event(b["id"], c)
                pu = getattr(state, "pusher", None)
                last = pushed.get(b["id"])
                if pu and pu.enabled and (not last or time.time() - last[0] > BRIDGE_PUSH_GAP or (c["lvl"] == "at" and last[1] != "at")):
                    pushed[b["id"]] = (time.time(), c["lvl"])
                    pu.queue_topic(bridge_push_texts(b, c), "threat", "bridges")
            prev = cur
        except Exception as e:
            log("bridge watch:", e)


PROX_SEEN = {}          # endpoint -> {marker id: time}
PROX_LAST = {}          # endpoint -> time of the last push to that device


def proximity_watch(state, interval=20):
    while True:
        time.sleep(interval)
        try:
            pusher = getattr(state, "pusher", None)
            if not (pusher and pusher.enabled):
                continue
            subs = [x for x in state.store.push_all() if (x.get("home") or {}).get("lat") is not None]
            if not subs:
                continue
            live = [m for m in state.markers_now() if not m.get("status") and not m.get("stale") and not m.get("endedBy")]
            if not live:
                continue
            now = time.time()
            for sb in subs:
                ep = sb["endpoint"]; home = sb["home"]
                radius = float(home.get("radius") or 15)
                seen = PROX_SEEN.setdefault(ep, {})
                for mid, t0 in list(seen.items()):
                    if now - t0 > 1800:
                        del seen[mid]
                near = []
                urgent = []
                for m in live:
                    if m["id"] in seen:
                        continue
                    # the stored point is a ~10 km cell, not a house, so the test is widened by half a
                    # cell: nobody inside their own radius is missed because their village was rounded
                    d = haversine_km(home["lat"], home["lon"], m["lat"], m["lon"])
                    # A ballistic missile crosses any radius a person can choose in seconds. Filtering it by
                    # that radius does not filter, it deletes the warning. These bypass it and alert the
                    # whole region — see geo.IMMEDIATE_TYPES for why the list is exactly this short.
                    if geo and geo.is_immediate(m["type"]):
                        if d <= geo.REGION_ALERT_KM:
                            urgent.append((d, m))
                    # 1.45: a post that named the oblast and no town has no position — its point is the oblast
                    # centre, nothing more. "Within 15 km of you" from that would be a distance nobody reported.
                    elif m.get("place") != "область" and d <= radius + HOME_CELL_KM / 2:
                        near.append((d, m))
                if not (near or urgent):
                    continue
                # A ballistic warning is never held back by the every-two-minutes throttle the rest obey.
                if not urgent and now - PROX_LAST.get(ep, 0) < 120:
                    continue
                if urgent:
                    urgent.sort(key=lambda x: x[0])
                    m = urgent[0][1]
                    for _, mm in urgent:
                        seen[mm["id"]] = now
                    PROX_LAST[ep] = now
                    kind = THREAT_EN.get(m["type"], "Ballistic threat")
                    place = m.get("place") or "?"
                    if place == "область":
                        place = f"{OBLAST_EN.get(m.get('oblast_uid'), 'the')} oblast (no town named)"
                    # No distance and no direction: at this speed neither is something the reader can act on,
                    # and the stored home is a grid cell that could not support a distance anyway.
                    pusher.queue_direct(
                        f"\U0001f6a8 {kind} in your region — shelter now",
                        f"Reported near {place} at {fmt_kyiv(m['ts'])} \u00b7 position from a public post, not radar",
                        "threat", ep)
                    # Nothing else goes out in the same breath. A Shahed 8 km away still matters, but not in
                    # the same second as this, and it will be re-reported on the next pass.
                    continue
                near.sort(key=lambda x: x[0])
                d, m = near[0]
                for _, mm in near:
                    seen[mm["id"]] = now
                PROX_LAST[ep] = now
                kind = {"drones": "Jet drone" if m.get("jet") else "Shahed"}.get(m["type"]) or THREAT_EN.get(m["type"], "Target")
                extra = f" ×{m['count']}" if (m.get("count") or 1) > 1 else ""
                more = f" (+{len(near) - 1} more)" if len(near) > 1 else ""
                place = m.get("place") or "?"
                hdg = f", heading {compass_en(m['heading'])}" if m.get("heading") is not None else ""
                # The stored home is a grid cell, so "23 km from you" would be precision this no longer
                # has. The reader gets the radius they chose and the place the POST named — both true.
                pusher.queue_direct(
                    f"\u26a0 {kind}{extra} within {round(radius)} km of you{more}",
                    f"Reported near {place}{hdg} at {fmt_kyiv(m['ts'])} \u00b7 position from a public post, not radar",
                    "near", ep)
        except Exception as e:
            log("proximity error:", e)


THREAT_EN = {"ballistic_missiles": "Ballistic missile", "cruise_missiles": "Cruise missile", "unspecified_missiles": "Missile",
             "supersonic_missiles": "Supersonic missile (Kh-22/32)",
             "guided_aerial_bombs": "Guided bomb (KAB)", "tactic_aircraft_activity": "Tactical aviation"}


def compass_en(deg):
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(round((deg % 360) / 45)) % 8]


def fmt_kyiv(ts):
    d = parse_iso(ts)
    if not d:
        return "?"
    return d.astimezone(timezone(timedelta(hours=3))).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Live streams
# ---------------------------------------------------------------------------
class StreamHub(threading.Thread):
    """Every open page's live connection, in one thread (1.29).

    It used to be one thread per open page, each blocked in a wait. On the 256 MB machine Linux allows about
    2,000 threads in all, so about 1,700 open pages was a hard stop: the next visitor's connection could not
    start. Now a page's connection is handed over here once its headers are sent, and this one thread writes to
    every page with non-blocking sockets (epoll). Each message is serialised once, not once per page.

    It also sends the data itself ("sync"): what changed in the marks, the alerts and the feed since the last
    message. A new post used to make every open page download the marks, the feed and the alerts again, five
    requests per page per post; now it is one short message. Every page states which version of each part it
    holds (its hash `h`); a message says which version it starts from (`b`), so a page that missed one simply
    fetches that part in full. A sync also goes out every 15 s (5 s with cruise missiles up, 2 s with a
    ballistic one) as the heartbeat that tells the page its line is alive — without it the page falls back to
    asking on its own, as before.

    A page that stops reading is dropped once `MAX_BACKLOG` bytes are waiting for it; its EventSource reconnects
    by itself. Nothing about a reader is kept: a connection is a socket, a language and which page it is."""

    MAX_BACKLOG = 512 * 1024
    FEED_N = 150

    def __init__(self, state):
        super().__init__(daemon=True, name="streams")
        self.state = state
        self.sel = selectors.DefaultSelector()
        self.clients = {}
        self.pending = []
        self.plock = threading.Lock()
        self._wr, self._ww = socket.socketpair()
        self._wr.setblocking(False)
        self._ww.setblocking(False)
        self.sel.register(self._wr, selectors.EVENT_READ, None)
        self.q = state.subscribe()
        self.pub = {}                 # part -> the entries last sent
        self.sync_due = 0.0
        self.last_sync = 0.0
        self.last_want = 0.0
        self.sent = 0
        self.peak = {"day": None, "n": 0, "at": None}
        state.on_publish = self.wake

    # -- called from other threads ------------------------------------------------------------------------------
    def wake(self):
        try:
            self._ww.send(b"\0")
        except OSError:
            pass                      # the pipe is full: the hub is already awake

    def add(self, sock, lang, parts, events, kind):
        with self.plock:
            self.pending.append((sock, lang, parts, events, kind))
        self.wake()

    def online(self):
        cs = list(self.clients.values())
        tac = sum(1 for c in cs if c["kind"] == "tac")
        return {"total": len(cs), "tactical": tac, "light": len(cs) - tac, "peak_today": dict(self.peak)}

    @staticmethod
    def interval(lvl):
        return 2 if lvl >= 2 else 5 if lvl else 15

    # -- the loop ---------------------------------------------------------------------------------------------------
    def run(self):
        while True:
            try:
                self._once()
            except Exception as e:                 # one bad moment must not end every page's live line
                log("streams:", e)
                time.sleep(0.5)

    def _once(self):
        now = time.time()
        nxt = self.last_sync + self.interval(self.state.missile_active())
        if self.sync_due:
            nxt = min(nxt, self.sync_due)
        for key, mask in self.sel.select(max(0.0, min(nxt - now, 5.0))):
            c = key.data
            if c is None:
                try:
                    while self._wr.recv(4096):
                        pass
                except OSError:
                    pass
                continue
            if mask & selectors.EVENT_READ:
                try:
                    if not c["sock"].recv(4096):
                        self._drop(c)             # the page went away
                        continue
                except (BlockingIOError, InterruptedError):
                    pass
                except OSError:
                    self._drop(c)
                    continue
            if mask & selectors.EVENT_WRITE:
                self._flush(c)
        new = self._adopt()
        with self.state.cond:
            items, self.q[:] = list(self.q), []
        if items:
            chunk = b"".join(_sse(ev["kind"], ev) for ev in items)
            for c in self.clients.values():
                if c["events"] and c not in new:
                    c["out"] += chunk
            if not self.sync_due:
                self.sync_due = time.time() + 0.15      # a burst of alerts becomes one sync
        now = time.time()
        if new or (self.sync_due and now >= self.sync_due) or now - self.last_sync >= self.interval(self.state.missile_active()):
            self._sync(new)
        if now - self.last_want > 20:
            self.last_want = now
            tr = getattr(self.state, "tr", None)
            if tr:
                for lang in {c["lang"] for c in self.clients.values()} & {"en", "fr"}:
                    tr.want(lang)
        for c in list(self.clients.values()):
            if c["out"]:
                self._flush(c)

    def _adopt(self):
        with self.plock:
            got, self.pending = self.pending, []
        new = []
        for sock, lang, parts, events, kind in got:
            c = {"sock": sock, "lang": lang, "parts": parts, "events": events, "kind": kind, "out": bytearray(),
                 "mask": selectors.EVENT_READ}
            try:
                sock.setblocking(False)
                self.sel.register(sock, selectors.EVENT_READ, c)
            except (OSError, ValueError):
                try:
                    sock.close()
                except OSError:
                    pass
                continue
            self.clients[id(c)] = c
            new.append(c)
        if new:
            day = kyiv_tz_day()
            if self.peak["day"] != day:
                self.peak = {"day": day, "n": 0, "at": None}
            if len(self.clients) > self.peak["n"]:
                self.peak.update(n=len(self.clients), at=now_iso())
        return new

    def _drop(self, c):
        self.clients.pop(id(c), None)
        try:
            self.sel.unregister(c["sock"])
        except (KeyError, ValueError, OSError):
            pass
        try:
            c["sock"].close()
        except OSError:
            pass

    def _flush(self, c):
        try:
            n = c["sock"].send(c["out"])
            del c["out"][:n]
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            self._drop(c)
            return
        if len(c["out"]) > self.MAX_BACKLOG:
            self._drop(c)                 # it stopped reading; its EventSource will reconnect and catch up
            return
        mask = selectors.EVENT_READ | (selectors.EVENT_WRITE if c["out"] else 0)
        if mask != c["mask"]:
            try:
                self.sel.modify(c["sock"], mask, c)
                c["mask"] = mask
            except (KeyError, ValueError, OSError):
                self._drop(c)

    def _current(self, part):
        st = self.state
        if part == "mk":
            st.markers_now()
            return st._entries.get("markers")
        if part == "st":
            st.state_now()
            return st._entries.get("state")
        st.feed_now(self.FEED_N)
        return st._entries.get(f"feed:{self.FEED_N}")

    def _sync(self, new=()):
        st = self.state
        now = time.time()
        # a sync to everyone is due after events and on the heartbeat; a page that just connected only needs its hello
        beat = bool(self.sync_due and now >= self.sync_due) or now - self.last_sync >= self.interval(st.missile_active())
        if beat:
            self.sync_due = 0.0
            self.last_sync = now
        everyone = list(self.clients.values())
        wanted = set().union(*[c["parts"] for c in everyone]) if everyone else set()
        changed = {}
        for part in ("mk", "st", "fd"):
            if part not in wanted:
                continue
            try:
                cur = self._current(part)
            except Exception as e:
                log("streams: building", part, e)
                continue
            if not cur:
                continue
            prev = self.pub.get(part)
            if prev and prev["h"] == cur["h"]:
                continue
            changed[part] = (_state_delta if part == "st" else _list_delta)(prev, cur)
            self.pub[part] = cur
        lvl = st.missile_active()
        base = {"v": f"{st.seq}-{st.store.feed_count()}", "msl": lvl, "hb": self.interval(lvl), "now": now_iso()}
        # one serialisation per combination of parts, not per page
        frames = {}
        for c in everyone:
            if c in new or not (beat or changed):
                continue
            key = tuple(p for p in ("mk", "st", "fd") if p in c["parts"] and p in changed)
            if key not in frames:
                d = dict(base)
                for p in key:
                    d[p] = changed[p]
                frames[key] = _sse("sync", d)
            c["out"] += frames[key]
        for c in new:
            hello = dict(base, h={p: self.pub[p]["h"] for p in c["parts"] if p in self.pub})
            c["out"] += _sse("hello", hello)
        self.sent += 1


def _sse(kind, obj):
    return f"event: {kind}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


def kyiv_tz_day():
    return datetime.now(kyiv_tz()).strftime("%Y-%m-%d")


class Server(ThreadingHTTPServer):
    """ThreadingHTTPServer that does not close a connection handed to the stream hub."""
    daemon_threads = True
    request_queue_size = 128      # Python's default of 5 left a burst of pages waiting on SYN retries

    def __init__(self, *a, **k):
        self.detached = set()
        self.detached_lock = threading.Lock()
        super().__init__(*a, **k)

    def shutdown_request(self, request):
        with self.detached_lock:
            if request in self.detached:
                self.detached.discard(request)
                return
        super().shutdown_request(request)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    state: State = None  # set at startup

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send_cached(self, hit):
        """A cached answer: the same bytes for everybody, gzipped once when the client takes it."""
        _, body, gz, _, _ = hit
        use_gz = gz is not None and "gzip" in (self.headers.get("Accept-Encoding") or "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Accept-Encoding")
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
        data = gz if use_gz else body
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _peer_ip(self):
        # only ever used to make a daily, salted, one-way hash — never stored, never logged
        fwd = self.headers.get("X-Forwarded-For") or ""
        return (fwd.split(",")[0].strip() if fwd else (self.client_address[0] if self.client_address else ""))

    # A marker somebody says is wrong. The whole point is that this costs one tap while looking at the map:
    # capture that is any harder than noticing simply does not happen during a raid.
    _corpus_cache = None

    def _corpus_pending(self, limit=30):
        """Cases nobody has ruled on yet, with what this build makes of them."""
        cls = type(self)
        if cls._corpus_cache is None:
            cases = []
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "data", "corpus.jsonl")
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            cases.append(json.loads(line))
            except Exception:
                cases = []
            cls._corpus_cache = cases
        done = self.state.store.corpus_reviews()
        out, total_pending = [], 0
        for c in cls._corpus_cache:
            if c.get("state") != "pending" or c["id"] in done:
                continue
            total_pending += 1
            if len(out) >= limit:
                continue
            reading = None
            if geo:
                try:
                    clean = _clean_post(c["text"])
                    reading = {"tags": sorted(tag_feed_text(clean, c["channel"])),
                               "markers": [{"status": m.get("status"), "type": m.get("type"),
                                            "place": m.get("place"), "count": m.get("count"),
                                            "jet": bool(m.get("jet")), "likely": m.get("likely"),
                                            "conf": ((m.get("evidence") or {}).get("position") or {}).get("confidence")}
                                           for m in (geo.parse_for_channel(c["channel"], clean) or [])]}
                except Exception as e:
                    reading = {"error": str(e)[:120], "tags": [], "markers": []}
            # Reviewing a reading means judging it against what the post SAYS. Ukrainian is not the first
            # language of everybody doing the reviewing, and a case with no way back to the source cannot be
            # checked at all — so every case carries its English text and a link to the post it came from.
            post_id, text_en = self.state.store.feed_find(c["channel"], c["text"])
            en_src = "feed" if text_en else None
            if not text_en:
                cached = self.state.store.kv_get("corpus_en:" + c["id"])
                if cached:
                    text_en, en_src = cached, "online"
            if not text_en and _tr:
                try:
                    # The glossary, not the network: this runs while somebody waits for the page, and 25 cases
                    # at a third of a second each is not a page load. A proper translation for the one case on
                    # screen is fetched separately by /api/corpus/translate.
                    text_en, en_src = _tr.translate_offline(c["text"]), "offline"
                except Exception:
                    text_en = None
            out.append({"id": c["id"], "channel": c["channel"], "ts": c.get("ts", ""),
                        "text": c["text"], "text_en": text_en, "en_src": en_src,
                        "post_id": post_id or c.get("post_id"), "reading": reading})
        return {"cases": out, "pending": total_pending, "reviewed": len(done)}

    def _flag(self, data):
        st = self.state
        mid = str(data.get("marker") or "")[:120]
        post_id = mid.split("#")[0] if "#" in mid else (str(data.get("post_id") or "")[:120] or None)
        reason = str(data.get("reason") or "other")[:32]
        if reason not in ("place", "type", "not_a_threat", "already_gone", "other"):
            reason = "other"
        text, channel = "", str(data.get("channel") or "")[:64]
        if post_id:
            try:
                with st.store.lock:
                    row = st.store.conn.execute("SELECT channel,text FROM feed WHERE post_id=?", (post_id,)).fetchone()
                if row:
                    channel, text = row[0], row[1]
            except Exception:
                pass
        usage = getattr(st, "usage", None)
        day_hash = ""
        if usage:
            try:
                import hashlib
                with usage.lock:
                    usage._roll()
                    day_hash = hashlib.blake2s(
                        usage.salt + (self._peer_ip() or "").encode()
                        + (self.headers.get("User-Agent") or "")[:120].encode(), digest_size=8).hexdigest()
            except Exception:
                day_hash = ""
        ok = st.store.flag_add({"ts": now_iso(), "post_id": post_id, "channel": channel, "marker_id": mid,
                                "place": str(data.get("place") or "")[:80], "kind": str(data.get("kind") or "")[:40],
                                "reason": reason, "note": data.get("note"), "day_hash": day_hash, "text": text})
        return self._json({"ok": bool(ok)})

    # TWO DIFFERENT KEYS, and confusing them takes the map away from everybody.
    #
    #   ACCESS_KEY  locks the WHOLE app behind a login form. It exists for a private deployment — a unit, a
    #               closed group. On a public instance it is an outage: every reader gets the form instead of
    #               the map, which during a raid is the worst thing this server can do.
    #   ADMIN_KEY   locks only /admin, /api/usage and /api/flags. The map stays open to everyone. This is what
    #               a public deployment wants, and it is what the dashboard needs.
    #
    # ADMIN_KEY falls back to ACCESS_KEY so an existing private deployment keeps working unchanged.
    def _admin_key(self):
        return (self.state.cfg.get("admin_key") or os.environ.get("ADMIN_KEY")
                or self.state.cfg.get("access_key") or os.environ.get("ACCESS_KEY") or "")

    def _admin_ok(self, q):
        key = self._admin_key()
        if not key:
            return False               # no key configured: the dashboard does not exist, it is never open
        if q.get("key", [None])[0] == key:
            return True
        cookie = self.headers.get("Cookie") or ""
        return any(c.strip() in (f"uadm={key}", f"uak={key}") for c in cookie.split(";"))

    def _authorized(self, u, q):
        key = self.state.cfg.get("access_key") or os.environ.get("ACCESS_KEY") or ""
        if not key:
            return True
        if q.get("key", [None])[0] == key:
            return "set"
        cookie = self.headers.get("Cookie") or ""
        return any(c.strip() == f"uak={key}" for c in cookie.split(";"))

    def do_GET(self):
        t0 = time.monotonic()
        try:
            return self._get()
        finally:
            v = getattr(self.state, "vitals", None)
            if v:
                v.note(self.path.split("?")[0], (time.monotonic() - t0) * 1000)

    def _get(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        st = self.state
        if u.path == "/healthz":
            # "ok" only when the database can actually be had: it said "ok" all through the 25 Sep freeze
            if not st.store.lock.acquire(timeout=3):
                return self._json({"ok": False, "stuck": "database"}, 503)
            st.store.lock.release()
            return self._json({"ok": True})
        if u.path.startswith(("/static/logo", "/static/heimdall-")) or u.path == "/favicon.ico":
            name = u.path.split("/")[-1] if u.path != "/favicon.ico" else "heimdall-64.png"
            return self._file(name, "image/png" if name.endswith(".png") else None)
        auth = self._authorized(u, q)
        if not auth:
            body = b"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><body style='font-family:system-ui;background:#0b0e13;color:#e6e9ef;padding:40px;text-align:center'><img src='/static/heimdall-192.png' style='width:96px;border-radius:18px'><h2>Heimdall</h2><form><input name=key placeholder='access key' style='padding:10px;font-size:16px;border-radius:8px;border:1px solid #333'> <button style='padding:10px 14px;border-radius:8px'>Enter</button></form></body>"
            self.send_response(401); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if auth == "set":
            self.send_response(302); self.send_header("Location", u.path or "/"); self.send_header("Set-Cookie", f"uak={q['key'][0]}; Path=/; Max-Age=31536000; SameSite=Lax"); self.end_headers(); return
        try:
            # 1.40: a page the browser loads ahead (Light ⇄ Tactical, Sec-Purpose: prefetch;prerender) is not a visit
            ahead = "prefetch" in (self.headers.get("Sec-Purpose") or self.headers.get("Purpose") or "").lower()
            if u.path in ("/", "/m", "/k", "/kyiv"):
                usage = getattr(st, "usage", None)
                if usage and not ahead:
                    ua = self.headers.get("User-Agent") or ""
                    usage.hit(self._peer_ip(), ua, "load",
                              lang=(q.get("lang", [None])[0] or ("uk" if "uk" in (self.headers.get("Accept-Language") or "").lower() else None)),
                              pwa="standalone" in (self.headers.get("Sec-Fetch-Site") or ""), lite=False)
                return self._file("kyiv.html", "text/html; charset=utf-8")
            if u.path in ("/desktop", "/index.html", "/dash"):
                return self._file("index.html", "text/html; charset=utf-8")
            if u.path in ("/ua", "/mobile", "/mobile.html"):
                return self._file("mobile.html", "text/html; charset=utf-8")
            if u.path == "/manifest.json":
                return self._file("manifest.json", "application/manifest+json")
            # The light page: one place, its official alert status, the threats within 60 km. Its own manifest,
            # its own scope, so it installs on the phone as a separate app from the full map.
            if u.path in ("/light", "/l"):
                usage = getattr(st, "usage", None)
                if usage and not ahead:
                    usage.hit(self._peer_ip(), self.headers.get("User-Agent") or "", "load", lang=None, pwa=False, lite=True)
                return self._file("light.html", "text/html; charset=utf-8")
            if u.path == "/light.webmanifest":
                return self._file("light.webmanifest", "application/manifest+json")
            # 1.35: what to do, weapon by weapon — the official guidance (ДСНС, police, Ministry of Health, an oblast
            # administration) on one page in three languages. Self-contained, and kept by the service worker so it
            # still opens with no network (static/sw.js). It asks the server for nothing.
            if u.path == "/guide":
                return self._file("guide.html", "text/html; charset=utf-8")
            if u.path == "/api/places":
                oq = q.get("oblast", ["14,31"])[0]
                # 1.43: "scope" — the oblasts the map covers now, as the dashboard set them
                obl = None if oq == "all" else set(SCOPE_UIDS) if oq == "scope" else set(oq.split(","))
                if q.get("villages", [None])[0] == "scope":
                    # 1.45: the regional villages of the oblasts the map covers, for the "villages and small towns"
                    # layer — fetched only when that layer is on; the core towns above are already drawn
                    sc = set(SCOPE_UIDS)
                    return self._send_cached(st.cached("villages:" + ",".join(sorted(sc)), 3600, lambda: {"places": [
                        {"name": n, "lon": lo, "lat": la, "oblast_uid": uid} for n, lo, la, uid in (geo.villages(sc) if geo else [])]}))
                # 1.46: built once an hour per set of oblasts and sent gzipped — it was rebuilt for every request
                key = "places:" + ("all" if obl is None else ",".join(sorted(obl)))
                return self._send_cached(st.cached(key, 3600, lambda: {"places": [
                    {"name": n.split(" (")[0], "lon": v[0], "lat": v[1], "oblast_uid": v[2]}
                    for n, v in (geo.PLACES.items() if geo else []) if obl is None or v[2] in obl]}))
            if u.path == "/api/markers":
                st.markers_now()
                return self._send_cached(st._resp["markers"])
            # The dashboard is yours alone: it needs ACCESS_KEY, and it refuses to serve anything when no key
            # is configured, so an open deployment can never expose it by accident.
            if u.path in ("/api/usage", "/admin"):
                if not self._admin_ok(q):
                    return self._json({"error": "set ADMIN_KEY and open /admin?key=… — ADMIN_KEY protects only "
                                                "the dashboard; ACCESS_KEY would lock the whole map"}, 403)
                if u.path == "/admin":
                    if q.get("key", [None])[0]:       # remember it so the page's own fetches are authorised
                        self.send_response(302); self.send_header("Location", "/admin")
                        self.send_header("Set-Cookie", f"uadm={q['key'][0]}; Path=/; Max-Age=31536000; SameSite=Lax")
                        self.end_headers(); return
                    return self._file("admin.html", "text/html; charset=utf-8")
                usage = getattr(st, "usage", None)
                return self._json(usage.report(int(q.get("days", ["30"])[0])) if usage else {"days": []})
            if u.path == "/api/drone_heat":
                # the Tactical map's heat layer: where drones were reported, place by place — public, counts per place
                # from public posts, cached 10 min
                try:
                    d = int(q.get("days", ["7"])[0])
                except ValueError:
                    d = 7
                d = d if d in (1, 7, 30) else 7
                return self._send_cached(st.cached(f"drone_heat:{d}", 600, lambda: st.drone_heat(d)))
            if u.path == "/api/analytics":
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                days = max(7, min(int(q.get("days", ["30"])[0]), 365))
                return self._send_cached(st.cached(f"analytics:{days}", 300, lambda: st.analytics(days)))
            if u.path == "/api/online":
                # the dashboard's live counter: how many pages have a live line open right now. A number, by page
                # type — nothing about who, and nothing kept but today's peak.
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                hub = getattr(st, "hub", None)
                pu = getattr(st, "pusher", None)
                vt = getattr(st, "vitals", None)
                return self._json({"online": hub.online() if hub else None, "notice": st.notice_now(), "nuke": st.nuke,
                                   "push_last": getattr(pu, "last_fanout", None), "now": now_iso(),
                                   "process": vt.report() if vt else None})
            if u.path == "/api/version":
                usage = getattr(st, "usage", None)
                if usage:
                    usage.hit(self._peer_ip(), self.headers.get("User-Agent") or "", "ping")
                with st.cond:
                    seq = st.seq
                lvl = st.missile_active()
                # `missile` stays a boolean for any client still on an older build; `msl` carries the level.
                return self._json({"v": f"{seq}-{st.store.feed_count()}", "now": now_iso(),
                                   "missile": bool(lvl), "msl": lvl, "build": BUILD, "app": APP_VERSION})
            if u.path == "/api/stats":
                days = max(1, min(int(q.get("days", ["14"])[0]), 30))
                return self._send_cached(st.cached(f"stats:{days}", 120, lambda: st.stats(days)))
            if u.path == "/api/replay":
                # 1.42: a past window for the time bar — at most 26 h, within the last 7 days (whole minutes, so the
                # pages asking for the same window share one answer)
                try:
                    t0, t1 = int(q.get("from", [""])[0]), int(q.get("to", [""])[0])
                except ValueError:
                    return self._json({"error": "from and to are Unix seconds"}, 400)
                now = int(time.time())
                t0, t1 = max(t0, now - (st.REPLAY_DAYS + 1) * 86400), min(t1, now + 60)
                t0, t1 = t0 - t0 % 60, t1 - t1 % 60
                if t1 <= t0 or t1 - t0 > st.REPLAY_MAX_H * 3600:
                    return self._json({"error": "a window of at most 26 hours within the last 7 days"}, 400)
                return self._send_cached(st.replay_cached(t0, t1))
            if u.path == "/api/impacts":
                hours = max(1, min(int(q.get("hours", ["24"])[0]), 168))
                return self._send_cached(st.cached(f"impacts:{hours}", 30, lambda: {"now": now_iso(), "hours": hours, "impacts": st.impacts(hours)}))
            if u.path == "/api/state":
                return self._send_cached(st.state_now())
            if u.path == "/api/feed":
                limit = max(1, min(int(q.get("limit", ["80"])[0]), 200))
                lang = q.get("lang", [""])[0]
                hit = st.feed_now(limit)
                tr = getattr(st, "tr", None)
                if tr and lang in ("en", "fr"):
                    tr.want(lang)
                    tr.add([p for p in hit[3]["feed"] if not (p["en_mt"] if lang == "en" else p["text_fr"])], lang)
                return self._send_cached(hit)
            if u.path == "/api/history":
                # every open page asks for it after an alert starts or ends: one query for all of them (1.29)
                hours = max(1, min(int(q.get("hours", ["24"])[0]), 168))
                obl = ",".join(sorted({x for x in (q.get("oblast", [""])[0] or "").split(",") if x.isdigit()}))
                return self._send_cached(st.cached(f"hist:{hours}:{obl}", 20, lambda: {"alerts": st.store.history(hours, obl.split(",") if obl else None)},
                                                   ver=st.seq))
            if u.path == "/api/events_log":
                return self._json({"events": st.store.events(int(q.get("limit", ["200"])[0]))})
            # Flagged readings are yours alone, on the same terms as the dashboard: they quote posts and
            # somebody's opinion of them, and neither belongs on an open endpoint.
            # The corpus, for reviewing from a browser instead of a terminal. The reading shown is computed
            # by THIS build, not the one recorded when the case was captured, because that is what the
            # reviewer is being asked to judge.
            if u.path == "/api/corpus":
                if not self._admin_ok(q):
                    return self._json({"error": "set ADMIN_KEY to review the corpus"}, 403)
                return self._json(self._corpus_pending(int(q.get("limit", ["30"])[0])))
            # The written summaries of each night and week — the dashboard's, and yours alone.
            if u.path == "/api/digests":
                if not self._admin_ok(q):
                    return self._json({"error": "set ADMIN_KEY to read the summaries"}, 403)
                return self._json({"ai": bool(st.cfg.get("ai_key")), "model": st.cfg.get("ai_model"),
                                   "digests": st.store.digests(int(q.get("limit", ["30"])[0]))})
            # The dashboard's health view: sources, channels, how early the map was. Yours alone as well.
            if u.path == "/api/health":
                if not self._admin_ok(q):
                    return self._json({"error": "set ADMIN_KEY to read the source health"}, 403)
                return self._json(st.health())
            if u.path == "/api/flags":
                if not self._admin_ok(q):
                    return self._json({"error": "set ADMIN_KEY to read flagged readings"}, 403)
                return self._json({"flags": st.store.flags(int(q.get("limit", ["200"])[0]),
                                                           include_done=q.get("done", ["0"])[0] == "1")})
            if u.path == "/api/stream":
                return self._stream()
            if u.path == "/sw.js":
                return self._file("sw.js", "text/javascript")
            if u.path == "/api/push/key":
                pu = getattr(st, "pusher", None)
                return self._json({"enabled": bool(pu and pu.enabled), "key": pu.pub if pu and pu.enabled else None, "subs": len(st.store.push_all()) if pu and pu.enabled else 0})
            if u.path.startswith("/static/"):
                return self._file(u.path[len("/static/"):], None)
            if u.path.startswith("/tiles/sat/"):
                return self._sat_tile(u.path)
            if u.path.startswith("/tiles/esri/"):
                return self._esri_tile(u.path)
            if u.path == "/favicon.ico":
                return self._file("heimdall-64.png", "image/png")
            self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            traceback.print_exc()
            try:
                self._json({"error": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query); st = self.state
        if not self._authorized(u, q):
            return self._json({"error": "unauthorized"}, 401)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
            if u.path == "/api/flag":
                return self._flag(data)
            if u.path == "/api/digest/run":
                # "write last night / last week up now": only asks the Digests thread — the model is never called here
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                kind = data.get("kind") if data.get("kind") in ("night", "week") else "night"
                dg = getattr(st, "digests", None)
                if not dg:
                    return self._json({"error": "summaries are not running"}, 503)
                dg.ask(kind)
                return self._json({"ok": True, "asked": kind})
            if u.path == "/api/admin/channel":
                # the dashboard's list of Telegram channels: add (on trial), map / trial / off, web / api, delete
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                action = str(data.get("action") or "")
                name = normalize_channel(str(data.get("name") or ""))
                if not name:
                    return self._json({"error": "not a Telegram channel name (letters, digits, _; 4–32)"}, 400)
                via = data.get("via") if data.get("via") in ("web", "api") else None
                if action == "add" and via != "api":
                    # can it be read at all? A channel with its web preview off shows no posts at t.me/s/
                    try:
                        _, _, body = http_get(f"https://t.me/s/{name}", {"Accept-Language": "uk,en"}, timeout=12)
                        if b"tgme_widget_message_wrap" not in body:
                            return self._json({"error": "no public posts at t.me/s/" + name + " — the channel does not exist, is private, "
                                                        "or has its web preview off" + ("; add it with “Telegram API”" if TelegramAPI.configured(st.cfg) else "")}, 400)
                    except Exception as e:
                        return self._json({"error": f"could not reach t.me: {str(e)[:120]}"}, 502)
                ok, msg = st.channel_update(action, name, data.get("mode"), via, data.get("home"))
                return self._json({"ok": ok, "message": msg, "name": name}, 200 if ok else 400)
            if u.path == "/api/admin/region":
                # 1.43: an oblast on or off as a whole — its channels and its place on the map
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                ok, msg = st.region_set(str(data.get("id") or ""), bool(data.get("on")))
                return self._json({"ok": ok, "message": msg}, 200 if ok else 400)
            if u.path == "/api/admin/nuke":
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                action = data.get("action")
                if action == "arm":
                    if st.nuke:
                        return self._json({"error": "already active"}, 400)
                    return self._json({"ok": True, "code": st.nuke_arm(), "expires_s": 120, "phrase": st.NUKE_PHRASE})
                if action == "fire":
                    text = {k: str((data.get("text") or {}).get(k) or "").strip()[:600] for k in ("uk", "en", "fr")}
                    text = {k: v for k, v in text.items() if v}
                    if not text:
                        return self._json({"error": "the message is empty"}, 400)
                    ok, msg = st.nuke_fire(data.get("code"), data.get("phrase"), text)
                    if ok and data.get("push"):
                        pu = getattr(st, "pusher", None)
                        if pu and pu.enabled:
                            pu.queue_all("☢ " + APP_NAME, (text.get("uk") or text.get("en") or text.get("fr"))[:240], "threat")
                    return self._json({"ok": ok, "message": msg, "nuke": st.nuke}, 200 if ok else 400)
                if action == "end":
                    st.nuke_end()
                    return self._json({"ok": True, "nuke": None})
                return self._json({"error": "unknown action"}, 400)
            if u.path == "/api/admin/notice":
                # the admin's message to every reader: a banner on both pages, optionally a push to every phone
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                if data.get("clear"):
                    st.set_notice(None)
                    return self._json({"ok": True, "notice": None})
                text = {k: str((data.get("text") or {}).get(k) or "").strip()[:500] for k in ("uk", "en", "fr")}
                text = {k: v for k, v in text.items() if v}
                if not text:
                    return self._json({"error": "empty message"}, 400)
                level = data.get("level") if data.get("level") in ("info", "warn", "alert") else "info"
                try:
                    hours = max(0.0, min(float(data.get("hours") or 0), 168.0))
                except (TypeError, ValueError):
                    hours = 0.0
                n = {"id": f"n{int(time.time() * 1000)}", "text": text, "level": level, "ts": now_iso(),
                     "until": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat() if hours else None}
                st.set_notice(n)
                pushed = 0
                pu = getattr(st, "pusher", None)
                if data.get("push") and pu and pu.enabled:
                    body = text.get("uk") or text.get("en") or text.get("fr")
                    pu.queue_all(APP_NAME, body[:240], "notice")
                    pushed = len(st.store.push_all())
                return self._json({"ok": True, "notice": n, "pushed": pushed})
            if u.path == "/api/corpus/review":
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                cid, state = str(data.get("id") or "")[:64], str(data.get("state") or "")
                if not cid or state not in ("verified", "known_bad", "pending"):
                    return self._json({"error": "bad review"}, 400)
                st.store.corpus_review(cid, state, data.get("note"))
                return self._json({"ok": True})
            if u.path == "/api/corpus/translate":
                # A real translation of the ONE case on screen. The list endpoint ships the offline glossary
                # so the panel is never empty, and this replaces it for the case actually being judged —
                # transliterated Ukrainian is not something anybody can review a reading against. One call per
                # case, cached forever, and the offline text stands if the service is unreachable.
                if not self._admin_ok(q):
                    return self._json({"error": "unauthorized"}, 401)
                cid = str(data.get("id") or "")[:64]
                text = str(data.get("text") or "")[:4000]
                if not cid or not text:
                    return self._json({"error": "bad request"}, 400)
                key = "corpus_en:" + cid
                cached = None if data.get("force") else st.store.kv_get(key)
                if cached:
                    return self._json({"text_en": cached, "en_src": "online"})
                if not _tr:
                    return self._json({"error": "no translator on this server"}, 503)
                try:
                    out = _tr.translate(text)
                except Exception as e:
                    return self._json({"error": str(e)[:120]}, 502)
                if out and getattr(_tr, "LAST_OK", [False])[0]:
                    st.store.kv_set(key, out)
                    return self._json({"text_en": out, "en_src": "online"})
                return self._json({"text_en": out, "en_src": "offline"})
            pu = getattr(st, "pusher", None)
            if not (pu and pu.enabled):
                return self._json({"error": "push not available on this server (pip install cryptography)"}, 503)
            if u.path == "/api/push/subscribe":
                sub = data.get("subscription") or {}
                if not sub.get("endpoint"):
                    return self._json({"error": "bad subscription"}, 400)
                st.store.push_add(sub, data.get("home") or {}, data.get("topics"), data.get("lang"))
                return self._json({"ok": True})
            if u.path == "/api/push/unsubscribe":
                st.store.push_remove((data.get("endpoint") or ""))
                return self._json({"ok": True})
            if u.path == "/api/push/test":
                pu.send_test(data.get("endpoint"))
                return self._json({"ok": True})
            self._json({"error": "not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _file(self, name, ctype):
        p = os.path.normpath(os.path.join(STATIC, name))
        if not p.startswith(STATIC) or not os.path.isfile(p):
            return self._json({"error": "not found"}, 404)
        with open(p, "rb") as f:
            body = f.read()
        ext = p.rsplit(".", 1)[-1]
        if ctype is None:
            ctype = {"js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8", "png": "image/png", "webp": "image/webp", "svg": "image/svg+xml", "json": "application/json", "html": "text/html; charset=utf-8", "md": "text/markdown"}.get(ext, "application/octet-stream")
        # On 2G every kilobyte is a second. Text goes out gzipped (the map outlines shrink to a third), and a
        # file the phone already holds is answered with a 304 instead of being sent again. "no-cache" still
        # makes the browser ask every time, so a new version is picked up exactly as with "no-store".
        etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        enc = None
        if ext in ("js", "css", "json", "html", "svg", "md") and len(body) > 1400 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body, enc = _gzipped(p, body), "gzip"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", etag)
        self.send_header("Vary", "Accept-Encoding")
        if enc:
            self.send_header("Content-Encoding", enc)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _SAT_RX = re.compile(r"/tiles/sat/(\d{1,2})/(\d{1,7})/(\d{1,7})\.webp")

    def _sat_tile(self, path):
        """1.47: one tile of the satellite layer. The tiles never change under the same address (the page asks for
        them with the layer's version), so the browser keeps them a year and never asks again."""
        m = self._SAT_RX.fullmatch(path)
        data = SAT.tile(*map(int, m.groups())) if m else None
        if data is None:
            self.send_response(404)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    _ESRI_RX = re.compile(r"/tiles/esri/(\d{1,2})/(\d{1,7})/(\d{1,7})\.jpg")

    def _esri_tile(self, path):
        """1.48: one tile of the closest zooms, asked of Esri with the owner's key (EsriTiles). Past a cap, or with no
        key, the page gets an empty answer and shows the Sentinel picture under it."""
        m = self._ESRI_RX.fullmatch(path)
        code, data, ctype, cc = (self.state.esri.fetch(*map(int, m.groups()), ip=self._peer_ip()) if m
                                 else (404, b"", None, "public, max-age=86400"))
        self.send_response(code)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cc)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        qs = parse_qs(urlparse(self.path).query)
        # a page reading English or French keeps its language "wanted" for as long as it is open
        lang = (qs.get("lang") or [""])[0]
        hub = getattr(self.state, "hub", None)
        detached = getattr(self.server, "detached", None)
        if hub is not None and hub.is_alive() and detached is not None:
            parts = set((qs.get("sync") or [""])[0].split(",")) & {"mk", "st", "fd"}
            events = (qs.get("ev") or ["1"])[0] != "0"
            kind = "light" if (qs.get("p") or [""])[0] == "light" else "tac"
            self.close_connection = True
            with self.server.detached_lock:
                detached.add(self.request)
            hub.add(self.request, lang, parts, events, kind)
            return
        # no hub (a test server): the old way, one thread for this page
        q = self.state.subscribe()
        tr = getattr(self.state, "tr", None)
        try:
            self.wfile.write(b"event: hello\ndata: {}\n\n")
            self.wfile.flush()
            last_beat = time.time()
            if tr:
                tr.want(lang)
            while True:
                with self.state.cond:
                    self.state.cond.wait(timeout=15)
                    items, q[:] = list(q), []
                for ev in items:
                    self.wfile.write(f"event: {ev['kind']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                if time.time() - last_beat > 20:
                    self.wfile.write(b": ping\n\n")
                    last_beat = time.time()
                    if tr:
                        tr.want(lang)
                self.wfile.flush()
        finally:
            self.state.unsubscribe(q)


# ---------------------------------------------------------------------------
def load_config(args):
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        log("created config.json — add your alerts.in.ua token there")
    if args.demo:
        cfg["demo"] = True
    if args.port:
        cfg["port"] = args.port
    if os.environ.get("PORT"):
        cfg["port"] = int(os.environ["PORT"])
        cfg["bind"] = "0.0.0.0"
    if os.environ.get("ALERTS_IN_UA_TOKEN"):
        cfg["alerts_in_ua_token"] = os.environ["ALERTS_IN_UA_TOKEN"]
    if os.environ.get("UKRAINEALARM_KEY"):
        cfg["ukrainealarm_key"] = os.environ["UKRAINEALARM_KEY"]
    for env, key in (("DEEPL_KEY", "deepl_key"), ("GOOGLE_TRANSLATE_KEY", "google_translate_key"),
                     ("ANTHROPIC_API_KEY", "ai_key"), ("AI_MODEL", "ai_model"), ("ESRI_KEY", "esri_key"),
                     ("TG_API_ID", "tg_api_id"), ("TG_API_HASH", "tg_api_hash"), ("TG_SESSION", "tg_session")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="UA Alerts local tracker")
    ap.add_argument("--demo", action="store_true", help="generate fake alerts (no keys needed)")
    ap.add_argument("--port", type=int)
    args = ap.parse_args()
    cfg = load_config(args)

    store = Store(DB_PATH)
    # re-tag the last hours with the current rules (a rule fix must also apply to posts already stored — a forecast
    # tagged 'ballistic' before the fix would otherwise keep the strip lit until it ages out)
    try:
        with store.lock:
            rows = store.conn.execute("SELECT post_id, channel, text, tags FROM feed WHERE ts>=?", ((datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),)).fetchall()
            n = 0
            for pid, ch, text, tg in rows:
                new = tag_feed_text(text, ch)
                if json.dumps(new) != tg:
                    store.conn.execute("UPDATE feed SET tags=? WHERE post_id=?", (json.dumps(new), pid)); n += 1
            store.conn.commit()
        if n:
            log(f"re-tagged {n} recent post(s)")
    except Exception as e:
        log(f"retag failed: {e}")
    global BUILD
    BUILD = build_id()
    log("build", BUILD)
    state = State(store, cfg)
    state.vitals = Vitals(state)
    state.vitals.start()
    state.usage = Usage(store)
    state.pusher = Pusher(store)
    log("push notifications:", "enabled (VAPID key ready)" if state.pusher.enabled else "disabled — pip install cryptography to enable")
    Handler.state = state
    try:
        n = store.coarsen_homes()
        if n:
            log(f"push: coarsened {n} stored home location(s) to ~{int(HOME_CELL_KM)} km cells")
    except Exception as e:
        log("could not coarsen stored homes:", e)
    if state.pusher.enabled:
        threading.Thread(target=proximity_watch, args=(state,), daemon=True, name="proximity").start()
    threading.Thread(target=bridge_watch, args=(state,), daemon=True, name="bridges").start()

    keyed = False
    if cfg.get("demo"):
        Demo(state, cfg).start()
        keyed = True
        log("DEMO mode — fake alerts")
    else:
        if cfg.get("alerts_in_ua_token"):
            AlertsInUa(state, cfg).start(); keyed = True
            log("source: alerts.in.ua (primary)")
        # the official data by raion: the API itself with a key, the keyless proxy of it without one
        detail = None
        if cfg.get("ukrainealarm_key") or cfg.get("use_siren_proxy", True):
            detail = UkraineAlarm(state, cfg)
            detail.start()
            log(f"source: {detail.NAME} — official alerts by raion" + ("" if keyed else " (primary)"))
        if cfg.get("use_ubilling_fallback", True):
            Ubilling(state, cfg, primary=not keyed, detail=detail).start()
            log("source: ubilling keyless mirror" + (" (cross-check)" if keyed else
                " (stands in, oblast level only, when the raion-level source is down)" if detail else " (primary — oblast level only)"))
    if cfg.get("telegram_channels"):
        tg = Telegram(state, cfg)
        tg.start()
        AFBackfill(state).start()
        Weather(state).start()
        log("feed:", ", ".join("t.me/" + c for c in cfg["telegram_channels"]))
        if TelegramAPI.configured(cfg):
            TelegramAPI(state, cfg, tg).start()
        elif state.channels_read("api"):
            log("telegram api: not configured — " + ", ".join("@" + c for c in state.channels_read("api"))
                + " can only be read after scripts/telegram-login.bat (TG_API_ID, TG_API_HASH, TG_SESSION)")

    bind = cfg.get("bind", "127.0.0.1")
    # machine translation of the feed: DeepL / Google Cloud with a key (config or env), off the alert path
    if _tr:
        _tr.configure(deepl=cfg.get("deepl_key"), google_cloud=cfg.get("google_translate_key"))
        log("translation: " + (", ".join(n for n, _ in _tr.backends()) or "offline glossary only") + " — machine translation on demand")
    state.tr = Translations(state)
    state.tr.start()
    Watchdog(state).start()
    state.digests = Digests(state, cfg)
    state.digests.start()

    # Every open page is a socket. Linux's default of 1,024 open files per process would stop the server long
    # before the stream hub does: raise it to what the system allows.
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        want = 65536 if hard == resource.RLIM_INFINITY else min(hard, 65536)
        if soft < want:
            resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
    except Exception:
        pass
    state.hub = StreamHub(state)
    state.hub.start()
    srv = Server((bind, int(cfg["port"])), Handler)
    log(f"dashboard → http://localhost:{cfg['port']}   mobile → http://localhost:{cfg['port']}/m")
    if bind == "0.0.0.0":
        ip = lan_ip()
        if ip:
            log(f"on your phone (same Wi-Fi) → http://{ip}:{cfg['port']}/m")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
