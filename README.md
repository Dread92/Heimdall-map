<p align="center">
  <img src="docs/brand/heimdall-logo.png" width="280" alt="Heimdall">
</p>

# Heimdall

**Unofficial air-raid and drone tracker for Kyiv, Kyiv oblast and the oblasts around it — and, since 1.43, Odesa,
Kharkiv and Dnipro oblasts.**
*Formerly Clear Sky — same app, same address, new name (1.29).*

A single Python service (standard library only) reads the official «Повітряна тривога» alert data raion
by raion, and eleven public Telegram channels — the Air Force, the live trackers of the Kyiv sky, and one tracker
each for Chernihiv, Odesa, Cherkasy, Kharkiv and Dnipro — parses the Ukrainian (and Russian) text, and shows what was reported in two ways: **Tactical** (`/m`), the full map with the evidence
behind every mark, and **Light** (`/light`), one place, its raion's official status and what is within 30 km.

> ### ⚠ This is not an official warning system
>
> Positions are **what a public post said**, machine-read — never radar, never exact, sometimes
> wrong. Follow the official *Повітряна тривога* app and the sirens first, and **go to a shelter as
> soon as an alert starts**. Nothing here should ever be used to decide it is safe to stay outside,
> to delay taking cover, or to go and watch. See [docs/SAFETY.md](docs/SAFETY.md) for the rules the
> code itself follows.

---

## Quick start

```bash
git clone https://github.com/Dread92/clear-sky.git
cd clear-sky
python app/server.py --demo          # fake alerts, no token needed
```

Open **http://localhost:8642/m**.

For real data, copy the config template and add a token (free, see [Sources](#sources)):

```bash
cp config.example.json config.json   # Windows: copy config.example.json config.json
# put your alerts.in.ua token in "alerts_in_ua_token", then:
python app/server.py
```

Windows: double-click **`start.bat`** — it installs the one optional dependency, starts the service
and opens the browser. Linux/macOS: `scripts/start.sh`.

*French quick start: [docs/DEMARRAGE-FR.md](docs/DEMARRAGE-FR.md).*

## What it does

| | |
|---|---|
| **Alerts by raion** | Each raion coloured by its own official alert, at the government app's level — red (massed drones, missiles) or yellow (drones) — never the whole oblast for one raion. |
| **Your place first** | The Tactical page opens on a card for the place you watch — Home, Work, Kids or a pin: its raion's official status, the MiG-31K / ballistic warning with what to do, the one target that matters most for it with its distance, and how fresh the data is. Below: the map, then Near · Feed · Alerts · Stats. Alerts settings behind a bell, the rest behind More, map layers on the map. |
| **Light version** | `/light`: Home, Work, Kids or a pin; the official status of that place's raion; a 30 km radar over a small local map; tap a row for what the post said. The places never leave the phone. |
| **Targets where they were reported** | Shaheds are drawn loitering around the reported point (their real path is erratic) with a chevron for the reported heading. No extrapolated trajectory unless you switch on EST, no invented ETA — [why](docs/SAFETY.md#no-liberties-with-trajectories). |
| **Per-target justification** | Tap any marker: the sentence it came from, the channel, the time, how position / heading / count were read, the confidence, and other reports nearby. |
| **Goes grey, then goes away** | A target with no new report for 5 minutes turns grey with a `?`, fades in steps, and disappears after 15 minutes. Stale is never shown as active. |
| **Preventive warnings** | MiG-31K take-off and ballistic threats raise a banner *before* anything is seen — and it disappears the moment a later post lifts it. Nightly *assessments* ("threats are above average tonight") are classified as forecasts and never raise it. |
| **Live, without asking** | The server sends each open page what changed — a new mark, a new post, an alert — the moment it knows, in one small message, and beats every 15 s (5 s with cruise missiles up, 2 s with a ballistic one). A page asks for nothing while its line is alive, and falls back to asking by itself when it is not. |
| **Missile mode** | The server reads its sources faster while a ballistic or cruise-missile threat is open, and the live line beats faster with it. |
| **History layer** | Explosions ✸ and confirmed shoot-downs ✕ over the last 24 / 48 / 72 h. |
| **Replay** | The last 24 hours or any of the last seven nights, played back on the map like a weather-radar loop: the official alert colours of each moment and the targets where the posts put them, with a time bar to drag, play and step. Nothing live or personal on the map while it plays — made for presentations (`/m#replay`). |
| **Stats** | The Air Force's own figures for all of Ukraine (24 h / 7 d / 30 d), weapon by weapon: drones (jet ones apart), Banderol, cruise, ballistic, aeroballistic, anti-ship and guided missiles — launched and shot down, "used" when the summary gives no number — and the hit locations, then each night's and day's summary with a link to it. |
| **Three languages** | Full UI in 🇬🇧 English, 🇺🇦 Ukrainian, 🇫🇷 French — including place names, raions, districts and channel names. See [docs/I18N.md](docs/I18N.md). |
| **Altitude when it is stated** | A post saying `знижується` marks the target ↓ DESCENDING in crimson — it is diving. Climbing, low, high and values in metres are read the same way. Never inferred: no public source publishes altitude. |
| **Push notifications** | Web Push (VAPID / RFC 8291, hand-rolled on `cryptography`) wakes the phone with the app closed — for a target reported within your radius, a MiG-31K take-off or a ballistic threat. No siren-start or all-clear pushes: the siren already says that. Sent to every phone at once over kept-open connections: a thousand phones in seconds, not minutes. |
| **Sources from the dashboard** | Add a Telegram channel, switch one off, or read it through the Telegram API — no deploy. A new channel starts on trial: shown in the feed, flagged, nothing on the map until you trust it. |
| **Oblast by oblast** | The dashboard groups the channels by the oblast they speak for, each oblast with its own switch: off, and it leaves the map. A regional tracker's posts are read against its oblast's villages and city districts (GeoNames), in Ukrainian or Russian; a village name several villages share is placed only when something says which. |
| **A word from the admin** | From the dashboard, one message to every reader — in Ukrainian, English and French, as information (bright green), a warning or urgent (bright red, pulsing), for a set time — shown as a banner on both pages, optionally also as a push. |
| **Analytics** | A dashboard tab with the trends: drones and missiles by type per night, the share shot down, jet drones, hits, launch areas and directions (Air Force); hours under alert in Kyiv, when alerts start, what the channels reported over Kyiv, by hour and course. 7 days to a year; every table downloads as CSV for Excel. |
| **Kyiv bridges** | The Kyiv HPP dam, Northern, Petrivskyi (rail), Podilsko-Voskresenskyi, Metro, Paton, Darnytskyi, Southern: a one-line red / amber bar and the crossing on the map when a target is reported at or near one, a tone and a vibration, and a push in the phone's language for those who want it. "Hit" only when a post says the bridge was hit — never from an explosion. |
| **Heat map** | Where drones were reported over 24 h, 7 days or 30 days, place by place — corridors zoomed out, villages and Kyiv districts zoomed in. Not live, off at every opening. |
| **Carriers, weather, approach** | On the dashboard: MiG-31K / Tu-95 / Tu-22M3 take-offs and the time to the launch, the weather of each night against the drones launched, the sides of Kyiv drones are reported on, alert hours by oblast week by week. |
| **What to do** | `/guide`: the official guidance (ДСНС, police, Ministry of Health), weapon by weapon — how much warning, how you notice it, what to do — and in a car or on a bridge, outside, at night, with children, after a strike, in a radiation danger; the emergency numbers to tap. Opens offline, prints on two A4 pages. |
| **Nuclear event** | For a confirmed nuclear or radiological emergency only: the radiation symbol over the map on every page with the admin's instructions. Behind three locks on the dashboard (arm → one-time code + phrase → hold 3 s); ended in one click. |
| **Sound you can turn down** | A volume slider, not just on/off: an iPhone played the tones at full media volume. Test it with ▶. |
| **Share in one tap** | The status of any target as text, for a chat: what, where, when, descent, heading, distance, source, and the caveat that it is not radar. |
| **Install as an app** | A PWA: add it to the home screen and it runs full-screen with no browser bar. No store, no download. |
| **Blackout mode** | For 2G during an attack: black and white, no tiles, no images, minimal data. |
| **Knows when it is stale** | A page left open for days notices that the server has a newer build and offers a one-tap reload. |
| **Your place** | Pick an oblast for the status band and, optionally, a precise place: targets heading there or within 10 km alert first. |

## Layout

```
clear-sky/
├── app/                    the service — four modules, no framework
│   ├── server.py           HTTP + API + SSE, pollers, SQLite store, marker logic
│   ├── geo.py              Ukrainian parsing: places, declensions, headings, counts, channel formats
│   ├── translate.py        offline UA→EN glossary; DeepL / Google machine translation, on demand
│   └── push.py             Web Push: VAPID ES256 JWT + aes128gcm
├── static/                 the whole front end
│   ├── kyiv.html           Tactical: SVG map, markers, sheets, stats (one self-contained page)
│   ├── light.html          Light: one place, its raion, a 30 km radar (one self-contained page)
│   ├── light-map.json      raion outlines, rivers, roads, towns for the Light map (built)
│   ├── i18n.js             EN / UK / FR strings, place and channel names
│   ├── live.js             applies the live line's changes (shared by both pages)
│   ├── kyiv-map.json       27 oblasts + 136 raions, projected to km around Kyiv
│   ├── kyiv-districts.json the 10 Kyiv city districts (OSM boundaries)
│   ├── sw.js               service worker (push + notification clicks)
│   └── manifest.json       PWA manifest ("add to home screen")
├── data/                   ua_regions.json (official region ids, built) · corpus.jsonl (regression corpus)
├── tests/                  ~400 tests — parsing, alerts by raion, privacy, languages, live line, push, documentation
├── docs/                   TECHNICAL.md (complete reference), SAFETY, DEPLOY, I18N, CORPUS
├── scripts/                release.bat, set-domain.bat, set-ai-key.bat, telegram-login.bat, build_geo.py, corpus.py, …
├── start.bat               Windows: double-click to run
├── deploy-fly.bat          Windows: one-click deploy to Fly.io
├── Dockerfile · fly.toml · render.yaml
└── config.example.json     template — copy to config.json and add your token
```

Read [docs/TECHNICAL.md](docs/TECHNICAL.md) before changing anything in `app/` — it is the complete
technical reference, updated with every patch.

## Configuration

`config.json` is created from the template on first run and is **git-ignored** (it holds tokens).

| Key | Default | What it does |
|---|---|---|
| `port` | `8642` | HTTP port (`PORT` env var wins — that is what Fly.io sets). |
| `use_siren_proxy` | `true` | Official alerts by raion through the keyless siren.pp.ua proxy. |
| `ukrainealarm_key` | `""` | Read the official API (api.ukrainealarm.com) directly instead. |
| `alerts_in_ua_token` | `""` | Optional: alerts.in.ua as the primary alert source. |
| `use_ubilling_fallback` | `true` | Oblast-level mirror, only while the raion source is down. |
| `deepl_key` | `""` | EN/FR machine translation of the feed (or `google_translate_key`). |
| `favourites` | `["31","14"]` | Region UIDs that drive notifications (31 = Kyiv city, 14 = Kyiv oblast). |
| `poll_alerts_seconds` | `15` | Alert feed interval. |
| `poll_telegram_seconds` | `30` | Telegram interval, normally. |
| `poll_telegram_missile_seconds` | `10` | Telegram interval while a missile threat is open. |
| `track_stale_minutes` | `5` | No new report for this long → the target goes grey with a `?`. |
| `marker_ttl_minutes` | `45` | Hard ceiling on how long any marker can live. |
| `history_backfill_hours` | `6` | How much history to pull at startup. |
| `bind` | `0.0.0.0` | Set to `127.0.0.1` to keep it on this machine only. |

Environment variables and every other key: [docs/TECHNICAL.md §5](docs/TECHNICAL.md#5-runtime-configuration-and-secrets).
The eleven default channels are in code (`AUTHORITATIVE_CHANNELS`), not in the config; the dashboard adds others
(on trial until you put them on the map), switches any of them off, or reads one through the Telegram API.

## HTTP API

Everything the page uses is public JSON; you can build your own client on it. The complete list, including
the admin routes: [docs/TECHNICAL.md §12](docs/TECHNICAL.md#12-http-api).

| Route | Returns |
|---|---|
| `GET /m` | The app (also `/`, `/k`, `/kyiv`). |
| `GET /api/state` | Active alerts, per-oblast status, threats, source health, єРадар counts. |
| `GET /api/markers` | Live targets with position, heading, count, staleness, and full evidence. |
| `GET /api/impacts?hours=24` | Explosions and confirmed shoot-downs in the window. |
| `GET /api/replay?from=&to=` | A past window (≤ 26 h, last 7 days): official alert intervals and the targets' reported positions. |
| `GET /api/stats?days=14` | Daily series, hour-of-day histogram, launch totals, per-oblast outcomes. |
| `GET /light` | The Light version (also `/l`). |
| `GET /api/feed?limit=150&lang=en` | Recent parsed posts with tags and translations (`lang` asks for machine translation). |
| `GET /api/history?hours=24&oblast=31,14` | Past alerts for those regions. |
| `GET /api/version` | Tiny version ping (`v`, `now`, `msl`) — a page asks it once a minute while its live line is up. |
| `GET /api/stream?sync=mk,st,fd` | The live line (server-sent events): `hello`, then `sync` messages carrying what changed in the marks, the alerts and the feed, plus the events `start`, `end`, `threat`, `update`, `feed`, `eradar`, `tr`. How a page applies them: [docs/TECHNICAL.md §5.4](docs/TECHNICAL.md#54-the-live-line-129). |
| `GET /api/places?oblast=all` | Gazetteer of places with coordinates. |
| `GET /healthz` | Liveness. |
| `POST /api/push/{subscribe,unsubscribe,test}` | Web Push subscriptions. |

## The two keys

| | what it protects | who can read the map |
|---|---|---|
| `ADMIN_KEY` | `/admin` (usage, online now, the team's message, sources, summaries) and its APIs | **everyone** — this is what a public deployment wants |
| `ACCESS_KEY` | **the entire app**, behind a login form | only people with the key — a private deployment |

On a public instance, setting `ACCESS_KEY` is an outage: every reader gets a password box instead of an
air-raid map. Use `ADMIN_KEY`.

**You do not need a terminal for this.** Double-click `deploy-fly.bat` — step 4 shows the secrets already set
on the app and asks for a dashboard key, and the last screen prints your `/admin?key=…` link. Press Enter at
the prompt to keep whatever is already there.

If you do want the commands:

```bash
fly secrets set ADMIN_KEY=…        # dashboard only, map stays public
fly secrets unset ACCESS_KEY       # if it was ever set on a public instance
fly secrets list                   # names only, never the values
```

Then open `https://<your-app>/admin?key=…` once; it remembers you in a cookie that grants the dashboard and
nothing else. With no key set at all, the dashboard is not served — it cannot be exposed by accident.

## The regression corpus

`data/corpus.jsonl` holds real posts and the parse each one must produce. It runs with the ordinary
test suite, and `python scripts/corpus.py replay` runs it alone. When something looks wrong on the live map,
capture it while you are looking at it:

```bash
python scripts/corpus.py add --channel kyiv_airdef --text "…" --note "what is wrong with this reading"
python scripts/corpus.py review
```

`docs/CORPUS.md` explains the three states and what is compared.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest            # parsing and tagging tests
python -m ruff check app tests
python app/server.py --demo --port 8099
```

In VS Code: **F5** runs *Heimdall — demo*, the Test panel is wired to pytest, and the recommended
extensions are proposed on first open. Tasks (`Ctrl+Shift+B`): run, demo, tests, lint, deploy.

CI runs the tests on Python 3.9 and 3.12, starts the service and checks it answers, parses the
front-end scripts, and verifies that every UI string exists in all three languages.

## Deploying

```bash
fly deploy                  # Windows: scripts\release.bat ships a patch (deploy + push); deploy-fly.bat the first time
```

Runs as one `performance-1x` machine (a dedicated CPU, 2 GB — 1.41.1) with a 1 GB volume for the history. Full
walkthrough, including Render and running it at home behind a tunnel: [docs/DEPLOY.md](docs/DEPLOY.md).

**How many readers.** Installed apps that are closed cost the server nothing; what counts is pages open at the
same moment. Since 1.29 one thread holds every open page's live line and sends each change once: measured on a
single core, 9,000 open pages took 8 threads, 62 MB and ~80 ms of CPU per second, and a change reached the last
page ~0.1 s after the first. Before 1.29 each open page held a thread (a hard stop near 1,700 on 256 MB) and
downloaded three answers again after every post. The machine's size is `[[vm]]` in `fly.toml`: every deploy
applies it.

**Its own address.** Buy the domain, then double-click `scripts\set-domain.bat`: it asks Fly for the HTTPS
certificates, shows the DNS records to add at the registrar, and — once the certificate is issued — tells pages
still opened on the old address that Heimdall has moved (with a button that takes the reader's settings along).

## Sources

The official «Повітряна тривога» data by raion (api.ukrainealarm.com, or its keyless proxy siren.pp.ua), with
the ubilling mirror as a stand-in; and eleven public Telegram channels: @kyiv_airdef, @chyste_nebo,
@kievinfo_kyiv, @war_monitor, @eRadarrua, the Air Force @kpszsu, and the regional trackers @chernihiv_nebo,
@monitoringodesa, @chyste_nebocherkasy, @radar_kharkov and @RadarDnepr.
Villages and city districts of the regional trackers' oblasts: [GeoNames](https://www.geonames.org/) (CC BY 4.0).
What each one gives and how it is parsed: [docs/TECHNICAL.md §6–7](docs/TECHNICAL.md#6-official-alert-data).

Map data: raion and oblast boundaries from [geoBoundaries](https://www.geoboundaries.org/) (CC BY
4.0); Kyiv district boundaries from OpenStreetMap via Nominatim (ODbL); street tiles from
OpenStreetMap (© OpenStreetMap contributors).

## Credits

**Heimdall** — made by **Black Flame Studio** & **NGO 07300**. Built by the French Cossack of Obolon.

The app is free and stays free. Donations cover the server, the development and the humanitarian work of
NGO 07300: **nomakievip@gmail.com**.

## License

[MIT](LICENSE). The map data keeps its own licenses, listed above and in
`static/ukraine-map.LICENSE.md`.
