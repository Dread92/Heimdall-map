# Heimdall — technical documentation

**Documented version: 1.58** · last updated 2026-10-14 (1.58.15)

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
9. [Notifications](#9-notifications) — and [9c. The owner's private Telegram channel](#9c-the-owners-private-telegram-channel-158)
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

An **unofficial** air-raid and drone tracker for **Kyiv city and Kyiv oblast first**, and the oblasts switched on
around them (the six around Kyiv, then Odesa, Kharkiv, Dnipro, Mykolaiv and, since 1.45, seven more — §7.1). One
Python process — standard library only, plus `cryptography` for Web Push — reads:

- the **official «Повітряна тривога» alert data** (which raions are under alert, at which level),
- **24 public Telegram channels** that report where drones and missiles are: the four Kyiv live trackers, three
  country-wide channels (the Air Force among them) and one live tracker per oblast (§7.1) — most through their
  `t.me/s/` previews, three through the Telegram API,
- the Air Force's summaries and the carriers' take-offs and launches, read from those posts (§7.5, §7.6), and the
  nights' weather (Open-Meteo, §7.6),

and serves its pages from the same data — and, with the owner's key, has an AI model write a bulletin of the last
hour and the last 24 hours from what it recorded (§7.11):

| Page | Address | For |
|---|---|---|
| **Tactical** | `/m` (also `/`, `/k`, `/kyiv`) | The full map: every mark with its evidence, the feed, alerts, statistics, display modes, layers. |
| **Light** | `/light` (also `/l`) | One place (one of the four pins, named by their owner): its raion's official status, what is within 30 km, what is heading there. |
| **Guide** | `/guide` | What to do, weapon by weapon and situation by situation — the official guidance, in three languages, offline (1.35, §10.5). |

Both install as separate PWAs (manifest ids `/m` and `/light` — unchanged by the 1.29 rename, so Android offers
the new name and icon as an update of the installed app; an iPhone keeps an installed app's name and icon until
it is added again). Production runs on Fly.io as `kyiv-air-watch-gb` (one performance-1x machine — a dedicated CPU —
with 2 GB since 1.41.1, a 1 GB volume for the database; `[[vm]]` in `fly.toml`, which every deploy applies).

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
 sources                          app/server.py (one process)                                 out
 ───────                          ───────────────────────────                                 ───
 official alerts ─────────▶ UkraineAlarm / AlertsInUa / Ubilling ──apply_snapshot──┐
  (siren.pp.ua or ukrainealarm,       every 10–30 s                                 │
   alerts.in.ua, ubilling mirror)                                                   ▼
                                                                         State: alerts → level by raion ──▶ /api/state
 24 Telegram channels ────▶ Telegram (t.me/s previews, 30 s; 10 s in a missile threat)        │
  (3 Kyiv trackers, 3 country, ─▶ TelegramAPI (chyste_nebo …, 15 s; polls, never subscribes)  │
   1+ per oblast)                    │ ingest(): stored BEFORE it is read                      │
                                     ▼                                                        ▼
                               Store (SQLite on the Fly volume): feed, alerts, events, marker_log, outcomes,
                               targets, target_points, track_moves, af_reports, air_reports, weather, ai_bulletins, kv …
                                     │
                                     ▼
                     State.markers(), re-read on every pass:
                       geo.parse_for_channel (gazetteer + villages of the oblast)
                       → _marks_from_posts (the channel's report before / after: shared names, a height alone)
                       → _chain_and_prune (one target only at a speed it can fly: 350 / 650 km/h)
                       → _tag_marks (#n for the night) → log_markers ──────────▶ /api/markers, /api/stream (SSE)
                                     │                                            /api/replay, /api/trail
                                     ├──▶ Pusher, proximity, bridges ──▶ Web Push ──▶ phones (~10 km cell only)
                                     ├──▶ activity_summary ──▶ bulletins (OpenRouter, 3 languages) ──▶ /api/bulletin
                                     └──▶ patterns, hourly: target_points → track_moves ──▶ /api/admin/patterns 🔒
 Open-Meteo ──▶ Weather ─────────────┘        Translations (DeepL / Google) ──▶ feed in EN / FR
 Sentinel-2 file on the volume ──▶ /tiles/sat · Esri (owner's key) ──▶ /tiles/esri
                                                                pages: /m Tactical · /light Light · /guide · /admin 🔒
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
│   ├── ai_reader.py        1.50: the AI reader in shadow mode (OpenRouter) — prompt, schema, checks, comparison (§7.7)
│   ├── chanpost.py         1.58: the owner's private Telegram channel — a post per report, its outcome, the all-clear (§9c)
│   ├── mapshot.py          1.58: its picture — the map around one target, drawn with Pillow in the app's style (§9c)
│   ├── areas.py            1.58.7: which official alert area a point is in, and is it under alert (`held`, §7.4; §9c)
│   └── push.py             Web Push: VAPID ES256 JWT + RFC 8291 aes128gcm, on `cryptography` only
├── static/
│   ├── kyiv.html           Tactical page (one self-contained file)
│   ├── light.html          Light page (one self-contained file)
│   ├── i18n.js             every UI string in EN / UK / FR, place / raion / river / channel names
│   ├── glyphs.js           the weapon silhouettes (G, GLYPH_BY_TYPE), shared by both pages
│   ├── kyiv-map.json       27 oblasts + all raions, in km around Kyiv (geoBoundaries)
│   ├── light-map.json      raions of the 8 oblasts + nearby oblast outlines, rivers, roads, towns (built)
│   ├── light-map-x.json    raions of the 11 oblasts farther out — fetched only for a place there (built, 1.43)
│   ├── map-ua.json         rivers, main roads, airports and power plants of the whole country (built, 1.45)
│   ├── towns-ua.json       raion centres and towns of 10,000+ of every oblast, for finding one's way (built, 1.49)
│   ├── kyiv-districts.json the 10 city districts of Kyiv (OSM)
│   ├── streets/            1.56: every settlement and named street of each oblast, `<uid>.json` (OSM, built; LICENSE.md: ODbL)
│   ├── streets.js          1.56: their search, on the phone — loaded by both pages' pin pickers when they open (§10.6)
│   ├── shelters.json       1.57: the shelters Kyiv city lists (KMDA, ІАС «Майно»; built by scripts/build_shelters.py)
│   ├── shelters.js         1.57: the nearest ones, on the phone — loaded by both pages for a pin in Kyiv (§10.7)
│   ├── lightmap.js         1.57.2: the Light radar's satellite / map background — loaded when asked for (§10.2)
│   ├── ukraine-map.json    oblast outlines in an affine lon/lat projection (Light page fallback lookup)
│   ├── admin.html          private dashboard: usage, source health, channels, lead time (/admin, ADMIN_KEY)
│   ├── index.html, mobile.html   older desktop / mobile views (/desktop, /ua)
│   ├── guide.html          what to do, weapon by weapon (/guide, 1.35): self-contained, content in its JSON block
│   ├── sw.js               service worker: push display, notification clicks, the pages and the guide kept for when the server is unreachable
│   ├── manifest.json, light.webmanifest   the two PWAs
│   ├── logo-cs*.png        the Clear Sky logo: app icons (any / maskable), favicon, badge, the notice
│   └── logo*.png (NGO 07300), bf-logo*.png (Black Flame Studio), ukraine-map.LICENSE.md
├── data/
│   ├── ua_regions.json     official region id → oblast / parent raion / map shape (built)
│   ├── regional_places.json the villages and city districts of the oblasts with a tracker (GeoNames, built, 1.43)
│   ├── extra_places.json   the villages of Kyiv oblast (built, 1.52; read by the rules too since 1.54.7)
│   └── corpus.jsonl        regression corpus of real posts and their expected readings
├── scripts/
│   ├── build_geo.py        rebuilds data/ua_regions.json and static/light-map.json (`--light`: the Light maps only)
│   ├── build_places.py     rebuilds data/regional_places.json from GeoNames (1.43)
│   ├── build_extra_places.py rebuilds data/extra_places.json from GeoNames (1.52)
│   ├── build_mapdata.py    rebuilds static/map-ua.json from Natural Earth (1.45)
│   ├── build_towns.py      rebuilds static/towns-ua.json from GeoNames (1.49)
│   ├── build_streets.py    rebuilds static/streets/ from the 27 regional OSM extracts (pyosmium, shapely; 1.56)
│   ├── build_shelters.py   rebuilds static/shelters.json from the city's shelter list saved in a browser (1.57)
│   ├── build_imagery.py    builds the satellite layer (imagery/sat-ua.mbtiles) from ESA WorldCover / Sentinel-2 (1.47)
│   ├── upload-imagery.bat  puts imagery/sat-ua.mbtiles on the Fly volume (1.47)
│   ├── set-esri-key.bat    one-time: the owner's Esri key for the closest zooms, into Fly's secrets (1.48)
│   ├── set-openrouter-key.bat  one-time: the owner's OpenRouter key for the AI reader, into Fly's secrets (1.50)
│   ├── set-telegram-channel.bat one-time: the owner's bot token and private channel, into Fly's secrets (1.58, §9c)
│   ├── build_manual.py     rebuilds docs/manual.html — the whole documentation as one page, with the system map (1.54.9)
│   ├── manual/             its template (template.html) and the system map, drawn by hand (map-svg.html)
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
| `Vitals` | 1.41: the process's own CPU, the CPU the host took away (steal — on a shared Fly vCPU, throttling), memory, how late its own clock woke it; every request over 2 s (path and time only); every start with its build (`kv.boots`, last 100). On the dashboard's Live tab (`/api/online` → `process`) | 10 s 1.58.3: each start says how the run before it ended — a stop signal (`last-exit.json` beside the database, written by the SIGINT/SIGTERM handler: a deploy, a secret set, Fly moving the machine), the watchdog, or nothing written (a crash, an out-of-memory kill); the server panel counts the week's starts by cause (`restarts_7d`) |
| `Watchdog` | the database and alert-state locks must be free within 15 s; a held lock logs every thread's stack, five in a row (~2 min) → exit, Fly restarts it; a starved process is only logged (load, not a deadlock) | 20 s |
| `Digests` | each night (18:00–08:00 Kyiv) after `digest_hour`, and each Monday for the week: the figures (`State.digest_facts`), and with `ANTHROPIC_API_KEY` a written summary in EN + UK; stored in `digests` | 5 min check |
| `Translations` | machine-translates feed posts into a language somebody reads | on demand, ~3 calls/s max |
| `bulletins` | 1.54, with `OPENROUTER_API_KEY`: the AI's bulletins (§7.11) — on the clock, the last hour and the last 24 hours once an hour at :00 (1.56.1; the last hour was every 20 minutes), only while there is activity, one call each in three languages → `ai_bulletins`; or one the dashboard asks for. (Until 1.53 an `ai-reader` thread read the posts — §7.7; retired) | 20 s; ≤ `ai_reader_monthly_usd` a month |
| `night-reports` | 1.53: after `ai_report_hour` (Kyiv), the AI's report on the night before (§7.10) → `ai_reports`; or a night the dashboard asks for | 5 min |
| `Pusher` | sends Web Push: one notification at a time, each to all its phones at once through `push.Sender` (32 workers, one kept-open HTTPS connection per push service per worker, VAPID signed once an hour per service) | queue |
| `streams` | **every open page's live line** (`StreamHub`, §5.4): one thread, non-blocking sockets (epoll), the data sent as changes | events + every 15 / 5 / 2 s |
| `proximity` | per-subscriber distance checks → push | continuous |
| `warm` | 1.58.3: 45 s after a start, `/api/stats`'s 14 days once in the background — the first ask after a start parsed four days of posts for the explosions while a reader waited (16.6 s after the 1.58 deploy) | once |
| `channel` | 1.58, with `TG_BOT_TOKEN` and `TG_CHANNEL_ID`: the owner's private Telegram channel (§9c) — a post per target over Kyiv and its oblast with the map around it (`mapshot.py`); 1.58.7: a new post for each new report, in reply to the last, then what became of it (an outcome, the official all-clear, no new reports); at most 18 calls a minute | 5 s |
| `AlertsInUa.backfill` | a month of history for the favourite regions | once at start |
| `AFBackfill` | the Air Force summaries of the last 14 days that `af_reports` lacks: first from the stored feed, then from `t.me/s/kpszsu?before=…` pages (at most 240, stops once nothing is missing); since 1.33 also the carriers (`parse_air_report`) in every stored post, once per parser version (`kv.air_parsed`) | 60 s after start, then daily |
| `bridges` | every 5 s: a Kyiv bridge whose state rose (nothing → near → at, §9b) is written to `bridge_events` and pushed to the phones that asked for the bridges (topic `bridges`, in their language), at most once per bridge every 10 min — a "near" turning "at" excepted | 5 s |
| `patterns` | 1.55 (§7.12): each tagged target's moves, from one reported position to the next (`target_points` → `track_moves`, kept for good): the last two days' nights again every hour, and once per `MOVES_VERSION` every night whose points are all still kept | 90 s after start, then hourly |
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
download the marks, the feed and the alerts again — five requests per page per post. On the 256 MB machine of
the time Linux allowed ~2,000 threads, so ~1,700 open pages was a hard stop, and the CPU cost grew with pages ×
posts.

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
    `unset` = keys of `oblasts` and `sources` that changed, `set` = other values whole. (1.46: `sources` is
    `{name: {ok}}` — the time of each reading changed at every poll and was resent to every page at every beat;
    the detail is the dashboard's, `/api/health`.)
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
| `telegram_channels` | the six of 1.42 | Informational only — `AUTHORITATIVE_CHANNELS` in code is what is read. |
| `favourites` | `["31","14"]` | Regions for history backfill and desktop notifications. |
| `history_backfill_hours` | `6` | History pulled at start. |
| `desktop_notifications` | `true` | Local desktop notifications (when running on a PC). |
| `deepl_key` | `""` | DeepL API key for EN/FR translation of the feed. |
| `google_translate_key` | `""` | Google Cloud Translation key (alternative). |
| `ai_key` | `""` | Anthropic API key for the written summaries of each night / week (dashboard). |
| `ai_model` | `"claude-sonnet-5"` | The model that writes them. |
| `digest_hour` | `9` | Kyiv hour after which last night is written up (the Air Force morning summary is out by then). |
| `access_key` | `""` | Locks the WHOLE app behind a key — private deployments only. |
| `esri_key` | `""` | Esri (ArcGIS Location Platform) API key: the satellite layer's closest zooms, 14–18 (1.48, §10.1). Set as `ESRI_KEY` by `scripts/set-esri-key.bat`. |
| `esri_monthly_tiles` | `1800000` | Esri tiles a month, at most — under the 2 M free tiles; a tenth of it in one day at most. Past it: Sentinel alone. |
| `openrouter_key` | `""` | OpenRouter API key: the AI (1.50, §7.7; 1.54 the bulletins, §7.11, and the night's report). Set as `OPENROUTER_API_KEY` by `scripts/set-openrouter-key.bat`. |
| `ai_reader` | `true` | `false` keeps the AI off even with a key. |
| `ai_reader_model` | `"anthropic/claude-haiku-5.5"` | Its model on OpenRouter (any model that takes a strict JSON schema). |
| `ai_reader_monthly_usd` | `10` | What it may spend in a calendar month (UTC), counted from OpenRouter's own cost of each call; past it, it stops until the 1st. |
| `ai_report_hour` | `9` | 1.53: the Kyiv hour after which the AI writes its report on the night that began the day before at 12:00. |
| `demo` | `false` | Fake alerts and posts. |

### 5.3 Environment variables

Environment variables win over `config.json`. On Fly they are set as **secrets** (`fly secrets set …`).

| Variable | Meaning |
|---|---|
| `PORT` | Listening port (Fly sets it). |
| `DB_PATH` | SQLite file (Fly: on the volume). |
| `SAT_TILES` | The satellite layer's MBTiles file (1.47). Default: `sat-ua.mbtiles` next to `DB_PATH` — on Fly, `/data/sat-ua.mbtiles` on the volume. |
| `CONFIG_PATH` | Alternative `config.json` location. |
| `ANDROID_CERT_SHA256` | 1.57.6: the SHA-256 fingerprint(s) of the Android app's signing key (§10.8), as keytool or apksigner prints them, several separated by commas — set with `scripts/set-android-key.bat`. Public, not a secret. Unset: `/.well-known/assetlinks.json` is an empty list. |
| `ANDROID_PACKAGE` | 1.57.6: the Android app's identifier, default `com.blackflamestudio.heimdall`. |
| `ADMIN_KEY` | Protects `/admin` and its APIs only. The map stays public. |
| `ACCESS_KEY` | Puts the whole app behind a key. **Never on the public app.** |
| `ALERTS_IN_UA_TOKEN` | alerts.in.ua token. |
| `UKRAINEALARM_KEY` | Official ukrainealarm API key. |
| `DEEPL_KEY` | DeepL key (`…:fx` = free plan → api-free.deepl.com). |
| `GOOGLE_TRANSLATE_KEY` | Google Cloud Translation key. |
| `ANTHROPIC_API_KEY` | Turns on the written summaries of each night / week on the dashboard (`ai_key`). |
| `AI_MODEL` | Overrides `ai_model`. |
| `ESRI_KEY` | Turns on the satellite layer's closest zooms (Esri World Imagery, `esri_key`, 1.48). Set only by `scripts/set-esri-key.bat`. |
| `OPENROUTER_API_KEY` | Turns on the AI reader in shadow mode (`openrouter_key`, 1.50, §7.7). Set only by `scripts/set-openrouter-key.bat`. |
| `AI_READER_MODEL` | Overrides `ai_reader_model`. |
| `TRANSLATOR` | `google` (default) allows the free Google endpoint as last resort; anything else disables it. |
| `TG_API_ID` | Telegram API app id (my.telegram.org). |
| `TG_API_HASH` | Telegram API app hash. |
| `CANONICAL_HOST` | The app's own address (e.g. `heimdall.com.ua`). Pages opened elsewhere show the move banner (§9). Set by `scripts/set-domain.bat`. |
| `TG_SESSION` | The signed-in Telegram session (a key to that account). Set only by `scripts/telegram-login.bat`, via `fly secrets import`. |
| `TG_BOT_TOKEN` | 1.58: the owner's bot (@BotFather) that posts in his private channel (§9c). Set only by `scripts/set-telegram-channel.bat`, via `fly secrets import`; never logged. |
| `TG_CHANNEL_ID` | 1.58: that channel's id (`-100…`), found by the same script. The channel runs only when both are set. |
| `PUBLIC_URL` | 1.58: the address the channel's posts link to (`/m`). Default `https://kyiv-air-watch-gb.fly.dev`. |

Secrets live only in `config.json` (git-ignored) or in Fly secrets. They are never committed, never printed
by the scripts, and `.dockerignore` keeps `config.json` out of the image.

### 5.5 What the process spends its CPU on (1.46)

Measured on 7 Oct 2026 with py-spy on a copy of the service, the channels read at the ballistic cadence (every 5 s),
the feed of that evening loaded: **87 % of the CPU went into building TLS contexts.** `urllib.request.urlopen()`
without a `context` makes a new one per request and loads the system's ~150 root certificates into it — 15–25 ms of
CPU each time, for each of the ~20 channel previews and the alert sources, every round. One shared context
(`server._SSL_CTX`, `translate._CTX`, passed to every `urlopen`) took the process from 10 % of a core to 1.6 %; with
500 pages on the live line and a full page load every second, 4.1 % and 113 MB of memory. This is very likely what
spent a shared vCPU's burst balance on attack nights (§15, "throttling") before 1.41.1 moved to a dedicated CPU.

Also in 1.46: the pages' state carries whether each source works and nothing more (§5.4); the oblasts a post
names are read once per post (`State._named_cache`, they were ~40 % of each rebuild of the marks); `/api/places` is
built once an hour per set of oblasts and sent gzipped (`State.cached`), and the Tactical page asks for
`oblast=all` only when the villages layer is turned on (`loadVillages`); SQLite runs `synchronous=NORMAL` (with
WAL: a sync at each checkpoint, not at each commit).

Not changed, already economical: the live line (one thread, one serialisation per combination of parts, deltas),
the 304s on static files, Web Push's pooled connections.

### 5.6 Zooming the map (1.49)

The map is one SVG in kilometres; the view is its `viewBox`. Measured in Chromium with the CPU slowed 4× (a mid-range
phone), a pinch of 200 frames: **every change of the viewBox restyled every element sized by `--k` and laid out every
label again** — 50 ms a frame (20 fps), the main thread busy 100 % of the time (style 49 %, layout 28 %). A change
of scale lays the SVG's text out again even when it is only a CSS transform of the SVG or of an element around it.
So, while a pinch or the wheel goes on (`zoomAt(…, true)` → `fastVB`), the map drawn last is moved and scaled on the
screen with a CSS transform (`svg#map`, `will-change:transform`, from its top-left corner), the names of places are
hidden for that moment (`svg.zoomg :not(.mk)>text`; the marks and their labels stay), and 150 ms after the last
movement the new view is drawn once (`applyVB()`). The view's arithmetic uses the map's box without the transform
(`SR()`). Result: 16.7 ms a frame (60 fps) on the slowed phone and on a computer, the main thread busy 20 %; the
redraw at rest costs one frame of ~70 ms. A one-finger drag still moves the viewBox (no change of scale: cheap).

**1.54.3, the owner: "sometimes the map flickers when I zoom in or out"** — black patches over the map, the left column
blank. The scaled map is one GPU picture only while nothing inside it moves; every mark's halo, a blinking glyph, a
marching course ray made the browser draw the whole map again at every frame, at the scaled size — and a long wheel zoom
scaled it to many times the screen, more than the GPU keeps. Now, while the gesture lasts, every animation inside the
map is paused (`svg.zoomg *{animation-play-state:paused}`), and a scale past 3× or below ⅓ is drawn again at its own size
at once (`fastVB` → `applyVB()`), so the scaled picture never grows past three screens. The glow of an oblast with a
target somewhere in it no longer breathes (a large clipped area repainted 60 times a second for nothing a reader
needs).

Tiles: the tiles of the zoom before stay under the new ones until all of these have loaded or failed (`tileSweep`,
4 s at most), so a change of zoom never shows the black background between two pictures.

**Zoomed in, nothing large is dashed or animated** (`svg.deep`, past ~90 px a km). Chrome draws a dashed line dash by
dash along its whole length — the 50 km ring around Kyiv is 25,000 dashes at 1 km across — and an animated one again
at every frame: 1.48 could stall a computer's page ("page not responding") at the closest zooms. There the rings,
the zones, the occupied areas' outline, the region rings, the reach and course rays and the tracks are drawn solid
and still, the occupied areas in a plain tint.

**Lengths sized by the zoom keep their digits** (`kx()`, `KDIG`): with two decimals, at 1 km across a drone's
`scale(0.0007)` was written `scale(0.00)` and the mark vanished; marks are placed to the metre.

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

**The history of the alerts** (1.58.4): `State.alert_rows(start, end)` — one row per alert, in the alerts table's shape,
rebuilt from the `start` / `end` events (`_alert_intervals`, the replay's own reading: a restart closes what was not
started again within five minutes of it; an alert with no end written and not on now is left out, never counted to
now; one over within a minute is a source's flicker, not an alert — an official channel read from 15 to 24 September
2026 flipped Kyiv's alert 1,290 times, ~17 s each). The stats (`/api/stats`), the dashboard's analytics (Kyiv's minutes, the starts, the oblasts' hours), the lead
times, the nights' summaries, the AI's records (bulletins, night reports) and the digests read it. Until 1.58.4 they read
the alerts table, whose one row per region kept the region's first start: Kyiv city was "under alert" 1,440 minutes
a day from mid-September and "the longest alert" ran from 24 September to 12 October (20,131 minutes).

### 6.6 What decides a colour, page by page

- **Tactical**: each raion shape is coloured by alerts with its `raion_key` (fallback: name stems); an
  oblast-wide alert colours all its raions. The banner uses the watched oblast pair (city ⇄ oblast) plus the
  home's own raion (found by point-in-shape on the map's outlines). The calm line never says "no alert in the
  oblast" while any raion of it is under one.
- **Light**: see [§10.2](#102-light-light).

## 7. The Telegram feed and the map marks

### 7.1 The channels

The defaults are in code (`AUTHORITATIVE_CHANNELS` — deployed configs list 33 channels, and a config
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
  counting at once; at most 40 channels.

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
| `kudy_letyt` | all of Ukraine, added on the dashboard (1.58.15) — lists: an oblast or city heading ("Київщина:", "Київ:"), then a target a line, "2х БпЛА курсом на Кременчук" | general `parse_post`; a list is never news by its length (`looks_like_target_list`); "залітає на Чернігівщину" is in that oblast; "по межі з Харківщиною" is not |
| `eRadarrua` | per-oblast group counts + live lines | `parse_eradar`, `parse_eradar_summary` (counts on oblast tags, never marks) |
| `kpszsu` | the Air Force | general parser + its summaries, read weapon by weapon (`parse_af_report`, §7.5) |
| `chernihiv_nebo` | live tracker of Chernihiv oblast (1.43) | `_parse_live(·, "25")` — Chernihiv's villages; "2 реакти … 1 реакт …" = two reports |
| `monitoringodesa` | live tracker of Odesa oblast, **in Russian** (1.43) | `_parse_live(·, "18")` after `geo.prepare` (§7.3b); bare village names |
| `chyste_nebocherkasy` | live tracker of Cherkasy oblast (1.43) | `_parse_live(·, "24")`; its preview is off like `chyste_nebo`'s — read through the Telegram API when it is configured (`CHANNEL_VIA_DEFAULT`) |
| `radar_kharkov` | live tracker of Kharkiv city and oblast, **in Russian** (1.43) | `_parse_live(·, "22")` after `geo.prepare`; the city's districts by their Russian names |
| `RadarDnepr` | live tracker of Dnipro city and oblast (1.43) | `_parse_live(·, "9")`; mixed with news and fundraising, which the news guard drops |
| `kabusumy` | live tracker of Sumy city and oblast — guided bombs (KAB) and drones by village (1.44) | `_parse_live(·, "20")`; its preview is off — read through the Telegram API (`CHANNEL_VIA_DEFAULT`); "Впали" after a KAB report is an impact, never a shoot-down |
| `air_alert_mk` | Mykolaiv oblast: the Air Force's lines for the oblast and a few of its own (1.44) | `_parse_live(·, "17")` → `parse_post`; no village-level tracker of Mykolaiv was found |
| `PoltavaRadar` | live tracker of Poltava oblast (1.44) | `_parse_live(·, "19")`; "Не фіксується." = lost; "з Дніпропетровщини на X" reads X in Poltava oblast first |
| `vinnytsiappo` | live tracker of Vinnytsia oblast (1.44) | `_parse_live(·, "4")`; its signature line ("💪 Телеграм канал ППО Вінниця") is cut before parsing (`translate.strip_promo`) |
| `zt_radar` | live tracker of Zhytomyr oblast, small and occasional (1.44) | `_parse_live(·, "10")`; "То свої" = ours, not kept |
| `kherson_monitoring` | live tracker of Kherson oblast: drones, FPV, "Ланцет", "Молнія", by village and raion (1.45) | `_parse_live(·, "23")`; artillery ("артобстріл … з ТОТ") is not in the sky and is not kept (`ARTY_RX`); injury reports are news |
| `controlkrop` | live tracker of Kirovohrad oblast (1.45) | `_parse_live(·, "15")`; "Область:" heads a list of reports; "вилітають на Черкащину" is where they go |
| `radarhmel` | live tracker of Khmelnytskyi oblast (1.45) | `_parse_live(·, "3")`; "Шепетівський район" is its centre town (raions, §7.3b); "зникає … появляється" is not a lost target |
| `radarofternopil` | live tracker of Ternopil oblast (1.45) | `_parse_live(·, "21")` |
| `rivne_radar` | live tracker of Rivne oblast; follows its targets into the next oblast (1.45) | `_parse_live(·, "5")`, with `near` (§7.3b); its raion alert notices ("Тривога — Вараський район") are not marks |
| `ppoualviv` | live tracker of Lviv oblast (1.45) | `_parse_live(·, "27")` |
| `lutsk_radar` | live tracker of Volyn oblast (1.45) | `_parse_live(·, "8")` |
| `vseok450` | "4.5.0", live tracker of Kyiv and its oblast, 12K readers (1.57.3, the owner's choice) — **on trial by default** (`CHANNEL_MODE_DEFAULT`): its posts in the feed, flagged, nothing on the map, until the owner puts it on the map from the dashboard | `parse_kyiv_airdef`; its posts are short lists of places and counts ("Яготин / Богуслав / 3 Чернігівська", "1-й до Чабанів", "Обухів/Українка 2 з півдня"), no weapon named (read as "probably a drone"), "Відбій" (never ends an alert), "Цього нема." (the previous one is gone). On 11 Oct the rules read the places of a bare list and "до X" but not yet the counts, "з півдня" after a pair of places, or a list under a sentence — to be taught from its posts on trial |

**A channel's mode until the dashboard sets one** (1.57.3): `map`, or `CHANNEL_MODE_DEFAULT` — a new tracker starts on
trial; the dashboard's choice, once made, is kept (`kv.channels`).

**The oblasts as compartments (1.43).** Every channel belongs to the compartment of the oblast it speaks for (its
`home`): an oblast uid, `31` (Kyiv city and Kyiv oblast) or `ua` (the country-wide channels) —
`CHANNEL_HOME_DEFAULT` for the defaults, chosen when a channel is added, changed from the dashboard. The dashboard
shows the channels oblast by oblast and switches a whole oblast on or off (`State.region_set`, kv `regions`, which
stores only what differs from the default). An oblast switched off leaves the map — `SCOPE_UIDS`, read by
`in_scope()` — and its channels are not read (`channel_mode()` answers `off` for them); `31` cannot be switched off.
By default the map covers Kyiv, the six oblasts around it, and the four farther out with a tracker of their own:
Odesa, Kharkiv, Dnipro, (1.44) Mykolaiv and (1.45) Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne, Lviv, Volyn
(`DEFAULT_SCOPE`). 1.44: every oblast on the map except Kyiv's has its own tracker — Chernihiv, Cherkasy, Odesa,
Kharkiv, Dnipro (1.43), Sumy, Mykolaiv, Poltava, Vinnytsia, Zhytomyr, and (1.45) the seven above. The pages follow: `state.scope` decides which oblasts are painted raion by raion
(`scopeRegs()`), the place lists ask `/api/places?oblast=scope`, and the Near list keeps to `NEAR_MAX` = 350 km of the
reader's place (a ballistic mark is "the whole region" only within `REGION_R` = 150 km). A channel's home is also how its posts are read (`geo.CHANNEL_HOME`, §7.3b), and
the posts of a regional channel carry `home` in the feed: the Tactical page raises a regional channel's ballistic or
MiG-31K report only for a reader whose oblast — picked, or of a watched place — is that one.

**1.56.6: a missile post is for the oblasts it names.** The Air Force's "🚀Швидкісна ціль на заході Донеччини, курс на
північ" raised "ballistic — shelter now" in Vyshenky and turned the Voronkiv target into "drone or missile" (the owner:
"the banner alarms the user for nothing"). `missile_obls(post_id, channel, text, tags)` gives, for a post tagged
`ballistic_missiles` or `cruise_missiles`, the oblasts it names: `geo.oblasts_named()` (the oblasts written out) and the
`oblast_uid` of every mark `geo.parse_for_channel()` reads in it (a town's oblast), `31` folded into `14`, `ua` dropped;
cached by post id and text (an edited post is read again). `Store.feed` adds them to the post as `obl`. The warning
strip (`threatStrip`) skips a post with an `obl` none of the reader's oblasts (`myOblasts()`, Kyiv city counting as its
oblast) is in — a MiG-31K take-off excepted, its missiles reach everywhere; a post with no `obl` warns everyone, as
before. `State._missile_active()` skips a post whose `obl` misses the oblasts on the map (`SCOPE_UIDS`), Kyiv and the
favourites: the level sets every reader's cadence, so it follows the map, not one reader. The official alerts are never
filtered this way — only the official data sets an alert.

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
відбутись у будь-який момент", and since 1.41.2 what the enemy "plans": "ворог планує запустити …" — never raise
anything), then the news guard (`geo.looks_like_news`: strong news words, reported speech and consequences, length,
summaries, and since 1.41.2 `looks_like_explainer` — a live tracker talking *about* the sky: "до прикладу",
"розповім про балістику", "по цій темі", "я описую ціль", "якщо ціль знищена …", "ворог планує"), then threat
tags. `parse_for_channel` applies `looks_like_explainer` to every channel's parser, so none of it is ever a mark.
1.42.1: **a retraction** comes before all of it (`is_retraction()`): a glitch of the system ("лаг системи", "збій
системи", "хибне спрацювання") on its own, or "not confirmed" / a false alert about something missile-shaped (a speed,
a launch, a rocket, a MiG) — "Хибна ціль" is not one, that is a decoy, which flies. It is tagged `retract` and nothing
else, kept (`is_relevant`), and it ends what the channels said before it: a ballistic or supersonic mark of the 20
minutes before (`_drop_retracted()`, also in the replay), the missile mode (`_missile_active()` stops at it), and the
warning strip's channel-raised ballistic / MiG-31K warnings. Never an official one — only the official data ends an
alert. "… не підтвердився" about anything else is an explainer: no mark. `banderol_missiles` removes
`cruise_missiles` and `unspecified_missiles`.

### 7.3 From post to mark (`geo.py`)

`parse_for_channel(channel, text)` picks the channel's parser; each returns candidates with an **evidence**
block for every value:

- **Type** — `TYPE_RX`: drones (Shahed / Geran / "мопед"), jet drones, cruise, ballistic, supersonic
  (Kh-22/32, before cruise), `banderol_missiles` (Banderol / S-8000 / "реактивні ракети з БпЛА"), KAB, tactical
  and strategic aviation, MiG-31K. No type word → `unknown` (drawn as an upright ⚠, never guessed).
- **Position** — the gazetteer with declension-aware stems (hyphen lookbehind: `Коцюбинське` ≠
  `Михайло-Коцюбинське`); aliases like "Велика Димерка" ← "димерк"; a stated part of an oblast is not its centre.
  1.56.3: the core gazetteer's coordinates (`geo.PLACES`, written by hand) checked against OpenStreetMap's settlements
  (`static/streets/`): 82 of 379 matched names were more than 1.5 km off and are where OSM puts them now — Гнідин was
  5.8 km east of the village (the owner: "Hnidyn is never reported there"), Березань 11 km, Ольшаниця 12, Мигалки 14,
  Котельва 19; Красилівка and Ясногородка, several of each, are the one near Brovary and the one near Makariv.
- **Heading** — "курсом на", compass words, "→", "A - B" routes (`bearing()`); a heading is marked *stated*
  only when the post stated it. A compass word after "з / зі / від" is where it comes **from** ("з півночі" = flying
  south), also after the destination (`_FROM_COMPASS`).
- **Where it is vs where it is going** (`_place_role`): a place after "на", "в район", "до", "в напрямку", "в бік"
  is the **destination**; after "від", "з", "повз", "над", "біля", "в районі" it is where the target **is**. After
  "на", a place in the locative ("на Позняках", "на Троєщині") is where it is. Only a destination named
  ("на Васильків з північного заходу", "курсом на Київ"): the mark is drawn **at the destination as an approach**
  (`approach: true`, `place: "→ X"`, low confidence) — also when the post's only other place is its own oblast
  heading. On live channels, "Від Глевахи на Васильків" is at Hlevakha heading for Vasylkiv; "йдуть на Васильків"
  alone (`dest_only`) stays at the channel's previous report (≤ 8 min) turned toward the destination — 1.58: only a
  report of the same weapon (`same_weapon`: the same type, or a drone and a weapon not named) —, or else is an
  approach. In tracking, a later approach about a target already on the map gives it its destination and course
  instead of moving it; an approach point is never a step of a track. 1.58.6: a part of the oblast the post placed it
  in ("на сході Київщини, в напрямку столиці") is where it is — the oblast centre shifted ~70 km to that side, with
  its `quad` — and the destination is its course (`side_stated`); the side is never read as the course.
- **Count**, **altitude** (only when written: "знижується", "низько", metres "висота 2200", a bare "1600, Вороньків"
  in a short live post, kilometres "висота 4,4км", 1.58.9: "на 300 метрах" / "на 400 м" — not "на 300 м від …", a
  distance), **phase** (`PHASE_LADDER`:
  prep → launch → entering…, with a per-sentence hedge guard: "може відбутись" is preparation, not a launch).
- **The oblast, then its towns** (1.42.1): "курсом на Київщину, Макарів / Наливайківку" — a town the post names
  right after the oblast it is in is the destination, not the oblast's centre.
- **The next target** (1.41.3, `_split_next`) — an outcome followed by a sentence starting "наступний", "ще один",
  "другий" or "інший" ("1 знищено.\nНаступний Нивки") is two reports. The outcome keeps only its own words (on a live
  channel the previous position, `needs_context`; otherwise no mark); the place after the word is the next target's
  position, never an outcome. Read whole, it was a confirmed shoot-down at Nyvky, shown 24 h in the history layer.
- **Immediate types** — `IMMEDIATE_TYPES = {ballistic, supersonic, mig31k}`, `REGION_ALERT_KM = 150`.

### 7.3b The regional trackers: their villages, their Russian (1.43)

A regional tracker names villages and city districts post after post ("2 реакти від Куликівки на Лихачів",
"Стрюково", "БпЛА на Лесное - Пятихатки"). **`data/regional_places.json`** holds every populated place of the
oblasts that have a channel of their own (Chernihiv, Cherkasy, Odesa, Kharkiv, Dnipro — about 6,700; 1.44: and Sumy,
Mykolaiv, Poltava, Vinnytsia, Zhytomyr — about 13,800; 1.45: and Kherson, Kirovohrad, Khmelnytskyi, Ternopil, Rivne,
Lviv, Volyn — about 19,000 in all), built by
**`scripts/build_places.py`** from the GeoNames dumps (<https://www.geonames.org>, CC BY 4.0): Ukrainian name,
coordinates, kind (city section / raion or hromada centre / place), population, raion, and every Ukrainian and
Russian name GeoNames has, plus the Russian-looking spellings of the Ukrainian name (і as и / е / о, `'я` as е, no
apostrophe — `_ru_variants`). Kharkiv city's districts are named by hand in the builder (`CURATED_BY_NAME`).

- They are answered by `PLACES[name]` like any place (`_Gazetteer`) but never iterated: not in the regex index, not
  in the map's town labels, not in `/api/places`. **They are matched only in their oblast's context** — a post from
  a channel whose home is that oblast, or a sentence that names the oblast (`_find_places(text, ctx_uid)` →
  `_find_regional`). "Іванівка" alone, from Kyiv, is nothing.
- Words that are also a village's name are never read as one (`REGIONAL_STOP`: the compass, the border, "new", 1.43.1
  "буде / будет" and the alert levels "жовтий / червоний" …; `_REG_PAIR_STOP`: a verb is never half of a two-word name —
  "новий буде" is not Нова Буда; an oblast's adjective "Київська / Черкаський" is never the village "Київське",
  `_ADJ_NOT_NEUTER_RX`); `REGIONAL_WORDS` gives a bare word its oblast's meaning ("Водосховище" from Chernihiv = the
  Kyiv reservoir).
- 1.43.1: **a core town of the next oblast against hamlets of its name** — "На Таращу" from the Cherkasy tracker is
  the town of Тараща (Kyiv oblast), not the hamlet in Cherkasy oblast: when every village of the channel's oblast with
  that name is a small place (kind P, < 2,000), the name becomes an ambiguity token with the core town as its default
  and the villages as the other candidates (so the channel's previous report or the post's other places can still
  pick the village).
- **A name several villages share** becomes one ambiguity token (`_ambig_token`) with its candidates: the one near
  another place the same post names (≤ 60 km) wins at once; otherwise the server takes the one nearest the channel's
  report of the last 30 minutes (≤ 60 km, `_marks_from_posts`); with neither, the clear default — the only city
  district, the only raion/hromada centre, or a population three times the next — or **no mark at all**. A
  destination nobody can tell apart gets no course drawn to it.
- **Routes**: "Любеч-Славутич", "Сновськ-Березна-Куликівка", "Лесное - Пятихатки" — two places joined by a dash are
  at the first, heading for the second (`_route_arrows` writes "→"), unless the joined word is one place
  ("Новгород-Сіверський") or it follows "в районі / між" ("в районі Котельва - Коломак" is an area, not a course).
- **One line, several reports**: a count of weapons after the words of the previous report starts a new one
  ("2 реакти … 1 реакт …"), so does ", 1 …" ("1 Райгород, 1 Буки на Бузівка, 1 на Привітне").
- Words: "реакт / реакти" (a jet drone, `JET_RX`), FPV, "Молния", "Ланцет" (small strike drones).
- 1.44: **an oblast named as the origin** — "Реактивний БпЛА з Дніпропетровщини на Світлогірське" from the Poltava
  tracker: after "з / із / від", the oblast is where it came from, and the sentence's villages are read in the
  channel's own oblast (`parse_post`, `home`). "в сектор / секторі A - B" is an area, not a route (`_AREA_PRE`).
  "високо / низько / далі" are never villages (`REGIONAL_STOP`); "Не фіксується" at the start of a sentence is a
  lost target (not "загроз не фіксується"). A channel's signature line — "X | Підписатись", "💪 Телеграм канал …" —
  is cut before the post is tagged or parsed (`translate._SIGN_LINE`), never its first line.
- 1.44.1: **a list after "в бік / курс"** ("в бік Велика Рибиця/Мала Рибиця/Осоївка", "на Димерку, Бровари") is a list of
  places it may be heading for: every name joined by `/`, `,`, "або / чи / і" to a destination is a destination
  (`_LIST_SEP_RX` in `_parse_live`) — read as a bare name, the second one became where the target was. 1.56.4, the
  owner: "Jet UAV to Kyiv/Irpin/Bucha — the post is talking about Bucha, yet the drone is put in the middle of the
  city": a target heading for a list and nowhere stated is drawn, as an approach, at the one `geo.approach_pick`
  chooses — in Kyiv and its oblast not the city when its suburbs are named with it, and of the rest the farthest from
  the centre (a target heading for all of them reaches the outermost first); elsewhere the first named, as before —
  and the mark keeps the whole list (`targets`), which the pages say as written ("heading for Київ / Ірпінь / Буча",
  `apprTo` in `i18n.js`). Four-letter names keep their last vowel in the stem, so "на Бучу", "у Бучі" were no place
  at all: their cases are written out in `ALT` (Буча, Ічня, Кілія; Мена as "Мену" only — "мені" is "to me"). A segment that
  names no place and says the target left ("вилетів з області") or is coming from outside ("підлітає до нас / до
  області") is no position (`_EXIT_RX`), nor is "Дорозвідка". "В. Михайловка" / "М. …" are Велика / Мала
  (`_REG_ABBR_RX`); a Russian name declined like an adjective is matched in its cases ("Раздельная" → "Раздельной",
  "Раздельную"). "Буялык" is Великий Буялик (`CURATED_BY_NAME`).
- 1.44.1: **the weapon a channel named last** (`weapon_by_channel` in `_marks_from_posts`, 15 min): "Пуски КАБів в
  нашому напрямку" names no place and the reports after it name no weapon; a "Впали" placed at the channel's
  previous report is then an impact of guided bombs, never a shoot-down. Guided bombs keep the standard clock
  (5 / 15 min), not the regional one.
- 1.43.1: **our own aircraft** (`geo.drop_friendly`): a sentence about "наш / свій БпЛА, дрон, борт, літак …"
  ("Акустика нашего БпЛА над Харьковом") is dropped before parsing and tagging; a post with "то наш / це наші / это
  наши" as a sentence of its own is about nothing hostile and is not kept. "Без фиксации", "Больше не фиксируется"
  (`більше не фіксується`) are a lost target (`STATUS_RX`).
- 1.45: **a town it is heading for is never the oblast centre.** "Чернігівщина: … / 3 реакти на Славутич з півночі"
  put three jet drones in the middle of Chernihiv oblast: a sentence that names where it is going and nowhere it is
  is drawn as an approach to that town (`parse_post`: `in_obl or (target and cm and not from_obl)`), whatever oblast
  heads the post. Only an oblast it comes **from** ("БпЛА з Чернігівщини курсом на Київ") is still the place — and
  such a place is a region on the map, not a point (§7.4). "вектор / вектором" is a course word ("2х вектор Велика
  Димерка/Бровари"). The lines of a multi-line post stay lines (`_drop_clear_sentences` keeps the separators), and a
  line that names no place, no oblast and no weapon ("‼️Увага!") is not a report of its own.
- 1.45.1: **a side of a town is not the town** (`_rel_settle`): "на півночі від Миколаєва", "північніше Харкова",
  "на північному заході від Броварів" name a reference and a side. With a distance ("за 20 км на північ від …") the mark
  is moved that far that way (medium confidence). Without one, a side of an oblast's capital (`_OBL_CAPITAL`) is the
  oblast — `place == "область"`, drawn on the region (§7.4) — and a side of any other town stays at the town with low
  confidence. Either way `evidence.position` carries `rel` (degrees) and `ref`, and the pages write "north of
  Mykolaiv" (`oblWhere`, `rq` / `rq_of`). The offline translation reads "на півночі від X" as "north of X".
- 1.49: **Kyiv named and no place in it is the city, not a point** (`_city_settle`): "над Києвом", "біля Києва", "на
  околицях правого берега Києва" were drawn at the city's centre, "town in gazetteer, high confidence, ±5 km" — a
  city 30 km across, and a resident read a drone over the centre that nobody had put there. Kyiv has its own outline,
  so it is marked like an oblast (`place == "область"`, `oblast_uid` 31, low confidence; §7.4), with the bank when
  the post names one (`evidence.position.bank`: "right" / "left" → "right bank · Kyiv"). A district, a street, a
  landmark, a distance or a side keep their point; a course to Kyiv ("→ Київ") stays an approach. The pages say
  "somewhere in the city" for it (`city_somewhere`, `city_noplace`).
- 1.45: **raions.** "Шепетівський район", "у Самбірському районі", "в напрямку Самбірського району" are read as the
  raion (`_RAION_RX` → `RAION_KEYS`): one pseudo-place per raion of a tracked oblast ("Самбірський р-н"), at the
  raion's centre town (the core gazetteer's first, never a power plant; `_load_raions`), with **low** confidence: a
  raion is an area. With a town it is heading for ("залітає у Гайсинський район … курсом на Теплик") it is an approach
  to that town, and no course is drawn from the raion's centre (`_raion_settle`). The pages write it "Sambirskyi
  raion" (`pn`). A raion alert notice ("Тривога — Вараський район", "Відбій — …") is a notice, not a mark
  (`ALERT_MSG_RX`).
- 1.45: **the oblast a tracker just named** (`near`): a tracker follows its target into the next oblast — "Це він на
  Хмельниччині", then "Далі на Плужне" (@rivne_radar). The oblasts a channel named in its last 30 minutes
  (`NEAR_CTX_MIN`; `near_by_channel` in `_marks_from_posts`, `Telegram._near_ctx` when tagging) are passed to
  `geo.parse_for_channel(channel, text, near)`; a post that places nothing in the channel's own oblast is read in
  them. **And the far filter**: a regional tracker's place more than 300 km from its oblast, in an oblast neither the
  post nor `near` names, is a misreading and dropped ("Велика Бобровиця", a village by Rivne, was the Бобровиця of
  Chernihiv oblast).
- 1.45: **names.** An exact alias wins over a stem ("Іванівка" is the one Іванівка by default where one is the hromada
  centre); a word declined like an adjective matches its town ("Кропивницького"); GeoNames' Soviet-era names are
  never the displayed one (`build_places.py`, `SOVIET`); "маякну" and other verb forms are not villages
  (`_VERB_TAILS`); "велика / мала / стара / верхня …" alone are never a village (`REGIONAL_STOP`). Artillery and
  mortar fire is not in the sky (`ARTY_RX`), and a report of the injured ("47-річний … поранення") is news.

**Posts in Russian.** The Kharkiv and Odesa trackers write in Russian. `geo.prepare(text, channel)` turns a post
from `RU_CHANNELS`, or one that `looks_russian()` (ы, э, ё, ъ, or a Russian-only word), into the Ukrainian words the
rules read (`ru_to_uk`, `_RU_MAP`: the weapons, the outcomes, the prepositions, the courses, the compass, the oblasts
— "Нико обл" is Mykolaiv oblast). Place names are not translated: the gazetteers hold their Russian names
(Харьков, Днепр, Чернигов … in `ALT`; the villages' in the regional file). The tagger reads the same Ukrainian
reading (`tag_feed_text`); the stored and shown text is never changed.

**Kyiv oblast's villages for the rules (1.54.7).** `data/extra_places.json` (1.52) was the AI reader's alone, and since
1.54 the AI reads no post: "Кулажинці" (@chyste_nebo, 10 Oct, 01:21, a drone at 400–500 m north-east of Brovary) drew
nothing. `_load_kyiv_villages()` puts the ~825 villages the core gazetteer does not have into the regional index of
oblast "14" (`REGIONAL`, `_REG_IDX["14"]`, kind P, raion as the key's suffix when two share a name), with
`KYIV_VILLAGE_STOP` for the ones that are everyday words ("Озеро", "Ферма", "Селище", "Кулі" …). They are read like any
regional channel's villages — in a Kyiv tracker's post (`_find_places(text, "31")` reads oblast 14's villages with the
city's: the one place of a name no town of the gazetteer has, or the candidates when several share it) and in a post
about Kyiv oblast — never in a long sentence from elsewhere. **A district of Kyiv and villages with its name** —
"лук'янівка" (01:12) was the village east of Brovary, not Lukyanivka in Kyiv — are candidates with the district as the
default (`_ambig_token`); the server takes the one next to the channel's report before (≤ 30 min) **and its report
after** (≤ 15 min, `State._reports_ahead`: the posts already read on this pass), the sum of the two distances, among
the candidates the target could have reached (`reach_km`, §7.4) — recomputed every pass, so the mark moves to the
village once "Кулажинці" is in. **A height alone** ("500", "400 м", "Увага 500", `geo._height_only`) is the height of
the target the channel reported last, within 15 minutes, at that report's place and time and of its kind
(`height_only`: carried by `_marks_from_posts` like an outcome line) — never a place of its own.

**A weapon not stated, in the app (1.54.8).** The owner: "'unknown' is badly worded — it is most likely a drone (a jet
Shahed); the only exception is when we know ballistic or cruise missiles are also coming". A mark of type `unknown` is
named by what else is in the air (`mslCtx(m)`: a missile on the map — `MSL_TYPES` — or a MiG-31K / ballistic /
strategic-aviation / cruise warning in the strip, `TS_TOP`; **local since 1.56.6**: a missile mark within `MSL_NEAR_KM`
= 150 km of the target — `MSLP`, the missiles' projected points, set by `mslPaint()` where the marks are painted — or
a strip warning, which is the reader's oblast's, with the target within 300 km of the reader's place; a missile in
Donetsk oblast no longer turns the drones around Kyiv into "drone or missile"): **"probably a drone"** on the map's label, the card's title
("Probably a drone — type not stated", `th_unk_dr`), its note (`unk_note_dr`: no missile reported right now, so most
likely a strike drone, a Shahed or a jet one), the Near list (`k_unk_dr`) and the counts (`lb_unk_dr`); **"drone or
missile"** (`unk_mix`, `th_unk_mix`, `unk_note_mix`, `k_unk_mix`, `lb_unk_mix`) while missiles are reported. The ⚠ sign
stays: the post did not say what it is. The Light page names it the same way (`lMsl`). **1.54.9, drawn as a drone** (the owner: "instead of the triangles, Shahed icons by default — outside a ballistic or
cruise missile context these threats are to be treated as drones"): `asDrone(m)` — an unstated mark with no missile
context (`mslCtx(m)`; until 1.56.6 one switch for the whole map, `MSLX`) — takes the drone's silhouette (`glyphKey`, `silSvg`, the oblast badges), colour
(`KIND_COL`) and class, turns to a stated course (`orientOf`), is counted with the drones, and its label is "probably a
drone" without the ⚠; the hover card and every other reader of `THREAT.unknown` (a getter) say "🛸 Probably a drone".
No ETA is worked out for it (`speedBand` has none for an unstated type): a jet drone flies 2.4 times as fast, and a
countdown on a guess could be late. While missiles are reported near it it is the red ⚠ "drone or missile" again. Light:
`lDr(m)`, with `lMsl(m)`: a MiG-31K or strategic aviation on the map, or `mslNear(m, marks)` (i18n.js: a missile mark
within 150 km).

### 7.4 Scope, chaining, staleness

`State.markers()`:

1. parses the recent feed into candidates; merges identical ones from the same post (a count). A live-tracking
   channel's bare line ("На Таращу", "Вибух", "Не спостерігається") is placed at that channel's last reported
   position (`last_by_channel`, at most 8 min old). 1.38: that position keeps **its own** time — the mark carries
   `pos_ts`, and a carried position never restarts the clock (only a newly named place does); the channel's own
   down / lost / clear line ends it; and the official all-clear for Kyiv city ends every position held inside the
   city (`State.kyiv_city_all_clears`: an end of the city's air-raid alert that left no other source's alert running).
   A live tracker's bare place with no course gets the bearing from its previous report (`last_by_channel`, ≤ 8 min,
   ≥ 0.4 km) — 1.56.3: only when that post and this one each report **one** target (`n_here`, the ctx's 4th field: the
   previous post's Kiptiv → this post's Liubech drew a target heading NW, back to Belarus — two targets, not a course),
   and never one that points back across the border (`outward`, below);
2. drops what is outside the scope: `in_scope()` = oblast uid in `SCOPE_UIDS` (1.43: the oblasts switched on —
   Kyiv, the six around it, Odesa, Kharkiv, Dnipro, 1.44 Mykolaiv, 1.45 seven more by default) or, with no oblast, within `SCOPE_KM = 330` km of
   Kyiv. `REGION_UIDS` (Kyiv and the six around it) still decides the feed's "region" tag;
3. `_chain_and_prune()` links consecutive reports of the same target (same family, time and distance windows,
   roughly ahead of the earlier heading) into a track with `history` — each entry keeps its own report's stated
   height (`alt_m`, `alt_state`), so the pages can show the heights the posts gave in sequence; marks `stale` after
   `track_stale_minutes`; drops an unknown after 5 min, others after `max(stale × 3, 15)` min — all counted from
   the position's time (`pos_ts`, else the post's); drops everything in an oblast with **no active alert of any
   kind** once 3 min old, and, in Kyiv city with no alert running, every mark reported before the last official
   all-clear there; missiles age on their own `MISSILE_TTL_MIN`;
   **1.43.1, the chaining windows** (`_chain`): a report continues a track of its own channel within 30 min, of
   another channel within **15 min**; two channels' unspecified threats (bare place names) are one target only at a
   drone's speed (7 km/min, not 15); a report naming only the oblast (`place == "область"`, drawn at the oblast
   centre) never takes over a report that named a place, a destination ("на Зміїв") is never handed to one, and its
   point is never a step of a track's history. Before this, the Kyiv channels' bare names — one a minute — took over
   every Odesa, Chernihiv and Kharkiv report within 475 km and 30 min, and those oblasts' reports were never drawn.
   **1.54.4, a drone's reach** (the owner: "not 100 % sure, but no wild assumption when the gap between two points is so
   huge" — #157, "Сквира" 00:29 then "Велика Димерка" 00:53, one track 150 km across Kyiv in 24 minutes): a drone's
   report continues a track only within `min(3.5 km/min × dt + 15, 80)` km — a Shahed's 210 km/h with a tailwind — a
   jet drone's within `min(9 × dt + 15, 120)`; an unstated type is a drone when it is a bare place name of a channel
   that tracks drones (`likely`) or another channel's; other unstated types and missiles keep `15 × dt + 25`. The
   tapped target's red dots (§7.8) leave out the line between two reports a drone could not have flown between, by the
   same measure — the dots stay (`drawSelPath`, `cut`).
   **1.54.7, the physical check** (the owner: "if attaching a new report to a target implies 1,000 km/h, reject the
   match — take the technical spec of the Shahed, the jet Shahed and the Banderol"): `reach_km(dt, jet)` =
   `VMAX_KMH` (350 km/h for a Shahed — 185 by its specification; 650 for a jet drone — the Geran-3 550–600, the Banderol
   about 500, 650 at most) × the minutes between the two reports + `POS_TOL_KM` = 8 km (two named places, each a few km
   from where the target was), never past `REACH_CAP_KM` (80 / 120 km; a Banderol has no cap). The minutes count from
   when the earlier report's **position** was reported (`pos_ts`: "500" carries a place nine minutes old). A Banderol
   is a jet drone here too (it had a missile's `15 × dt + 25`). The same reach decides between places that share a name
   (§7.3b) and leaves out a line on the card (`cut`: `d>(jet?650:350)/60*dt+8`).
   **1.43.1, the regional clock**: a report from a channel with a regional home (`geo.CHANNEL_HOME`) is `stale` after
   `REGIONAL_STALE_MIN` = 10 min and dropped after `REGIONAL_GONE_MIN` = 25 (an unknown after 10) — the trackers
   post every five to twenty minutes; it carries `slow: true`, and the map fades it on the same clock (grey at 10,
   fainter at 15, "contact lost" at 20). The oblast's all-clear still ends it at once;
4. outcomes (down, impact, lost) close the track they belong to;
5. 1.58.7, `State._hold`: a drone, a weapon not stated or a Banderol (`HOLD_TYPES`) whose post said only where it is
   heading (`approach`, `dest_only`, a place "→ Київ" — drawn at that place) is marked `held` while that place has no
   official alert (`areas.under_alert` with `areas.alert_fill` of `State.active`: the city, Kyiv oblast's raions, the
   oblasts and raions around — the shapes the pages paint; a point in no known shape is never held). The owner, of a
   jet drone the Air Force put "на сході Київщини, в напрямку столиці", drawn on Kyiv with no alert there: "alarm ALWAYS
   is better … why put a drone icon here, it's dangerous" — picked: off the map until the alert. The Tactical and Light
   maps do not draw a held mark; the Near list keeps it, without a distance, "position not stated — on the map once
   that place is under alert" (`mc_held`); no "near you" push is sent for it (`proximity_watch`). A missile is never
   held: its alert follows within a minute or two, and a ballistic warning must not wait for it.

**1.45: a target reported for a whole oblast is a region, not a point.** A mark with `place == "область"` ("БпЛА на
Харківщині", "з Чернігівщини курсом на Київ") still carries the oblast centre as its coordinates, for the server's
windows; nothing draws it there. The Tactical map puts it on the region with the outcomes of 1.38 (`OBLEVT`,
`paintOblEvents`): a dashed outline (1.51: for targets in the air, cyan — never the alerts' amber or red — over a hatching
that says "an area", blinking, and a chip with the tag, the weapon, the count, a stated height and the words "somewhere
in the oblast"; still under `prefers-reduced-motion`. 1.52.1: the hatching only on the whole-region view. 1.53.1, the
owner: "still unreadable — and not this cyan": a **white** dashed outline (dark in daylight) slowly fading in and out, no
hatching, and a compact chip — the weapon, the count, a height, "AI" when only the AI read it — right under the oblast's
own name; "somewhere in the oblast" is written under the chip from the regional view in (`svg.veryfar` hides it), and in
words on a tap. **1.54**, the owner: "this tiny square marking looks really bad": the oblast's own name **lights up**
(`#obllbl .oblbl.hot`, the names carry `data-o`), a **rounded badge** under it — the weapon's silhouette in its colour,
×count, a height, its border the weapon's colour — whose pieces are measured once drawn (`fitOblChips`: the phone's own
font never runs one into the next), and the oblast's **border glows from the inside** (`.obglow`: three wide strokes
clipped to the oblast, so only their inner half shows, and a thin solid line; breathing slowly, still under
`prefers-reduced-motion`): "somewhere in here", the middle of the oblast left clear for the targets placed in it. An
oblast drawn without a name (Kyiv oblast, the city, Sevastopol, Crimea: `OBL_UNNAMED`) carries it in the badge ("KYIV
OBL.", `ob_kyiv`); every outline is drawn before every badge; two badges never overlap (`layoutOblChips`, at each zoom:
the one of an unnamed oblast steps down); the town names under a lit name or a badge give way; 1.54.5, the owner: "too
big on a phone" — on a phone (< 1,000 px) a fifth smaller, `OBS()`: 19 px high instead of 24, its text 10.5 / 9.5 px), the posts one tap away
(`oblEventSheet`). The Near list keeps it without a distance, as "Chernihiv oblast ·
somewhere in the oblast" (`oblWhere`, `nearRows` `vague`); it never raises the level. A push never says "within N km
of you" for it (`proximity_watch`) — only a ballistic warning, which covers the region anyway, is still sent, naming
the oblast; the Light page's radar does not draw it.

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

**1.57.9: a flash report and a model's number.** The Air Force at 23:48 on 12 October: "❗️О 22.10 ворог завдав удару по
столиці попередньо 6-ма балістичними ракетами … Інформації щодо пусків з території противника не поступало … Крім того,
противник атакував Харків 9-ма баражуючими боєприпасами S-8000 «Бандероль»". Tagged `af_summary` by the feed, it was
drawn all the same as ballistic missiles over Kyiv, "launch completed", 98 minutes after the strike, and stored as
8,000 Banderols. Now:
- `_marks_from_posts` drops the marks of a post `parse_af_report` reads, from `AF_SUMMARY_CHANNELS`, unless it says what
  flies now (`AF_LIVE_RX`: "курсом на", "рухається", "у напрямку", "загроза застосування", "швидкісна ціль");
- `geo.SUMMARY_RX` reads a strike told after it happened ("ворог завдав удару", "О 22.10 ворог атакував …"), whoever
  relays it; `_parse_live` (the Kyiv trackers) returns nothing for a post `looks_like_news` — it fell through to the place
  names when `parse_post` said so by returning nothing;
- a number glued to a model's letters ("S-8000", "Х-101") is the model, and a model may stand between a count and its
  weapon (`_AF_TYPE_RX`); "завдав удару" opens the attack as "атакував" does (`_AF_ATTACK_RX`);
- a report dated by its own clock time and no night or day is `period: "flash"`: listed, never added to a date's or a
  window's totals (`AF_TOTAL_PERIODS`) — the morning's summary counts the same missiles;
- the stored reports are read again once (`Store.af_reparse`, `AF_PARSE_V`) at start;
- "Інформації щодо пусків … не поступало" is no launch (`geo._launch_denied`); "столиця" is Kyiv named and no place in it —
  the city is marked, not a point at its centre, and a course to it is "→ Київ" (`_city_settle`)
  (`tests/test_retro_strike_1579.py`, `tests/fixtures/af_flash_2026_10_12.json`).

### 7.7 The AI reader (1.50; its facts in the target tags since 1.51; retired from the map in 1.54)

> **1.54, the owner: "the AI placing things on the map — we forget it".** Nothing in §7.7, §7.9 or §7.10's check runs any
> more: no post is handed to the AI (`Telegram._to_ai` is gone), no AI mark is drawn (`State._ai_marks`), no AI fact
> fills a tag (`State._ai_facts`, the `ai_live` switch), and the map's context for it (`ai_context`, `ai_map`) is gone. The
> reading itself — prompt, schema, validators, `AIReader.read` / `check` — is kept in `ai_reader.py` with its tests, and
> the dashboard still shows what it read until then. The AI now writes **bulletins** (§7.11) and the night's report.

A second reader of the channels' posts: a language model, through OpenRouter (`app/ai_reader.py`, thread
`ai-reader`). **It never places, moves or removes a mark, and never reaches the alerts, the feed, the banners or a
push.** 1.51: with the dashboard's switch on (§7.8), the facts it quoted that the rules did not read — origin,
height, speed — fill the target tags, marked as the AI's. It reads
the same posts as the rules, its reading and the rules' are stored side by side (`ai_reads`), and the dashboard's
**AI reader** tab shows where they part. What it is for, first: finding what the rules misread or miss, so that the
rules are fixed — they stay deterministic, free and instant. Whether it ever does more (a fallback for a post nothing
else can read) is decided on what this record shows, in a later version.

**What it reads.** `Telegram.ingest` hands it (`_to_ai`, off the post's path: a queue, read on its own thread) every
new post of a channel **on the map** — never one on trial or off — that the tagger saw a target or a place in
(`AIReader.WANT`), and, from the posts the rules set aside as not about the sky, those that name a place and are
300 characters or shorter (a tracker's line the rules did not understand, "Ціль на Бровари"; a long one is news).
Not the Air Force's summaries, not a retraction. The post as the reader sees it (`_clean_post`).

**What is sent** (`OPENROUTER_URL`, one request a post): the post's public text, the channel's
name and its oblast, the channel's previous posts of the last 40 minutes (at most 3, `Store.ai_previous`, context
only), and the **candidate places** — the gazetteer's places the post's words match (`geo._find_places`, the regional
villages of the oblasts in play) and those oblasts, at most 30, each with an id (`c1`…, `o<uid>`). Never anything
about a reader, a watched place, a device or an address; a run of 13–19 digits (a card number in a fundraising line)
is replaced before anything is sent or stored (`mask`).

**The prompt is a component**, versioned (`PROMPT_VERSION`, stored with every reading; 3 since 1.51, a `p` after it
when the answer was asked for by the prompt alone). 1.51: it is the **second reader** of a deterministic parser and is
told so — its job is to cross-check the rules' reading against the post, the channel's previous posts and the targets
on the map from every channel, to correct it, and above all to add the targets the rules missed ("a target missed is
worse than a duplicate"), never inventing: every fact still quotes the post and every place is a candidate. Each post
comes with (`user_message`): the channel and **the oblast it speaks for and the oblasts its last posts named**
(`channel_block` — a regional tracker's bare name is read in those oblasts); the **PARSER READING** — the rules' marks
for this very post, one line each (`parser_lines`); and **ON THE MAP NOW** — the tagged targets other posts placed in
the candidates' oblasts or within 80 km of them, newest first, at most 10 (`State.ai_context`, never the post's own
marks). Its answer can say which of those a target is (`same_as`, a tag it was shown — anything else is dropped) and a
**vertical state** (`vertical`: descending, climbing, low, high, quoted).

1. fixed rules from [SAFETY.md](SAFETY.md) (`SYSTEM`): never infer; every fact quotes the post; places only from the
   candidates, by id, never coordinates; "на X" is heading to X, not at X; a city named with no place in it is the
   city; the weapon words (Banderol a jet drone, never a cruise missile); the status words; previous posts are
   context, never a source of facts; an alert or an all-clear alone is no target; 1.50.2: the **origin** — a
   direction or a country or area ("з півночі", "з Білорусі", "з Брянщини", "з моря", "з Криму", "з ТОТ"), never a
   Ukrainian oblast or town, which is a place it comes *from* — and the **speed**; a height or a speed belongs to
   the target of its own line or paragraph, a height on a line of its own to the target just above it;
2. worked examples (`EXAMPLES`, six, as earlier turns of the conversation);
3. the post's context, assembled per post (`user_message`);
4. a strict JSON schema (`SCHEMA`: `targets` with `kind`, `count`, `status`, `place_id`, `relation`, `side`,
   `distance_km`, `origin`, `heading`, `altitude_m`, `speed_kmh`, each fact with its `*_quote`; `uncertain`) —
   `response_format: json_schema, strict`, and `provider.require_parameters` so that no provider ignores it.
   **Nothing in it is nullable** (1.50.2): what a post does not state is `""`, `0` or `"none"` on the wire (`wire`,
   `unwire`; the examples are written with `None` and sent in that form). A nullable field is a "union type" to
   Anthropic's structured outputs, which take at most 16 in a schema, and 1.50.0's 15 came back as "HTTP 400:
   Provider returned error" on every post. A provider that still refuses the schema (400) is asked once more by the
   prompt and the examples alone, without the schema and the caching marks (`plain`); if that works it is kept
   (`AIReader.way`, `format` on the dashboard: `schema` / `prompt`), an answer wrapped in a code fence is still read
   (`_json_of`); refused both ways, it pauses 10 minutes. A refusal shows the provider's own words
   (`error.metadata.raw`, `_why`), not only OpenRouter's. The
   request carries no other model parameter (1.50.1): with `require_parameters`, one the model does not take — the
   `temperature` claude-haiku-5.5 does not — leaves no provider at all (OpenRouter's "HTTP 404: No endpoints found
   that can handle the requested parameters"). A model set in `ai_reader_model` must take `response_format`.

The fixed part comes first and the post last, so a provider can reuse the unchanged beginning (prompt caching; for
Anthropic's models its end is marked `cache_control`).

**Checked against the post** (`validate`): a quote that is not in the post drops its fact; a place id that was not
offered drops the place; a count needs a number in its words, a distance must be written, an altitude must be
30–20,000 m with a figure in its quote, a speed 30–5,000 km/h with a figure and "км" in its quote; an origin's quote
must hold a word of its class (`ORIGIN_WORDS`: "білорус", "брянщ", "мор", "крим", "окупов"…, or a compass word for
a direction) — "з Чернігівщини" is never an origin; a target with nothing left (no weapon, no place, no outcome) is
dropped. The
number of facts dropped is stored (`dropped`) — a model that keeps inventing shows here.

**Compared with the rules** (`compare`, on `geo.parse_for_channel` of the same text): `agree`; `place` (the places
differ); `kind` (another weapon at the same place — a jet drone is the rules' drone or Banderol); `status` (shot down
/ impact); `ai_only` (only the model found a target — perhaps a miss of the rules); `rules_only`; `none`; `error`. A
side of a town ("на півночі від Миколаєва") matches the rules' oblast for it (`_rel_settle`), and Kyiv named alone is
the city to both (`_city_settle`).

**Cost and limits.** The month's spend is OpenRouter's own figure for each call (`usage.cost`), kept in
`kv` `ai_usd:YYYY-MM`; at `ai_reader_monthly_usd` (10) it stops until the 1st; at most 400 posts an hour; a refused
key, no credit, or a model or parameter no provider serves (401 / 402 / 403 / 404) pauses it 10 minutes, "too many requests" (429) one minute; a post that arrives
meanwhile is not read (counted in `skipped`). With the default model (`anthropic/claude-haiku-5.5`, $0.10 / $0.50
per million tokens) a post costs ~$0.0003–0.0005: the $10 cap is ~25,000 posts a month.

**The dashboard** (`GET /api/ai_reads`, 🔒): the state (key, model, prompt version, paused, last error), the month's
readings by verdict, the spend against the cap, the median answer time, and the readings — disagreements by default,
all on request — each with the post, the rules' places and the model's targets with their quotes. `/api/health`
carries the same state (`ai_reader`). Readings are kept 90 days.

**The switches** (1.51, `POST /api/admin/ai` 🔒, `{reader: bool, live: bool}`, on the AI reader tab): `reader`
(`kv` `ai_reader_on`) stops every call at once — `AIReader.enabled()` reads it; `live` (`kv` `ai_live`) is the kill
switch for its facts in the target tags — `State.ai_live()`; the marks are recomputed at the next ask (≤ 10 s). Both
on unless switched off.

### 7.8 Target tags (1.51)

**1.56.5: not shown in the app, for now** — the owner: "let's disable the target IDs for now, it doesn't work and it's
very unreliable". `TAGS_SHOWN` (`i18n.js`, false) keeps every number out of the pages: the map's label and its compact
tag, a whole oblast's chip, the tooltip, the card's tag line and its explanation (`tg_what`), the replay's label, and
the night's path built from a tag (`loadTrail`, `trailLine`: no `/api/trail` request). The server still works them
out — the patterns (§7.12), the night's record and the bulletins' record, a height or a speed an earlier report of the
track gave (`tag.alt`, `tag.spd`, still shown) — and `/api/markers` still carries `tag`. `true` brings them all back.

Every target in the air carries `tag` in `/api/markers`: `{id: "#07", n, p, night, o, os, oq, oc, ot, alt, spd}` —
Heimdall's own number for the night. **1.53.2, the owner: "remove the direction altogether for now — it gets it wrong
almost all the time"** (a drone from Belarus over Chernihiv oblast was "E-82": its track had taken "з брянської" from
another post's report). `tag_id` is the number alone ("#07"); the letter and the origin below are still worked out and
kept (`p`, `o`…, `targets`, the night's record, the CSV) but shown nowhere — not on the map, the card, the replay, nor
in the AI's view of the map (`ai_map`, `ai_context` send no origin). It is not an official or military designation
(SAFETY.md).

- **The number** (`TargetTags`): counted per night, from 12:00 to 12:00 Kyiv time (the replay's nights), the night
  named by the date it starts on (`tag_night`, as the replay names its nights — tonight is in the charts at once). `_chain` carries every report of a track
  (`reports`, oldest first; an absorbed approach report too); a track's tag is found by **any** of them, so it does not
  change when its first report leaves the 45-minute window, and `target_reports` keeps it across a restart. A new
  track gets the night's next number. The replay looks tags up (`TargetTags.find`, `tg` in its tracks) and never makes
  one.
- **The letter** (`TAG_PREFIX`): N — north, north-west, Belarus; E — north-east, east, south-east, Russia; S — south,
  south-west, the sea, Crimea; W — west; ? — not said, or "the occupied territories". From `geo.stated_origin` on the
  report's own words ("з півдня", "з території Білорусі", "з Брянщини", "з моря", "з Криму", "з ТОТ"; never a Ukrainian
  oblast or town) — the first any report of the track stated (`origin_t`) — and, when the rules found none and the
  switch is on, the AI reader's checked `origin` for that track (`State._ai_facts`, `ai_reader.match`: the AI target at
  one of the track's places, or the only target of a post the rules also read as one). `os` says whose (`rules` /
  `ai`), `oq` the words, `oc` the channel.
- **The bottom line**: the height and the speed the track's **latest** report stated — the rules' (`alt`,
  `geo.parse_speed`) or, where they read none, the AI's for that report (`alt.s` / `spd.s` = `ai`); and `vs`, its
  vertical state (descending…), the rules' or the AI's. Height and descent are **always shown when given** (the
  owner's priority): at every zoom, and on the chip of a target reported for a whole oblast ("↓2200", `oblAlt`) —
  **1.56.2: for 4 minutes at most** (`ALT_MAX_MIN` in `i18n.js`, `altNow`, `altFresh`; the owner: "never more than 4
  minutes — a drone at 900 m last reported 10 minutes ago is down, has hit, has climbed again or has turned"): the map's
  height and arrow, an earlier report's height with its age, the oblast chip, the card's height chip, Light's mark and
  row, and `altTrend` (a run of heights whose last one is older) all go when the report that stated them is older; the
  card's source line then says "reported N min ago — too old to be its height now" (`alt_old`), and its track keeps
  every report's height with its time. **1.54.9: outlined, not a pill** (1.54.6 drew a
  filled pill; the owner: "not a filled bullet — just make the characters more visible, with an outline"): 12 px, heavy,
  sky blue (#5cc8ff; red #ff4d6a while it descends) on a dark outline (`paint-order: stroke`); the card's height chip is
  coloured text in a coloured frame (`.chip.alt`, `.chip.desc`), a region-wide report's height light blue (`.obalt`).
  A mark with nothing stated shows nothing. Night mode dims it (#8fb8ec / #ff8c9c on black), the day mode deepens it
  on a white outline, the light version is white on black.
- `targets` keeps each tag's letter, origin, source and words, first and last time and type (for the analytics:
  `targets` in `/api/analytics`, per night by letter, and how many letters the AI read); `target_reports` maps each
  report to its tag. Both kept 60 days.

On the map the tag heads the label ("S-07 Реактивний ×2", yellow, hidden when zoomed out to the whole country), and
the bottom line under the glyph adds the speed ("3500 м · 400 км/год", italic when read by the AI). The card and the
hover say where it came from, in the post's words and from which channel, with an "AI" chip when the AI read it, and
what the tag is. **A target drawn at the town it is heading for** (an approach mark with a stated side) stands off
the town on that side, 30 px on the screen, pointing in along its dashed course: nobody said where it is, and the
town stays clear.

**1.52 — only when it is sure, and "probably".** A target reported for a whole oblast (`place == "область"`) gets **no
tag** (the owner's rule: a number only when we are sure which target it is); it gets one when a post places it. Where
no post says where a target came from, the oblast its **first** report was in (`first_uid`, carried by `_chain`) says
it probably — `TAG_REGION`: Chernihiv oblast `n` (Belarus), Cherkasy oblast `s` (the south or the east) — in **lower
case** (`n-07`), `os` = `region`, and the card says "probably from …, first reported in …; no post said so". A stated
origin, the rules' or the AI's, always wins. The height on the bottom line is the latest the track stated (`alt.cur`
false: an earlier report's, shown with its age "2900 м (3′)" — 1.56.2: never past 4 minutes, `ALT_MAX_MIN`). In daylight the tag, the height and the region outline
take dark colours (`body.m-day`).

**The path of a tapped target** (1.52, `drawSelPath`, layer `#selpath`): the places the posts reported it at, oldest
first, joined in red dots, each with its time — the path the posts put it on, not a flight path; cleared when the
card closes. 1.52.1: **the tag's whole path for the night** — every point of a tagged track (the report's place, time
and stated height; a destination or a whole oblast is no point) is kept with its tag (`TargetTags.points`, table
`target_points`, 60 days), so it outlives the 45-minute window; a tap fetches it (`GET /api/trail`, `loadTrail`) and
draws the reports older than the window fainter (`.old`) before the ones still on the map, a time on a dot only where it
does not sit on the last one shown, and the card adds "N-07 tonight: 12 reports since 19:02: Ріпки 19:02 → … →
**Вишгород 20:22**" (`trailLine`, `#shtrail`).

1.52.1: an answer may be `MAX_OUT` = 2,400 tokens long (1,200 cut one reading in ten off mid-answer — "not JSON");
an answer cut off at the length is recorded as "cut off at 2400 tokens".

### 7.9 The AI reader's targets on the map (1.52; gone in 1.54)

> 1.54: no target the AI alone found is drawn any more (§7.7's note).

The owner's decision (9 Oct 2026): a target missed is worse than a duplicate. A target the AI reader found that the
rules did not read goes **on the map**, while the switch `live` is on (§7.7), with the same chaining, scope, ageing,
tags and pushes ("near you", for the phones that asked) as any other — `State._ai_marks`, from the readings of the
window (`Store.ai_recent`), each AI target of a post that the rules have no mark for at its place or its destination,
and none when both read one target within 30 km of each other (`_ai_marks_of`; read further apart — "біля Сомкової
Долини", which the rules took for Dolyna in Ivano-Frankivsk oblast — the AI's stands too). It is placed **only at a place the post names**, a candidate the
server offered (`ai_reader.place_of`: the gazetteer, or 1.52's `data/extra_places.json`, the villages of Kyiv oblast,
which the rules never read): at it, near it, heading to it (an approach), or for its whole oblast; never at an official
alert message (`geo.ALERT_MSG_RX` without `MOVE_RX`). Its id is `<post>#ai<n>`, it carries `ai: true`, the map dashes
its halo and heads its label with "AI", and its card says the AI placed it from the post and to check the post.

What the first 54 real readings showed (dashboard, 9 Oct) and 1.52 changed:

- the prompt (version 4): **two places per target** — where it is (`place_id`) and where it is going (`toward_id`;
  only the latter → it is the place, `heading_to`); the channels' **emoji** are weapons and quotes (`EMOJI_KIND`:
  🛵 Shahed, 🏍 jet, 🛸 drone, 🚀 missile, 💣 guided bomb); a tracker's **bare place name** is a target at it; "н.п. X"
  after an oblast is at X; "повз X" is near X; an **official alert message** is not a target; "спускається" is a
  descent; a `missile` of no stated kind;
- the candidates: **a looser match** (`fuzzy_places`) among the oblasts in play (Kyiv oblast for the Kyiv channels) —
  a village the rules' matchers do not read and a slip of one letter ("Пепеяслав" → Переяслав), by the stem;
- a post the server set aside is compared with **nothing** — the rules did not draw it.

The rules' own errors it showed, fixed in `geo._fix_readings` (applied once, by `prepare` with the channel): a channel's
signature on the last line ("‼️ RND | Житомир") is dropped; "з Чорного/Азовського моря" followed by a course is "from the
south", not a position in the sea; an oblast named by its adjective alone after a preposition ("З Житомирської",
"через черкаську", "в київську") is the oblast — except, from a Kyiv channel, going to a Kyiv place of that name ("на
Житомирську", the metro station). And `is_relevant` drops posts about power cuts, giveaways and subscriptions that name
no weapon and no strike (`NOT_SKY_RX`). A relay of a report already read (another channel, ≤ 5 min, the same place) is
still not drawn twice, but **the height, descent, speed and origin it adds** go onto the mark it relays
(`State._merge_relay`, the evidence names the channel) — "Вишеньки 2900" had lost its 2,900 m that way. A post giving a
height and a descent together ("Хотів 1200 знижується") keeps both (`geo._alt_full`).

Two tracks never show one tag: an approach mark a track took over (`absorbed` in `State._chain`) is no longer a report a later one
can continue — it made a second track sharing that report, and both found the same tag by it — and `TargetTags.assign`
skips a tag another track of the same pass already has (`taken`, the tracks taken oldest first). Place names ending in
"-лець" decline with a soft sign (Козелець → Козельця, Козельцем): the stem index has that form too.

### 7.10 The 10-minute check (1.53; stopped in 1.54) and the night's report

> 1.54: the owner chose to stop the check — nothing schedules it, the dashboard has no switch for it. The night's report
> stays (`REPORT_VERSION` 2: there are no checks' notes to read any more).

The owner (9 Oct 2026): one call a post costs too much at the channels' pace — the dashboard showed ~150 posts an hour
at ~$0.0004 each (≈ 8,000 tokens in: the rules and eleven worked examples, for every post), the month's $10 gone in a
week. **The check** (`ai_reader_mode` "check", the default): every `ai_check_minutes` (10, on the clock: :00, :10…) the
`ai-reader` thread takes the queue (the same posts as before, `AIReader.wants`) and makes one call
(`AIReader.check` → `_check_call`): the posts **grouped by the oblast they concern** (the oblast of the rules' marks, else
of the places they name, else the channel's own; `=== OBLAST o14 · Київська область ===`), each block with **what the
map shows there now** (`State.ai_map`: every target in the air, tagged or for the whole oblast), each post with its time,
channel, text (700 characters at most), `RULES:` (`parser_lines` of the rules' marks — or "set aside") and `NAMES:` (its
candidate ids; one numbering for the whole check). At most 30 posts a call (1.53.1: 60 made answers past 6,000 tokens
on a busy night); more → several, by oblast. An answer may be 12,000 tokens; the notes come first in it, and of an answer
cut off at the length what came complete is kept (`salvage_check`; the check says what was lost, `uncertain`).
1.53.4: the first real checks (9 Oct, 18:40–19:41) were cut off 10 times in 12 at 6,000 tokens — a finding in the
one-post schema cost 600–1,000 tokens. A finding is now flat (`FIND`, 18 fields: no origin, course, side, distance, speed
or tag link; `find_target` gives `validate` the one-post shape), each check records how many findings it was given
(`findings.returned`), and a check that still fails says how its answer began (`error`). The prompt
(`SYSTEM_CHECK`, version 5) reuses the reading rules 1–12 of the one-post prompt (`RULES_READ`) and asks only for
**findings** — where a post's words show the rules wrong or incomplete: `missed` (a target no rules line has), `place`,
`weapon`, `outcome`, `not_sky` (the rules drew a target from a post that reports none), `facts` (the right place, a
stated origin, height, descent, speed, count or destination missing) — each with its target in the one-post schema
(`CHECK_SCHEMA`) and a few words why, and a **note per oblast** on what its posts show together. One worked check
(`CHECK_EXAMPLE`) is the earlier turn. Every finding's target goes through `validate` with that post's text and
candidates; a `missed` target at a place the rules have is `facts`; a `not_sky` where the rules drew nothing is
dropped. Each post read gets its row (`ai_reads`, `chk`, cost 0, the word from `check_verdict`: agree / none / place /
ai_only / kind / status / rules_only / **facts**) and the check its own (`ai_checks`: posts, tokens, cost, findings,
notes). A failed call is kept as a failed check and its posts go back to the queue once. ~$0.001–0.002 a check.

What the findings do on the map is what 1.52's readings did: the facts fill the tags (`_ai_facts`; a `missed` or
`place` target is never taken for the track's own, `match`); a `missed` / `place` target the rules have nowhere is
drawn, marked AI (`_ai_marks_of`; `facts`, `weapon`, `outcome` never are) — **up to ten minutes late, so never pushed**
(`proximity_watch` skips `ai` marks; the owner's decision). A namesake is the place the rules read (`_canon` drops the
disambiguation: "Козин (Прилуцький р-н)" was drawn 120 km from the Kyiv Kozyn the post meant), and of several candidates
of one name the one nearest the target's other place, the post's other places, the rules' marks or the channel's own
oblast (Kyiv for the Kyiv channels) is kept, whichever the AI chose (`pick_namesakes`, `anchors_of`; both modes). The dashboard: the
switch "How it reads" (`mode`), "Check now", the checks with their findings and notes, each post's findings with why.

**The night's report.** `State.night_summary(night)` is everything recorded over one tag night (12:00 → 12:00 Kyiv): the
official alerts by oblast (minutes, alerts, first start, last end, raions), every tag with its **path** (`target_points`),
heights, origin and who read it, minutes followed, reports, km, oblasts crossed; the entry places by letter; heights
by band; the reports by hour and oblast and those for a whole oblast; the outcomes; the Air Force's summaries; the
channels; the checks (cost, findings, every note) and every post where the AI and the rules parted. Counts and the
places the posts named — no reader, no watched place. `State.night_text` is the same as plain text (`compact`: a path cut
to its ends, 40 partings). The `night-reports` thread gives the compact text, after `ai_report_hour` (9), to the reader's
model with `REPORT_SYSTEM` (sections: the night in brief, routes, heights and speeds, against the Air Force, patterns,
Heimdall itself — only what the record shows, "reported", no forecast as a fact, ≤ 900 words) and keeps the answer
(`ai_reports`). Dashboard → Analytics: the night card (pick a night, the report, "write it now / again", the record as
JSON or text to download for any AI), and "the AI's checks per night" (findings by kind, checks, posts, cost; CSV).

**Tags that hold (1.53)**, the owner: "the ID number changes during the course — it is probably the same drone".
`TargetTags.assign` gives a track the tag its **latest shown** report had (`shown`, kept by `show` for every mark drawn),
then the tag of any of its reports, oldest first; and a new track whose first report sits ≤ 6 km and ≤ 4 minutes from
another tagged track's report of the same kind (another channel's word for the same target, `State._twin`) takes that
track's tag — one target, two reports, one number (`twins`: those reports may share it).

**Nothing over a target (1.53)**, the owner: "do not stack things like this". The label de-collision (tick) also keeps
clear of every mark's height (`.dn`) and compact tag (`.tgc`); and the town names give way to the targets' glyphs and
heights as well as their labels (`LBLBOX`). (Until 1.54 also of the explosions layer's glyphs and names — §10.1.)

**A short card (1.53)**: on a phone a target's card opens at most 38 % of the screen high — the kind, height, tag, where
and the post in three lines; the track, the night's path, the notes and the evidence are `.sec` and come with "More"
(`#shmore`, `.sheet.more`). **1.54.1, on a computer** (the owner: "the UI isn't that great when we click a threat"): the
card is no longer a bar across the whole window under the map but a card over the map's lower left, beside the list
(`#sheet` at ≥ 1,000 px: 420 px wide, as high as it needs up to the map's height, scrolling inside, its buttons in a bar
that stays in view); a target it would hide is brought, sideways and at the same zoom, to the middle of the map beside it
(`sheetClear`, from the card's box without its slide). 1.54.2: a tap on an oblast's badge opens its card on a computer too
— the map holds the pointer from the press (pointer capture), so the badge never received its click; it is read in the
map's own pointerup, like a mark (`downCh`).

**The map opens at once (1.53)**: `sw.js` keeps the satellite tiles (`/tiles/sat/`, cache `heimdall-tiles-1`,
cache-first, ≤ 5,000, the oldest dropped) — their address carries the layer's version, so a kept tile is never stale —
and answers the map's drawing (`FAST`: the map JSON files) from its cache at once, refreshing it behind. The page asks it
once per version to fetch the tiles of Kyiv and the oblasts around it ahead (`warmTiles`, z5–8 over the region, z9–10
over Kyiv oblast, ~200 tiles), never with `saveData` or on 2G. Esri's closer tiles are left to the browser's cache. The
data (`/api/…`) is never kept.

**Full-screen map (1.53)**: the last button of the map's column (`#fsbtn`, yellow) hides the header and the drawer
(`body.fullmap`) and asks the browser for full screen where it allows it (Android); the alert status stays as a chip
top left (`#fmchip`, mirroring the band `#kyiv`; a tap, Escape or the phone's Back leaves).

### 7.11 The bulletins (1.54)

The owner: "instead of all that on the map, summaries of the activity of the last hour / the last 24 hours, a bit like
a weather bulletin". The `bulletins` thread (`Bulletins`) writes two, on the clock: **the last hour** and
**the last 24 hours**, both once an hour at :00 — 1.56.1, the owner: "instead of a bulletin every 20 minutes, really only one an hour" (the last hour was every `ai_bulletin_minutes`, 20, gone with it).

- **The record.** `State.activity_summary(since, until)` reads what the server itself recorded over the oblasts the map
  covers (`scope_uids`): the official air-raid alerts by oblast (minutes in the window, on now, started, ended, whole
  oblast or raions; Kyiv city first), the targets the rules drew (`marker_log`: reports, not drones) by oblast, kind and
  10-minute or hourly slice, the window before for comparison, the places most reported, the targets reported for a
  whole oblast, the followed tracks' paths (`target_points`: the places in order, at most four shown), the heights, the
  outcomes (`outcomes`: shot down, explosions), what is on the map at the end of the window, and for 24 hours the Air
  Force's figures. `State.activity_text` makes it the plain text the AI is given. Counts, place names and times only —
  never a post's text, a channel's name in the answer, a reader, a watched place or a device.
  **1.54.8, everything it knows** (the owner: "those data are precious — the goal will be pattern recognition too; we
  need to be aware of the maximum amount of things possible"): also the raions under alert (`raion_names`, up to 15),
  the first, last and busiest slice, the kinds of the window before, the **missiles and carriers** reported (missile
  marks on the map's oblasts, `air_reports` anywhere: MiG-31K, strategic bombers, Tu-22M3, Kalibr carriers — up, launch),
  the **courses** the marks carried by oblast (8-point compass), **every stated height** (`heights_all`: min / median /
  max, descending, by band and by oblast — `heights` stays the followed tracks'), the **speeds** stated, **where the
  posts said the targets came from** ("for the record, not for the bulletin"), the reports drawn only at their
  destination, the outcomes' times, the followed tracks with their tag, minutes, heights and up to 12 places (20 for the
  hour, 30 for the day), 25 / 40 places, 25 outcome places, and for 24 hours **the night's weather** (Kyiv and the launch
  areas, `weather`). **A weapon not stated** (`kind_name`, `unstated_kind`) is `"probable drone (type not stated)"`
  when no missile and no carrier was reported in the window, `"drone or missile (type not stated)"` when one was — with
  how many of them carried a drone tracker's signs (a height, a count, its drone mark). The night's report uses the same
  words (`kind_name(…, raw=True)`). The marks it is built from keep what they stated (`marker_log` 1.54.8 columns,
  `Store.MLOG_EXTRA`: `alt_m`, `alt_state`, `speed_kmh`, `origin`, `target`, `likely`, `tag`, `approach`).
- **Only while there is activity** (`State.activity_active`: a report, an outcome, an alert, a target on the map). A
  window with nothing in it gets the server's own line (`Bulletins.QUIET`, `quiet` = 1), once, with no call. The same
  record (`sig`, a hash of the text) is never written twice. The 24 hours are written again only after an hour with
  activity, or every 6 hours.
- **One call, three languages** (`AIReader.ask_bulletin`): `BULLETIN_SYSTEM` (`BULLETIN_VERSION` 2 since 1.54.8) and a
  strict schema `{uk, en, fr}`; `bulletin_clean` takes out markdown, links, channel names and card numbers and cuts a text
  past `BULLETIN_CHARS` (1.54.8: 1,100 / 2,600 characters; it was 700 / 1,600) at its last full sentence; a language
  missing is an error. 1.54.8, "more leeway on the token cutoff": `MAX_OUT_BULLETIN` 4,000 / 8,000 tokens (it was
  1,200 / 2,400 — three languages and a model that thinks first ran out), `BULLETIN_TIMEOUT` 120 s (a post's reading
  keeps 40). The prompt's rules:
  only what the record shows, "reported" (channel reports, not radar, not a count of drones), Kyiv first, alerts only
  from the official ones, never "safe", never shelter advice, never a forecast (a trend in the record may be said), never
  where targets came from or are heading (a followed target's places in order may be told), Kyiv time, 90 / 220 words a
  language (1.54.8; it was 60 / 140), and never "unknown" — "probably drones", or "drones or missiles" while missiles are
  reported, never a certainty. Within the month's budget like every call; its refusals (off, paused, budget, rate) store nothing.
- **Kept** in `ai_bulletins` with the record it was written from, the cost and any error — 1.54.8: every one for
  `BUL_FULL_DAYS` (90), then **for good** one an hour (the last hour's first of each clock hour) and one a day (the
  24 hours' nearest noon, Kyiv time: the night), marked `kept`; quiet windows and failed attempts go at 90 days
  (`Store.bulletin_prune`, once a day, whole Kyiv days). It was 30 days, all of them. About 25 rows a busy day (~150 kB),
  far less on a quiet one; the dashboard shows a record up to 30,000 characters.
- **In the app** (`GET /api/bulletin`): only while the dashboard's switch is on (`kv` `ai_bulletin_public` = "1"), the
  latest bulletin of each kind — and only while the server still stands by it: each turn that finds the latest still
  true (nothing new, the same record) sets `kv` `bul_checked:<kind>`, and a bulletin neither written nor checked within
  75 minutes is not shown (the hour's was 35 until 1.56.1) — when the AI cannot write (off, no key, out of budget) it goes
  stale and leaves the app. The Tactical page shows it over the Near list (`#bul` in the drawer on a phone, `#bulL` in
  the left column on a computer): "Bulletin · AI", the last hour / 24 hours, the text in the reader's language, the time
  it was written and "written by AI from the channels' posts and the official alerts — not radar" (`loadBulletin`,
  every 2 minutes; `localStorage.bulk` remembers the tab).
- **Dashboard → AI**: the AI's switch and the app's, "write the last hour / 24 hours now", the month's bulletins and their
  cost, each bulletin in three languages with the record it was written from; the readings and checks of 1.50–1.53 are
  folded below.

### 7.12 The direction patterns (1.55; the dashboard only)

The owner (10 Oct 2026): "one crucial detail we need to aggregate through time and accumulate is the pattern of
direction of the drones — what pattern the typical drone follows depending on its location — proper foundations so we
can then calculate the % of probability that the drone goes to X, Y or Z. Those data shouldn't be seen yet inside the
app, but on the admin dashboard." Nothing of it reaches the app: no page asks for it, and `/api/admin/patterns` is 🔒.

- **A move** is one tagged target's step from a reported position to the next (§7.8: `target_points`, in time order):
  `Patterns.moves_of`. A report within `MOVE_MIN_KM` (2 km) of the last position is the target still there — the move
  starts from its latest sighting there; a report further than the target could have flown (`reach_km`, the physical
  check of 1.54.7: 350 / 650 km/h, + 8 km for two named places) is another target's and is left out; after a gap of
  more than `MOVE_MAX_MIN` (120 min) the track starts again. Each move keeps where it was and where the next report put
  it (lon, lat, place), the time of each, km, minutes, the bearing, the heights, the track's **kind** (`move_kind`:
  `drone`, `jet` — a mark of the track flagged jet —, `banderol`, `unstated` — a weapon not stated, a probable drone —,
  or a missile's own type, kept but out of the drones' patterns), where a post said it came from (`origin`, `osrc`)
  and the builder's version (`ver`).
- **Kept for good** in `track_moves` (the points go after `TAG_KEEP_DAYS`, 60 days). The `patterns` thread rebuilds the
  nights of the last two days every hour (a night still going gets its new moves: its rows are replaced), and once
  per `MOVES_VERSION` (`kv` `moves_v`; `moves_at`, the last build) every night whose points are all still kept
  (`BACKFILL_DAYS`, 58). A night older than that keeps the moves its version built.
- **The reading** (`Patterns.report`): over the last `days` (0: all), for a kind (`PATTERN_KINDS`: `drones` — all four
  drone kinds —, `drone`, `jet` with the Banderol, `unstated`), on a grid of `MOVE_CELL` (0.2° × 0.125°, about
  14 × 14 km) × `res` (1, 2, 4: ~14, 28, 56 km). For each area with `min` moves out of it or `min` stated courses in
  it: its moves, tracks and nights; where **the next report** put the target (places and areas, a share of the
  moves out of it; `stay`, the moves that stayed in the area); where **the tracks that passed through it were last
  reported** (a share of those tracks); the 8 directions of its moves, their mean bearing and how consistent they are
  (the mean resultant length, 0–1); the **courses the posts stated** there (`marker_log` `heading`, town-level
  positions, no approach mark; 1.56.3: not a course worked out from two of a channel's reports) and the destinations they
  named (`target`); where a post **said** these tracks came
  from (`osrc` rules / ai — a region's "probably" is not counted); the median speed and the median minutes to the next
  report. **Every share comes with its 95% range** (`wilson`, Wilson's interval): 2 moves of 3 is 67% (21–94%), 200
  of 300 is 67% (61–72%) — the probability's honesty, shown beside every %. The names of an area are the places most
  reported in it.
- **1.56.1: from the first night the posts are kept.** The tags began on 9 Oct 2026 and the posts are kept since
  18 Sep: every night before the first tagged one is **read again from its posts** with today's rules
  (`Patterns.build_replay`: `State._replay_tracks`, the replay's own tracks, 12:00 to 12:00 Kyiv time) and its moves
  are written with `src` "replay" (a tag's are "tag"; a replayed track is numbered `REPLAY_N` + its order: no origin,
  no height — the replay keeps neither). At most `REPLAY_PER_TICK` (6) nights an hour, `REPLAY_PAUSE_S` (10 s) apart,
  and none while Kyiv or its oblast is under an air-raid alert or a missile threat is up (`busy`) — the live map comes
  first; a night once done (for this `MOVES_VERSION`) is not done again (`replay_nights`). Two reports of one track
  less than `MOVE_MIN_MIN` (2 min) apart are no move (two places reported at once: a quarter of the first build's moves
  were 0 minutes); a Banderol (`banderol_missiles`) is counted with the jet drones (it was left out); an area is named
  by the places most reported in it, the marks' and the moves' together (the cell of Kyiv is "Київ", not a village one
  track passed); the destinations the posts named are a share of the courses that named one. `MOVES_VERSION` 2: every
  kept night is built again.
- **In plain words** (1.56.1, the owner: "see whether you can identify patterns, in plain English"):
  `Patterns.plain(report)` turns the figures into sentences, English and Ukrainian (`plain` in the answer), only where
  they say something — an area with `PLAIN_MIN` courses stated (30), moves out of it (8) or tracks through it (8),
  whose main course, next place or last place holds a share whose 95% range starts at `PLAIN_LO` or more (30%, 25%,
  25%): "Славутич: of the 526 courses the posts gave here, 53% were south and 31% north (95% range for the first:
  49–57%)". Strongest first (the bottom of the range), 12 at most, after one line on what it is built from (tracks,
  nights, live and replayed moves, courses stated and since when, "the channels' reports, not radar"). What was
  reported — never a forecast.
- **These are the channels' reports, not radar**: a target nobody reported between two places is one move between them,
  a channel that names only big towns makes big moves, and an area's shares are only as good as the tracks the chains
  kept together (§7.4). The foundation of a probability, not one: a next-area share is a first-order transition (where
  it went next from here, whatever it did before), and the moves' CSV (`raw=1`, every move of the window, at most
  50,000) is there for any further model.
- **Dashboard → Patterns** (`static/admin.html`, `loadPatterns` / `drawPatterns`): the period (30 / 90 days, a year,
  all), the kind, the area size; the counts (tracks, moves, nights, stated courses, areas) and when the moves were last
  built; **in plain words** (the sentences of `Patterns.plain`, or why there are none yet); a **flow map** — the oblasts (`static/ukraine-map.json`), each area shaded by the moves out of it (one blue
  ramp, square root), an arrow for its mean direction (longer when more of them go the same way), and from the area
  chosen, lines to the areas the next report put it in (width by share, the top three labelled); the chosen area's
  card — the directions (its moves and the stated courses, % of each, one axis), the next places, the last-reported
  places, the next areas, the destinations named, the origins said, each with its range as a bar; every area in a
  table (click a row, or an area on the map); CSV of the areas and of every move. English and Ukrainian.

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

`/admin` has seven tabs (the last one opened is remembered, `localStorage.admintab`): **Live** (online now, the
admin's message with a preview in the readers' colours, the nuclear event — §9), **Analytics**, **Patterns** (1.55,
§7.12: where the drones go, area by area, and since 1.56.1 in plain words — the dashboard only), **Nights & weeks**
(§8b), **Sources** (lead time, official sources, the channels and their controls, translation; a red dot on the
tab when a source or a channel on the map fails), **AI reader** (1.50, §7.7: the shadow reader's readings beside
the rules') and **Usage** (the anonymous counters). Each tab loads its own data; only Live, Sources and AI reader
refresh on their own (10 s, 60 s, 60 s while open).

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
  minutes, **one attempt** right or wrong — `State.nuke_arm`), then the code and the phrase `NUCLEAR EVENT` (or,
  1.42.2, `ЯДЕРНА ПОДІЯ` — case and spacing never matter) typed in full (the button unlocks only then), then the
  button **held for 3 s** (it keeps the pointer while held — `setPointerCapture` — so a drift off it does not stop the
  hold; Space or Enter held works too); `State.nuke_fire` checks the code, its age and the phrase again. 1.42.2: the
  arming is also kept in `kv.nuke_arm`, so a restart between arming and firing (every release, and the crashes of the
  shared-CPU nights) no longer answers "not armed"; still one attempt, still two minutes. A failed fire shows the
  server's answer in full. **Preview** draws the symbol and the banner with the text written above in a window of the
  dashboard only — nothing is sent or stored; it is the way to test. The text (UK / EN / FR, prefilled with shelter-in-place advice to edit) and an
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

## 9c. The owner's private Telegram channel (1.58)

The owner: "a small private Telegram channel that posts alerts like the channels we read, with a 'screenshot' of the
app where the drone is (Kyiv and Kyiv oblast only)" — a post per target, with a picture in the app's style drawn on the
server. Off unless `TG_BOT_TOKEN` and `TG_CHANNEL_ID` are set; then `main()` starts `ChannelPoster` (`app/chanpost.py`,
thread `channel`). Its rules are SAFETY.md's "The private channel says what the map says". 1.58.7, the owner:
"instead of editing the post, we need to add a screenshot every time — it's better to keep track of what's going on",
and "when the alarm is over, or it exploded or fell, or the threat is no longer here, we should mark it too".

**Its sources** (1.58.9, the owner: "for the Telegram bot we'll take a single source: t.me/chyste_nebo"; 1.58.12, after
@chyste_nebo fell silent at 03:59 while kyiv_airdef and kievinfo_kyiv reported a drone towards Boryspil, his pick: "all
the Kyiv sources"): `SOURCES = ("chyste_nebo", "kyiv_airdef", "kievinfo_kyiv")`, the three Kyiv live trackers — only a
mark whose latest report is one of theirs is posted (a target the Air Force or a regional channel reported last waits
for theirs; gone from them 5 min, "no new reports"), and only their outcomes close a target (`link_outcomes` over their
marks alone). The official alerts and all-clears are the official data's, as before; the
posts still name no channel.

**What it posts.** Every 5 s it takes the marks as the pages see them (`State.markers_now()`) and keeps
(`chanpost.eligible`) the ones of its source over Kyiv city or Kyiv oblast (`oblast_uid` 31 / 14) at a named place, of a flying type
(drones, the missiles, Banderol, a weapon not stated) — no outcome (`status`), no faded mark (`stale`), no merged one
(`superseded_by`), no oblast-wide guess, no reading still waiting for its context. A target whose post named only where
it is heading ("Балістика на Київ!": `approach`, a place "→ Київ") is posted as the app draws it — at that town,
fainter, set off on the side a post named, no course ray — and its caption says "📍 Де саме зараз — у дописі не
сказано"; 1.58.7: while that place has no official alert (`held`, §7.4) it has no silhouette there and the caption says
"⚪ Офіційної тривоги там поки немає — значка на мапі немає, доки її не оголосять"; the alert starting is a new post, with
it. They are grouped by target tag (`tag.night` + `tag.id`, else the mark's id): one thread of posts per target.

| When | Call | What |
|---|---|---|
| a new target, reported in the last 5 min (`FRESH_S`), not already ended by an outcome | `sendPhoto` | the picture and the caption; the phone rings. A target closed before and reported again: a new thread, in reply to its last line |
| the same target reported again (a new place, course, count, height, path, minute, held or drawn) | `sendPhoto` with `reply_parameters` | 1.58.7: a new post, in reply to its last one, at most every 60 s (`UPDATE_EVERY_S`) and only for a report of the last 5 min — never an edit |
| an outcome a post reported, linked to it as kyiv.html's `linkStatus` links it (`link_outcomes`: down, impact, lost, clear; same family, −2…40 min, ≤ 60 km, ahead of a stated course beyond 8 km, "clear" ≤ 25 km; one each) | `sendMessage`, in reply | 1.58.7: "⬇️ **Збито / Приземлено** — так у дописі о HH:MM" (the app's `st_*` words: "💥 Вибух (влучання або перехоплення — невідомо)", "❔ Локаційно втрачено", "✅ Повідомлено: у районі чисто") and the target's line. Not where it happened, no picture. Also once after "no new reports" (a target gone from the map is linked by its last report) |
| the official alert of the target's area gone for 60 s (`CLEAR_AFTER_S`) | `sendMessage`, in reply to the area's last post | 1.58.7: "✅ **Відбій тривоги** о HH:MM · Броварський район (офіційно)" — once per area and alert, closing the targets still open there |
| gone from the flying marks for 5 min (`END_AFTER_S`) | `sendMessage`, in reply | "⏹ Нових дописів після HH:MM немає" and the target's line |

The caption (Telegram HTML, Ukrainian): the type as the app names it (Шахед, Реактивний дрон, Балістична ракета,
Бандероль (реактивний дрон), "Ймовірно, дрон — тип не вказано" — as `asDrone`: no missile within 150 km), the count,
the place; a course **only when a post stated it** (`stated_course`: a target town, or compass words with a confidence —
never the bearing the app worked out between two reports, nor a destination a later post gave a carried mark); the
height a post gave — 1.58.9, the owner: "I see the altitude is not shown most of the time": @chyste_nebo gives a
height in a post of its own ("3800", "Бондарня другий 4600") and names only places after it, so when this report gave
none, the latest one an earlier report of the same track gave (one of its sources'), with its time ("~4600 м (у дописі о
00:44)", `stated_alt`), only if said at most 4 minutes before this report (`ALT_MAX_S`, the maps' `ALT_MAX_MIN`); on the
picture "↕ ~4600 м · 00:44" —; the time of the report (Kyiv) and of the first one; "З дописів каналів, не радар. Сирена й офіційна
тривога — головне."; a link to `/m` (`PUBLIC_URL`). 1.58.7, the owner: "no need to say the source of info" — the channel
a post came from is no longer named (nor in a closing line).

**Areas and the all-clear** (`app/areas.py`, 1.58.7): `area_at(lon, lat)` finds the shape of `static/kyiv-map.json` a
point is in — the shapes the Tactical page paints the alerts on, Kyiv oblast's raions and the city first —, and
`under_alert` says whether `alert_fill` (moved here from `mapshot.py`, shared with the server) paints it. A channel
target's area (`area_of`): "kyiv-city", a raion of Kyiv oblast, or "14:*" for one placed only in a part of the oblast
(the oblast is "on" while any of its raions is). An area under alert with a target in it is watched
(`ChannelPoster.watch`); its alert gone for a minute (a flicker of the feed is no all-clear), one line says so. The
watches live in memory only: after a restart the alerts are not read yet, so an area must be seen under alert again
before its all-clear can be said; the kill switch clears them (no all-clear of an alert that ended while it was off).

**The picture** (`app/mapshot.py`, `MapShot.render`, ~0.3 s plain, ~0.5 s over the satellite): a 1080 × 1350 JPEG
(1.58.10: portrait, 4:5 — the oblast is taller than wide), drawn at twice the size and scaled down. **The view**
(1.58.10, the owner: "a change of tactics, it's too unreadable — we'll take a snapshot of the oblast and show the whole
oblast on the screenshot, but ONLY Kyiv oblast and the city of Kyiv"): Kyiv oblast and the city, Slavutych included
(`MapShot.extent`, 3 % of margin, `PAD`) — 1.58.13, the owner: "the image is too zoomed out, ideally a bit more focus on
where the activity is": framed on the activity (`MapShot.view(m, others)`): the target, its last six reported places,
the other targets within 60 km of it (`FOCUS_NEAR_KM`) and Kyiv when it is within 50 km (`KYIV_NEAR_KM`), ×1.3 + 15 km
each side, at least 110 km tall (`FOCUS_MIN_KM`, ~10 px a km), the picture's 0.91 width to height, kept inside the
oblast's extent; activity wider than the oblast, the whole of it —, and **nothing else**: the
oblasts around are neither drawn nor tinted, their towns not named, the satellite picture and the rivers are cut to the
oblast's shape (`_oblast_mask`, kept), outside it the plain background (`OUT_BG`). (1.58–1.58.9 framed each target,
30–220 km round it, and 1.58.7 named villages — the owner: "far too many places named, it's unreadable"; both gone.)
The data the pages draw: Kyiv oblast's raions and the city of `static/kyiv-map.json`, the rivers of `map-ua.json`, the
towns of kyiv.html's `TOWNS` inside the oblast (Ukrainian names from i18n.js), the raion labels (`RAION_LBL`,
`RAION_ADJ` + "р-н"), the silhouettes of `static/glyphs.js` (checked shape by shape by the tests), the colours of the
Tactical page. The official alerts of the moment are painted as `alertMap()` paints them (`alert_fill`: the city;
Kyiv oblast's raions — oblast-wide, by raion, a hromada's raion). The target, its last six reported places (a dotted
path) and the other targets of the moment (the channel's own, `ChannelPoster.cur`, not a held one — smaller and
fainter, under the one the post is about): the whole situation over the oblast in one picture. The silhouette is 2.6 px
a unit (`GLYPH_SC`; 3.9 until the owner: "the Shahed is far too big"), the others 1.7 (`OTHER_SC`), the halo 36 px
(`HALO`), the course ray 80 px; the names (1.58.11, the owner: "a bit smaller, please") Kyiv 22 px, a town 16, a raion 14
(`BIG_PX`, `TOWN_PX`, `RAION_PX`). `to_pixel(lon, lat)`: where a point is in the picture (the tests).
1.58.6: a target placed only in a part of Kyiv oblast ("на сході Київщини") is posted as that part ("Схід Київщини",
"📍 Точного місця в дописі немає — лише частина області"), drawn with a dashed circle of 35 km round the point
(`AREA_KM`). The silhouette turns as `orientOf()` turns it; the course ray is drawn only with a stated course. The
place the post named stands in a pill beside it — 1.58.7, the owner: "display altitude on the screenshot": with the
height a post gave under it ("↕ ~150 м", "↕ низько", `alt_text`; the caption's words). A held target (1.58.7): no
silhouette, halo or course at the place it is heading for — the places it was reported at before, and the pill.
Town names that would cover the target are left out; the places it was reported at before are named beside their
dots where there is room. Header: HEIMDALL · Київ · Київщина · the report's time; foot: the warning and the map's
credits. Without Pillow (or the font) the channel posts its text alone. The image installs `fonts-dejavu-core`.

1.58.2, the owner: "il faudrait idéalement la vision map satellite". **Under the map, the satellite picture**: the app's
own Sentinel-2 tiles (`SAT`, the MBTiles file on the volume, §10.1 — no map provider is asked, Esri's are never used
here), at the zoom as sharp as the picture (~z9–10 for the whole oblast; 10–60 tiles), each tile placed by
its own corners in the map's kilometres, then dimmed as the Tactical page dims its layer (`#sat`: brightness .62,
saturate .82, contrast 1.04 — `SAT_LOOK`). The areas are not filled; the alerts' tint is drawn in one layer of its own
(over the picture, two shapes meeting at an edge or an enclave would otherwise be tinted twice); the rivers are the
picture's. The last 200 decoded tiles are kept (~40 MB; a bad tile is not). Credits: "Знімки: ESA WorldCover 2021,
modified Copernicus Sentinel data (2021) · межі: OCHA, geoBoundaries · © OpenStreetMap". No file on the volume (a local
run): the plain map, as before.

**Limits**: 18 calls a minute (`BUDGET`; Telegram's is ~20 messages a minute per channel), in this order: new targets
(the most recent first), outcomes, all-clears, new reports (the longest-waiting first), "no new reports"; a 429's
`retry_after` is obeyed. **State**: `kv` `chan_posts` — per target, the last message id (what the next post replies
to), first / last report, what was drawn (`signature`), its area, how it ended, a trimmed copy of the mark for the
closing line and the outcome's link (place, point, course, part of the oblast); 24 h, kept over a restart so a deploy
neither reposts nor forgets a post. **Health**: the dashboard's official sources list "telegram channel (posting)" —
working or failing (the last call to Telegram), targets / new reports / closed / all-clears counts.

**Kill switch** (1.58.3, the owner: "il faudrait faire un killswitch"): dashboard → Live, "Private Telegram channel —
ON / OFF" (`POST /api/admin/channel_switch` 🔒, `kv` `chan_on`). Off: from its next pass (≤ 5 s) the channel makes no
call at all — no post, no closing line, no all-clear; the bot and its secrets stay. On again: it carries on with what is
reported from then — nothing first reported more than 5 min ago is posted late, and the targets gone meanwhile get
their closing line. Without the secrets the block says "not set up" and how to set it up.

**Setup** (`scripts/set-telegram-channel.bat`, once): @BotFather /newbot → a private channel → the bot as an
administrator ("Post messages", "Edit messages of others") → a message in the channel → the script: the token asked
hidden and checked (`getMe`), the channel found from the bot's updates (`getUpdates`: a channel post or the bot's own
addition) — 1.58.1: or, when the bot is told nothing (no update; another program reading its updates, a webhook),
the channel's id typed in (Telegram Desktop's "Show Peer IDs in Profile", or the channel's address in web.telegram.org/a;
with or without -100) and checked with `getChat`; what Telegram answered is shown in its own words, the token masked —,
the bot's rights checked (`getChatMember`), a test message, then `TG_BOT_TOKEN` and `TG_CHANNEL_ID` into
Fly's secrets through `fly secrets import`'s input. To stop: `fly secrets unset TG_BOT_TOKEN TG_CHANNEL_ID`.

## 10. The two pages: Tactical and Light

### 10.1 Tactical (`/m`)

One self-contained `kyiv.html`: an SVG map in a km projection around Kyiv (`proj`/`unproj`, `KX`, `KY`),
level-of-detail classes by zoom, OSM tiles under the vector layers below 150 km width, on every device, and inside
Ukraine only (`#tiles` is clipped to the oblasts' outlines, `#uaclip`). (1.45 laid them under the whole country on a
computer, neighbours included; zoomed out, the map was unreadable, and 1.45.1 took it back.)

**The satellite layer (1.47).** Layers → "Satellite imagery (Sentinel-2, 2021)", under everything, inside Ukraine
only (`#uaclip`), at every zoom, on by default on every device (1.47.1; it was off on phones). It and the OSM streets
are **one choice or the other** (1.47.1): checking one unchecks the other — under the satellite, zooming in fell back
to the streets every time. A saved choice was moved to the satellite once (`layers_v3`); with the satellite chosen
and no imagery on the server, the streets are drawn in its place (`updateOsm`). The imagery is the **ESA WorldCover Sentinel-2 composite of 2021** — the median of a
year of cloud-free Sentinel-2 pixels, 10 m, one processing for the whole country, so the tiles join without seams;
CC BY 4.0, credited on the map whenever it is drawn (`SAT_ATTR` in `#attrib`: "© ESA WorldCover 2021 · contains
modified Copernicus Sentinel data (2021)"). `scripts/build_imagery.py` reads it once from the public bucket
(`s3://esa-worldcover-s2`, no account) and makes the WebP tiles that touch Ukraine: 1.47's first file, zoom 5–12
from the 20 m overview (about 21,000, ~130 MB); **1.48's, zoom 5–13 from the full 10 m** (each 1° cell read in four
pieces with a 16-pixel margin; 80,415 tiles, 406 MB — 59,736 of them at zoom 13, ~4 KB each). Closer than the file's deepest zoom the page enlarges its tiles. **The open sea is
transparent**: the oblasts' outlines take in coastal waters (Odesa oblast reaches Zmiinyi) and the composite has sea
pixels near the coast and none farther out, so the Black Sea ended in a staircase of tiles. Water (near-infrared
below `NIR_WATER`) connected to the open Black Sea or the Sea of Azov — found once on a ~150 m mosaic of the region
after an opening of ~1 km, so that no river joins it (`sea_mask`) — is left out, and the map's own background is the
sea; the Dnipro, its reservoirs, the Dniester, the lakes stay in the picture. The **server serves them
itself** (`GET /tiles/sat/{z}/{x}/{y}.webp`, `SatTiles`, `SAT_TILES` on the volume): no map provider learns which
part of the country a reader looks at, and nothing is paid per tile. The tiles never change under one address — the
page asks with the file's version (`?v=SAT_V`) and the answer is cached a year (`immutable`). 1.48: that version
and the deepest zoom are the **file's own** (its `metadata`: `version`, `maxzoom`; `SatTiles.info()` →
`state.config.sat_v`, `sat_z`), not numbers in the page — a page that asked for zoom 13 or version 2 before the new
file was on the volume would have kept the old pictures under the new address for a year. The page offers the
layer only when the server has the file (`state.config.sat`); a new file put in place is read within ten seconds,
no restart. **1.54.7**: a tile that could not be read just then (the file going in, a busy volume — `SatTiles.lookup`
→ `(None, None)`) is a `503 no-store`; only a tile the file does not have is the 404 the browser keeps a day — in
1.47–1.54.6 both were that 404, and a tile asked for at the wrong moment stayed missing for a day. The page asks a
satellite tile that did not come again after 2, 8 and 30 s (`tileDone`, `&r=n` — an address no kept failure answers);
the service worker keeps only an answer that is a picture, and its store was emptied once (`heimdall-tiles-2`, the
warm-up flag `satwarm2`) after a reader's map showed pale squares; the page says `color-scheme: only light`, so a
browser's "dark theme for sites" never recolours it or its tiles. With the layer drawn the map is "tiled" like under the OSM streets (outlines over the picture, our own
roads and rivers hidden). Darkened by mode (`#sat`
filter: standard, day, night). Why this source and not a commercial one: a paid product cannot use the
non-commercial tiers, and the commercial imagery services (Esri, Mapbox, Google) bill per tile and forbid keeping
their tiles — a one-off build of open data costs nothing per reader.

**The closest zooms: Esri World Imagery (1.48).** 10 m Sentinel pixels show a town, not a street. From zoom 14
(`tileZoom()`, ~1:35,000) to 18 the satellite layer draws **Esri World Imagery** (Maxar, Earthstar Geographics and
others; ArcGIS Location Platform, which allows a commercial app) over the Sentinel tiles (`#esri`, between `#sat`
and `#tiles`, inside `#uaclip`, same filters), credited "Powered by Esri · Esri, Maxar, Earthstar Geographics, and
the GIS User Community" whenever drawn (`ESRI_ATTR`). It is part of the satellite layer, not a layer of its own.
The page asks **this server** (`GET /tiles/esri/{z}/{x}/{y}.jpg`); `EsriTiles` asks Esri with the owner's key
(`ESRI_KEY`, set by `scripts/set-esri-key.bat`) — the key never reaches a browser and is never logged (the request
address carries it). **Nothing is kept on the server** (Esri's terms forbid storing its tiles); the reader's browser
keeps a tile as long as Esri's cache header says, `private`. Only tiles over Ukraine (`ESRI_BBOX`), zoom 14–18, are
asked for. Every tile counts against the free tier (2 M a month, then paid), so they are **counted and capped**:
`esri_monthly_tiles` a month (1.8 M), a tenth of it a day at most (one busy night cannot spend the month), 3,000 an
hour for one reader (a salted hash of the address, in memory for the hour). The counts are kept in `kv`
(`esri_tiles:YYYY-MM`, `esri_tiles_day:YYYY-MM-DD`, saved every 200 tiles) and shown on the dashboard
(`/api/health` → `imagery`). Past a cap, or with no key, `state.config.esri` is false and the page draws the Sentinel
picture alone; a refused key (HTTP 401/403/498/499, or Esri's 200-with-a-JSON-error) pauses the asking for 5 minutes.
At most 12 requests to Esri at once. A large screen that would need more than 140 tiles at its zoom gets the zoom
below (`placeTiles(…, zmin)`), for both layers.

**The background: Satellite, Map or Plain (1.49).** Layers → Background is one choice of three (radio buttons;
`LAYERS.sat` / `LAYERS.tiles`): **Satellite** — Sentinel-2, Esri World Imagery from zoom 14, and over them **Esri's
roads and names** from zoom 10 (`#lbl`, `updateLbl`: "arcgis/imagery/labels"); **Map** — **Esri's street map** at every
zoom (`#emap`, `updateMap`: "arcgis/streets", "arcgis/streets-night" in the standard and night modes), or without
Esri (no key, or past the cap) the OSM streets zoomed in, as before; **Plain** — our own map, nothing under it. Both
Esri layers come from the Static Basemap Tiles service: 512-pixel PNG tiles (asked one zoom below the 256-pixel grid
for the same sharpness — a quarter of the tiles), with the reader's language (`language=en|uk|fr`) and the worldview
that draws Crimea as Ukraine (`worldview=unitedStatesOfAmerica`); a request refused with them (HTTP 400, or — 1.49.3 —
401/403, as the static tiles answered "401 Token Invalid" to a key World Imagery took) is asked once more without
them, then (1.49.4) with the key in an `Authorization: Bearer` header instead of the address, Esri's other documented
way: the way that works is remembered for the kind (`EsriTiles.way`, `no_prefs`), and only when none does is the
service paused, the dashboard saying "(also without language / worldview, and with the key in a header)". Same proxy, key and caps as the imagery
(`/tiles/esri/{img|lbl|map|mapn}/…`). 1.49.2: the two services are **refused and paused apart** (`EsriTiles.down`,
`refused`: "img" for World Imagery, "st" for the Static Basemap Tiles) — in 1.49 a key without the static tiles'
privilege (`premium:user:staticbasemaptiles`) paused the imagery too and the satellite went back to Sentinel's 10 m;
the page is told each (`state.config.esri`, `esri_st`), and the log and the dashboard give Esri's own reason
("HTTP 403: You do not have permissions…"). On the page, when every Esri name or map tile of the view fails, or three
in a row, it does without them for two minutes (`esriSeen`, `stOK()`): the Map falls back to the OSM streets and our
own names come back over the imagery. A tile that fails never takes the older picture away (`tileSweep` waits for
every new tile to have **loaded**; a server restart or a refusal leaves the previous zoom's picture in place).
1.58.14, a reader's phone (Oppo Reno 15 Pro), through the owner: "with the Map background it crashes — solid artifacts,
and it falls out to the lock screen" (not reproduced: no such phone here). The older pictures kept are counted by their
memory (`placeTiles(…, px)`: 150 of 256 pixels, a quarter as many 512-pixel tiles of Esri's map and names — 37); the
night mode dims the street map and the names tile by tile (`#emap image`, `#lbl image`: opacity .55) instead of
filtering each whole group as one picture; and **a page that died on the screen with the Map background opens next time
on the satellite** (`run_v1` in localStorage: what background the opening shows and whether it ended well — hidden or
left, `visibilitychange` / `pagehide`, it did), with a quiet toast (`map_fell_t`, `map_fell_b`: no tone) — the Map is one
tap away again, never a crash at every opening. Where Esri's names are drawn (`svg.lbld`, `svg.mapd`) our own town and village
names step aside — the same names twice, a few pixels apart, could not be read. Credited "Powered by Esri · Esri,
TomTom, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors, and the GIS User Community".

**The towns of every oblast (1.49).** `TOWNS` (in the page) names every town of Kyiv oblast and the oblast and
regional centres elsewhere; zoomed out over Kharkiv or Poltava oblast the map showed four names in a region the size
of Belgium. `static/towns-ua.json` (`scripts/build_towns.py`, from GeoNames' Ukraine dumps, CC BY 4.0) adds the raion
centres and every town of 10,000+ of every oblast that `TOWNS` does not name (352): Ukrainian names as
`build_places.py` gives them, with the renamed ones (Хрустальний, not Красний Луч) and city sections GeoNames files
as towns left out. Drawn in `#twng` (`loadTownsUA`): tier 2 (a centre, or 20,000+) up to 520 km of map (`svg.wide`),
tier 1 up to 230 km (`veryfar`); `layoutTownLabels` ranks them after the regional centres, and a town whose name has
no room loses its dot. 1.49.1: a layer of its own (Layers → "Main towns of every oblast", `LAYERS.towns`), on by
default on a computer and off on a phone, where it was unreadable; on a phone tier 2 shows up to 230 km of map and
tier 1 up to 90 km. The file is fetched only once the layer is on.

**Zoom to a kilometre (1.48).** `setView` / `zoomAt` stop at 1 km across (8 km before). Over a picture (`svg.tiled`)
the oblast and raion names are light on a dark halo like the towns (`paint-order:stroke`), dark on a light halo in
day mode — dark slate on darkened imagery could not be read.

**The layers outside Kyiv oblast (1.45).** The rivers, roads and "airports / plants" layers were drawn by hand for
Kyiv oblast only, and "villages and small towns" had the core gazetteer's hundred-odd Kyiv-oblast places and a couple
of dozen elsewhere — on an Odesa or Lviv view they did nothing. Now:

- `static/map-ua.json` (`scripts/build_mapdata.py`, from Natural Earth 1:10m, public domain): the main rivers cut to
  Ukraine's oblasts (the Dnipro with its reservoirs, the Dniester, Southern Bug, Siverskyi Donets, Desna, Prypiat,
  Prut, Western Bug, Seim, Danube; names in the three languages), the first-rank roads outside Kyiv oblast, and by
  hand from GeoNames the civil airports of the oblast capitals and the large power plants (four nuclear, Burshtyn,
  the Dniester and Dnipro HPPs) — **no military airfield**. Each checked on the satellite picture in 1.57.7: all on
  their runway, dam or plant but the South Ukraine NPP, which GeoNames rounds to the minute (500 m off, in the cooling
  pond) — now on its reactors. Loaded with the map (`drawUA`); it replaces the
  hand-drawn Dnipro, Desna and Kyiv Reservoir lines (`.river.hand`), whose labels stay;
- the villages layer fetches `/api/places?villages=scope` the first time it is turned on (`loadVillages`): the regional
  gazetteer's hromada centres and places of 1,000+ in the oblasts the map covers, about 1,800 names, drawn like the
  core villages and laid out by `layoutTownLabels` (which now tests the screen position before the style).
  1.45.1: with the layer on, names show up to 300 km of map on a computer (`vilfar`; the small towns too — the
  `veryfar` rule applies only with the layer off) and up to 90 km on a phone; `geo.villages` lists hromada centres
  first, then by population, so the collision pass keeps those; a village whose name has no room loses its dot;
- the 15 / 30 / 50 km rings are around the reader's oblast capital (`OBL_CAP`, `drawRings`, redrawn by
  `setMyOblast`); Kyiv for Kyiv oblast and for an occupied capital.

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
  replay, full screen. **1.54**, the owner: the explosions layer of the last 24 hours (`#impbtn`, `IMP_H`, its key over
  the map and its report by place) "does not help much for now" — gone; the live outcomes stay on the map as before.
- **The drawer** at the bottom, tabs **Near · Feed · Alerts · Stats** (1.54: the AI's bulletin over the Near list, §7.11), three heights (tab bar / half / most of the
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
  Telegram, about, build tag); **Layers** — the map layers, Kyiv's 10 districts, EST (suspended since 1.45.1: hidden, always off), zoom out to oblast / region / Ukraine,
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
- **1.56.3, a drone faces into Ukraine** (the owner: "in the Chernihiv region the drones must always face into Ukraine
  when no direction is given — it is extremely unlikely that a drone goes back to Belarus or Russia"): in an `INWARD`
  oblast (Chernihiv, `"25"` → towards Kyiv, where its drones go — the patterns: south-west, south) a drone or an
  unstated weapon with no course is drawn facing that way (`inward_face`, the mark's `face`: `orientOf`, Light's
  `markOrient`) — the glyph only: no course ray, no heading in the card or the tooltip, no ETA, and the card says why
  (`face_note`); a course worked out from two reports that is more than `INWARD_MAX_DEG` (100°) off the way in is not
  kept (`outward`; a course a post stated always is). **1.58.8, south north of Kyiv** (the owner, of two drones over
  the Kyiv reservoir, one drawn facing north: "for those drones here, take the habit by default to make them face south
  — it's the most likely direction they will go anyway"): in Kyiv oblast north of 50.60° N (`SOUTH_FACE`: from just
  north of Vyshhorod — the reservoir, Ivankiv, the north of Bucha and Brovary raions) such a drone faces south
  (`face: 180`, `face_by: "south"`, the card's `face_south`), the glyph only, as above; nothing is dropped there. Elsewhere
  a mark with no course stays upright, as before;
- **1.57.5, a mark faces the way its reports moved** (the owner, a jet drone at Obolon drawn facing north while its
  reported path came down from above the reservoir: "the drone should face downward when it is possible to guess"):
  with no course stated, `track_face` gives `face` the bearing from the last earlier report of the mark's own track
  (`history`) at least `TRACK_FACE_MIN_KM` (1.5 km) away and at most `TRACK_FACE_MAX_MIN` (45 min) older, to this one,
  and `face_by: "track"`; it comes before the way into Ukraine (`face_of`: `track_face`, else `inward_face`), and never
  points back across the border (`outward`). The glyph only, as above — no ray, no heading, no ETA — and the card says
  why (`face_track`). The replay keeps its own rule: a stated course or upright;
- `tick()` — marks: silhouettes per weapon (`G`, `GLYPH_BY_TYPE` from `static/glyphs.js`), turned only to a stated course (`orientOf`),
  uncertainty ring up to 25 km, 5-minute tail, labels (1.53.3: no off-screen edge indicators any more — the owner: the map has too much on it now; a target off the screen is in the Near list);
- `threatStrip()` — the banner stack, coloured by `officialLevel()`; `idleLine()` when calm;
- **the four pins** (`SLOTS`, `localStorage` only — 1.54.9, the owner: "numbered pins instead of Home / Work / Kids;
  let the user rename them"): "Pin 1" to "Pin 4" (`slotName`, `sl_n`), or the name their owner typed in the pin's
  sheet (`slot_names`, `setSlotName` in `i18n.js`, 24 characters, on this phone only; the storage keeps its old slot
  ids, so no place set before is lost). Each pin's sheet (a tap on an empty one, a long press on any): its name, a
  search, or "📍 Put it on the map" (`armPin(true, id)`, then a tap). The active pin is drawn as a numbered pin
  (`POI_G.pin`) with its name. Zones 10 / 30 / 60 km (their labels sized in screen pixels, `--k`), the conditional ETA
  band (`etaBand`);
- **a pin dropped on the map**: press and hold on open map (a ring fills while the finger stays; a drag only starts past
  `HOLD_SLOP_PX` = 10 screen px; the browser's long-press menu is suppressed) — the fourth pin, as before; or a pin's
  "on the map" (`PIN_FOR`), banner with Cancel, a tap where it goes (`dropPin`). A pin put on the map is named by its pin;
- **a pin on a street** (1.56, §10.6): the sheet's search finds every street and village of the oblast chosen; a street
  sets the pin at the street's point (`hsPick`), zooms the map to the street (`setView`, the street's reach), and arms
  the pin (`armPin(true, id, true)`: "Pin 2 is on the street — tap your exact spot to move it") — a tap moves it and it
  keeps the street's name (`PIN_KEEP`); on the plain background the street map is shown for it (not saved);
- **the place search above the keyboard** (1.54.9, the owner: "on a phone the keyboard overlaps the suggestions"): the
  page asks to be resized by the keyboard (`interactive-widget=resizes-content`, Android); where it is not (iPhone),
  `vvSync` keeps the visual viewport in `--kb` / `--vvh`, the sheet stands on the keyboard, and while it is up
  (`body.kbd`) the list takes the room that is left and scrolls. Light's picker fills the visual viewport the same way;
- **a shared text never says where the reader is** (1.54.9, the owner: "the location of our pin must NOT be shared"):
  `markerText` is what the post said — the kind, the place, the time, the height, the course, the channel — and no
  more; until 1.54.8 it added "19 km — Вишеньки", the distance to the reader's own pin and its place. The first push
  subscription sends the browser's coarse geolocation only, like every later one (`pushSync`) — no pin name, no raion;
- **the heat layer** (1.34; Layers since 1.36, off at every opening — never remembered): where drones and
  unidentified targets were reported over 24 h / 7 days / 30 days (`GET /api/drone_heat`: the places the posts named,
  town and district level, the number of posts — shoot-downs and hits left out, never an oblast's centre or "Kyiv"
  alone), drawn as a density whose spread keeps its size on the screen, so it is layered by zoom (out: the
  corridors across the region; in: the villages and the Kyiv districts); the most-named places in view written on it
  and listed in its legend; under every mark. (1.54.3: Layers also has **Path of a tapped target** — the red dots of
  §7.8's night path, on by default, `LAYERS.selpath`, `svg.no-selpath #selpath`; the explosions layer's two switches
  went with it in 1.54.) 1.40: **the colour is the number of reports** — pale yellow, orange,
  red for the most (it was violet). `heatGrid()` adds each place's count around it on a grid a quarter of the
  screen's pixels (a smooth bump of 30 px); a spot's colour is √(its sum ÷ the scale), the scale being the busiest
  place of the period or the busiest spot in view if that is more — so a quiet corner never turns red because it is
  zoomed in on; a place with few reports is faint as well as yellow. 1.54.2, the owner: "the heat map is rather
  bad" — every village named once painted its own pale disc and a busy week spotted the whole region: below
  t = 0.18 (about 3 % of the scale) nothing is painted, and above it the colour comes in with the count, so what
  stands out is where the reports gather. The legend's ramp reads "1 … N+" and says "not live, not alerts"; while the
  layer is on, the official alert colours are a faint tint (`svg:not(.no-heat)`, 1.54.2: no more outline — "the
  yellow outline of every oblast when zoomed out is bad": a night of yellow-level alerts drew a yellow mesh over every
  raion), so the two are never read as one colour. **The legend folds and moves** (1.54.2, the owner: "the card can't
  be moved or made smaller — a problem on a phone"): ▾ / ▸ or a tap on its title line folds it to "Heat map · 7 days"
  (`localStorage.heatfold`; folded at first on a phone), and its title line drags it anywhere over the map
  (`heatpos`, as a share of the map, kept below the header where the header runs over the map: `heatMinTop`). On a
  phone it starts at the top left, below the header. Dark map: blended with `screen`; day: `multiply`. (1.33's alert hours by oblast stay in the dashboard's Analytics.)
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
  at night and in blackout) and the watched place's house — the same on every phone. 1.57.7: Kyiv oblast's `POIS` are
  at the plants' and airfields' own coordinates (Global Energy Monitor, Wikipedia), each checked on the satellite
  picture — they had been rounded to 0.01°, so ТЕЦ-6 stood 4.6 km off in Troieshchyna's flats, ТЕЦ-5 on the Stolychne
  highway and the Bila Tserkva airfield 10 km east, past the town; `geo.PLACES` carries the same points for ТЕЦ-5,
  ТЕЦ-6 and the two airports, so a post naming the plant marks the plant (`tests/test_poi_places_1577.py`). Each
  name (`.poilbl`) stands on its icon's point and is set aside in screen pixels by the CSS (`--k`), as the icon is
  sized: offset 2 km in map units, it was 200 px away at the street view — "Київська ТЕЦ-5" in the Dnipro;
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
  (the outlines are accurate to a few hundred metres; a house on the line gets either side's alert). 1.43: a
  place in Odesa, Kharkiv or Dnipro oblast fetches their raions then (`light-map-x.json`, `loadLMX`), so a reader
  there gets their raion's status without everyone else downloading those outlines. Outside the covered oblasts it
  falls back to the oblast (`ukraine-map.json`).
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
- **The radar's background** (1.57.2, the owner: "the light version should show the satellite / map too"): plain by
  default; the layers button on the radar (`#zbg`) opens Background → Plain / Satellite / Map (the Tactical words,
  `l_base`, `l_plain`, `l_sat`, `l_map`; "uses more data" under the two pictures), kept on the phone (`localStorage.lbg`).
  Its code is `static/lightmap.js` (`LT`), loaded only when the button is pressed or a choice is kept (`ldLT`): the
  page stays light. The pictures are the Tactical map's — the server's own satellite tiles (`/tiles/sat/`, their
  version and deepest zoom from `state.config`) or Esri's dark street map (`/tiles/esri/mapn/`, in the reader's
  language) — in an SVG of their own under the radar (`#rtile`), clipped to the disc, its viewBox following the
  radar's at once (a `MutationObserver` on `#radar`'s viewBox); the radar's own background is a veil over them
  (`#rwrap.tl`), and the source is credited under it (`#rtattr`). An option the server does not have is greyed.
  **The tiles say the cell, not the place**: the radar is centred on the place, so the tiles of exactly its view would
  say where the pin is. The tiles asked for (`LT.tiles`) cover the view as seen from the ~10 km cell of its centre —
  the grid the push stores (`HOME_CELL_KM`) — plus the cell's margin (7.5 km): every place of one cell asks for the
  same tiles. Fewer than 50 a view (`MAX_TILES`: one zoom less rather than more); zoom 10–11 for the whole disc, 12–13
  zoomed in.

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

1.42: **flipping, not loading.** When the other version is the page just before or just after this one in the
history — the reader came from it — `swNav()` goes back (or forward) to it instead of loading it again
(`navigation.back()` / `forward()`, only where the Navigation API can say which page that entry is; the paths `/`,
`/k`, `/kyiv` count as `/m`, `/l` as `/light`). The browser keeps the page it left in memory (back/forward cache), so
after the first switch both versions flip at once, as they were left. To be kept there a page must hold no open
connection: both close their live line on `pagehide` (when the page is being kept) and open it again on `pageshow`
(`persisted`) — Tactical with `connect()` and a `pulse(true)`, Light with `connectLive()` and `refresh(true)` — so
what changed meanwhile arrives at once. The pages are served `no-cache` with an ETag, never `no-store`, which would
keep them out of that memory too.

### 10.3e The map first on a phone (1.42.1)

On 7 Oct 2026 at 01:20 a ballistic warning, the admin's message and a mark's sheet left the map 260 px of an 860 px
phone screen — 7 px with the sheet open. On a phone (`max-width:999px`): the slots are 40 px; the warning's "what to
do" sits beside its sentence (`.tsrow`); the caveat under "nothing within 30 km" steps aside while a warning shows; the
card's foot is one line; the admin's message keeps to two lines (a tap opens it whole); the toast puts itself away on a
tap. A mark's sheet (`.sheet.mark`) takes the lower half (52 vh, its buttons pinned at the foot) while the card folds to
its one line (`body.shmk` in `miniWanted()`) and the admin's message steps aside. Measured: 364 px of map with the
warning and the message, 460 px with a sheet open.

**A ballistic report while no official alert covers the place** (`officialLevel()` null, and not an official threat)
says so — "Ballistic threat reported — no official alert here yet" — asks the reader to be ready and to go the moment
the siren sounds (not "do not wait for the siren"), and turns grey after 4 minutes (`TS_FRESH_BAL_UNOFF`, 8 for the
rest). The in-app toast says the same, one tone level lower. With an official alert over the place, the full warning
at once. A mark drawn at the town it is heading for (`approach`) is "heading for Kyiv — where it is now was not
given" in its sheet, with no distance and no zone (it said "Kyiv · 0 km from Kyiv · near zone, up to 10 km").

### 10.3d Daylight and night (1.42)

The display modes recolour everything, not only the map: the bottom sheets (how it works, support, the place pickers, a
mark's details), the buttons inside the panels, the cards' links, the statistics, the live-count chips and the bars.
Daylight swaps the colours made for a dark screen — pale blue links, mint green, pale orange, yellow, pale pink — for
ones that read on white (`#14459c`, `#0d6b3f`, `#b8480a`, `#7a5f00`, `#b3140d`, all ≥ 4.5:1); night's faintest grey
(`--ink3`) is `#566a80`, 3.6:1 on black (it was 2.3:1). Checked by a contrast scan of every text on every panel, sheet,
tab and bar in the four modes (`tests/test_replay.py` keeps the key values).

### 10.3b Motion (1.40)

Short, eased, never bouncy, and none in blackout mode or with "reduce motion" (`CALM()`): a panel (bell, More,
Layers) rises in on a phone and drops in on a computer (0.26 s), its rows following 14 ms apart, and leaves in
0.16 s (`hidePanel()` sets `hidden` after the animation); one orange line slides under the drawer's tabs to the
chosen one (`tabInd()`); a tab's content fades in; switches move their knob with a slight ease; buttons give a
little under the finger (`scale(.95)`); sheets and the drawer use the same easing. Light: the place picker and the
target card slide in.

### 10.3c The replay (1.42)

A past window on the Tactical map, like a weather-radar loop: the ⟲ button on the map (and "Replay — the last 7 days"
in Layers) opens a bar at the foot of the map with the window (the last 24 h, or one of the last seven nights, each
12:00 → 12:00 Kyiv time), a strip of the reports per quarter-hour with the time Kyiv city or oblast was under an
official alert, a slider, −10′ / ▶ / +10′ and the speed (2, 10 or 30 minutes of replay per second). Keys: space,
← / → (a minute), Esc. It starts ten minutes before the attack (the first ten minutes with at least a quarter of the
busiest ten minutes' reports). `/m#replay` opens it at once (for a presentation). `static/replay.js` is downloaded only when it
is opened. **1.54.7** (the owner: "an obvious loading spinner — people think the feature simply does not work"): while a
window loads (up to half a minute the first time), a spinner turns over the map with the words (`#rpwait`,
`role=status`, "the night is being read again from its posts") and in the bar, the slider shimmers and the controls
wait greyed out (`#rpbar.loading`, `waiting()`).

- **The alerts**: `GET /api/replay` rebuilds them as intervals from the start / end **events** (§13) — the `alerts`
  table cannot answer "what was on at 02:14": it keeps one row per region and alert type, and a region's second alert
  overwrites its first. A restart loses the alerts the process held without writing an end (the first reading after
  it writes a start for everything still on, and nothing for what ended while it was down), so a restart — recorded
  in `boots` since 1.41, and before that seen as a start for a region already on — closes every interval not started
  again within five minutes, at the restart. The page paints a moment's alerts with the live map's own function
  (`alertMap()` / `applyAlertMap()`), only when they change; the live colours are not painted while it is on.
- **The targets**: the stored posts of the window are read with **today's rules** — `_marks_from_posts()` and
  `_chain()`, the live map's own functions — so a reading fixed since is fixed in the replay too; scope as on the map;
  no outcome. Each target stands where the latest post before that moment put it, until the next post moved it or its
  time ran out (the live clocks: a drone fades after 5 min and goes at 15, a missile at 12, an unspecified sign at 5),
  with its reported positions of the last 20 minutes as a trail — a leg longer than the target could have flown between
  the two posts is two targets joined, and the trail stops there. Nothing is extrapolated; a course is drawn only where
  a post stated one.
- **While it is on** nothing live and nothing personal is on the map — no live mark, history, heat, bridge, watched
  place, pin or ring (for a screen shared in a presentation); the band and the card at the top stay live (the card
  folds to its line unless something near matters). The bar says "official alerts, and the targets where the channels'
  posts put them — not radar".
- Server: a window of at most 26 h within the last 7 days, in whole minutes; built once an hour for a window in the
  past, once a minute for one that reaches now; twelve windows kept (`replay_cached()`). About 12 kB gzipped a day.

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

**The way back** (1.57.4, the owner: "in the what to do section we need a back button"): the header is sticky and starts
with "← Back" (`#back`, `back` in each language, 44 px): to the app page the reader came from (`history.back()` when the
referrer is one of ours), to Light when it was Light, else to the map (`/m`) — the guide opened from a link or a
notification. Not printed.

- **Five rules** that always apply; **weapon cards** (`shahed`, `jet`, `cruise`, `ballistic`, `kab`, `debris`):
  the usual warning time as a chip, how you notice it, what to do — with the map's own silhouette and colour
  (`static/glyphs.js`, `ICON` in the page); **situations** (`car` — the bridges, `out`, `home`, `kids`, `after`,
  `rad`); the **emergency numbers** as `tel:` links; the **sources**, with what is not taken from them said.
- Every rule comes from the listed official guidance (ДСНС, National Police, Ministry of Health, Poltava ОВА) —
  [SAFETY.md](SAFETY.md#the-guide-says-what-the-official-guidance-says). The checked date is in the footer.
- **Offline**: the page registers `sw.js`; the worker stores `/guide`, `glyphs.js` and the logo at install and
  answers those paths **network first**, the stored copy only when the network fails. "Saved on this phone" appears
  only once `caches.match('/guide')` finds it.
- **1.41: the two pages too.** Tactical and Light register the same worker on every phone (not only when push is
  on); it keeps `/m`, `/light`, `i18n.js`, `live.js`, `glyphs.js`, the logos, `light-map.json`, `kyiv-districts.json`
  and the manifests (`heimdall-shell-N`), network first, and answers from the stored copy when the network fails **or
  the server answers 5xx** (a deploy, a restart, an overloaded host). The app then opens and says so — Tactical: a
  red bar at the top after 15 s without the server ("No connection to Heimdall — retrying; the sirens and «Повітряна
  тривога» do not depend on Heimdall"), and "connecting…" instead of "updated 5 s ago" before anything arrived;
  Light: its offline line after 15 s (was 60). **No data is ever stored** (`/api/…`): an old alert status shown as
  current would be worse than none.
- **Print**: `@media print` — black on white, no buttons, cards kept whole, three columns; two A4 pages in each language.
- Linked from the Tactical More panel (About, `m_guide`), the card (What to do →, and the ballistic warning's button), the top of the help sheet (`.gdl`), the Light footer (`#gdl`)
  and the nuclear-event banner (`/guide#rad`, `static/nuke.js`). The page asks the server for nothing.

### 10.5b A way back from everything (1.57.4)

The owner, the shelter list open on his phone: "there is currently no way to quit this popup" — "overall we need clear
return-to-home buttons in the app, simple and accessible".

- **Every sheet has its ✕** (`.shx`, the first thing in `#sheet` and `#homesheet`): top right, sticky while the sheet
  scrolls, 44 px, labelled in the reader's language (`btn_close`). The shelter sheets end with a Close button too
  (`SH_CLOSE`), like every other sheet.
- **The phone's back button closes what is open** — a target's card, the shelters, the place sheet, the bell, more or
  layers panel — instead of leaving the app: while one is open the page holds one history entry (`backSync`, watching
  their `class` / `hidden`); the back button pops it and closes them all (`closeAll`); closed by its ✕, a tap or
  Escape, the entry is taken back 300 ms later (a card replaced by another stays one entry). Escape closes it all.
- **Light**: the target's card had its ✕ (`#rcx`); the open shelter list now has one too (`SH.light`).
- **The guide**: "← Back" (§10.5).

### 10.6 The streets and villages of Ukraine (1.56)

The owner (10 Oct 2026): "for the district / village etc. it would be good to have a complete registry of the streets
within the city / oblast so the user can set the pin accurately" — then "all the towns and streets of Ukraine".

- **The data**: OpenStreetMap, © OpenStreetMap contributors, ODbL 1.0 (`static/streets/LICENSE.md`; credited in the list
  wherever a street or a village from it is shown). `scripts/build_streets.py DIR` reads the 27 regional extracts of
  download.openstreetmap.fr (`EXTRACTS`: one per oblast of the app, Kyiv and Sevastopol included; ~1 GB, not in git)
  with pyosmium and shapely — build-time tools, not the server's — and writes one file per oblast,
  `static/streets/<uid>.json` (format 1, described in the script): the **settlements** (every place = city / town /
  village / hamlet named in OSM inside the oblast's boundary — admin_level 4 —, streets or not, with its raion,
  admin_level 6) and the **streets** (every named way of a street's kind: residential, living street, the primary to
  tertiary roads, unclassified, pedestrian; a service road or a track only when its name is a street's — `STREET_WORD`
  —; never a road between towns, "Київ — Чоп", `ROAD_NAME`). A street belongs to the settlement whose boundary its
  middle is in (admin_level 9 — Ukraine's settlement boundaries — or a place area), or else to the nearest settlement
  node within that kind's reach (`REACH_KM`: 10 km for a city, 4 a town, 2 a village, 1 a hamlet); ways of one name in
  one settlement are one street: its point (the vertex nearest their centre), how far its ways reach, another name it
  is known by (`old_name` — the renamed streets: "Московський проспект" finds Bandera Avenue — or the Russian `name`
  where a `name:uk` was used, in Crimea), and in Kyiv its district (admin_level 10). The Ukrainian name (`name:uk`)
  first. 2026-10-10: 30,215 settlements, 230,814 streets; 15.8 MB, 3.9 MB gzipped (the server gzips them once, `_GZ`);
  Kyiv 2,710 streets (51 KB on the wire), Kyiv oblast 18,051 in 1,195 settlements (283 KB).
- **The search, on the phone** (`static/streets.js`, `HS`): the Tactical sheet (`#homesheet`) and Light's picker
  (`#pick`) load it when they open (`hsOpen`), and it adds a "Streets & villages in" choice under the search — "Kyiv
  and Kyiv oblast" (`31,14`), or any oblast (`localStorage.hs_obl`; the oblast of the pin being set first). It
  downloads that oblast's list once (`HS.load`), and after the page's own places it lists the **streets** (up to 50)
  and the **settlements** the page does not already have (up to 20). Every word typed starts a word of the street or of
  its settlement, one at least of the street: "шевченка бровари" is Shevchenko Street in Brovary; an apostrophe or none
  (лук'янівка, лукянівка); Latin typed against the Cyrillic names (`SK`: khreshchatyk). The settlement named first,
  then the bigger settlement, Kyiv before its oblast, the shorter name. A row: the street, its old name (uk) or its
  transliteration (en, fr), its settlement and (a village) its raion or (Kyiv) its district.
- **What is typed never leaves the phone**: the one request is the oblast's file — the server sees only which oblast's
  list was opened, the way it sees the map tiles a phone shows.

### 10.7 The shelters Kyiv city lists (1.57)

The owner's colleague: "a layer of the official shelters — only the government's data: metro, official shelters,
underpasses — baked into the app so the nearest one is found offline; no parking garages". The owner chose **every
shelter the city lists, each labelled with what it is** — the city's own list includes 2,882 "simplest shelters"
(basements, parkings), and keeping only ~520 would put the nearest one 1–2 km away for many pins.

- **The data**: the city's shelter map, https://gis.kyivcity.gov.ua/shelter/ (KMDA, ІАС «Майно»), an ArcGIS web app
  whose layer `public_protection/Укриття_редактор` (MapServer/0) holds the shelters; the map shows those with
  `actual = 1` (4,192 on 11 Oct 2026). The service states no licence: the source is credited on every list, and the
  owner asks KMDA. Its firewall refuses a script, so **the owner saves the list from a browser** — the query
  `…/MapServer/0/query?where=actual%3D1&outFields=guid,type,kind,type_building,address,district,working_time,invalid,tel,description&returnGeometry=true&outSR=4326&f=json`
  — and `scripts/build_shelters.py FILE` turns it into `static/shelters.json` (format 1, described in the script):
  `[lon, lat, category, kind, ramp, address, access, phone, note]`, 360 KB, 69 KB gzipped. Nothing is fetched by the
  server; Heimdall never calls the city's service.
- **Category and kind** (`classify`) from the city's "Тип укриття" and "Вид укриття": `metro` (stations, entrances),
  `underpass`, `shelter` (the type "Укриття" — a civil-defence structure — and the anti-radiation ones, ПРУ) — the three
  the pages call the strong kinds (`SH.STRONG`) —, `dual` (dual-use structures: parkings, basements, a ground floor),
  `simple` (the simplest shelters) and `mobile` (modular ones). A pair the rules do not know is a simplest shelter of no
  stated kind, never ranked higher than the city ranked it, and the build lists it. Several shelters of one category at
  one point and address (374 points) are one point — the one anybody may enter. 85 metro entrances are written
  "Вхід в станцію метро" with no station: the station within 350 m is named, as "біля ст. …" (`_name_entrances`).
- **Who may come in** (`_access`), from the city's "Режим роботи" and note, never guessed: round the clock; the hours
  where given ("10:00–18:00" — also when the hours say round the clock and the note says otherwise); `s` a school's,
  for its pupils and staff during the school day (841); `S` for them only (144); `r` under repair (7); `?` not stated.
  `S` and `r` are drawn dimmed and never offered as "the nearest" (`SH.closed`). A ramp: "з пандусом", or "В наявності".
- **On the phone** (`static/shelters.js`, `SH`, its words in its own three languages): loaded by the Tactical page for a
  pin in Kyiv city while an alert or a warning concerns it (`shCard`: `LEVEL >= 1`, the place's status not green, or
  the layer on) or when the layer is on (`shLoad`), by Light under an alert (`lShel` → `SH.light`, which also carries
  Light's look, so the page stays light). The service worker keeps both files (`FAST`). **One radius, 5 km round the
  pin** (`SH.RADIUS_KM`; 1.57.1, the owner: "shelters around me, a 5 km radius based on the pin"), for the card, the
  list and the layer. **The card** (`#mysh`): the nearest of the strong kinds, its address and access, and the nearest
  of any kind when nearer (`SH.line`). A tap — "Shelters around me": the three nearest of the strong kinds and the three
  nearest of the others — basements, parkings — (`openShelters`, `SH.listHTML`, `SH.near` with `strong` / `weak`), one
  row per address, each with its access and ramp; a tap on one shows it on the map (`shShow`). **The layer**
  ("Shelters around me (5 km)": `LAYERS.shelters`, off by default; `drawShelters`, `#shelg`): the shelters within 5 km
  of the pin (`SHNEAR`, worked out again when the pin changes — `drawHome`), inside a dashed circle (`.shr`); a square
  per shelter — filled for the strong kinds, ringed for the pin's nearest, dimmed for a school's own or one under repair
  (`SH.near` with `all`) —, the strong kinds from 120 km across and every kind from 8 km (1,500 at most; 893 within 5 km of Pechersk); no pin in
  Kyiv city, no layer, and switching it on says so (`shNoPin`). A tap on a square opens its card (`openShelter`,
  `SH.oneHTML`: address, access, distance from the pin, phone, the city's note).
- **What it never says**: a distance is a straight line ("відстань по прямій") — never a route, a walking time or a
  time to get there; a place is never "safe" — every list ends with "Heimdall does not check shelters: one may be
  closed, locked or full", the source and its date, and "Outside is dangerous during an attack. If you cannot get
  there in time: two walls between you and the street, away from windows." No shelter is offered outside Kyiv city.

### 10.8 The Android app (1.57.6)

The owner: "an app we can really install on the phone, an APK, without going through the Play Store first — in a
folder of its own, to keep things clear". It is **`heimdall-android`**, a separate folder (not in this repository): a
Trusted Web Activity built on Google's `androidbrowserhelper` — the app shows `https://kyiv-air-watch-gb.fly.dev/m` full
screen through the phone's Chrome, with its notifications (the library's `DelegationService`; Android 13+ asks the
reader once), its icon, a splash, and two shortcuts (Light, What to do). **Every release of this web app reaches the
Android app at once**; a new APK is needed only for its name, icon, address or Android behaviour. Identifier
`com.blackflamestudio.heimdall`; Android 7 (API 24) and later; `compileSdk`/`targetSdk` 36.

- **The signing key is the owner's**: made on his computer by `heimdall-android\scripts\2-make-key.bat` (keytool asks
  for the password; the key lives in `%USERPROFILE%\.heimdall`, outside both folders), used by `3-build-apk.bat`
  (apksigner asks for the password, nothing stored). A test build (`…heimdall.test`, "Heimdall (test)", the debug key)
  installs beside it.
- **The site says the app is its own**: `GET /.well-known/assetlinks.json` (`android_asset_links`) names the app and the
  fingerprint(s) in `ANDROID_CERT_SHA256` (`scripts/set-android-key.bat`, a Fly secret like the others — public, but set
  by the owner). Without it, Android opens the app with an address bar on top (a Custom Tab), as for the test build.
- No pin and no setting changes hands: the app is the web app, its storage the browser's.

### 10.9 As of when, and a raion named as one (1.57.8)

- **The line under the header** (`#asofbar`), from the government app's header the owner showed ("Станом на: 12 жовтня
  о 20:27 (1692 день) · Оновлення через 05 с · ⟳"): "Станом на 12 жовтня о 20:27 · 1692-й день війни" — the time of
  the server's last word, Kyiv's date and time (`asOf`), and the day of the full-scale war counted in Kyiv as the
  government app counts it, 24 February 2022 being day 1 (`warDay`); then "Наживо — зміни надходять одразу" while the
  live line beats, or "Оновлення через 05 с" counted down to the next ask without it (`nextPulse`); the stale and
  offline warnings as before. **⟳** (`#rfr`) asks everything again at once (`lastFull=0; pulse(true)`) and opens the
  live line again if it had dropped; it turns while that is under way (still, with reduced motion). In the header, so
  it shows with the card folded too; it replaces the card's "updated 5 s ago" (`mc_upd_s`, `mc_upd_m` removed).
  Light keeps its own "updated" line (its budget, §10.2).
- **A raion is named as a raion.** The owner: "it's the Vyshhorod district here, not the Vyshhorod city (which is
  rightfully placed correctly on the map)". Kyiv oblast's seven raions were written by their centre town alone —
  "ВИШГОРОД" in the middle of the raion (`RAION_LBL`), 30 km from the town, and "Вишгород" for an alert over the whole
  raion. Now `RAION_ADJ` gives each its name: "Вишгородський район" in the place's status and the list of raions under
  alert (`raionFull`), "Вишгородський р-н" on the map (`raionLbl`), "Vyshhorod raion", "raion de Vychhorod" (`lt_unit_r`,
  with "raion d'Obukhiv"); the place picker lists "Вишгородський район" (tests/test_asof_raions_1578.py).

## 11. Privacy and security

- The four places never leave the phone; the Light page's requests carry no place (checked in the render tests).
- 1.56: a street or a village is searched on the phone (`static/streets.js`); the server sees only which oblast's list
  was opened (`/static/streets/<uid>.json`, the Kyiv pair by default) — what the map tiles a phone shows already say,
  and less — never what is typed, nor the street chosen.
- 1.57.2: the Light radar's satellite or map background asks for the tiles of the ~10 km cell the place is in, never
  of the place itself (`LT.tiles`, §10.2): the server learns no more than the push already stores.
- 1.57: the nearest shelter is found on the phone (`static/shelters.js`), from one file that is the same for everyone
  (`/static/shelters.json`): no pin and no position is in any request.
- Push subscriptions: a ~10 km cell only; older stored homes are coarsened at start.
- 1.58: the private channel's bot token (`TG_BOT_TOKEN`) is the owner's, created by him at @BotFather and stored by
  `scripts/set-telegram-channel.bat` straight into Fly's secrets (asked hidden, read from stdin by `fly secrets
  import`). The server reads it from the environment and puts it only in the address of its calls to Telegram: no
  error, log line, dashboard row or `kv` entry carries it (`BotAPI` reports the method's name and Telegram's words).
  The bot posts and edits in that one channel; it reads nothing. Revoke it at @BotFather (/revoke).
- The Telegram session (`TG_SESSION`) is a key to a whole Telegram account. It is created on the owner's PC by
  `scripts/telegram-login.bat` and goes straight into Fly's secret store (`fly secrets import`, read from stdin):
  never on a command line, in a file, in the logs, in `config.json` or in the repository. Revoke it in Telegram:
  Settings → Devices → "Clear Sky server" → Terminate.
- Usage counters (`usage`, `usage_seen`): a daily salted hash, no IP address, no location, no per-person
  history. A page the browser loads ahead of a tap (prerender, `Sec-Purpose: prefetch`) is not counted (1.40).
- Flags and the corpus review are behind `ADMIN_KEY`.
- The AI reader (1.50, §7.7) sends OpenRouter only public posts (the channel's text, its name, our place names), a
  card-like run of digits masked; never anything about a reader. Its key (`OPENROUTER_API_KEY`) is set by the owner
  with `scripts/set-openrouter-key.bat`, straight into Fly's secrets. Its readings are behind `ADMIN_KEY`.
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
| `GET /.well-known/assetlinks.json` | 1.57.6: the Digital Asset Links that let the Android app open this site full screen (§10.8): `[]` until `ANDROID_CERT_SHA256` is set |
| `GET /healthz` | liveness: `{"ok": true}`, or **503** when the database cannot be had within 3 s |
| `GET /api/version` | `{v, now, missile, msl, build, app}` — the cheap ping pages poll |
| `GET /api/state` | active alerts, per-oblast status, whether each source works (1.46: `{ok}` only — the detail is `/api/health`), єРадар counts, the admin's message, the nuclear event, the Kyiv bridges (`bridges`, §9b), the oblasts on the map (`scope`, 1.43), config summary |
| `GET /api/markers` | live marks with evidence, history, staleness; 1.51: each target in the air with its `tag` (§7.8) |
| `GET /api/bulletin` | 1.54 (§7.11): `{on: false}` while the dashboard's switch is off; else `{on: true, h1, h24}`, each the latest bulletin still checked (`at`, `since`, `until`, `quiet`, `uk`, `en`, `fr`) or null |
| `GET /api/trail?night=&n=` | 1.52.1: a tag's path for the night (§7.8), oldest first: `{night, n, points: [{ts, lon, lat, place, alt}]}` — at most 300 |
| `GET /api/feed?limit=&lang=` | recent posts (`text`, `text_en`, `text_fr`, `en_mt`, tags, and `home` for a regional channel's post — 1.43); `lang` asks for translation |
| `GET /api/stream?sync=&ev=&p=&lang=` | the live line (§5.4): `hello`, `sync` (changes of `mk`, `st`, `fd` as asked in `sync`) and, unless `ev=0`, the events `start`, `end`, `threat`, `update`, `feed`, `eradar`, `tr`, `notice`, `nuke`; `p=light` counts it as a Light page |
| `GET /api/history?hours=&oblast=` | past alerts (1–168 h; cached, one query per change for every page) |
| `GET /api/events_log?limit=` | alert events |
| `GET /api/impacts?hours=` | explosions and confirmed shoot-downs |
| `GET /api/replay?from=&to=` | the replay (§10.3c), Unix seconds, ≤ 26 h within the last 7 days: `alerts` `[{k, o, lt, rk, lv, at, ti, s, e}]` (intervals, `e` null while on) and `tracks` `[{ty, jet, n, ap, h, ch, p: [[t, lon, lat, place]], tg}]` (1.51: `tg`, the tag the live map gave, or null) |
| `GET /api/stats?days=` | statistics; the Stats tab reads only `windows` (with `af`: launched / down by type, used, impacts, debris) and `af_days` (the Air Force summaries, each with its `post`) |
| `GET /tiles/sat/{z}/{x}/{y}.webp` | the satellite layer's tiles (1.47, §10.1): WebP from `SAT_TILES`, cached a year (`immutable`); 404 where there is none |
| `GET /tiles/esri/{z}/{x}/{y}.jpg` | the satellite layer's closest zooms (1.48, §10.1): Esri World Imagery asked with `ESRI_KEY`, zoom 14–18 over Ukraine only, nothing kept; 404 outside / no key, 429 past a cap, 503 key refused |
| `GET /tiles/esri/{kind}/{z}/{x}/{y}.{jpg\|png}?lang=` | 1.49 (§10.1): `img` (the imagery again), `lbl` (roads and names over it, zoom 9–18), `map` / `mapn` (the street map, light / dark, zoom 4–18) — Esri's Static Basemap Tiles in the reader's language; same key, caps and answers |
| `GET /api/places?oblast=` | gazetteer (names, coordinates, oblast; 1.46: built once an hour, gzipped): `oblast=14,31,…`, `all`, or (1.43) `scope` — the oblasts the map covers now; (1.45) `villages=scope`: the regional villages of those oblasts (hromada centres and places of 1,000+, `geo.villages`), for the map's villages layer, cached an hour |
| `GET /api/drone_heat?days=1|7|30` | the heat layer: `points` `[lon, lat, posts, place, oblast]` — where drones and unidentified targets were reported (cached 10 min) |
| `POST /api/push/subscribe`, `/api/push/unsubscribe`, `/api/push/test`; `GET /api/push/key` | Web Push; subscribe takes `{subscription, home, topics: ["bridges"], lang}` |
| `POST /api/flag` | "this reading is wrong" report |
| 🔒 `GET /admin`, `/api/usage` | dashboard, usage counters |
| 🔒 `GET /api/health` | official sources (ok, last check, detail), every channel read (posts / marks 24 h, share read 7 d, last post, reader state, `mode`, `read_via`, `builtin`, `home`), the compartments (`regions`: `id`, `name`, `en`, `on`, `locked`, `channels`), translation backends, lead time over the official alert in Kyiv + oblast (30 days), the imagery (`imagery`, 1.48) and the AI reader's state (`ai_reader`, 1.50) |
| 🔒 `GET /api/online` | pages open now with a live line (`total`, `tactical`, `light`, today's peak), the current message, the nuclear event (`nuke`), the last push fan-out (phones, seconds, delivered) |
| 🔒 `GET /api/analytics?days=` | the dashboard's Analytics (§8c), 7–365 days: `af` per date (launched, down, used, impacts, debris, periods), `af_areas`, `af_directions`, `af_models`, `kyiv` per date (city / oblast minutes, city alerts), `starts` (7 × 24), `reports` per date by type, `hours`, `headings`; since 1.33 `weather` per date (`kyiv`, `launch`), `approach` (8 sectors per date), `air` (`per_date`, `stats`, `sorties`), `obl` (`by`, `cols`, `rows`), `weather_status`; since 1.34 `places` (the heat layer's top 25) and `bridges` (`per_date`, `totals`, `recent`) |
| 🔒 `POST /api/admin/nuke` | `{action: arm}` → `{code, expires_s, phrase}` (refused while one is on); `{action: fire, code, phrase, text: {uk, en, fr}, push}`; `{action: end}` — the nuclear event (§9) |
| 🔒 `POST /api/admin/channel` | `{action: add|set|delete, name, mode: map|trial|off, via: web|api, home}` — the channels read (§7.1); `home` is the compartment (an oblast uid, `31`, `ua`, or `""`); `add` checks `t.me/s/<name>` for readable posts and starts it on trial |
| 🔒 `POST /api/admin/ai` | `{reader: bool}` — the AI at all (every call stops); 1.54 (§7.11): `{bulletin_public: bool}` — the bulletins in the app; `{bulletin_now: "1h"\|"24h"}` — asks the `bulletins` thread to write one now. (`live`, `mode`, `check_now` went with the AI's reading in 1.54) |
| 🔒 `GET /api/admin/night?night=YYYY-MM-DD` | 1.53: one night in full (§7.10): `summary` (`State.night_summary`), `text` (`State.night_text`), `report` (the AI's, or null), `reports` (the nights that have one), `writing`, `report_hour` |
| 🔒 `GET /api/admin/patterns?days=&kind=&res=&min=&raw=` | 1.55: the direction patterns (§7.12) — `days` 0–3650 (0: all; 90), `kind` `drones`\|`drone`\|`jet`\|`unstated`, `res` 1\|2\|4 (×14 km), `min` (3): `coverage` (`moves`, `tracks`, `nights`, `first`, `last`, `stated`, `cells`, `by_kind`, 1.56.1 `by_src`, `stated_first`, `built`, `version`), 1.56.1 `plain` (`en`, `uk`: the sentences, the first on what they are built from; `found`), `cell_deg`, `cell_km`, `cells` (≤ 400, busiest first: `cell`, `lon`, `lat`, `name`, `names`, `moves`, `tracks`, `nights`, `dir`, `dir_p`, `mean_bearing`, `consistency`, `stay`, `next`, `next_places`, `through`, `final`, `final_places`, `origins`, `stated`, `stated_n`, `said`, `speed_kmh`, `gap_min`; each share `{n, p, lo, hi}` in %, Wilson 95%); `raw=1` adds `moves` (≤ 50,000, not cached). Cached 5 min |
| 🔒 `POST /api/admin/ai_report` | 1.53: `{night}` — asks the `night-reports` thread to write (again) that night's report |
| 🔒 `POST /api/admin/channel_switch` | 1.58.3 (§9c): `{on: bool}` — the private Telegram channel's kill switch (`kv` `chan_on`); answers `{channel: {configured, running, on, health}}`, also on `/api/online` |
| 🔒 `POST /api/admin/region` | `{id, on}` — an oblast on or off as a whole (1.43, §7.1): its place on the map and its channels; `31` is always on |
| 🔒 `POST /api/admin/notice` | `{text: {uk, en, fr}, level: info|warn|alert, hours: 0–168 (0 = until removed), push: bool}` or `{clear: true}` — the team's message (§9) |
| 🔒 `GET /api/ai_reads?limit=&all=` | the dashboard's AI tab: `stats` (`key`, `enabled`, `model`, `prompt_v`, `mode` "bulletins", `usd_month`, `cap_usd`, `paused`, `last_error`, 1.54 `bulletins_month`, `usd_bulletins_month`, `bulletin_errors_month`; and of the readings before 1.54 `reads_month`, `by_verdict`, `ms_median`), 1.54 `bulletins` (the last 30, with the record each was written from) and `bulletin` (`public`, `every_min`, `writing`, `why`), `checks`, and `reads` (newest first, ≤ 300; only the disagreements and errors unless `all=1`): post, channel, `stored`, `verdict`, `rules`, `ai` (`targets`, `uncertain`), `dropped`, `cost`, `ms`, `model`, `error` |
| 🔒 `GET /api/digests` | the stored nights and weeks: figures, written summary (EN / UK), model |
| 🔒 `POST /api/digest/run` | `{kind: night|week}` — asks the `Digests` thread to write the last one up now (never calls the model itself) |
| 🔒 `GET /api/flags`, `/api/corpus`; `POST /api/corpus/review`, `/api/corpus/translate` | flags and corpus review — no longer in the dashboard (1.19); used by `scripts/corpus.py` |

## 13. Storage

SQLite in WAL mode (`DB_PATH`; on Fly, the volume). Tables:

| Table | Holds |
|---|---|
| `alerts` | every alert seen (active and finished) — the normalised shape. One row per region and alert type (key `ua:<region>:<type>`): a region's next alert rewrites the row — since 1.58.4 its start too (before, the start stayed the region's first). **Not a history**: what happened over time is read from `events` (`State.alert_rows`, below) |
| `events` | start / end / threat / update events — the alert history the replay rebuilds intervals from (§10.3c) |
| `feed` | posts: `post_id, channel, ts, text, tags, text_en, text_fr, en_mt` |
| `kv` | small settings: the VAPID key pair, the usage counter's daily salt, the channels (`channels`), the admin's message (`notice`), the nuclear event (`nuke`), the AI's switches (`ai_reader_on`, 1.54 `ai_bulletin_public`), 1.58 the private channel's posts of the last 24 h (`chan_posts`: per target, the message id, when first and last reported, what was drawn — never the token), and similar |
| `push_subs` | push subscriptions with a ~10 km cell, the topics asked for (`bridges`) and the language |
| `marker_log` | every mark as computed, with its evidence; 1.54.8: and what it stated — `alt_m`, `alt_state`, `speed_kmh`, `origin`, `target`, `likely`, `tag` (night#n), `approach` (`MLOG_EXTRA`). Kept for good so far: `Store.prune_log(days)` exists but nothing calls it — the volume's size is the limit |
| `outcomes` | shoot-downs, impacts, losses |
| `channel_stats` | per channel per day: posts, posts with a reading, flagged readings |
| `digests` | each night / week: the figures (JSON), the summary in EN and UK, the model, any error |
| `af_reports` | each Air Force summary read (§7.5): `post_id, channel, ts, period, date` and the reading (JSON) — kept for good, one row per post |
| `air_reports` | what posts reported about the carriers (§7.6): `post_id, kind, phase, channel, ts` and a fingerprint of the text |
| `bridge_events` | each time a target was reported on or near a Kyiv bridge (§9b): time, bridge, level, km, type, place, channel |
| `weather` | each night's weather per point (`date, place`, JSON: mean wind, strongest gust, mean cloud cover, rain, lowest temperature) |
| `flags` | readings people reported as wrong |
| `corpus_reviews` | verdicts from `/admin` review, merged back with `scripts/corpus.py pull` |
| `targets` | 1.51: each target tag (§7.8) — `night`, `n`, the letter, origin, whose reading (`osrc`), its words, the post, first / last time, type. Kept 60 days |
| `target_reports` | 1.51: which tag each report of a track belongs to (`report` = the mark id) — how a tag survives the window and a restart |
| `target_points` | 1.52.1: where each report of a tagged track was (`report`, `night`, `n`, `ts`, `lon`, `lat`, `place`, `alt_m`) — the tag's path for the night, `/api/trail`; 60 days |
| `track_moves` | 1.55: each tagged target's moves (§7.12) — `night`, `n`, `seq`, from / to (`ts_*`, `lon_*`, `lat_*`, `place_*`, `alt_*`), `km`, `minutes`, `bearing`, `kind`, `origin`, `osrc`, `ver`, 1.56.1 `src` ("tag", or "replay": a night read again from its posts); the direction patterns' foundation, **kept for good** (`kv` `moves_v`, `moves_at`) |
| `ai_reads` | 1.50: the AI reader's reading of each post it read (§7.7) — when, the post, whether the rules stored it, model, prompt version, ms, tokens, cost, verdict, the rules' reading and its own (JSON), facts dropped, error. Kept 90 days; the month's spend is `kv` `ai_usd:YYYY-MM`. 1.53: `chk`, the check that read it (its `ai` then holds the findings: `targets` with `f`, `findings`) |
| `ai_checks` | 1.53: each 10-minute check (§7.10) — `id` (its UTC time), the posts' first and last time, how many, the oblasts, model, prompt version, ms, tokens, cost, `findings` (by kind), `notes` (per oblast), `uncertain`, `error` |
| `ai_reports` | 1.53: the AI's report on each night (§7.10) — `night`, when, up to when, model, tokens, cost, `text`, `error` |
| `ai_bulletins` | 1.54: each bulletin (§7.11) — `kind` ("1h" / "24h"), when, the window (`since`, `until`), `quiet`, `sig` (a hash of the record), `uk`, `en`, `fr`, model, tokens, cost, `error`, and `input` (the record it was written from). 1.54.8: all of them 90 days, then one an hour and one a day for good (`kept`, `bulletin_prune`); `kv` `ai_bulletin_public` (the app's switch) and `bul_checked:<kind>` (when the latest was last found still true) |
| `usage`, `usage_seen` | anonymous usage counters |

Columns are added in place by `Store.__init__` (`ALTER TABLE … ADD COLUMN`), so an old database upgrades itself.

Next to the database, on the volume (1.47): **`sat-ua.mbtiles`**, the satellite layer (`SAT_TILES`, §10.1) — an
MBTiles file (SQLite, `tiles` / `metadata`), read-only for the server, built once by `scripts/build_imagery.py`
and uploaded by `scripts/upload-imagery.bat`. Never in git or the image (`imagery/` is in `.gitignore` and
`.dockerignore`). 1.48's zoom-13 file is 406 MB: the upload goes beside the old file before it replaces it, so the volume needs
~0.45 GB free for it (the 1 GB volume has it; `fly volumes extend` otherwise, DEPLOY.md). No Esri tile is ever stored.

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
  new one. The image is built by Fly's own builder (`--depot=false`); if that deploy fails — its builder machine
  sometimes does not answer ("failed to get status … unable to upgrade to h2c, received 500") — it tries once more
  with Fly's other builder, Depot (1.41.4). GitHub is pushed only after a deploy succeeded.
- **First deployment, or changing a key**: `deploy-fly.bat` (Windows) — sign-in, app, volume, the dashboard
  key, the optional DeepL key, deploy. Details in [DEPLOY.md](DEPLOY.md). `fly deploy -a kyiv-air-watch-gb`
  alone also works.
- **GitHub**: `scripts\github-push.bat` creates the **private** repository `<you>/clear-sky` with the GitHub CLI
  (sign-in in the browser; no token is ever typed or stored by the script) and pushes; run again to push new
  commits. Optional auto-deploy: add the repository secret `FLY_API_TOKEN` and `fly-deploy.yml` deploys every
  push to `main`.

### When the app "goes off"

Four causes look the same from a phone, and the dashboard (Live → **Server**, 1.41) tells them apart:

- **a release** — a start with a new build in the list of starts: every deploy restarts the one machine (the
  database is on its volume), a few seconds to half a minute without answers. Deploy outside attacks.
- **a crash or an out-of-memory kill** — "starts without a new version" above zero; `scripts\diagnose.bat`
  shows the machine's events (`exit_code`, `oom_killed`) and the last logs.
- **throttling** — "taken by the host (steal)" above ~10 %, late wake-ups, slow requests: the shared vCPU has
  spent its burst balance and runs at its 6.25 % baseline (Fly's CPU quota). Remedy: a bigger machine, or
  less work per minute. Since 1.41.1 production runs on a dedicated CPU (`performance-1x`, 2 GB), which has no
  burst balance to spend: steal should stay near 0. 1.46 removed the work that most likely caused it (§5.5): once
  an attack night has been watched on the dedicated CPU with 1.46, a shared machine (`shared-cpu-4x`, 1 GB: a 25 %
  baseline) may be enough again — at about a quarter of the cost. The size is `[[vm]]` in `fly.toml` — `fly deploy` resets the
  machine to it, so a `fly scale vm` without editing the file lasts only until the next release.
- **a slow piece of work** — slow requests on one path with normal steal; the watchdog's stack dump in the logs
  names it.

`scripts\diagnose.bat` (double-click on the owner's PC) writes `fly status`, the machines and their event logs, the
recent logs and 20 timed pings to `diag\fly-diag.txt` (git-ignored): no key, no token, nobody's address.

## 16. Maintenance recipes

**Rebuild the streets** (1.56, §10.6): download the 27 extracts of https://download.openstreetmap.fr/extracts/europe/ukraine/
(`kiev.osm.pbf`, `kiev_oblast.osm.pbf`, … — `EXTRACTS` in the script) into a folder outside the repository, then
`pip install osmium shapely` and `python scripts/build_streets.py THAT_FOLDER` (or name the extracts or uids to rebuild
only those); about 10 minutes on two cores. Raise `V` in `static/streets.js` when the format changes.

**Refresh the shelters** (1.57, §10.7): open the city's query (§10.7) in a browser, save it as
`imagery/shelters-kyiv.json` (not committed), then `python scripts/build_shelters.py imagery/shelters-kyiv.json`. It
refuses a list of under 1,000 shelters (a page of the answer) and names any type/kind pair the rules do not know.

**Rebuild the geography** (after an administrative change, or when the log says "not in ua_regions.json"):
`python scripts/build_geo.py` — downloads the official region list, rewrites `data/ua_regions.json` and
`static/light-map.json`, prints any raion it could not match to a map shape. Run the tests; commit both files.

**Telegram sign-in for the API reader**: create an app on <https://my.telegram.org> (API development tools),
then run `scripts\telegram-login.bat`: it asks for the api_id, the api_hash and the phone number of the reading
account (a dedicated account is best), signs in with the code Telegram sends, joins the channel, and stores the
three secrets on Fly. If the sources panel ever shows "Telegram session no longer valid", run it again.

**Add or remove a channel**: from the dashboard (Live → Telegram channels, oblast by oblast — pick its oblast; it
starts on trial). As a default: edit `AUTHORITATIVE_CHANNELS` and `CHANNEL_HOME_DEFAULT` in `server.py` (and
`DEFAULT_CONFIG` for the record);
a channel whose web preview is off also goes in `telegram_api_channels`;
a fixed format gets a parser in `geo.py` registered in `CHANNEL_PARSER`; add real posts to the corpus
(`scripts/corpus.py add`); a mixed channel goes in `NEWS_CHANNELS`.

**Change the region**: an oblast on or off is a switch in the dashboard (1.43). The default is `DEFAULT_SCOPE` in
`server.py`. An oblast with a tracker of its own also wants its villages: add its GeoNames admin1 code to `ADMIN1`
(and its raions to `RAION`) in `scripts/build_places.py` and rebuild `data/regional_places.json`
(`python scripts/build_places.py`); and its raions for the Light page: `SCOPE` in `build_geo.py`, then
`python scripts/build_geo.py --light` (the oblasts after the first eight go to `static/light-map-x.json`, fetched
only for a place there — add the oblast's uid to `loadLMX`'s list in `static/light.html`; the base `light-map.json`
is at its size budget, so the far oblasts' outlines are not in it).

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
- 1.43: the regional villages come from GeoNames, whose Russian names are often transliterations and whose
  Ukrainian names are sometimes a renamed village's old one; a village GeoNames does not have (Cherkasy's Mytnytsia
  district) is not placed. `chyste_nebocherkasy` needs the Telegram API (its preview is off). The new trackers'
  formats were read from a day of their posts: watch the first nights in the dashboard (Read 7 d) and add their
  misreads to the corpus.
- 1.58: the private channel follows the map's marks, so it is as right as they are, and a little later (it looks every
  5 s, redraws a post at most every 45 s). Telegram allows about 20 messages a minute in a channel: on a heavy night
  the channel keeps to 18 calls a minute, new targets first, and a target first reported more than 5 minutes ago is
  not posted late. One post per target tag: two tags the app could not join are two posts.
- 1.45: GeoNames has no Гулівці, Мокроволя, Завірці, Кром'яне — those posts place nothing. "Велика Березна" from
  Rivne still reads as Березне. Natural Earth's rivers are 1:10m — about a kilometre off in places — and its roads
  carry no names, so the roads outside Kyiv oblast are unlabelled lines.

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
6. **Rebuild the manual**: `python scripts/build_manual.py` (docs/manual.html, stamped with the documents' hash —
   `tests/test_manual.py` fails until it is rebuilt). A new source, thread, table or route also goes on the system map
   by hand (`scripts/manual/map-svg.html`; the test checks its channel counts and speed limits against the code). The
   shared copies (the "Heimdall Technical Manual" page and its PDF, `--pdf FILE`) are published again from it.
7. Commit in the working folder (never `config.json`), then ship with `scripts\release.bat` (deploy + push).
8. Post the patch note to users once it is live.
