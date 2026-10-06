# Heimdall — technical documentation

**Documented version: 1.40** · last updated 2026-10-06

Heimdall was called **Clear Sky** until 1.29; the repository, the Fly app (`kyiv-air-watch-gb`) and some
internal names still carry the old name.

This is the complete technical reference: what runs, where the data comes from, how a Telegram post becomes a
mark on a map, how an official alert becomes a colour, what is stored, what is sent, and how to change any of
it safely. It is **updated with every patch** — see [§18](#18-the-patch-checklist). `tests/test_docs.py` fails
the build when this file, `APP_VERSION` and `CHANGELOG.md` disagree, or when a route, a config key, an
environment variable or a database table exists in the code but not here.

The rules the code follows are in [SAFETY.md](SAFETY.md). This document says *how*; SAFETY.md says *why not
otherwise*. Deployment walkthrough: [DEPLOY.md](DEPLOY.md). Strings and languages: [I18N.md](I18N.md). The
regression corpus: [CORPUS.md](CORPUS.md). French quick start: [DEMARRAGE-FR.md](DEMARRAGE-FR.md).

---

## Contents

1. [What it is](#1-what-it-is)
2. [Principles the code enforces](#2-principles-the-code-enforces)
3. [System overview](#3-system-overview)
4. [Repository layout](#4-repository-layout)
5. [Runtime, configuration and secrets](#5-runtime-configuration-and-secrets)
6. [Official alert data](#6-official-alert-data)
7. [The Telegram feed and the map marks](#7-the-telegram-feed-and-the-map-marks)
8. [Translation](#8-translation)
9. [Notifications](#9-notifications)
10. [The two pages: Tactical and Light](#10-the-two-pages-tactical-and-light)
11. [Privacy and security](#11-privacy-and-security)
12. [HTTP API](#12-http-api)
13. [Storage](#13-storage)
14. [Testing and quality](#14-testing-and-quality)
15. [Deployment and the GitHub repository](#15-deployment-and-the-github-repository)
16. [Maintenance recipes](#16-maintenance-recipes)
17. [Known limitations and open items](#17-known-limitations-and-open-items)
18. [The patch checklist](#18-the-patch-checklist)

---

## 1. What it is

An **unofficial** air-raid and drone tracker for **Kyiv city, Kyiv oblast and the oblasts around it**
(Zhytomyr, Chernihiv, Sumy, Poltava, Cherkasy, Vinnytsia). One Python process — standard library only, plus
`cryptography` for Web Push — reads:

- the **official «Повітряна тривога» alert data** (which raions are under alert, at which level), and
- **six public Telegram channels** that report where drones and missiles are,

and serves two web pages from the same data:

| Page | Address | For |
|---|---|---|
| **Tactical** | `/m` (also `/`, `/k`, `/kyiv`) | The full map: every mark with its evidence, the feed, alerts, statistics, display modes, layers. |
| **Light** | `/light` (also `/l`) | One place (Home / Work / Kids / Pin): its raion's official status, what is within 30 km, what is heading there. |
| **Guide** | `/guide` | What to do, weapon by weapon and situation by situation — the official guidance, in three languages, offline (1.35, §10.5). |

Both install as separate PWAs (manifest ids `/m` and `/light` — unchanged by the 1.29 rename, so Android offers
the new name and icon as an update of the installed app; an iPhone keeps an installed app's name and icon until
it is added again). Production runs on Fly.io as `kyiv-air-watch-gb` (one shared-cpu-1x machine, 256 MB, a 1 GB
volume for the database).

## 2. Principles the code enforces

Summarised here, argued in [SAFETY.md](SAFETY.md), and each pinned by tests:

- **The official alert decides the colour.** Red / yellow / nothing comes only from the official data, by
  raion. A Telegram post can neither start nor end an alert (`OFFICIAL_ALERTS_FROM_TELEGRAM = False`).
- **Nothing is invented.** No trajectory, ETA, threat type, altitude or position the post did not state. A
  course is drawn only if the post reported it; an ETA is a band, only toward the watched place, only for a
  stated course, never for ballistic / Kh-22 / MiG-31K.
- **Weapons that outrun a radius ignore the radius.** Ballistic, supersonic (Kh-22/32) and MiG-31K are
  "immediate": they concern the whole region (150 km), with no distance and no countdown.
- **Stale is never shown as live.** A target with no new report turns grey, then disappears.
- **A news item is not an observation of the sky.** Press releases, tallies and reported speech never become
  marks.
- **Banderol (S-8000) is a jet drone**, never a cruise missile — in parsing, tags, chaining and every language.
- **Places stay on the phone.** The four watched places are never sent to the server; a push subscription
  stores a ~10 km cell, never a village; the Light page works out the oblast and raion on the phone.
- **Every mark is traceable** to the post, the channel, the time and the rule that read it.

## 3. System overview

```
 official data                              app/server.py                                  browser
 ─────────────                              ─────────────                                  ───────
 siren.pp.ua (keyless proxy) ─┐
   or api.ukrainealarm.com    ├─▶ UkraineAlarm ──┐
 alerts.in.ua (token) ────────┤─▶ AlertsInUa ────┤  apply_snapshot()
 ubilling mirror (stand-in) ──┘─▶ Ubilling ──────┤        │
                                                 ▼        ▼
 5 Telegram channels ──▶ Telegram ──▶ Store ◀── State ──▶ /api/state ─────────▶ kyiv.html (/m)
   (t.me/s previews)       │  ingest()        (SQLite)     /api/markers ───────▶ light.html (/light)
 chyste_nebo ──▶ TelegramAPI ─┘ (Telegram API, preview off)
                           │  is_relevant                  /api/feed?lang=
                           │  translate_offline            /api/stream (SSE) ──▶ both
                           ▼                               /api/version (ping)
                     geo.parse_for_channel                        │
                           │                                      ▼
                     markers(): scope → chain → prune      Pusher / proximity_watch ──▶ Web Push ──▶ phone
                           │
                     Translations worker (DeepL / Google, on demand) ──▶ 'tr' event
```

Everything that arrives is **stored before it is interpreted**: a parsing bug is always replayable against the
real post, and a fix to the rules applies to posts already in the database.

## 4. Repository layout

```
clear-sky/
├── app/
│   ├── server.py           HTTP server, API, SSE, source pollers, SQLite store, marker pipeline, push
│   ├── geo.py              Ukrainian parsing: gazetteer, declensions, types, headings, counts, phases, altitude
│   ├── translate.py        offline UK→EN glossary; DeepL / Google machine translation with a circuit breaker
│   └── push.py             Web Push: VAPID ES256 JWT + RFC 8291 aes128gcm, on `cryptography` only
├── static/
│   ├── kyiv.html           Tactical page (one self-contained file)
│   ├── light.html          Light page (one self-contained file)
│   ├── i18n.js             every UI string in EN / UK / FR, place / raion / river / channel names
│   ├── glyphs.js           the weapon silhouettes (G, GLYPH_BY_TYPE), shared by both pages
│   ├── kyiv-map.json       27 oblasts + all raions, in km around Kyiv (geoBoundaries)
│   ├── light-map.json      raions of the 8 oblasts + nearby oblast outlines, rivers, roads, towns (built)
│   ├── kyiv-districts.json the 10 city districts of Kyiv (OSM)
│   ├── ukraine-map.json    oblast outlines in an affine lon/lat projection (Light page fallback lookup)
│   ├── admin.html          private dashboard: usage, source health, channels, lead time (/admin, ADMIN_KEY)
│   ├── index.html, mobile.html   older desktop / mobile views (/desktop, /ua)
│   ├── guide.html          what to do, weapon by weapon (/guide, 1.35): self-contained, content in its JSON block
│   ├── sw.js               service worker: push display, notification clicks, the guide kept for offline
│   ├── manifest.json, light.webmanifest   the two PWAs
│   ├── logo-cs*.png        the Clear Sky logo: app icons (any / maskable), favicon, badge, the notice
│   └── logo*.png (NGO 07300), bf-logo*.png (Black Flame Studio), ukraine-map.LICENSE.md
├── data/
│   ├── ua_regions.json     official region id → oblast / parent raion / map shape (built)
│   └── corpus.jsonl        regression corpus of real posts and their expected readings
├── scripts/
│   ├── build_geo.py        rebuilds data/ua_regions.json and static/light-map.json
│   ├── corpus.py           add / review / pull corpus cases
│   ├── release.bat         ships a patch: checks all is committed, fly deploy, git push, shows the live version
│   ├── telegram-login.bat  one-time Telegram sign-in for the API reader (runs telegram_login.py)
│   ├── github-push.bat     creates the private GitHub repo and pushes (browser sign-in via GitHub CLI)
│   └── start.sh, dev.sh, tunnel.bat
├── tests/                  pytest suites (see §14) and tests/fixtures/
├── docs/                   this file, SAFETY, DEPLOY, I18N, CORPUS, DEMARRAGE-FR
├── .github/workflows/      ci.yml (tests on 3.9 and 3.12), fly-deploy.yml (optional auto-deploy)
├── Dockerfile · fly.toml · render.yaml · deploy-fly.bat · start.bat
├── config.example.json     template for config.json (config.json itself is never committed)
└── CHANGELOG.md · README.md · CONTRIBUTING.md · SECURITY.md · LICENSE
```

## 5. Runtime, configuration and secrets

### 5.1 The process

`python app/server.py` (`--demo` for fake alerts, `--port N`). One `ThreadingHTTPServer` and these threads:

| Thread | What it does | Cadence |
|---|---|---|
| `UkraineAlarm` | official alerts by raion (keyless proxy or keyed API) | `/alerts/status` every 10 s, full list on change or every 30 s |
| `AlertsInUa` | official alerts from alerts.in.ua, when a token is set | 15 s |
| `Ubilling` | oblast-level mirror; applies only while the raion source is down | 30 s |
| `Telegram` | reads the channels' `t.me/s/` previews (all but those the API reads) | 30 s; 10 s while a missile threat is open or a threat is within 12 km of a Kyiv bridge (1.34) |
| `TelegramAPI` | reads `telegram_api_channels` (chyste_nebo) through the Telegram client API — polls the channel, **never subscribes to updates** | last 20 posts every 15 s (8 s in a missile threat) |
| `Watchdog` | the database and alert-state locks must be free within 15 s; a held lock logs every thread's stack, five in a row (~2 min) → exit, Fly restarts it; a starved process is only logged (load, not a deadlock) | 20 s |
| `Digests` | each night (18:00–08:00 Kyiv) after `digest_hour`, and each Monday for the week: the figures (`State.digest_facts`), and with `ANTHROPIC_API_KEY` a written summary in EN + UK; stored in `digests` | 5 min check |
| `Translations` | machine-translates feed posts into a language somebody reads | on demand, ~3 calls/s max |
| `Pusher` | sends Web Push: one notification at a time, each to all its phones at once through `push.Sender` (32 workers, one kept-open HTTPS connection per push service per worker, VAPID signed once an hour per service) | queue |
| `streams` | **every open page's live line** (`StreamHub`, §5.4): one thread, non-blocking sockets (epoll), the data sent as changes | events + every 15 / 5 / 2 s |
| `proximity` | per-subscriber distance checks → push | continuous |
| `AlertsInUa.backfill` | a month of history for the favourite regions | once at start |
| `AFBackfill` | the Air Force summaries of the last 14 days that `af_reports` lacks: first from the stored feed, then from `t.me/s/kpszsu?before=…` pages (at most 240, stops once nothing is missing); since 1.33 also the carriers (`parse_air_report`) in every stored post, once per parser version (`kv.air_parsed`) | 60 s after start, then daily |
| `bridges` | every 5 s: a Kyiv bridge whose state rose (nothing → near → at, §9b) is written to `bridge_events` and pushed to the phones that asked for the bridges (topic `bridges`, in their language), at most once per bridge every 10 min — a "near" turning "at" excepted | 5 s |
| `Weather` | the last nights' weather at the launch areas and Kyiv from Open-Meteo (`WEATHER_POINTS`; 92 nights the first time, then 10) into `weather` | 90 s after start, then every 6 h (1 h after a failure) |

**One computation for everybody** (`State.cached`): `/api/markers`, `/api/state`, `/api/feed`, `/api/stats`,
`/api/impacts` are built once per change (the publish sequence `seq`) and at most every few seconds, by one
thread while the others wait, serialised and gzipped once; every page gets the same bytes (`_send_cached`). The
proximity pushes use the same marks (`markers_now()`). Nothing in a request path calls the network: the marks'
English text is the offline glossary (machine translation is the `Translations` worker's alone). The listen
backlog is 128. Measured on a 200-post window: ~1,000 requests/s, p95 ≈ 50 ms, where 1.23 managed 3/s.

`poll_gap()` shortens the official-source and Telegram intervals while a missile threat is open. The live line
beats faster with it (`msl` 0 → every 15 s, 1 → 5 s, 2 → 2 s); a page whose line is down falls back to asking
`/api/version` at 15 / 5 / 1 s, as before 1.29.

At start the process raises its open-file limit to what the system allows (up to 65,536): every open page is a
socket, and Linux's default of 1,024 would stop the server long before the hub does.

### 5.4 The live line (1.29)

Before 1.29 each open page held one server thread in `/api/stream`, and every new post made every page
download the marks, the feed and the alerts again — five requests per page per post. On the 256 MB machine
Linux allows ~2,000 threads, so ~1,700 open pages was a hard stop, and the CPU cost grew with pages × posts.

Now `Handler._stream` sends the headers and hands the socket to **`StreamHub`** (the connection is not closed:
`Server.shutdown_request` skips it). The hub writes to every page from one thread, each message serialised
once. What it sends:

- the old events, unchanged, for a page that asked for them (`ev=1`, the default): `start`, `end`, `threat`,
  `update`, `feed`, `eradar`, `tr`, `notice` — the Tactical page raises its toasts and sounds from them;
- **`hello`** on connecting: `{v, msl, hb, now, h: {part: hash}}` — which version of each part is current;
- **`sync`** after a burst of events (150 ms to gather it) and at least every `hb` seconds (15 / 5 / 2 by
  missile level — the heartbeat): `{v, msl, hb, now}` plus, for each part that changed and that the page asked
  for (`sync=mk,st,fd`), what changed:
  - `mk` (the marks, by `id`) and `fd` (the feed's 150 posts, by `post_id`): `set` = changed entries, same
    order; `pre` + `n` = new entries at the head (a new post, a new mark); `ids` = a new order; `all` = the
    whole list when there is nothing to diff against;
  - `st` (the alerts state): `act` = the active alerts as a list (by `location_uid|alert_type`), `sub` /
    `unset` = keys of `oblasts` and `sources` that changed, `set` = other values whole.
  Every part carries `b` (the version it starts from) and `h` (the version it leads to). The full answers
  (`/api/markers`, `/api/state`, `/api/feed`) carry the same `h`. A page applies a change only when it holds
  exactly `b` (`static/live.js`, `LiveSync.part`), otherwise it fetches that part in full — nothing is
  guessed. `tests/test_live.py` checks that the deltas rebuild exactly what the server serves.

The pages: while the line beats (a message within 3 × `hb`), they ask nothing; the Tactical page checks
`/api/version` once a minute (build, safety) and does a full reload every 10 minutes. A silent line is
reopened, and the page asks at its old cadence until it beats again. The Light page takes `sync=mk,st` without
events (`p=light&ev=0`); the Tactical page in blackout mode takes `mk,st` and still fetches its 25-post feed.

A page that stops reading is dropped once 512 KB are waiting for it (its EventSource reconnects). Nothing
about a reader is kept: a connection is a socket, a language and which page it is; `/api/online` counts them.

Measured on the demo feed (one core, 2026-09-28): 9,000 open pages — **8 threads, 62 MB**, ~80 ms of CPU per
second, a change reaching the last page ~0.1 s after the first; ~25 KB per page per minute under the demo's
heavy churn. The same pages on 1.28 needed 9,000 threads and ~45,000 requests per post.

### 5.2 Configuration keys

`config.json` is created from `DEFAULT_CONFIG` on first run and is **git-ignored**. `config.example.json` is
the committed template.

| Key | Default | Meaning |
|---|---|---|
| `port` | `8642` | HTTP port (`PORT` wins). |
| `bind` | `0.0.0.0` | `127.0.0.1` keeps it on the machine. |
| `marker_ttl_minutes` | `45` | Hard ceiling on a mark's life. |
| `track_stale_minutes` | `5` | No new report for this long → grey. |
| `alerts_in_ua_token` | `""` | alerts.in.ua token; when set, alerts.in.ua is the primary alert source. |
| `ukrainealarm_key` | `""` | Official API key; when set, the API is read directly instead of the proxy. |
| `use_siren_proxy` | `true` | Read the keyless siren.pp.ua proxy of the official API when there is no key. |
| `telegram_api_channels` | `["chyste_nebo"]` | Channels read through the Telegram API (their web preview is off); needs the `TG_*` secrets. |
| `use_ubilling_fallback` | `true` | Run the oblast-level mirror (stand-in only). |
| `poll_ukrainealarm_seconds` | `10` | Official raion data interval. |
| `poll_alerts_seconds` | `15` | alerts.in.ua interval. |
| `poll_ubilling_seconds` | `30` | Mirror interval. |
| `poll_telegram_seconds` | `30` | Telegram interval. |
| `poll_telegram_missile_seconds` | `10` | Telegram interval while a missile threat is open. |
| `telegram_channels` | the six | Informational only — `AUTHORITATIVE_CHANNELS` in code is what is read. |
| `favourites` | `["31","14"]` | Regions for history backfill and desktop notifications. |
| `history_backfill_hours` | `6` | History pulled at start. |
| `desktop_notifications` | `true` | Local desktop notifications (when running on a PC). |
| `deepl_key` | `""` | DeepL API key for EN/FR translation of the feed. |
| `google_translate_key` | `""` | Google Cloud Translation key (alternative). |
| `ai_key` | `""` | Anthropic API key for the written summaries of each night / week (dashboard). |
| `ai_model` | `"claude-sonnet-5"` | The model that writes them. |
| `digest_hour` | `9` | Kyiv hour after which last night is written up (the Air Force morning summary is out by then). |
| `access_key` | `""` | Locks the WHOLE app behind a key — private deployments only. |
| `demo` | `false` | Fake alerts and posts. |

### 5.3 Environment variables

Environment variables win over `config.json`. On Fly they are set as **secrets** (`fly secrets set …`).

| Variable | Meaning |
|---|---|
| `PORT` | Listening port (Fly sets it). |
| `DB_PATH` | SQLite file (Fly: on the volume). |
| `CONFIG_PATH` | Alternative `config.json` location. |
| `ADMIN_KEY` | Protects `/admin` and its APIs only. The map stays public. |
| `ACCESS_KEY` | Puts the whole app behind a key. **Never on the public app.** |
| `ALERTS_IN_UA_TOKEN` | alerts.in.ua token. |
| `UKRAINEALARM_KEY` | Official ukrainealarm API key. |
| `DEEPL_KEY` | DeepL key (`…:fx` = free plan → api-free.deepl.com). |
| `GOOGLE_TRANSLATE_KEY` | Google Cloud Translation key. |
| `ANTHROPIC_API_KEY` | Turns on the written summaries of each night / week on the dashboard (`ai_key`). |
| `AI_MODEL` | Overrides `ai_model`. |
| `TRANSLATOR` | `google` (default) allows the free Google endpoint as last resort; anything else disables it. |
| `TG_API_ID` | Telegram API app id (my.telegram.org). |
| `TG_API_HASH` | Telegram API app hash. |
| `CANONICAL_HOST` | The app's own address (e.g. `heimdall.com.ua`). Pages opened elsewhere show the move banner (§9). Set by `scripts/set-domain.bat`. |
| `TG_SESSION` | The signed-in Telegram session (a key to that account). Set only by `scripts/telegram-login.bat`, via `fly secrets import`. |

Secrets live only in `config.json` (git-ignored) or in Fly secrets. They are never committed, never printed
by the scripts, and `.dockerignore` keeps `config.json` out of the image.

## 6. Official alert data

### 6.1 Sources and precedence

| Source | Granularity | Key | Role |
|---|---|---|---|
| **api.ukrainealarm.com** — the backend of the government app | oblast, raion, hromada; red/yellow level; official reason text | `UKRAINEALARM_KEY` | Primary when a key is set. |
| **siren.pp.ua** — keyless read-only proxy of the same API | same | none | **Primary without a key (production today).** |
| **alerts.in.ua** | oblast, raion, hromada, city; level; threats | `ALERTS_IN_UA_TOKEN` | Primary when a token is set (the raion source then only reports health). |
| **ubilling mirror** | **one on/off per oblast**, usually no start time | none | Stand-in only, while the raion source has not answered for 90 s. |

The mirror lights an oblast as soon as any raion in it is under alert. That is why it can only stand in: it
painted the whole of Kyiv oblast red while Boryspil raion had been clear for ten minutes (24 Sep 2026). When it
stands in, the Light page says "official data for the whole oblast only — your raion is unknown", and an alert
with no known start shows no "since" (`since_known: false`).

The ukrainealarm reader polls `/alerts/status` every 10 s and reads the full `/alerts` list when the change index
moves — and **at least every 30 s** regardless, so a level change on an alert already on (yellow → red) is never
more than half a minute behind (it was up to 2 min before 1.19).

### 6.2 The official levels

Since 11 Sep 2026 each alert carries the government app's danger level:

| Level | Official meaning | Shown as |
|---|---|---|
| `red` | massed drone, missile, or drone-and-missile threat | red; "AIR RAID ALERT" |
| `yellow` | drone threat | yellow; "ALERT · YELLOW LEVEL" |
| none (mirror) | unknown | treated as **red** — never as "maybe" |

The official reason ("Дронова загроза (жовтий рівень)") is kept word for word in the alert's `notes` and shown
as-is in Ukrainian; EN/FR show the level's definition.

### 6.3 The normalised alert

Every source is normalised to one shape (dicts in `State.active`, rows in `alerts`):

`key, source, location_uid, location_title, location_title_en, location_type (oblast | raion | hromada | city),
oblast_uid, alert_type (air_raid | artillery_shelling | urban_fights | chemical | nuclear | info), alert_level
(red | yellow | null), started_at, finished_at, notes, threats[]` — plus, from the official raion source,
`raion_uid`, `raion_key` (the map shape), `raion_title`; and from the mirror, `since_known`.

`started_at` for the official source is the earliest of the alert's `lastUpdate` and its levels' `createdAt`,
normalised to `YYYY-MM-DDTHH:MM:SSZ`.

### 6.4 From an official id to a place on the map

The API names a raion or hromada by a bare numeric id. `data/ua_regions.json`, built by `scripts/build_geo.py`
from the official region list, maps:

- `states`: official oblast id → this app's oblast uid (Crimea `9999` → `29`);
- `districts`: raion id → name, oblast, **shape key** on the map (`boryspil`, `korostenskyi` …);
- `communities`: hromada id → name, parent raion (cities listed at the top level, like "м. Харків та … громада",
  are hromadas of their oblast, not the oblast);
- `ignore`: the API's test region.

An id not in the table is **kept, never dropped**, placed as well as its name allows, and logged once
("rebuild ua_regions.json"). Oblast uids follow alerts.in.ua: 31 Kyiv city, 14 Kyiv oblast, 10 Zhytomyr,
25 Chernihiv, 20 Sumy, 19 Poltava, 24 Cherkasy, 4 Vinnytsia.

### 6.5 Reconciliation

`State.apply_snapshot(source, alerts, authoritative_levels)` diffs a source's full list against the active set
and emits `start`, `update`, `threat` and `end` events (stored in `events`, published on SSE). A source only
**closes** its own alerts or alerts at levels it is authoritative for — so the mirror (authoritative for
`oblast`) can never close a raion alert, and the raion source (authoritative for every level) takes back what
the mirror painted when it returns. `snapshot()` merges duplicates and computes each oblast's status: **A**
(an oblast-wide alert), **P** (only raions / hromadas), **N**.

### 6.6 What decides a colour, page by page

- **Tactical**: each raion shape is coloured by alerts with its `raion_key` (fallback: name stems); an
  oblast-wide alert colours all its raions. The banner uses the watched oblast pair (city ⇄ oblast) plus the
  home's own raion (found by point-in-shape on the map's outlines). The calm line never says "no alert in the
  oblast" while any raion of it is under one.
- **Light**: see [§10.2](#102-light-light).

## 7. The Telegram feed and the map marks

### 7.1 The channels

The six defaults are in code (`AUTHORITATIVE_CHANNELS` — deployed configs list 33 channels, and a config
whitelist would have changed nothing on any machine; `telegram_channels` in a config is still ignored). Since
1.31 the **dashboard** manages the list on top of them (`State.channel_list`, stored in `kv.channels`, so it
survives restarts and deploys):

- each channel is **Map** (its posts place marks and can raise banners and alerts), **Trial** (its posts are
  shown in the feed with their place tags only and a "trial" chip — no threat tag, no mark, no banner, no toast,
  no push, not in any count or summary) or **Off** (not read, and its posts leave the feed);
- read via the **web preview** (`t.me/s/…`) or the **Telegram API** (when the `TG_*` secrets are set);
- **added** channels start on **Trial** — a channel nobody has vetted must not be able to put a drone over
  somebody's house; the admin promotes it after judging what it posts and the share of it the app reads;
- the defaults can be switched off, never deleted; a deleted channel stays off for 6 h so its recent posts stop
  counting at once; at most 30 channels.

How: `Store.feed_since` (every computation — marks, the missile level, statistics, summaries) keeps only Map
channels; `Store.feed` (what the pages show) drops Off ones and strips a Trial one's threat tags; the `feed`
event of a Trial post carries `tags: ["trial"]` only. Both readers take the list afresh each round
(`State.channels_read`). A web channel is checked for readable posts when it is added. The defaults:

| Channel | Kind | Parser |
|---|---|---|
| `kyiv_airdef` | fast live tracker over Kyiv | `parse_kyiv_airdef` (one mark per line, ✈️ = drone, "A - B" routes) |
| `chyste_nebo` | fast live tracker; **states drone heights** | same — its web preview is off, so it is read through the **Telegram API** (`TelegramAPI`, §7.2) once the `TG_*` secrets are set; without them it shows as a failed source |
| `kievinfo_kyiv` | live tracker + news | same, with the news guard |
| `war_monitor` | wider picture, jet drones | general `parse_post` |
| `eRadarrua` | per-oblast group counts + live lines | `parse_eradar`, `parse_eradar_summary` (counts on oblast tags, never marks) |
| `kpszsu` | the Air Force | general parser + its summaries, read weapon by weapon (`parse_af_report`, §7.5) |

A channel whose preview shows no messages is marked failed with "web preview disabled by the channel", so "no
drones reported" and "cannot read this channel" never look the same.

### 7.2 From page to stored post

Two readers, one path. `Telegram.poll()` parses a channel's preview HTML; `TelegramAPI` re-reads a channel's
last 20 posts every 15 s (8 s in a missile threat), with `receive_updates=False`: a personal account's update
stream (every chat it is in) took the 256 MB server down within minutes on 25 Sep 2026. `ingest()` runs in a
worker thread (`asyncio.to_thread`), off the client's event loop. Both hand `(post_id, time, text)` to
`Telegram.ingest()`, so a post read through the API is stored, tagged, parsed and shown exactly like one read
from a preview. The preview reader skips a channel the API is reading (`api_channels`).

`Telegram.ingest()` skips posts already stored, runs `tag_feed_text()` and
`is_relevant()` (news, fundraising, culture → dropped), stores the post with the **offline** English (§8) and
publishes a `feed` event. Tagging order matters: forecasts first (`FORECAST_RX` — "оцінка загроз", "може
відбутись у будь-який момент" — never raise anything), then the news guard (`geo.looks_like_news`: strong news
words, reported speech and consequences, length, summaries), then threat tags. `banderol_missiles` removes
`cruise_missiles` and `unspecified_missiles`.

### 7.3 From post to mark (`geo.py`)

`parse_for_channel(channel, text)` picks the channel's parser; each returns candidates with an **evidence**
block for every value:

- **Type** — `TYPE_RX`: drones (Shahed / Geran / "мопед"), jet drones, cruise, ballistic, supersonic
  (Kh-22/32, before cruise), `banderol_missiles` (Banderol / S-8000 / "реактивні ракети з БпЛА"), KAB, tactical
  and strategic aviation, MiG-31K. No type word → `unknown` (drawn as an upright ⚠, never guessed).
- **Position** — the gazetteer with declension-aware stems (hyphen lookbehind: `Коцюбинське` ≠
  `Михайло-Коцюбинське`); aliases like "Велика Димерка" ← "димерк"; a stated part of an oblast is not its centre.
- **Heading** — "курсом на", compass words, "→", "A - B" routes (`bearing()`); a heading is marked *stated*
  only when the post stated it. A compass word after "з / зі / від" is where it comes **from** ("з півночі" = flying
  south), also after the destination (`_FROM_COMPASS`).
- **Where it is vs where it is going** (`_place_role`): a place after "на", "в район", "до", "в напрямку", "в бік"
  is the **destination**; after "від", "з", "повз", "над", "біля", "в районі" it is where the target **is**. After
  "на", a place in the locative ("на Позняках", "на Троєщині") is where it is. Only a destination named
  ("на Васильків з північного заходу", "курсом на Київ"): the mark is drawn **at the destination as an approach**
  (`approach: true`, `place: "→ X"`, low confidence) — also when the post's only other place is its own oblast
  heading. On live channels, "Від Глевахи на Васильків" is at Hlevakha heading for Vasylkiv; "йдуть на Васильків"
  alone (`dest_only`) stays at the channel's previous report (≤ 8 min) turned toward the destination, or else is an
  approach. In tracking, a later approach about a target already on the map gives it its destination and course
  instead of moving it; an approach point is never a step of a track.
- **Count**, **altitude** (only when written: "знижується", "низько", metres "висота 2200", a bare "1600, Вороньків"
  in a short live post, kilometres "висота 4,4км"), **phase** (`PHASE_LADDER`:
  prep → launch → entering…, with a per-sentence hedge guard: "може відбутись" is preparation, not a launch).
- **Immediate types** — `IMMEDIATE_TYPES = {ballistic, supersonic, mig31k}`, `REGION_ALERT_KM = 150`.

### 7.4 Scope, chaining, staleness

`State.markers()`:

1. parses the recent feed into candidates; merges identical ones from the same post (a count). A live-tracking
   channel's bare line ("На Таращу", "Вибух", "Не спостерігається") is placed at that channel's last reported
   position (`last_by_channel`, at most 8 min old). 1.38: that position keeps **its own** time — the mark carries
   `pos_ts`, and a carried position never restarts the clock (only a newly named place does); the channel's own
   down / lost / clear line ends it; and the official all-clear for Kyiv city ends every position held inside the
   city (`State.kyiv_city_all_clears`: an end of the city's air-raid alert that left no other source's alert running);
2. drops what is outside the scope: `in_scope()` = oblast uid in `REGION_UIDS` or within `SCOPE_KM = 330` km
   of Kyiv;
3. `_chain_and_prune()` links consecutive reports of the same target (same family, time and distance windows,
   roughly ahead of the earlier heading) into a track with `history` — each entry keeps its own report's stated
   height (`alt_m`, `alt_state`), so the pages can show the heights the posts gave in sequence; marks `stale` after
   `track_stale_minutes`; drops an unknown after 5 min, others after `max(stale × 3, 15)` min — all counted from
   the position's time (`pos_ts`, else the post's); drops everything in an oblast with **no active alert of any
   kind** once 3 min old, and, in Kyiv city with no alert running, every mark reported before the last official
   all-clear there; missiles age on their own `MISSILE_TTL_MIN`;
4. outcomes (down, impact, lost) close the track they belong to.

Fires, ground damage and the channels' own "чисто" are not drawn (`HIDDEN_STATUS` on the pages).

### 7.6 The carriers: take-offs, launches, stand-downs (1.33)

`parse_air_report(text)` reads what a post reports about the aircraft and ships that carry the missiles — `mig31k`
(MiG-31K, Kinzhal), `strategic` (Tu-95MS / Tu-160), `tu22` (Tu-22M3, Kh-22/32), `kalibr` (the ships) — as
`(kind, phase)` pairs, phase `up` (airborne: "зліт", "у повітрі", "відбувся виліт", "борт Ту-22м3 в районі …"),
`launch` ("пуски КР «Калібр»", "перші пуски … повітряного базування Х-101", "Кинджал вектор …", "Пуски Х-22", the
Air Force's "імовірно здійснено пуски" included — it reads them from the aircraft) or `end` ("Відбій загрози
МіГ-31К", "Посадка МіГ-31К", "Чисто по Х-22"). Sentence by sentence, so that the sentence that says what MAY come
("Якщо будуть пуски…", "Загроза пусків Х-22", "Може відбутись пуск", "готових до вильоту") never counts; a post
about moving aircraft between airfields, a tally written after the attack, and the Air Force's summaries are
not reports. Pinned on 63 real posts read by hand (`tests/fixtures/air_posts_2026.json`).

Every post read (before the relevance filter) goes into `air_reports` (`Store.air_save`, with a fingerprint of the
text). `air_sorties()` groups them: several channels reporting one take-off are one sortie; a sortie stays open
`AIR_OPEN` minutes after its last report (MiG-31K 90, Tu-95/160 12 h, Tu-22M3 6 h); a take-off more than 10 min
after a stand-down is a new sortie; the same words from the same channel within 45 min count once. Each sortie has
its first take-off report, first launch report and stand-down, the minutes from take-off to launch and to
stand-down. Statistics only: none of it places a mark or raises anything.

Two live bugs were found on the way and fixed in 1.33:
- **A reply was read as the message it answers.** On `t.me/s/` a reply carries the quoted message first, in a div
  of the same class. The reader took it: the Air Force's "📢 Відбій небезпеки по МіГ-31К", posted as a reply to its
  take-off message, was stored as "Зафіксовано зліт МіГ-31К" — a second take-off at the minute the danger was
  called off. `tg_post_text()` takes the post's own text (`js-message_text`, never `js-message_reply_text`) for
  every `t.me/s/` reader.
- **A Tu-160 airbase was drawn near Kyiv.** "Також у повітрі 4х борти Ту-160 з «Українки»" (the airbase in the Amur
  region) placed strategic aviation at Ukrainka, Obukhiv raion. The carriers never fly over Ukraine: `geo.NEVER_PLACED`
  (strategic aviation, MiG-31K) — their posts raise their banners and place no mark. And "Кинджал", the way the Air
  Force and war_monitor spell it, is now read as ballistic (it was an unspecified missile, without the ballistic
  banner).

### 7.5 The Air Force's summaries (1.32)

Twice a day `kpszsu` sums up the attack on all of Ukraine: "У ніч на 28 вересня (з 18:00 27 вересня) противник
атакував 165 ударними БпЛА … (79 із них — реактивні) … збито/подавлено 112 …". Until 1.31 these were read for two
totals (drones, missiles) and, from 25 Sep, tagged `news` and dropped — so the Stats tab lost whole nights, and
missiles were never counted at all: the Air Force names most of them **without a number** ("балістичними
ракетами Іскандер-М") and gives the number only for those shot down.

`parse_af_report(text, ts)` returns, or `None` for anything that is not a summary ("продовжує атакувати" is an
update):

- `period` (`night` / `day`) and `date` (the morning of the night; the day's own date);
- `launched` per type — `drones` (Shahed type and other strike drones), `jet` (the "із них — реактивні" part of
  `drones`, never added to it), `banderol` (a jet drone, never a missile), `cruise`, `ballistic`,
  `aeroballistic` (Kinzhal), `antiship`, `guided`, `decoys`, and `missiles` when the post gives a missiles total
  with a breakdown in brackets. A type is counted once, by its most specific name (`AF_TYPES` order);
- `used`: the types named **without a number** — shown as "used", never counted as 0;
- `down` per type and `total` (the "збито/подавлено" part, or the headline "ЗБИТО/ПОДАВЛЕНО N");
- `impacts` and `debris` (the number of **locations**), `areas` (where launched from, "рф" dropped),
  `directions` (the "основний напрямок" oblasts), `models` (Іскандер-М, Калібр, Кинджал, Циркон, Х-101 …).

`tag_feed_text` tags such a post `af_summary` (kept in the feed; not a live threat: it raises no banner). Every
summary from `AF_SUMMARY_CHANNELS` is stored in `af_reports` as it is read (`Store.af_save`, `INSERT OR IGNORE`
on the post id); `Store.af_reports()` keeps one per (date, period) — the Air Force's own post over a re-post, then
the fullest, then the latest. `AFBackfill` fills the gaps (§5.1). The Stats tab (§10.1), the dashboard's
Analytics (§8c) and the nights' figures (§8b) all read this table. `parse_af_summary` (the two totals) remains as
a wrapper for older callers. `tests/test_af_reports.py` pins it on 11 real summaries of 21–28 Sep 2026
(`tests/fixtures/af_summaries_2026_09.json`).

## 8. Translation

The feed is Ukrainian; EN and FR readers get a translation.

- **At ingest: the offline glossary only** (`translate_offline`) — instant. It never waits for a network call:
  the free Google endpoint refuses data-centre addresses, and each refusal used to cost ~3 s per post in front of
  the drone reports of the same poll. The glossary (`G`, `WORDS`) covers the channels' vocabulary, collected
  from ~1,000 real posts; anything left is transliterated.
- **Then, on demand: machine translation** (`Translations` worker): DeepL (`DEEPL_KEY`), else Google Cloud
  (`GOOGLE_TRANSLATE_KEY`), else the free Google endpoint. Domain words are fixed before (`PRE`, `PRE_FR`: "мопед"
  → Shahed, "реактив" → jet drone, "ударні" → strike drones) and after (`POST`, `POST_FR`).
- **Only for a language somebody reads.** A page in EN/FR sends `?lang=` on `/api/feed` and `/api/stream`; for
  the hour after, new posts are translated into it, and older ones in view are queued. The result is stored
  (`feed.text_en` + `en_mt = 1`, or `feed.text_fr`) and announced with a `tr` event; the page reloads the feed.
- **Circuit breaker**: a backend that refuses (401/403/429/456) rests 30 min, any other failure 5 min.
- French has no offline stand-in: without a machine translator, FR shows the English.

## 8b. Nights and weeks (the dashboard's record)

A record that builds up from now on (no import of older data). After each night (18:00–08:00 Kyiv time; written up
after `digest_hour`, 09:00, once the Air Force morning summary is out) and each Monday for the week before,
`State.digest_facts()` computes, from what the app itself recorded, for **Kyiv city and Kyiv oblast**: minutes under
official alert (overlaps counted once), number of alerts and the longest, alert waves (starts within 30 min are
one wave), alert levels, minutes per oblast raion; the channels' **reports** (not a count of targets) by type, the
most-named places, the reported courses (8 sectors), the busiest hours, first / last report; shoot-downs and
explosions reported and where; how many waves had a mark on the map in the hour before them and the median lead;
the Air Force's own figures (all of Ukraine, from `af_reports`: each summary of the period with launched and shot
down by type, the types used without a number, hit locations, main directions). A week also gets the previous
week's totals to compare with.

With `ANTHROPIC_API_KEY` set, the figures are sent to the model (`ai_model`) — counts and place names only, never a
post or anything about a reader — with a system prompt (`AI_SYSTEM`) that allows it to describe them and nothing
else: no forecast, no guessed intention, target, weapon or damage, "reports" called reports. It answers in English
and Ukrainian. The figures are stored with the text (`digests`), shown under it on the dashboard, so every sentence
can be checked. Without a key the figures are still stored and shown. The model is only ever called from the
`Digests` thread — never in a request path. Cost: a few thousand tokens a night, well under a dollar a month.

## 8c. The dashboard (1.32: tabs and Analytics)

`/admin` has five tabs (the last one opened is remembered, `localStorage.admintab`): **Live** (online now, the
admin's message with a preview in the readers' colours, the nuclear event — §9), **Analytics**, **Nights & weeks**
(§8b), **Sources** (lead time, official sources, the channels and their controls, translation; a red dot on the
tab when a source or a channel on the map fails) and **Usage** (the anonymous counters). Each tab loads its own
data; only Live and Sources refresh on their own (10 s and 60 s).

**Analytics** (`GET /api/analytics?days=7|30|90|365`, `State.analytics`, cached 5 min) — the trends, for the
owner and his partners, "Excel-like":

- all of Ukraine, from `af_reports` (a date = the night that ends that morning + that day): drones launched
  (Shahed type / jet / Banderol) with the number shot down; missiles shot down by type (the launched numbers the
  Air Force gave, and the types used without a number, on hover); the share of drones shot down or suppressed and
  the share of jet drones (drones only — the missiles launched are not always given, and a rate over everything
  would read higher than it was); hit and debris locations; launch areas, main directions and models named;
- Kyiv, from the app's own records: hours under official air-raid alert per day for the city (oblast 31) and the
  oblast (any raion of 14); when alerts start in the city (weekday × hour); the marks placed over the city and the
  oblast per 24 h from 18:00 by type (Banderol with the jet drones), by hour, and the drone courses **stated** in
  posts (8 sectors; none guessed);
- the KPIs compare the last 7 days with the 7 before; a date without a summary says so instead of showing zeros;
- (1.33) **the carriers** (§7.6): sorties per date by kind, and per kind the number on record, how many a launch
  report followed, the median (and middle half) from take-off to launch, the MiG-31K's median time to the stand-down,
  the last 25 in a table;
- (1.33) **the weather**: one dot per night — the mean wind, cloud cover and rain over the launch areas (Orel,
  Kursk, Bryansk, Shatalovo, Millerovo, Primorsko-Akhtarsk; 18:00–06:00) against the drones the Air Force says were
  launched that night; Pearson's r, the number of nights and a least-squares line from 8 nights, with the reminder
  that a link is not a cause;
- (1.33) **the approach sides**: drone positions the posts named in Kyiv oblast 20–130 km from the centre, by side of
  Kyiv (8 sectors), per 24 h from 18:00 (a post once per side; town-level positions only), and the total per side;
- (1.33) **hours under alert by oblast**, all Ukraine: official air-raid alerts in any part of each oblast, per week
  (per day up to 14 days), coloured by the share of the time in the heat layer's bins; an alert row a restart left
  open counts only while it is really active.

Each of the new cards has its CSV (carriers, weather with the night's drones, approach sides, oblast hours).
Charts are SVG drawn in the page (no library), in the validated dark categorical order (blue, orange, aqua,
yellow, magenta — never by rank), one axis each, a legend for two series or more, a tooltip on every mark; the
width follows the screen so a phone can read them. Every chart's table downloads as **CSV for Excel** (UTF-8
with its mark, `;` between columns): the Air Force by date and type, Kyiv's alert minutes, Kyiv's reports by
type. Nothing about a reader is in it.

## 9. Notifications

- **Web Push** (`push.py`; the VAPID key pair is generated on first run and kept in the `kv` table). A subscription
  stores the browser's coarse location snapped to a **~10 km cell** (`HOME_CELL_KM`), never a name.
- **How it is sent** (1.29): all the phones at once — `push.Sender`, 32 sends in flight, each worker keeping one
  open HTTPS connection per push service, the VAPID signature made once an hour per service. It used to be one
  phone at a time on a new connection (~0.15 s per Android phone, up to ~0.5 s per iPhone): with a thousand
  subscribers the last one heard of a ballistic missile minutes late. `tests/test_push_fanout.py`: 400 phones
  against a 50 ms push service in well under 3 s, over at most 32 connections.
- **What is pushed**: MiG-31K airborne (country-wide), ballistic threat (Kyiv city/oblast), and from
  `proximity_watch`: a live, non-stale target within the subscriber's radius (+ half a cell), throttled to one
  push per 2 min per device — except immediate types, which alert the whole region with no throttle. Siren-start
  and all-clear pushes were removed on purpose (nothing to act on, and they train people to swipe).
- **In the page**: the Tactical page raises toasts with sound/vibration scaled by zone (near / approach /
  observe). The sound has a **volume** (the bell: slider 0–100 %, 0 = off, 50 % for a new reader, kept in
  `localStorage` as `sndvol`): every tone goes through one Web Audio master gain, squared from the slider (50 % =
  −12 dB), because an iPhone ignores an `<audio>` element's volume. 100 % is the pre-1.28 level; letting go of
  the slider or **▶** (test) plays the loudest alert at the chosen level. The zones keep their relative levels under
  it. Push notifications (app closed) use the phone's own notification sound and volume.
- **The escalation level** (1.36, `escLevel()`), 0–4, from what is already known — never from a guess:
  **1** an official alert over the watched place's own raion (or, with no place set, over Kyiv); **2** a live target
  within 30 km of the place, or one a post says is heading for it; **3** within 10 km, or a target **at** a Kyiv bridge
  (with the bridges on); **4** a fresh ballistic or MiG-31K warning, or an immediate type over the region. It colours
  the card's edge (`#mycard.lv2`–`lv4`) and the bell's dot, and picks the **tone**: `l1` one soft sine (an official
  alert starting), `l2` two short beeps, `l3` three rising beeps twice, `l4` a 3-second two-tone warble with no gap —
  each with its vibration (`VIB_L`). At most one tone in 10 s unless the level rises (`TONE`), so a busy night does
  not become a noise people mute. The bell's ▶ plays `l2`, `l3`, `l4` in turn at the chosen volume. And a **shoot-down notice** for a track the reader was warned about — worded so it can never read
  as an all-clear.
- **The admin's message** (1.29; headed "Message from the system admin" since 1.30): the dashboard publishes one message (UK / EN / FR, info / warning / urgent, for
  1 h – 3 days or until removed), stored in `kv.notice` and carried in the alerts state (`notice`), so the live
  line and `/api/state` bring it to both pages as a banner. A reader can close it (remembered on that phone,
  `notice_x`). Optionally sent as a push to every subscribed phone (the Ukrainian text). Since 1.32 it is loud:
  **Information** is bright green, **Urgent** bright red with a slow pulse (one cycle in 1.6 s, still under
  `prefers-reduced-motion`), the same in every display mode; Warning stays amber. The dashboard previews it in
  that colour while it is written.
- **The nuclear event** (1.32): the one message that covers the map. On the dashboard (Live tab) it is folded
  away in a danger zone with three locks: **Arm** (the server hands back a one-time 6-character code, valid 2
  minutes, **one attempt** right or wrong — `State.nuke_arm`), then the code and the phrase `NUCLEAR EVENT` typed
  in full (the button unlocks only then), then the button **held for 3 s**; `State.nuke_fire` checks the code,
  its age and the phrase again. The text (UK / EN / FR, prefilled with shelter-in-place advice to edit) and an
  optional push to every phone (confirmed). It is stored in `kv.nuke`, logged, published as a `nuke` event and
  carried in the alerts state (`nuke`), so it survives restarts and reaches every open page in seconds. The pages
  download `static/nuke.js` only while one is on: the radiation trefoil over the whole map (Light: over the
  radar), pulsing once every 1.6 s and still under reduced motion, `pointer-events: none` so the map still works;
  a red banner with "NUCLEAR EVENT — RADIATION DANGER", the admin's text (as text, never HTML) and "Heimdall is
  an unofficial app, not an alert system — follow ДСНС and local authorities"; the banner can be folded, not
  closed; one critical tone (at the reader's volume) and a vibration, once per event per phone. **End** is one
  confirmed click and clears every page. `tests/test_nuke_analytics.py` holds the locks.
- **A new address** (1.29): with `CANONICAL_HOST` set, pages opened on any other address show "Heimdall has moved
  to …" with a button to the new one; the phone's **settings** (language, display, sound, oblast, layers — the
  `CARRY` list) travel in the link's `#fragment` (never sent to a server) and are stored there only where the new
  address has nothing of its own (`<script id="carry">`). The watched places do **not** travel: they never leave
  the phone, not even in a link that browser history might keep; the reader sets them again. `scripts/set-domain.bat` attaches the domain (Fly certificates, DNS records) and sets it.

## 9b. The Kyiv bridges (1.34)

From 1 October 2026 the Dnipro bridges are the targets — the Southern bridge hit five times in two days, the
Northern bridge on 3 and 4 October, by Shaheds and jet drones, by day, with cars on them. The live trackers post just
the bridge's name ("Південний міст", "🔻Зниження Північний міст", "на міст патона", "Північний міст падає‼️✈️"),
and until 1.34 those posts were dropped as saying nothing, or drawn at the centre of Kyiv.

- **The eight crossings** (`BRIDGES`, north to south): the Kyiv HPP dam at Vyshhorod (`ges`, the road on the dam),
  Pivnichnyi (Northern), the Petrivskyi railway bridge (`petrivskyi`, "Рибальський залізничний міст" on the map),
  the Podilsko-Voskresenskyi crossing (`podilskyi`: the harbour, Rybalskyi, the arch over the Dnipro, Trukhaniv
  island, Raiduzhnyi — one bridge, named by "Подільський" or "Воскресенський"), Metro, Paton, Darnytskyi (also "the
  Darnytskyi railway bridge", 100 m from it) and Pivdennyi (Southern). Each is its line over the water, `pts` — two
  points, or more where it bends (1.38) — from OpenStreetMap; `bridge_km` measures to the nearest piece. They are in
  the gazetteer (`geo.PLACES`, the middle of each crossing — "Київська ГЕС" at the HPP too — with every declension
  and the Russian names in `geo.ALT`), so a post naming one places its mark on it; plus "Рибальський острів". A traffic notice about them ("рух … перекритий", "смугою", "контактна
  мережа", "режим руху") and a video of a strike ("Момент вчорашнього удару…") are news: no mark.
  `tests/fixtures/bridge_posts_2026_10.json`: 43 real posts of 1–4 October, each with the bridge it puts a live
  mark on, read by hand (24 on a bridge, 19 news / traffic / hits after the fact / "Міст" alone: none).
- **The state, bridge by bridge** (`State.bridges_now`, carried in the alerts state as `bridges` — a dict by bridge,
  so the live line sends only the bridge that changed): `at` — a live mark on the bridge or within 1.2 km of its
  span, or a post of the last 5 minutes that names it (when its mark went elsewhere: "Повз лівий берег на Південний
  міст") and says nothing happened to the target; `near` — within 3.5 km (a Shahed's minute), 6 km for a jet drone
  or a missile; `hit` — **only** a post of the last 30 minutes that names the bridge and says it was hit
  (`BRIDGE_HIT_RX`: влучання, пошкоджено, зруйновано, приліт). 1.38: an explosion is not a hit — on 5 October a bare
  "Вибух" (the interception), placed at the tracker's last position, made "hit reported" on two bridges for half an
  hour. Never from an outcome (shot down, explosion, lost), a stale mark, a mark outside Kyiv city / oblast, one
  placed at a vague point ("Київ" alone, a bank of the river: 2–4 km from several bridges at once), or anything
  reported before the official all-clear for Kyiv city (`State.kyiv_city_all_clears`). With the distance, the type,
  the place named, the time and the channel.
- **The pages**: Tactical — a bar in the card (red for at / hit, amber for near), one line since 1.38: the bridge
  that matters most, the distance, how long ago, and "+N" for the others (a tap on it lists them; a tap on the bar →
  the map on that bridge); the crossings drawn on the map in their state, named a few pixels past their east end
  (`placeBrgLabels`, at every zoom) — a lit one always, the others only when zoomed in under 22 km; and — the
  bell → "Kyiv bridges" (on by default) — a toast, a tone at the reader's volume (the level-3 tone at the bridge, louder
  for a jet drone or a missile; level 2 near it, §9) and a vibration when one rises. Light — one line above the places
  (the bridge that matters most, "+N"), a vibration when one reaches `at`.
- **Push**: the same toggle subscribes the phone to the topic `bridges` (`push_subs.topics`, with its `lang`);
  `bridge_watch` sends "🌉 Південний міст: ціль за 2,3 км — Реактивний БпЛА · 17:33 · з дописів каналів, не радар.
  Не заїжджайте на міст, якщо можете." in the phone's language.
- **Faster reading**: while a threat is within 12 km of a bridge (`State.bridges_busy`), the web channels are read
  every 10 s and the Telegram-API ones every 8 s, as in a missile threat.
- Every rise is kept (`bridge_events`) for the dashboard's "Kyiv bridges" card.

Limits, said in the texts: the positions are the places the posts named (a district is ±1 km), and a post comes
1–3 minutes after the sighting — a jet drone covers 6 km in that time. A bridge with nothing reported is "nothing
reported", never "safe".

## 10. The two pages: Tactical and Light

### 10.1 Tactical (`/m`)

One self-contained `kyiv.html`: an SVG map in a km projection around Kyiv (`proj`/`unproj`, `KX`, `KY`),
level-of-detail classes by zoom, OSM tiles under the vector layers below 150 km width.

**The screen (1.36)** — the reader's own place first, the map second, everything else one tap away:

- **Header**: the two logos, the LIGHT | TACTICAL switch, the **bell** (`#bellbtn`, a dot in the escalation
  level's colour) and **More** (`#menubtn`). No clock, no rotating ticker. 1.39: the switch (`#top .vsw`) takes the
  room between the logos and the icons (`flex:1 1 auto`, at most 340 px, centred), its two halves equal, its text
  sized with `clamp()` so "ПРОСТА / ТАКТИЧНА" or "LÉGÈRE / TACTIQUE" is never cut; under 380 px the NGO logo steps
  aside. Checked at 320 / 360 / 390 / 1440 px in the three languages.
- **The card "My place"** (`#mycard`), in the header's flow — never over the map; `syncTop()` measures it:
  the four places as 44 px chips, each with its **own official status** as a dot (`placeLevel()`: R / Y over the
  place's raion or the city, H a hromada inside its raion, G none, U not known — `unitAt()` finds the unit on the
  map's own outlines, on the phone); the **official block** (`#kyiv`) — with a place set it says that place's status
  ("Obolon · Kyiv · since 19:08 · official") and the duration, without one Kyiv's; the **preventive strip**
  (`#tstrip`), whose fresh ballistic or MiG-31K warning adds one sentence ("Little time — go to a shelter now, do
  not wait for the siren", `mc_go_now`, the guide's own rule) and a **What to do** button to `/guide#w-ballistic`;
  the **channels block** (`#mych`): the one target that matters most for the place — one a post says is heading for
  it, else the nearest within 30 km — with its silhouette, place, course as stated, age, the number of channels and
  the distance; with none, "Nothing reported within 30 km — that is not the same as safe"; with no place set, the
  nearest within 30 km of the centre or an invitation to set one (1.37: "nothing reported" is two lines of text,
  not a box); and the **foot**: the data's age ("updated 4 s ago", amber past 2 min, the block greyed past 10), the
  sources' dot, "unofficial · not radar" (a tap opens the full notice), **What to do →** and **▴**.
- **Folding the card** (1.37, phone only): ▴ folds it to one line (`#mcmini`) — the place's official status, its
  name, the alert's duration, the targets within 30 km — remembered on the phone (`localStorage.card_fold`). It
  opens by itself when the escalation level rises above the one it was folded at (`FOLD.at`, at least 1), or when a
  fresh preventive warning or a bridge bar appears that was not there when it was folded (`warnKey()`), and folds
  back once that is over (`foldShut()`). While a fresh warning is on, the line carries the warning itself, in its
  colour. A tap on the line opens the card. Measured at 360 × 760: about 210–230 px open on a quiet night, 56 px
  folded.
- **The map** with its controls on the right, each 44 px: **Layers** (`#laybtn`), +, −, centre on my place, the
  impacts toggle.
- **The drawer** at the bottom, tabs **Near · Feed · Alerts · Stats**, three heights (tab bar / half / most of the
  screen: a tap on a tab opens it to half, the handle cycles, a swipe moves it). While it is up the card folds to
  the same one line (a tap folds the drawer back).
- **Near** (`nearRows()`, `nearHTML()`): every live target with its distance from the watched place (or the centre
  of Kyiv), in bands — the whole region (immediate types, no distance) / within 10 / 30 / 60 km / further — nearest
  first, inbound ones (as a post said) before others at the same distance; a tap opens the mark's sheet. A
  distance between two reported points is a fact; nothing is projected.
- **The feed** has no row of category chips under each post any more ("on trial" and the Air Force summary keep a
  label): it adds, when the map placed a mark from the post, its distance from the watched place, its type and
  place (`.meta2`, redrawn when the marks change — `feedSync()`), and starts with "Do not publish air-defence or
  impact locations during an attack".
- **Panels** (`#bell`, `#menu`, `#lay`; a sheet from the bottom on a phone, a drop-down under the header on a
  computer; outside tap or Escape closes): **the bell** — push, warn near my position, Kyiv bridges, sound, volume and
  test, vibration, as switches with a line saying what each does; **More** — places (priority place, my oblast),
  view (language, normal / day / night, blackout, Light), about (What to do, Share the app, how it works, support,
  Telegram, about, build tag); **Layers** — the map layers, Kyiv's 10 districts, EST, zoom out to oblast / region / Ukraine,
  and the legend behind a button.
- **Computer** (≥ 1000 px): the card is a 360 px column on the left with the Near list under it, the map in the
  middle, the drawer on the right opening on the Feed. The column is a flex column of fixed height that scrolls:
  its blocks never shrink (`#mycard>*{flex-shrink:0}`, 1.39 — the "nothing reported" line was squeezed under the
  card's foot when a warning made the card tall).
- **The footer** (1.39) is one component, `footerHTML(o)` in `static/i18n.js`, the same under the notice
  (`#discfoot`), under Near (`#panelfoot`), in the support and help sheets and on Light (`#hfoot`): the "free
  service" line with **🔗 Support** (`CONTACT.donate` when the owner sets a donation link; until then it opens the
  support sheet with the addresses — above the notice when tapped from it, `.sheet.top`), **Share the app**, the
  © line with the two logos (`o.logos:false` on Light: no images on 2G), "Built by Dread92 · version · build", and
  **💬 Community & feedback** (`CONTACT.telegram`) on its own line. `CONTACT` (addresses, Telegram, `ngoSite`,
  `donate`) moved to `static/i18n.js` with it.
- **Share the app** (1.39; the footer and More → About): `shareApp()` — the phone's own share sheet
  (`navigator.share`), else the link copied (`navigator.clipboard`, else a hidden textarea), "Link copied" on the
  button for 2 s. The link is the app's canonical address and nothing else — never a place, a slot or a setting.
- Every control of the header, the card, the map, the panels and the drawer can be hit over at least 44 × 44 px
  (the "unofficial" line and the drawer's tab through an invisible margin); the card, panels and drawer use no text
  under 12 px; secondary text `--ink2` `#b5b3ab`, tertiary `--ink3` `#8f8d86` (at least 4.9:1 on the panels and
  the drawer in the normal mode).

Main parts:

- `render()` — official colours (raions, oblasts, banner band, raion chips, alerts tab);
- `tick()` — marks: silhouettes per weapon (`G`, `GLYPH_BY_TYPE` from `static/glyphs.js`), turned only to a stated course (`orientOf`),
  uncertainty ring up to 25 km, 5-minute tail, labels, off-screen edge indicators;
- `threatStrip()` — the banner stack, coloured by `officialLevel()`; `idleLine()` when calm;
- the four places (`SLOTS`: Home / Work / Kids / Pin — `localStorage` only), zones 10 / 30 / 60 km (their
  labels sized in screen pixels, `--k`), the conditional ETA band (`etaBand`);
- **the 📍 pin**: press and hold on open map (a ring fills while the finger stays; a drag only starts past
  `HOLD_SLOP_PX` = 10 screen px; the browser's long-press menu is suppressed), or tap the empty Pin chip to arm the
  map (`armPin`, banner with Cancel) and tap where it goes (`dropPin`);
- **the heat layer** (1.34; Layers since 1.36, off at every opening — never remembered): where drones and
  unidentified targets were reported over 24 h / 7 days / 30 days (`GET /api/drone_heat`: the places the posts named,
  town and district level, the number of posts — shoot-downs and hits left out, never an oblast's centre or "Kyiv"
  alone), drawn as a density whose spread keeps its size on the screen, so it is layered by zoom (out: the
  corridors across the region; in: the villages and the Kyiv districts); the most-named places in view written on it
  and listed in its legend; under every mark. 1.40: **the colour is the number of reports** — pale yellow, orange,
  red for the most (it was violet). `heatGrid()` adds each place's count around it on a grid a quarter of the
  screen's pixels (a smooth bump of 30 px); a spot's colour is √(its sum ÷ the scale), the scale being the busiest
  place of the period or the busiest spot in view if that is more — so a quiet corner never turns red because it is
  zoomed in on; a place with few reports is faint as well as yellow. The legend's ramp reads "1 … N+" and says "not
  live, not alerts"; while the layer is on, the official alert colours are drawn as outlines over a faint fill
  (`svg:not(.no-heat)`), so the two are never read as one colour. Dark map: blended with `screen`; day: `multiply`. (1.33's alert hours by oblast stay in the dashboard's Analytics.)
- tabs: **Near** (1.36, above); **Feed**; **Alerts** (the live tally of what is on the map, then the official alerts); **Stats** — the Air
  Force's official figures only, weapon by weapon since 1.32 (§7.5): for 24 h / 7 d / 30 d (`windows[…].af`) a
  row per type — launched and ↓ shot down, ✓ when used without a number — and the hit locations; a key under the
  table, one sample per line (`.aflg`, 1.39: it was one sentence whose end fell under the screen's edge); then each
  summary (night / day) with chips and a link to its post (`af_days`). Each type wears the app's own silhouette
  (`gIco()`: the glyph of `static/glyphs.js` in a small svg, the same shape as on the map), not the phone's emoji;
  so do the threats in the Alerts tab and the preventive strip (`thrIco()`). (The **Map** tab became the Layers panel in 1.36.)
- **approach marks** (drawn at the town they are heading to): a dashed course coming **into** the town from the
  side the post named, no ray or cone ahead, never dead-reckoned (Est.), no ETA; label "→ Vasylkiv from the NW";
  on Light "heading for Vasylkiv — where it is now was not said";
- **mark labels never overlap**: after each tick the label blocks are placed in screen pixels — which lines are
  drawn is read back from the CSS (`getComputedStyle`), candidates right / left / a line lower or higher, clear of
  other labels, other marks' glyphs and the map's edge; placed by priority (to a watched place, inbound,
  descending, others, outcomes); an ordinary label that fits nowhere loses its second line (`nolbl2`), then is
  left out (`nolbl`). The boxes (`LBLBOX`) hide the town names under them (`layoutTownLabels`);
- the map's own pictograms are vector shapes, not the phone's emoji (1.39): the airfields, power plants and nuclear
  plants of the infrastructure layer (`POIS`, `POI_G`: a plane, a lightning bolt, a trefoil; shown zoomed in, hidden
  at night and in blackout), the watched place's house, and the impacts button's burst — the same on every phone;
- the OSM tile credit sits small in the bottom corner; the Crimea Cossack is drawn in `#obllbl`, above the raion
  outlines, one path per colour;
- display modes: normal, day (inverted, WCAG-checked), night (dim, arrows only), blackout (2G);
- the **notice** (disclaimer, language, oblast): shown **once per opening** — `sessionStorage.disc_seen`, shared
  with the Light page, so switching Light ⇄ Tactical does not show it again; always reachable from the card's foot
  ("unofficial · not radar") and More → About. Changing the language inside it reloads the page **and shows it
  again** in the new language (`pickLang(l, true)` clears `disc_seen`); "I understand" is a full-width button,
  centred, and since 1.36 it stays at the bottom of the screen while the notice scrolls (`.dok`, `position:
  sticky`). 1.39: the owner's text — the title is "IMPORTANT INFORMATION" alone, centred, with the language
  under it; the first paragraph opens with "HEIMDALL is an unofficial volunteer service"; the footer component
  closes it.

### 10.2 Light (`/light`)

One place, what concerns it, nothing else. Built to load and be read on 2G (page ≈ 24 KB gzipped, map data
≈ 41 KB, fetched after the status is on screen; `test_light` holds both under budget).

- **Status = the place's raion**, from the official data only. The raion is found **on the phone**: point in
  polygon on `light-map.json`'s raion outlines. A place within **1.5 km of a border** belongs to both raions
  (the outlines are accurate to a few hundred metres; a house on the line gets either side's alert). Outside
  the covered oblasts it falls back to the oblast (`ukraine-map.json`).
- States: **R** / **Y** (alert over the place's unit, official level + reason), **H** (a hromada inside the
  raion is under alert), **P** (raion unknown, part of the oblast), **G** (no alert over the unit — neighbours
  under alert are *named*, never painted on the place), **U** (no data). "Nothing reported" never says "safe".
- **Radar: 30 km** (`R_KM`), rings at 10 / 20 / 30 km, over a local map: raions shaded by alert, oblast borders,
  Kyiv's districts, rivers, main roads, towns, villages and neighbourhoods (from `/api/places`), labels placed
  without overlap. Marks are **the same silhouettes as the Tactical map** (`static/glyphs.js`): turned to a
  course only when the post reported one (`markOrient`), upright with a "?" otherwise; the ⚠ for unknown
  types stays upright with a small orange course arrow; a dotted tail joins earlier reports; each mark
  carries its list number. The list shows the same silhouette beside each row.
- **List**: number, type, count, distance, zone, "→ here" (stated course within 28° of the place), place,
  course, **height** when a post stated one (descending in crimson; a run of stated heights as
  "↓ 2,2 км → 1,6 км → 600 м" via `altTrend()` in `i18n.js`), age, ETA band. The height is also written beside
  the mark on the radar. **Tap a row** for what the post said (original + translation), the track so far,
  altitude when stated, the source and time.
- **The radar zooms by itself** (1× = the 30 km disc, up to 4×): pinch, double-tap, the + / − / ⟲ buttons,
  ctrl + wheel. Only the map zooms — never the page; unzoomed, one finger still scrolls the page (`touch-action:
  pan-y`), zoomed in, one finger moves the map. Symbols and names sit in groups scaled by `1/zoom` (`--iz`), so
  they keep their size; names are placed again (more of them) once the fingers stop. Nothing on it can be
  selected as text.
- **Tap a mark on the radar**: the nearest mark within a finger's width (`tapAt`, `RT`) opens its row as a card
  over the part of the map it is not on (`#rcard`), kept current on every repaint; a tap on open map closes it.
- **Approaching (30–100 km)**: listed apart, only targets whose **stated** course points at the place.
- 1.36: each of the four place chips carries its own official status as a dot (`placeStatus()` for that place);
  the colour legend is behind a "?" button; the footer is two buttons (What to do, the Tactical map); every control
  44 px, no text under 13 px, the same secondary-text colours as Tactical.
- 1.39: under the two buttons, the same footer component as Tactical (`footerHTML({logos:false})`, §10.1) —
  without the two logos, which would cost 20 KB on 2G; it is drawn again when the language changes.
- Immediate types: a banner for the whole region, no distance, no countdown.

### 10.3 The switch

Both pages carry the **LIGHT | TACTICAL** switch (UK: ПРОСТА | ТАКТИЧНА, FR: LÉGÈRE | TACTIQUE): a full-width
two-segment control on Light, each half captioned; a high-contrast pill in the Tactical header.

1.40: **a toggle, not a reload.** The orange half is one thumb (`::before`); a tap on the other half (`a[data-sw]`,
handled in `static/i18n.js`, `swGo()`) slides it across in 0.2 s, then opens the other page. Three things keep the
screen from going blank in between:

- **cross-document view transitions** (`@view-transition{navigation:auto}` in Tactical, Light and the guide): the
  browser keeps the old page on screen until the new one has painted, then fades one into the other (0.16 s out,
  0.24 s in, a 6 px rise). Chrome and Edge 126+, Safari 18.2+; elsewhere an ordinary navigation.
- **speculation rules**: Tactical prerenders `/light` on hover or press (`moderate`), Light prerenders `/m` only on
  the press (`conservative` — Light is the 2G page); the page is usually ready when the thumb has finished.
- a prerendered page is not a visit until it is shown: it opens no live line and sends no ping (`whenShown()` waits
  for `prerenderingchange`), and the server does not count a load that carries `Sec-Purpose: prefetch`.

Nothing is carried between the two: both read the same places, language and settings from the phone. With
"reduce motion" the thumb does not slide and the pages do not fade.

### 10.3b Motion (1.40)

Short, eased, never bouncy, and none in blackout mode or with "reduce motion" (`CALM()`): a panel (bell, More,
Layers) rises in on a phone and drops in on a computer (0.26 s), its rows following 14 ms apart, and leaves in
0.16 s (`hidePanel()` sets `hidden` after the animation); one orange line slides under the drawer's tabs to the
chosen one (`tabInd()`); a tab's content fades in; switches move their knob with a slight ease; buttons give a
little under the finger (`scale(.95)`); sheets and the drawer use the same easing. Light: the place picker and the
target card slide in.

### 10.4 Languages

`static/i18n.js`: every string in EN / UK / FR (`t()`, `tn()` for plurals), place, raion, river and district
names, `OBL_N` / `oblFull()`. A test fails when a key is missing in one language. See [I18N.md](I18N.md).
The language is a **drop-down** on both pages (`langSelect()`: the Tactical More panel and notice, the Light header —
flag and code only — and notice); `pickLang()` stores it and reloads.

### 10.5 The guide (`/guide`, 1.35)

What to do, weapon by weapon. One self-contained `static/guide.html`; its content is the JSON block `#gd`
(`uk` / `en` / `fr`, the same shape in each — `tests/test_guide.py` compares them key by key and list by list) and
the sources in `#gsrc` ([publisher, title, URL]). The script draws it, so the page reads `?lang=` (not stored),
then `localStorage.lang` (shared with the two pages; the УКР / EN / FR buttons store it), then the phone's language.

- **Five rules** that always apply; **weapon cards** (`shahed`, `jet`, `cruise`, `ballistic`, `kab`, `debris`):
  the usual warning time as a chip, how you notice it, what to do — with the map's own silhouette and colour
  (`static/glyphs.js`, `ICON` in the page); **situations** (`car` — the bridges, `out`, `home`, `kids`, `after`,
  `rad`); the **emergency numbers** as `tel:` links; the **sources**, with what is not taken from them said.
- Every rule comes from the listed official guidance (ДСНС, National Police, Ministry of Health, Poltava ОВА) —
  [SAFETY.md](SAFETY.md#the-guide-says-what-the-official-guidance-says). The checked date is in the footer.
- **Offline**: the page registers `sw.js`; the worker stores `/guide`, `glyphs.js` and the logo at install
  (`heimdall-guide-N`) and answers those three paths **network first**, the stored copy only when the network
  fails. Nothing else goes through it. "Saved on this phone" appears only once `caches.match('/guide')` finds it.
- **Print**: `@media print` — black on white, no buttons, cards kept whole, three columns; two A4 pages in each language.
- Linked from the Tactical More panel (About, `m_guide`), the card (What to do →, and the ballistic warning's button), the top of the help sheet (`.gdl`), the Light footer (`#gdl`)
  and the nuclear-event banner (`/guide#rad`, `static/nuke.js`). The page asks the server for nothing.

## 11. Privacy and security

- The four places never leave the phone; the Light page's requests carry no place (checked in the render tests).
- Push subscriptions: a ~10 km cell only; older stored homes are coarsened at start.
- The Telegram session (`TG_SESSION`) is a key to a whole Telegram account. It is created on the owner's PC by
  `scripts/telegram-login.bat` and goes straight into Fly's secret store (`fly secrets import`, read from stdin):
  never on a command line, in a file, in the logs, in `config.json` or in the repository. Revoke it in Telegram:
  Settings → Devices → "Clear Sky server" → Terminate.
- Usage counters (`usage`, `usage_seen`): a daily salted hash, no IP address, no location, no per-person
  history. A page the browser loads ahead of a tap (prerender, `Sec-Purpose: prefetch`) is not counted (1.40).
- Flags and the corpus review are behind `ADMIN_KEY`.
- The weather (1.33) asks Open-Meteo for seven fixed points (six launch areas and Kyiv) — nothing about a reader.
- No secret is committed: `config.json`, `vapid.json`, `.env`, `*.pem`, databases and `.flyapp` are
  git-ignored; the history was scanned for tokens before the repository was published.
- Static files are served gzipped with an ETag (`Cache-Control: no-cache`): a phone revalidates instead of
  downloading again, and still picks up a new version immediately.

## 12. HTTP API

All JSON unless stated. Public unless marked 🔒 (`ADMIN_KEY`).

| Route | Returns |
|---|---|
| `GET /`, `/m`, `/k`, `/kyiv` | Tactical page |
| `GET /light`, `/l` | Light page |
| `GET /guide` | the what-to-do guide (§10.5): static, three languages, kept offline by `sw.js` |
| `GET /desktop`, `/index.html`, `/dash` | older desktop view |
| `GET /ua`, `/mobile`, `/mobile.html` | older mobile view |
| `GET /manifest.json`, `/light.webmanifest`, `/sw.js`, `/favicon.ico`, `/static/*` | PWA files, assets (gzip + ETag) |
| `GET /healthz` | liveness: `{"ok": true}`, or **503** when the database cannot be had within 3 s |
| `GET /api/version` | `{v, now, missile, msl, build, app}` — the cheap ping pages poll |
| `GET /api/state` | active alerts, per-oblast status, sources' health, єРадар counts, the admin's message, the nuclear event, the Kyiv bridges (`bridges`, §9b), config summary |
| `GET /api/markers` | live marks with evidence, history, staleness |
| `GET /api/feed?limit=&lang=` | recent posts (`text`, `text_en`, `text_fr`, `en_mt`, tags); `lang` asks for translation |
| `GET /api/stream?sync=&ev=&p=&lang=` | the live line (§5.4): `hello`, `sync` (changes of `mk`, `st`, `fd` as asked in `sync`) and, unless `ev=0`, the events `start`, `end`, `threat`, `update`, `feed`, `eradar`, `tr`, `notice`, `nuke`; `p=light` counts it as a Light page |
| `GET /api/history?hours=&oblast=` | past alerts (1–168 h; cached, one query per change for every page) |
| `GET /api/events_log?limit=` | alert events |
| `GET /api/impacts?hours=` | explosions and confirmed shoot-downs |
| `GET /api/stats?days=` | statistics; the Stats tab reads only `windows` (with `af`: launched / down by type, used, impacts, debris) and `af_days` (the Air Force summaries, each with its `post`) |
| `GET /api/places?oblast=` | gazetteer (names, coordinates, oblast) |
| `GET /api/drone_heat?days=1|7|30` | the heat layer: `points` `[lon, lat, posts, place, oblast]` — where drones and unidentified targets were reported (cached 10 min) |
| `POST /api/push/subscribe`, `/api/push/unsubscribe`, `/api/push/test`; `GET /api/push/key` | Web Push; subscribe takes `{subscription, home, topics: ["bridges"], lang}` |
| `POST /api/flag` | "this reading is wrong" report |
| 🔒 `GET /admin`, `/api/usage` | dashboard, usage counters |
| 🔒 `GET /api/health` | official sources (ok, last check, detail), every channel read (posts / marks 24 h, share read 7 d, last post, reader state, `mode`, `read_via`, `builtin`), translation backends, lead time over the official alert in Kyiv + oblast (30 days) |
| 🔒 `GET /api/online` | pages open now with a live line (`total`, `tactical`, `light`, today's peak), the current message, the nuclear event (`nuke`), the last push fan-out (phones, seconds, delivered) |
| 🔒 `GET /api/analytics?days=` | the dashboard's Analytics (§8c), 7–365 days: `af` per date (launched, down, used, impacts, debris, periods), `af_areas`, `af_directions`, `af_models`, `kyiv` per date (city / oblast minutes, city alerts), `starts` (7 × 24), `reports` per date by type, `hours`, `headings`; since 1.33 `weather` per date (`kyiv`, `launch`), `approach` (8 sectors per date), `air` (`per_date`, `stats`, `sorties`), `obl` (`by`, `cols`, `rows`), `weather_status`; since 1.34 `places` (the heat layer's top 25) and `bridges` (`per_date`, `totals`, `recent`) |
| 🔒 `POST /api/admin/nuke` | `{action: arm}` → `{code, expires_s, phrase}` (refused while one is on); `{action: fire, code, phrase, text: {uk, en, fr}, push}`; `{action: end}` — the nuclear event (§9) |
| 🔒 `POST /api/admin/channel` | `{action: add|set|delete, name, mode: map|trial|off, via: web|api}` — the channels read (§7.1); `add` checks `t.me/s/<name>` for readable posts and starts it on trial |
| 🔒 `POST /api/admin/notice` | `{text: {uk, en, fr}, level: info|warn|alert, hours: 0–168 (0 = until removed), push: bool}` or `{clear: true}` — the team's message (§9) |
| 🔒 `GET /api/digests` | the stored nights and weeks: figures, written summary (EN / UK), model |
| 🔒 `POST /api/digest/run` | `{kind: night|week}` — asks the `Digests` thread to write the last one up now (never calls the model itself) |
| 🔒 `GET /api/flags`, `/api/corpus`; `POST /api/corpus/review`, `/api/corpus/translate` | flags and corpus review — no longer in the dashboard (1.19); used by `scripts/corpus.py` |

## 13. Storage

SQLite in WAL mode (`DB_PATH`; on Fly, the volume). Tables:

| Table | Holds |
|---|---|
| `alerts` | every alert seen (active and finished) — the normalised shape |
| `events` | start / end / threat / update events |
| `feed` | posts: `post_id, channel, ts, text, tags, text_en, text_fr, en_mt` |
| `kv` | small settings: the VAPID key pair, the usage counter's daily salt, the channels (`channels`), the admin's message (`notice`), the nuclear event (`nuke`), and similar |
| `push_subs` | push subscriptions with a ~10 km cell, the topics asked for (`bridges`) and the language |
| `marker_log` | every mark as computed, with its evidence |
| `outcomes` | shoot-downs, impacts, losses |
| `channel_stats` | per channel per day: posts, posts with a reading, flagged readings |
| `digests` | each night / week: the figures (JSON), the summary in EN and UK, the model, any error |
| `af_reports` | each Air Force summary read (§7.5): `post_id, channel, ts, period, date` and the reading (JSON) — kept for good, one row per post |
| `air_reports` | what posts reported about the carriers (§7.6): `post_id, kind, phase, channel, ts` and a fingerprint of the text |
| `bridge_events` | each time a target was reported on or near a Kyiv bridge (§9b): time, bridge, level, km, type, place, channel |
| `weather` | each night's weather per point (`date, place`, JSON: mean wind, strongest gust, mean cloud cover, rain, lowest temperature) |
| `flags` | readings people reported as wrong |
| `corpus_reviews` | verdicts from `/admin` review, merged back with `scripts/corpus.py pull` |
| `usage`, `usage_seen` | anonymous usage counters |

Columns are added in place by `Store.__init__` (`ALTER TABLE … ADD COLUMN`), so an old database upgrades itself.

## 14. Testing and quality

```bash
pip install -r requirements-dev.txt
python -m pytest              # ~410 tests
python -m ruff check app tests scripts
python app/server.py --demo --port 8099
```

| Suite | Pins |
|---|---|
| `test_geo`, `test_tagging`, `test_misreads`, `test_odesa`, `test_news_and_banderol` | parsing, tags, news guard, Banderol |
| `test_phases`, `test_immediate`, `test_marks`, `test_prune` | lifecycle, immediate types, silhouettes, staleness |
| `test_raion_alerts`, `test_scope`, `test_banner` | official data by raion, channels, scope, banner |
| `test_light`, `test_places`, `test_privacy_push`, `test_usage` | Light page, places stay local, push cell, counters |
| `test_translation`, `test_i18n`, `test_modes` | translation path, three languages, display-mode contrast |
| `test_corpus`, `test_review_source`, `test_af_summary` | the regression corpus, review, launch totals |
| `test_cadence`, `test_version`, `test_keys`, `test_docs` | refresh rates, build info, keys, this documentation |
| `test_official_stats`, `test_ui_details` | Air Force-only stats, the dashboard's health view and lead time, pin, zoom, language, logo |
| `test_destination`, `test_scripts_parse` | where it is vs where it is going; every page script parses (node) |
| `test_load`, `test_watchdog` | no network in the marks' path, one computation for everybody; the watchdog |
| `test_digests` | a night's figures, the model's rules and answer, windows, owner-only and never in a request |
| `test_bridges`, `test_after_the_all_clear` | 43 real bridge posts, the eight crossings and every spelling, at / near / hit and what never counts, a post naming a bridge, the push by topic and language, faster reading, the heat layer's places; the evening of 5 October replayed — nothing left in Kyiv after the official all-clear, no hit from an explosion, a carried position keeps its own time |
| `test_carriers_weather_heat` | the carriers on 63 real posts, sorties and delays, a reply read as itself, no mark for a carrier, Kinzhal ballistic, the weather, the approach sides, the oblast hours, the heat layer |
| `test_card`, `test_guide` | 1.36's card: in the header, each chip's official status, the one target and no time promised, the guide's own instruction, the escalation level and its tones, the bell / More / Layers split, 44 px targets, what the ticker said; 1.35's guide |
| `test_af_reports`, `test_nuke_analytics`, `test_channels` | the Air Force read weapon by weapon, one per night, the backfill; the nuclear event's locks, Analytics, the loud message, both languages on the dashboard; channels from the dashboard |

**The corpus** (`data/corpus.jsonl`, [CORPUS.md](CORPUS.md)): real posts with their expected reading; a
changed reading fails the suite until it is re-verified as the intended change.

**Render checks** (before each release, not in CI): Playwright against a local server, Tactical in three
languages × phone/desktop × modes, Light for several places, no JS errors, no overflow, no request carrying a
place.

CI (`.github/workflows/ci.yml`) runs ruff and pytest on Python 3.9 and 3.12, starts the service and checks it
answers; a **front-end** job checks that the page scripts parse and that every English string exists in Ukrainian
and French (a plural counts when Ukrainian has its `_2` and `_5` forms for English's `_n`). `test_scripts_parse`
runs that job's steps as written, so it cannot fail only on GitHub — and, since 1.40.1, without a global `navigator`,
as on the job's Node 20 (Node 21+ has one: `static/i18n.js` read `navigator.language` at load and passed here while
failing there). `static/i18n.js` must evaluate with no browser globals at all.

## 15. Deployment and the GitHub repository

- **The working folder** is `Desktop\clear-sky-main` on the owner's PC: a Git clone of the private repository
  **Dread92/clear-sky**. Patches are committed there.
- **Shipping a patch**: double-click **`scripts\release.bat`**. It refuses to run if anything is not committed,
  deploys to Fly.io, pushes to GitHub, and prints the live `/api/version` — the version shown must be the
  new one.
- **First deployment, or changing a key**: `deploy-fly.bat` (Windows) — sign-in, app, volume, the dashboard
  key, the optional DeepL key, deploy. Details in [DEPLOY.md](DEPLOY.md). `fly deploy -a kyiv-air-watch-gb`
  alone also works.
- **GitHub**: `scripts\github-push.bat` creates the **private** repository `<you>/clear-sky` with the GitHub CLI
  (sign-in in the browser; no token is ever typed or stored by the script) and pushes; run again to push new
  commits. Optional auto-deploy: add the repository secret `FLY_API_TOKEN` and `fly-deploy.yml` deploys every
  push to `main`.

## 16. Maintenance recipes

**Rebuild the geography** (after an administrative change, or when the log says "not in ua_regions.json"):
`python scripts/build_geo.py` — downloads the official region list, rewrites `data/ua_regions.json` and
`static/light-map.json`, prints any raion it could not match to a map shape. Run the tests; commit both files.

**Telegram sign-in for the API reader**: create an app on <https://my.telegram.org> (API development tools),
then run `scripts\telegram-login.bat`: it asks for the api_id, the api_hash and the phone number of the reading
account (a dedicated account is best), signs in with the code Telegram sends, joins the channel, and stores the
three secrets on Fly. If the sources panel ever shows "Telegram session no longer valid", run it again.

**Add or remove a channel**: edit `AUTHORITATIVE_CHANNELS` in `server.py` (and `DEFAULT_CONFIG` for the record);
a channel whose web preview is off also goes in `telegram_api_channels`;
a fixed format gets a parser in `geo.py` registered in `CHANNEL_PARSER`; add real posts to the corpus
(`scripts/corpus.py add`); a mixed channel goes in `NEWS_CHANNELS`.

**Change the region**: `REGION_UIDS` and `SCOPE_KM` in `server.py`, `SCOPE` in `build_geo.py` (then rebuild),
the Light page's place list (`/api/places?oblast=…`).

**Add a string**: all three blocks of `i18n.js`; `test_i18n` checks.

**Regenerate the app icons** from the master logo `docs/brand/clear-sky-logo.png` (transparent PNG): the files
are `static/logo-cs-512.png` / `-192` (logo on `#0b0d11`, 90 %), `logo-cs-maskable-512.png` (56 %, inside the
maskable safe circle), `logo-cs-64.png` (the radar emblem alone, transparent — favicon), `logo-cs-badge.png`
(white on transparent, for Android's notification badge) and `logo-cs.png` (280 px, the notice). The 07300 and
Black Flame logos (`logo*.png`, `bf-logo*.png`) stay as they are.

**Official data by key instead of the proxy**: request a key at <https://api.ukrainealarm.com/>, then
`fly secrets set UKRAINEALARM_KEY=…` — the same code reads the API directly.

## 17. Known limitations and open items

- `chyste_nebo` is read through the Telegram API with a user session. Telegram can restrict an account that
  reads channels by program; a dedicated account keeps the owner's own out of that risk. Its post formats have
  not been seen yet (the preview never showed them): check the first live posts and tune the parser.
- siren.pp.ua is a volunteer proxy of the official API; an official key is more robust (§16).
- Without a DeepL / Google key, English is the offline glossary and French shows English.
- Ukrainian declension of place names after a preposition ("біля …") is not implemented; labels avoid it.
- `outcomes` is written but nothing reads it yet (`marker_log` and `channel_stats` feed the dashboard's health view).
- About 265 corpus cases are still pending review; the review left the dashboard in 1.19 and is done from the
  terminal (`scripts/corpus.py`, [CORPUS.md](CORPUS.md)) when needed.
- Hromada alerts have no shapes of their own: on the Tactical map they colour their parent raion; on Light they
  are named ("alert in part of your raion").

## 18. The patch checklist

Every patch, in this order:

1. Code + tests (a behaviour change gets a test that fails without it).
2. `python -m pytest` and `python -m ruff check app tests scripts` clean; render checks for page changes.
3. Bump the version in three places: `APP_VERSION` in `app/server.py`, and in `static/kyiv.html` both
   `const APP_VERSION` and the `buildtag` footer (`tests/test_version.py` checks they agree).
4. Add the `## X.Y.0 — date` entry at the top of `CHANGELOG.md` (Added / Changed / Fixed / Removed).
5. Update **this file**: the header's *Documented version* and date, and every section the patch touches
   (routes → §12, config / env → §5, tables → §13, sources → §6–7, pages → §10, open items → §17).
   `tests/test_docs.py` enforces the version, routes, config keys, env vars and tables.
6. Commit in the working folder (never `config.json`), then ship with `scripts\release.bat` (deploy + push).
7. Post the patch note to users once it is live.
