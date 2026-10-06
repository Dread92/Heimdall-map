# Changelog

Every patch adds an entry here and updates [docs/TECHNICAL.md](docs/TECHNICAL.md) — see its §18.

## 1.41.3 — 2026-10-06

### Fixed
- **"1 destroyed. Next: Nyvky" is two targets.** @eRadarrua's "1 знищено. Наступний Нивки" was drawn as a confirmed
  shoot-down at Nyvky, which the 24-hour history layer then kept showing the next day. The shoot-down's place was
  never given; Nyvky is where the next one was. An outcome followed by "next", "another" or "the second" now keeps only
  what its own words say, and the place after it is the next target's position.

## 1.41.2 — 2026-10-06

### Fixed
- **A channel explaining is not a channel reporting.** Between two waves on 6 October, @chyste_nebo explained how
  ballistics works: "for example — the direction of Brovary and whatever is behind it …". The example was drawn as a
  ballistic missile heading for Brovary, which also sends the region's "shelter now" notification; the next post
  ("if the target is destroyed over Kyiv …") became two shoot-downs, over Kyiv and Bila Tserkva. An example, a
  lesson or a channel describing its own method now places nothing, raises nothing and ends nothing.
- **What the enemy "plans" is a forecast.** "From 01:30 to 03:00 the enemy plans to launch up to 40 ballistic
  missiles …" was drawn as a ballistic missile at Dnipro; it is now tagged as a forecast, like the nightly
  assessments.

## 1.41.1 — 2026-10-06

### Changed
- **A bigger machine.** Production moves from one shared CPU with 256 MB to one dedicated CPU with 2 GB
  (`performance-1x`, about $34 a month in Amsterdam instead of a few dollars). A shared CPU is slowed to a sixteenth
  of its speed once its short burst is used up — on attack nights, when everyone opens the app at once — and the
  pages time out. The size is in `fly.toml`, so every release keeps it.

## 1.41.0 — 2026-10-06

### Added
- **The dashboard says why the app went off.** Live → Server: the program's CPU, the CPU the host took away (on
  the shared Fly CPU, the throttling that makes pages time out), memory, late wake-ups, requests over 2 s, and every
  start with its build — a start with the same build is a crash or an out-of-memory kill, a new build is a release.
- **`scripts\diagnose.bat`**: one double-click writes Fly's status, the machine's events (exit codes, out of
  memory), the recent logs and 20 timed pings to `diag\fly-diag.txt`, for Claude to read.

### Changed
- **The app opens even when the server does not answer.** The two pages and their files are kept on the phone and
  used only when the network fails or the server answers with an error; Tactical then says "No connection to
  Heimdall — retrying" at the top, and that the sirens and «Повітряна тривога» do not depend on it. Light says so
  after 15 s (was 60). No data is ever kept: no old alert status is ever shown as current.
- Tactical no longer says "updated 5 s ago" before anything has arrived ("connecting…").

## 1.40.1 — 2026-10-06

### Fixed
- **CI, front-end job**: `static/i18n.js` read `navigator.language` while loading; the job runs on Node 20, which has
  no `navigator`, so the key check stopped with "navigator is not defined". The language guess now checks that
  `navigator` exists (no change in a browser), and the local test runs the job without one, as GitHub does.

## 1.40.0 — 2026-10-06

### Changed
- **The heat map's colour is the number of reports**: pale yellow for a few, orange, red for the most (it was
  violet). Each place adds its count around itself; the colour is read on a scale set by the busiest place of the
  period (or the busiest spot in view, if more), so a quiet corner never turns red because it is zoomed in on. The
  legend reads "1 … N+" and "not live, not alerts"; while the heat map is on, the official alerts are drawn as
  outlines so the two are never read as one colour.
- **Light ⇄ Tactical is a toggle, not a reload**: the orange thumb slides to the other half, and the browser fades
  one version into the other — having usually loaded it already when the switch was pressed. A page loaded ahead
  opens no live line and is not counted as a visit until it is shown.
- **Motion in the menus**: the bell, More and Layers panels rise in and leave quickly, their rows a few
  milliseconds apart; one orange line slides under the drawer's tabs; switches, buttons and sheets move with the same
  easing. Nothing moves in blackout mode or with "reduce motion". Light: the place picker and the target card slide in.

## 1.39.0 — 2026-10-06

### Changed
- **The opening notice, in the owner's words.** The title is "ВАЖЛИВА ІНФОРМАЦІЯ" alone, centred, the language
  under it; the first paragraph opens with "HEIMDALL — це неофіційний волонтерський сервіс"; new Ukrainian text for
  the three paragraphs (English and French follow it).
- **One footer, everywhere.** The notice, the Near tab, the support and help sheets and Light now share one
  footer (`footerHTML()` in `static/i18n.js`): the "free service" line for the NGO «07300 — Люди для Людей» with
  🔗 Support, Share the app, © Black Flame Studio & NGO 07300 with their logos, "Built by Dread92 · version ·
  build", and 💬 Community & feedback on its own line. The old sentence under Near ("буде дуже вдячно прийнята") is
  gone with it. Light shows it without the logos (2G).
- **The LIGHT | TACTICAL switch** takes the room between the logos and the icons, centred, and its text scales so it
  is never cut (checked at 320, 360, 390 and 1440 px in the three languages).
- **The bell's lines** say what each switch does, in the owner's Ukrainian: push — targets within your radius, a
  ballistic threat, a MiG-31K take-off (a take-off is a warning for the whole country, not a target near you);
  bridges — a target on a bridge or within 3.5 km (6 km for jet drones and missiles, as the code measures); sound —
  a distinct tone per threat level; vibration — long for a ballistic threat or a MiG-31K take-off.
- **The app's own pictograms instead of the phone's emoji**: the weapon types in Stats and its summaries, the
  threats in the Alerts tab, the airfields, power plants, nuclear plants and the watched place on the map, and the
  impacts button — the same shapes on every phone.

### Added
- **Share the app** — under the notice, in every footer and in More: the phone's share sheet, or the link copied.
  The link is the app's address only; never a place.

### Fixed
- The key under the Stats table is one sample per line; as one sentence its end ("· ✓: …") fell under the
  screen's edge.
- On a computer the "nothing reported" line was squeezed under the card's foot when a warning made the card tall.
- "Звичайний ✓" was cut in the display-mode buttons on a 360 px phone.

## 1.38.0 — 2026-10-05

### Fixed
- **No more "hit reported" from an explosion.** A bridge is "hit reported" only when a post names it and says it was
  hit (влучання, пошкоджено, приліт). On 5 October a bare "Вибух" — the interception — was placed at the tracker's
  last position, Vydubychi, and the Darnytskyi and Southern bridges read "hit reported" for half an hour. An explosion
  stays on the map as an explosion; it never lights a bridge.
- **A target that is gone no longer stays on the map.** A tracker's line that only says where a target is going ("На
  Таращу") was placed at the channel's last position *and gave that position its own time*: a jet drone destroyed at
  Vydubychi at 20:25 stood there as live, "1 min ago", until 20:37, carried by lines about another target 100 km south,
  and lit the bridges. Now a carried position keeps the time it was reported at; the channel's "fell / lost / clear"
  ends it; and the official all-clear for Kyiv city ends everything reported in the city before it — marks and
  bridges alike. Replayed from the posts of that evening in the tests.
- "Від Лисянки на Ставище": Lysianka is now a known place.

### Added
- **Three more crossings**: the Kyiv HPP dam at Vyshhorod, the Petrivskyi railway bridge, and the
  Podilsko-Voskresenskyi bridge (one crossing, from the harbour over Rybalskyi, the Dnipro and Trukhaniv island to
  Raiduzhnyi — named by "Подільський" or "Воскресенський"). A crossing that bends is measured along its whole line.
  Posts naming the Darnytskyi railway bridge light the Darnytskyi bridge, 100 m away.

### Changed
- **The bridge bar is one line**: the bridge that matters most, how far, how long ago, and "+N" for the others (a tap
  lists them). On Light too. On the map a bridge is named a few pixels from its end at every zoom; the unlit ones only
  when zoomed in.
- The card's age for a target is the age of its position.

## 1.37.0 — 2026-10-04

### Changed
- **The card takes less of the map.** On a phone it took about 290 px of 760 on a quiet night; now about 210–230:
  "Nothing reported within 30 km — that is not the same as safe" is two lines of text instead of a box, the official
  block is a little tighter, and "What to do" sits beside "unofficial · not radar".
- **▴ folds the card to one line** (phone): the place's official status, its name, how long the alert has lasted and
  the targets within 30 km. Remembered on the phone. It opens by itself when something new matters — a target within
  30 km or heading for the place, a bridge "at", a ballistic or MiG-31K warning, a new preventive warning or bridge
  bar — and folds back once that is over. A tap on the line opens it.
- While a fresh preventive warning is on, the one-line card (folded, or with the drawer pulled up) shows the warning
  itself, in its colour, instead of the status.

### Fixed
- CI: the front-end job failed on 1.36 and 1.37 — its translation check read the Ukrainian plurals of the new card
  strings (`_1` / `_2` / `_5`) as missing. It knows them now, and the test suite runs that job's steps too.

## 1.36.0 — 2026-10-04

### Changed — the Tactical page, redesigned around the reader's own place
- **A "My place" card at the top**, in the header and never over the map: the four places as large chips, each with
  its own official status as a dot; the watched place's official status in words ("Air raid alert · Obolon · Kyiv ·
  since 19:08 · official") with how long it has lasted; the MiG-31K / ballistic warning, which now also says what to
  do ("Little time — go to a shelter now, do not wait for the siren") with a button to the guide; the one target
  that matters most for the place — the one a post says is heading for it, else the nearest within 30 km — with its
  silhouette, course as stated, age and distance; or "Nothing reported within 30 km — that is not the same as safe";
  and at its foot how old the data is (amber past 2 minutes), "unofficial · not radar" (a tap opens the notice) and
  What to do. With no place set, the nearest target from the centre of Kyiv, or an invitation to set one.
- **The menu of 27 controls is split by where each one is looked for**: the **bell** (push, warnings near my
  position, Kyiv bridges, sound, volume and test, vibration — as switches, each with a line saying what it does);
  **More** (places, language, display mode, blackout, Light, the guide, how it works, support, about); **Layers**,
  a button on the map (map layers, Kyiv's districts, EST, zoom out, the colour legend). The drawer's Map tab is gone.
- **Near**, a new first tab: every live target by distance from the watched place, in bands (the whole region /
  10 / 30 / 60 km / further), with a badge counting those within 30 km.
- **The drawer has three heights** (tabs / half / most of the screen); while it is up the card folds to one line.
- **The feed**: no row of category chips under every post; instead, when the map placed a mark from the post, its
  distance from the watched place. "Do not publish air-defence or impact locations during an attack" at its top.
- **Escalation levels 0–4** colour the card's edge and the bell's dot, with a tone each: one soft note for an
  official alert starting, two beeps, three rising beeps, a 3-second warble for a ballistic or MiG-31K warning — at
  most one tone in 10 seconds unless the level rises. The test button plays the three.
- **Computer**: the card is a column on the left with the Near list, the map in the middle, the feed on the right.
- **Larger and clearer**: every control can be hit over 44 × 44 px, no text under 12 px in the card, panels and
  drawer, lighter secondary text (at least 4.9:1); the red alert block is a brighter red with white text.
- The rotating ticker and the clock are gone; the essentials they carried sit where they apply (see SAFETY.md).
- The opening notice is unchanged, shown at every opening; its "I understand" button now stays on screen while the
  notice scrolls.

### Changed — Light
- Each place's chip shows that place's official status as a dot; the colour legend is behind a "?" button; the
  footer is two buttons (What to do, the Tactical map); every control 44 px, no text under 13 px.

## 1.35.0 — 2026-10-04

### Added
- **What to do — a threat cheat sheet** at `/guide`, in Ukrainian, English and French: five rules that always apply,
  then weapon by weapon — Shahed, jet drone (Geran-3, Banderol), cruise missiles, ballistic missiles and Kinzhal,
  KAB, debris — how much warning there usually is, how you notice it and what to do, each card with the symbol the
  map uses; then in a car and on the bridges, caught outside, at home at night, with children, after a strike (and
  under rubble), a radiation danger; the emergency numbers (101, 102, 103, 104, 112) as tap-to-call buttons; and
  the official guidance every rule comes from (ДСНС, police, Ministry of Health, Poltava oblast administration).
- It opens with no network: the service worker keeps a copy (the page says so only once the copy is there), and
  it prints on two A4 pages for a shelter or a door.
- Linked from the Tactical menu (About → What to do), the top of the help sheet, the Light page's footer, and the
  nuclear-event banner (straight to "Radiation danger").

## 1.34.0 — 2026-10-04

### Added
- **The Kyiv bridges.** The five Dnipro bridges — Northern, Metro, Paton, Darnytskyi, Southern — bridge by bridge:
  a red bar at the top of the Tactical page when a target is reported **at** a bridge (the post names it, or a place
  within 1.2 km of it) and an amber one when it is **near** (3.5 km; 6 km for a jet drone or a missile), with the
  distance, how long ago and which channel; the spans drawn on the map in that state; a toast, a tone and a vibration
  when one rises (menu → Alerts → Kyiv bridges, on by default); the same on the Light page.
- **Push for the bridges**: with push notifications on, the same switch sends "🌉 Південний міст: ціль за 2,3 км" to
  the phone, in its language, at most once per bridge every 10 minutes (and again if "near" becomes "at").
- While a threat is within 12 km of a bridge, the Kyiv channels are read every 10 seconds instead of 30.
- **Heat map, redone**: where drones were reported (the places the posts named, over 24 h, 7 days or 30 days), as a
  density that adapts to the zoom — the corridors across the region zoomed out, the villages and Kyiv districts
  zoomed in — with the most-named places written on it and listed. Shoot-downs and hits are left out. The alert
  hours by oblast stay in the dashboard.
- Dashboard: "Kyiv bridges" (each alert, per bridge and per day) and "Where drones were reported most".

### Fixed
- **The bridge posts were dropped.** The live trackers write just "Південний міст", "🔻Зниження Північний міст",
  "на міст патона": with no other word the app read nothing in them (or put the target at the centre of Kyiv). The
  bridges are now places: 24 of 24 such real posts from 1–4 October are drawn on the right bridge, and the traffic
  notices and videos about them on none.

## 1.33.0 — 2026-09-28

### Added
- **Heat map of alert hours on the Tactical map** (Map tab → Layers): how long each oblast was under an official
  air-raid alert over 24 h, 7 days or 30 days, in violet by the share of the time, with the hours written on each
  oblast. It never hides the live picture: drawn under every mark, the oblasts under an alert right now outlined
  in red / yellow on top, "not live" in its legend, and off again at every opening.
- **Analytics — the carriers**: MiG-31K, Tu-95/Tu-160 and Tu-22M3 take-offs and the Kalibr ships' salvos, read
  from the channels; how often a launch followed, and the time from the take-off report to the launch report
  (median and middle half); the MiG-31K's time to the stand-down; the last 25 in a table.
- **Analytics — the weather**: the wind, cloud cover and rain of each night over the launch areas (Open-Meteo)
  against the drones launched that night, with the strength of the link and a trend line.
- **Analytics — where the drones come from around Kyiv**: the side of Kyiv (8 sectors, 20–130 km) the channels
  placed drones on, night by night, and over the period.
- **Analytics — hours under alert by oblast**, all Ukraine, week by week. Every new card downloads as CSV.

### Fixed
- **A reply was read as the message it answers.** The Air Force's "Відбій небезпеки по МіГ-31К", posted as a reply
  to its take-off message, was stored as a second "Зафіксовано зліт МіГ-31К" at the minute the danger was called
  off. Every reply is now read as its own text.
- **Strategic aviation drawn near Kyiv.** A Tu-160 taking off from the "Українка" airbase (Amur region) was placed
  at Ukrainka, 40 km south of Kyiv. Tu-95/Tu-160/Tu-22M3 and MiG-31K posts now place no mark (they never fly over
  Ukraine); their banners are unchanged.
- **"Кинджал" is ballistic.** Spelled that way (the Air Force's spelling) it was read as an unspecified missile,
  without the ballistic banner.

## 1.32.0 — 2026-09-28

### Fixed
- **The Stats tab was missing nights and every missile.** From 25 Sep the Air Force's summaries were read as news
  and dropped, so whole nights vanished from the figures; and missiles were never counted, because the Air Force
  names most of them without a number ("балістичними ракетами Іскандер-М …") and gives the number only for those
  shot down. The summaries are now read weapon by weapon — drones and the jet ones among them, Banderol, cruise,
  ballistic, aeroballistic, anti-ship and guided missiles, decoys — launched, shot down, and "used" when no number
  is given (never 0) — with the hit and debris locations, the launch areas, the main directions and the models
  named. They are **kept** (a new table, `af_reports`), and a background task recovers the last 14 days of
  summaries the app missed from the Air Force's channel, so the missing nights come back after the deploy.
- The Stats tab shows it as a table: a row per weapon type, launched and ↓ shot down, for 24 h / 7 d / 30 d; then
  each night and day with its figures and a link to the summary.

### Added
- **The dashboard in tabs**: Live, Analytics, Nights & weeks, Sources, Usage. A red dot on Sources when a source
  or a channel on the map fails.
- **Analytics**: the trends of the attacks, 7 days to a year — drones launched per night (Shahed type / jet /
  Banderol) with the number shot down; missiles shot down by type; the share of drones shot down and the share of
  jet drones; hit and debris locations; launch areas, directions and models; for Kyiv: hours under alert per day
  (city and oblast), when alerts start (weekday × hour), what the channels reported by type, by hour and by stated
  course; the last 7 days against the 7 before. Each table downloads as **CSV for Excel**.
- **The nuclear event**: from the dashboard, the radiation symbol, pulsing, over the whole map on every page, with
  a red banner, the admin's text (UK / EN / FR, prefilled with shelter-in-place advice) and one critical tone.
  Three locks: arm (the server gives a one-time code, 2 minutes, one attempt), type the code and "NUCLEAR EVENT",
  hold the button 3 s. One click (confirmed) ends it everywhere. The overlay is a separate file loaded only while
  one is on, so the pages stay as light as they were.

### Changed
- **The admin's message is loud**: Information is bright green, Urgent bright red with a slow pulse (still for
  readers who ask for less motion); the dashboard previews the colour while you write.
- The nights' figures (and their written summaries) take the Air Force's numbers type by type from the kept
  summaries.

## 1.31.0 — 2026-09-28

### Added
- **Telegram sources from the dashboard.** The channels table now has, for each channel: **Map / Trial / Off**,
  **web preview / Telegram API** (when the API is set up), and ✕ to remove an added one; under it, a box to add a
  channel (`@name`, `t.me/name` or a link to a post). No deploy, and it survives restarts.
- **A new channel starts on trial.** Its posts are shown in the feed with an orange "source on trial — not on the
  map" chip and nothing else: no mark, no banner, no sound, no push, not in the statistics or the summaries.
  Switching it to Map (after a confirmation) makes its posts count from then on, including those already in the
  window; switching a channel off or removing it takes its posts off the map and out of the feed at once.
- The six default channels can be switched off or moved to the Telegram API, not removed. At most 30 channels.
  A channel added for the web preview is checked for readable posts first.

## 1.30.0 — 2026-09-28

### Changed
- **The logo from its transparent original.** The 1.29 icons were cut out of a picture with the transparency
  painted in; these come from the real file: a sharper, brighter radar on the home screen, in notifications and
  in the header. The notice now opens with the whole logo, name included (a 40 KB WebP, loaded only when the
  notice is shown). The icon files have new names (`static/heimdall-*.png`): a phone that took the 1.29 icon
  identifies icons by their address, so it takes this one as an update too.
- The dashboard's message now reads **"Message from the system admin"** (was "from the Heimdall team").

## 1.29.0 — 2026-09-28

**Clear Sky is now Heimdall.** Same app, same address, same data; a new name and a new logo.

### Changed
- **The name and the icon.** Heimdall everywhere a reader sees it, in the three languages; the radar over Ukraine
  is the app icon (home screen, notifications, favicon), cut out of the logo. The installed Tactical app keeps its
  identity (manifest `id` `/m`), so Android offers the new name and icon as an update of the same app. An
  iPhone keeps an installed app's name and icon until it is added to the home screen again — Apple does not
  update them. NGO 07300 and Black Flame Studio stay where they were.
- **Push goes to every phone at once.** It went one phone at a time, each on a new HTTPS connection: ~0.15 s per
  Android phone, up to ~0.5 s per iPhone, so with a thousand subscribers the last phone heard of a ballistic
  missile minutes after the first. Now 32 sends are in flight together, each worker keeps one open connection
  per push service, and the VAPID signature is made once an hour per service: a thousand phones in seconds.
- **The live line carries the data.** Every new post made every open page download the marks, the feed and
  the alerts again — five requests per page per post. The stream now sends what changed (a new post at the head
  of the feed, the marks that moved, the raions whose alert changed), each part labelled with the version it
  starts from, so a page that missed something fetches that part in full instead of guessing. It beats every
  15 s (5 s with cruise missiles up, 2 s with a ballistic one); while it beats a page asks for nothing but a
  version check once a minute, and when it stops the page asks by itself as before. The Light page uses it too
  (alerts and marks only): it no longer downloads both every 15 s.
- **One thread for every open page.** Each open page held a server thread; on the 256 MB machine Linux allows
  about 2,000, so ~1,700 open pages was a hard stop. Now one thread holds them all (epoll). Measured on one
  core: 9,000 open pages — 8 threads, 62 MB, ~80 ms of CPU per second, a change reaching the last page ~0.1 s
  after the first. The open-file limit is raised at start.
- The alert history (asked by every page after an alert starts or ends) is cached, and the pages ask for it
  spread over 20 s instead of all at the same instant.

### Added
- **A message from the team.** The dashboard publishes one message to every reader — Ukrainian, English,
  French; information, warning or urgent; for 1 h to 3 days or until removed — shown as a banner on both pages
  (a reader can close it), optionally also as a push to every phone.
- **Online now** on the dashboard: pages open with a live line, Tactical and Light, and today's peak. A count
  only — nothing about who.
- **Ready for its own address.** `scripts/set-domain.bat` attaches a domain (Fly certificates, the DNS records
  to add) and sets `CANONICAL_HOST`; pages opened on the old address then show "Heimdall has moved to …" with a
  button that takes the reader's settings along in the link's #fragment (never sent to a server). The watched
  places do not travel — they never leave the phone — and are set again there.

## 1.28.0 — 2026-09-28

### Changed
- **Sound has a volume, not just on/off.** On an iPhone the alert tones played at the phone's media volume — often
  full — and nothing in the app could turn them down (iOS ignores a web page's audio volume). Menu → Alerts now
  has a volume slider under Sound / Vibration: 0 is off, a new reader starts at 50 %, 100 % is the old level.
  Every tone goes through one Web Audio gain (the one level an iPhone lets a page set), on a squared curve so the
  slider sounds even. Letting go of the slider, or ▶ (test), plays the loudest alert at that level, so what you
  hear is the ceiling. Near-zone and ballistic alerts stay louder than background ones, within that ceiling.
- Each tone now fades in over 12 ms instead of starting at full level — the click at the start of a square wave
  was most of the jump.

## 1.27.0 — 2026-09-28

### Fixed
- **"I understand" out of reach on some iPhones** (seen on an iPhone 14 in Safari). The disclaimer box was sized
  with `vh`, which Safari measures as if its address bar and bottom bar were hidden; with the bars showing, the
  bottom of the box — and the button — sat under the bottom bar and sprang back when scrolled to. The overlay now
  scrolls itself and is sized by what is really on screen: the box is centred when it fits, starts at the top when
  it does not, and ends with room under the button. Same fix on the Light page; the menu and the bottom sheets use
  `dvh` where the phone knows it.

## 1.26.0 — 2026-09-27

### Added
- **Nights and weeks, recorded and written up** (dashboard only). After each night (18:00–08:00 Kyiv time, written
  up after 09:00 so the Air Force morning summary is in it) and each Monday for the week before, the app computes
  from what it recorded over Kyiv and Kyiv oblast: minutes under official alert, alert waves and levels, raions,
  the channels' reports by type, place, course and hour, shoot-downs and explosions reported, how far ahead of the
  alert the map was, and the Air Force's own figures. With an `ANTHROPIC_API_KEY` secret an AI model writes them up
  in English and Ukrainian — told to describe the figures and nothing else: no forecasts, no guessed targets. The
  figures are kept with the text and shown under it. Buttons write last night or last week up on demand.
- The record builds up from today (nothing older is imported). Without a key the figures are still kept.

## 1.25.0 — 2026-09-27

### Fixed
- **White clouds over the map in daylight mode.** The white halo around town, road and river names was 2.4 px
  in the map's own units — 2.4 km — so zoomed in on Kyiv every name became a white cloud covering the streets and
  the marks. It is 3 screen pixels now, like every other label; a test checks that no text on the map has a halo
  measured in kilometres.

## 1.24.0 — 2026-09-25

### Fixed
- **The server froze again a few minutes after 1.23 went live.** The real cause, reproduced here: every new post
  made every open page ask for the marks, the feed and the state at the same moment, and each request recomputed
  them from scratch — and the marks' computation called the machine translator over the network (up to 6 s a
  post) for any post without an English text. During an attack the requests piled up faster than they finished.
  On a copy with 200 posts in the window, 1.23 answered 3 requests a second with time-outs; 1.24 answers about
  1,000 a second, 95 % of them within 55 ms, with 150 pages asking at once.
  - Each answer (marks, state, feed, statistics, impact history) is built **once per change**, by one thread
    while the others wait for it, serialised and compressed once, and sent as the same bytes to every page.
  - No network call is ever made while answering a page: the marks use the offline English glossary; machine
    translation stays in its own background worker.
  - The connection queue holds 128 pages instead of 5.
- The watchdog no longer restarts a server that is only busy — a restart under load brings every page back at
  once. It restarts only when a lock stays held for about two minutes.

## 1.23.0 — 2026-09-25

### Fixed
- **The server stopped answering** (25 Sep, ~22:10 Kyiv time): pages, the version ping and the official alert
  reader froze minutes after the chyste_nebo reader signed in for the first time — the Telegram reader was
  subscribed to the update stream of the whole account (every chat and channel it is in), which the 256 MB server
  could not carry. It now only reads the channel it needs: its last 20 posts every 15 s (8 s while a missile is in
  the air), with the parsing off its event loop.

### Added
- **A watchdog**: every 20 s the database and the alert state must be free within 15 s and the process must not be
  starved. A miss writes every thread's stack to the log (`fly logs` then says exactly where it is stuck); three
  misses in a row, about a minute, and the process exits so that Fly restarts it. A freeze can no longer last.
- `/healthz` answers 503 when the database cannot be had, instead of "ok" through a freeze.

## 1.22.0 — 2026-09-25

### Fixed
- **A video of a strike was drawn as a fresh explosion.** @kievinfo_kyiv's "😱 Момент прильоту Герань-5
  бізнес-центром «Інком» у Києві" (with "send us other videos of the impact — we'll buy them") put an
  "explosion" mark over Kyiv, as if it had just happened. Video and photo captions — "момент прильоту / удару /
  падіння", "кадри / відео з місця, прильоту, наслідків, роботи ППО", "надсилайте відео", "купимо" (and their
  Russian forms) — are news, never a mark.

## 1.21.0 — 2026-09-25

### Fixed
- **A drone heading for a town was drawn as if it had already passed it.** "🏍 Київщина: реактивний БпЛА на
  Васильків з північного заходу" — north-west of Vasylkiv, on its way in — was placed ON Vasylkiv with a
  confident position, turned south-east, its course ray pointing on past the town. The parser read "на Васильків"
  as where the drone was. It now tells where a target **is** ("від", "з", "повз", "над", "в районі", a bare name)
  from where it is **going** ("на", "в район", "до", "в напрямку"). A post that names only the destination is
  drawn at the destination **as an approach**: a dashed course coming into the town from the side the post named,
  "→ Vasylkiv from the NW", nothing ahead of it, never moved on by the Est. mode, no countdown.
- **@kyiv_airdef "Від Глевахи два на Васильків"** was drawn at Vasylkiv; it is at Hlevakha, heading for Vasylkiv.
  "Два керованих йдуть на Васильків" alone keeps the target where the channel last reported it, turned toward
  Vasylkiv. "Від Васильків на Макарів йде" was drawn at Makariv; it is at Vasylkiv.
- **"з півночі" after the destination was read as the course** ("курсом на Вишгород з півночі" drawn flying north).
  It is where the target comes from.
- **An oblast heading was used as a position**: "Київщина: … на Васильків" put the drone at the oblast's centre.
- A later "heading for X" post about a target already on the map gives it its destination instead of moving it
  there.
- A test now parses every script of the pages, so a missing brace can never ship a page that does not run.

## 1.20.0 — 2026-09-25

### Fixed
- **Labels written over each other on the map.** A descending drone's two lines ("⚠ likely a drone" and
  "↓ DESCENDING · updated 21:46") were drawn on top of each other: the code that spaces labels kept its own copy
  of the rules saying which lines are shown, and that copy did not know "descending". It now reads what is
  actually drawn. Labels are also kept off other marks and off the edge of the map, tried on the right, the
  left, a line lower or higher; the marks coming at a watched place are placed first; an ordinary label that
  fits nowhere drops its second line, then is left out (the mark stays, its detail one tap away). A town name
  under a threat label is hidden instead of being written over.
- **`telegram-login.bat` stopped with "No module named 'telethon'"** right after installing it, on a PC where it
  was the first package installed for the user: Python only looks in that folder when it starts. It now adds
  the folder itself and carries on. The api_hash is now typed visibly and checked (32 characters, 0-9 a-f)
  before Telegram sees it — a hidden prompt could swallow a Ctrl+V paste — and a pair Telegram refuses is asked
  again instead of ending the script.
- **The two-step password** can be shown while it is typed (a keyboard left on УКР/РУС or an AltGr character
  turned the right password into "Invalid password" three times, invisibly), and the script says which password
  it is: the one set in Telegram's Two-Step Verification.

## 1.19.0 — 2026-09-25

### Added
- **The Clear Sky logo** — the radar over Ukraine — is the app icon on both pages (home screen, maskable icon,
  favicon, notification icon and badge) and heads the opening notice. The NGO 07300 logo stays in the header and
  the Black Flame Studio logo in the credits.
- **Light: the map zooms by itself** — pinch, double-tap, the + / − / ⟲ buttons — never the page around it.
  Marks and names keep their size; more village names appear as you zoom in.
- **Light: tap a mark on the map** to open what the post said, the track, the height and the source, right on
  the map. A tap no longer selects a place name (which also brought up the phone's translate bubble).
- **Pin: tap the empty 📍 chip, then tap the map** where the pin goes (with a Cancel).
- **The dashboard shows what matters on a live night**: every official source and whether it answers, every
  channel read (posts and marks in 24 h, share of posts read, last post, reader failing), the translation
  service, and how many minutes ahead of the official alert the map was in Kyiv and the oblast over 30 days.

### Changed
- **Stats show only the official figures of the Air Force**: drones and missiles launched and shot down over
  24 h, 7 and 30 days, and each summary with a link to its post. The explosion and shoot-down counts the app
  read from channels are gone — next to official numbers they were read as totals, and they never were. The
  live tally of what is on the map moved to the Alerts tab.
- **The language is a drop-down**: in the Tactical menu and notice, in the Light header and notice.
- **"I understand" is a big, centred, full-width button**, well clear of the links above it.
- The official alert list is re-read at least every 30 s, so a level change on an alert already on (yellow →
  red) is never more than half a minute behind (up to 2 minutes before).
- The dashboard no longer reviews posts or reported readings (still possible from `scripts/corpus.py`).

### Fixed
- **Changing the language in the opening notice closed it** before it could be read. It now stays open, in
  the new language.
- **The KCSA metro notice was drawn as a threat** ("Changes in the operation of the red line of the Kyiv
  metro … Stay in shelters"). Transport notices — metro lines, trains, changes in operation — are news.
- **The "10 km" zone label** was sized in kilometres and filled the screen when zoomed in; it is screen-sized now.
- **The Crimea Cossack glitched when zoomed out**: the raion outlines ran across him. He is drawn above them.
- **Press and hold to drop the pin almost never worked**: the slightest tremble of the finger (0.2 km — less
  than a pixel at oblast zoom) counted as a drag. A drag now starts past 10 screen pixels, a ring fills while you
  hold, and the phone's long-press menu no longer interrupts it.
- **The OpenStreetMap credit sat on the place chips**; it is small, in the bottom corner.

## 1.18.0 — 2026-09-25

### Added
- **chyste_nebo is read through the Telegram API.** Its owner switched the web preview off, so the channel that
  states drone heights most often could not be read at all. A new reader signs in with a Telegram session and
  receives its posts as they are published (plus a catch-up read every 30 s); every post goes through the same
  path as the other channels, so its heights, positions and courses appear on both pages like any other.
- **`scripts\telegram-login.bat`**: the one-time sign-in. It asks for the api_id / api_hash from my.telegram.org
  and the phone of the reading account, signs in with the code Telegram sends, joins the channel, and stores the
  session in Fly's secret store — never on screen, in a file or in the repository.
- Dependency: `telethon` (only used when the Telegram secrets are set).

## 1.17.0 — 2026-09-25

### Fixed
- **Heights in kilometres are read.** war_monitor writes a jet drone's height as "висота 4,4км" or "висота 5км";
  the parser only knew metres and read those as nothing at all.
- **Light showed a height only behind a tap**, and dropped it altogether when the post gave a number without a
  word like "низько".

### Added
- **Height on the Light page, where it is seen first**: on the row ("висота 4,4 км", "↓ знижується" in crimson)
  and beside the mark on the radar. A low or falling drone may be diving.
- **The stated heights of a track**: each report keeps the height its post gave, so a run like
  "↓ 2,2 км → 1,6 км → 600 м" is shown — in crimson when the posts report it lower and lower. Only numbers the
  posts wrote; nothing is interpolated. The Tactical detail panel lists the heights along the track too.

## 1.16.0 — 2026-09-25

### Changed
- **Light draws the real silhouettes** — the Shahed, the jet Shahed, the Banderol, the cruise and ballistic
  missiles, the KAB, the aircraft — the same drawings as the Tactical map, in the list and on the radar. They
  turn only to a course the post reported; with no course they stay upright with a "?". The ⚠ for an unknown
  type stays upright with its small orange course arrow.
- The silhouettes moved to `static/glyphs.js`, shared by both pages, so the same weapon can never be drawn two
  different ways.

### Added
- **`scripts\release.bat`** — one double-click ships a patch: checks everything is committed, deploys to Fly.io,
  pushes to GitHub, shows the live version.
- The working folder is now a Git clone of `Dread92/clear-sky` (private).

## 1.15.0 — 2026-09-25

### Changed
- **Light watches 30 km, not 60.** Rings at 10 / 20 / 30 km; the map under the radar is drawn at twice the
  scale, so it now shows Kyiv's districts, villages and neighbourhoods, and river names, placed without
  overlapping.
- **Light is more detailed.** Each mark carries its number in the list. Each row adds where it was reported
  and its course; a tap opens what the post said (original and translation), the track so far, the altitude
  when the post stated one, and the source and time.
- **Beyond 30 km, only what is coming.** Targets 30–100 km out are listed apart, under "Approaching", and only
  when the post's own course points at the place.
- **The Light | Tactical switch is impossible to miss.** On Light it is a full-width two-part control under
  the title, each half saying what it is ("your place only" / "the full map"); on Tactical, a high-contrast
  pill in the header (the clock gives way on very narrow phones).
- **The notice at opening appears once per opening.** Switching Light ⇄ Tactical no longer shows it again; it
  is shared by both pages and comes back when the app is closed and reopened. Light now shows it too when it
  is the page the app was opened on.
- The yellow level reads "Yellow level (drones)", short enough for the banner.

### Added
- **docs/TECHNICAL.md** — the complete technical reference, updated with every patch. `tests/test_docs.py`
  fails when its version, `APP_VERSION` and this changelog disagree, or when a route, config key, environment
  variable, table or channel in the code is missing from it.
- The repository is ready for GitHub: history scanned for secrets (none), `scripts/github-push.bat` creates the
  private repository and pushes.

## 1.14.0 — 2026-09-24

### Fixed
- **Alerts follow raions, as the government app gives them.** The only official source on the server was a
  mirror with one on/off per oblast, lit whenever any raion is under alert and with no start time: at 22:21 it
  showed all of Kyiv oblast red, and "since 22:17" (the reboot), while Boryspil raion had been clear since
  22:07. The primary source is now the official data by raion and hromada — api.ukrainealarm.com with a key,
  or siren.pp.ua, its keyless proxy — with the official level and reason. The mirror only stands in when that
  source is down, and a start time it does not know is not shown.
- **Translation no longer delays alerts.** The free translator refuses servers, and each refusal cost ~3 s per
  post in front of the drone reports of the same poll. Posts are stored with the offline glossary at once;
  machine translation happens afterwards.

### Added
- **Light: status of the place's own raion**, found on the phone; a place within 1.5 km of a border gets
  either side's alert; neighbouring raions under alert are named, not painted on the place.
- **Light: a small map under the radar** — raions shaded by alert, rivers, roads, towns; threats as small
  arrows only where a course was reported; the ⚠ for unknown types upright.
- **Light | Tactical switch** on both pages.
- **English and French by DeepL or Google Cloud** when a key is set (`DEEPL_KEY`, optional step in
  `deploy-fly.bat`), only for a language somebody is reading. The offline glossary learned the channels'
  everyday words ("Oblast overall clear, breathing easy for now").
- `data/ua_regions.json` and `static/light-map.json`, built by `scripts/build_geo.py`.
- Static files are served gzipped with ETag revalidation.

## 1.13.0 — 2026-09-24

### Changed
- **Six channels only**: kyiv_airdef, chyste_nebo, kievinfo_kyiv, war_monitor, eRadarrua, kpszsu — in code,
  because deployed configs listed 33. chyste_nebo is reported as unreadable (web preview disabled).
- **Only the official data sets the alert colour.** A channel writing "відбій" or "чисто" can no longer turn
  the band green.
- **Region**: Kyiv city, Kyiv oblast and the oblasts around it (Zhytomyr, Chernihiv, Sumy, Poltava, Cherkasy,
  Vinnytsia).
- Cruise and ballistic missiles look like missiles and are smaller; the uncertainty ring stops at 25 km and
  says "position no longer known"; the ⚠ for an unknown type stays upright with an orange course arrow.

### Fixed
- **News is not a threat**: press releases, reported speech, tallies and long posts no longer become marks.
- **Banderol is a jet drone**, never a cruise missile — in parsing, tags and track chaining.
- kievinfo_kyiv parsing: "Димерка" is not Dymer, "A - B" routes give the heading, one mark per line, ✈️ is a
  drone on the live channels.

### Added
- **Clear Sky Light** (`/light`): one place, its official status, what is near, installable on its own.

### Removed
- "Show original Ukrainian", the "All threats / Towards me" switch, fire and ground-damage marks.

## 1.12.0 — 2026-09-22

### Added
- **Threat lifecycle**: the stage a post reports (prep, take-off, launch line, launch, entering), read only
  from the post's own words, with hedges kept as hedges.
- **Immediate weapons**: ballistic, Kh-22/32 (now its own type, not "cruise") and MiG-31K ignore every radius
  and concern the whole region; the banner takes its colour from the official alert.
- **Four places** — Home, Work, Kids, Pin — kept only on the phone; zones at 10 / 30 / 60 km; a conditional
  ETA band only for a stated course toward the place.
- **Marks point where the post said**: a silhouette per weapon, turned only to a reported course; a five-minute
  tail; no animation that could read as an observed path.
- **Display modes**: daylight (inverted, contrast-tested), night (dim), blackout.
- **Shoot-down notice** for a target the reader was warned about, worded so it can never read as an all-clear.
- The Shahed silhouette is the real airframe.

## 1.11.0 — 2026-09-17

### Added
- **Confidence now says how sharp the reading is.** "High confidence" on its own told nobody how far off the
  marker could be. Each method's tolerance is stated beside the word: a named town is **±5 km**, an oblast
  name is **anywhere in the oblast**, a bearing between two named places is **±10°**, a compass word **±30°**.
  These are the app's reading tolerances, not a probability that the report is true — no channel publishes
  such a number and this app does not invent one.
- **Reviewing the corpus from `/admin`, not from a terminal.** 260 captured cases were sitting there readable
  only by `corpus.py review` on a command line — the third feature in two days whose capture step assumed a
  keyboard that is not where the work happens. **Review readings** shows one post, what this build makes of
  it, and three answers: correct · wrong (with a note) · skip. It works on a phone.
  - The corpus file ships inside the deployed image and cannot be written from the server, so verdicts are
    stored on the volume and merged back with `python scripts/corpus.py pull`.
  - The reading shown is computed by the **running build**, not the one recorded at capture time — that is
    what the reviewer is actually being asked to judge.
  - `/api/corpus` and `/api/corpus/review` need `ADMIN_KEY`, like the rest of the dashboard.
  - The terminal `review` still exists and does the same thing; use whichever is in front of you.

### Added
- **The app keeps what it said, not only what it was told.** Markers are written as computed, with their
  evidence, and outcomes get a table of their own, and a per-channel ledger counts posts seen, posts the app
  could read and readings people flagged as wrong. Nothing reads these yet — the statistics built on them
  were reverted — but the record only exists from the moment it starts being kept.

### Removed
- **Siren-start and all-clear push notifications.** "Kyiv oblast — alert" says nothing anyone can act on, and
  the siren already said it louder — but it still wakes somebody at 3 a.m., and after enough of those the
  notification that matters gets swiped away too. MiG-31K, ballistic launches and targets near you stay.

### Changed
- **Push subscriptions no longer store where you live.** The row paired the address a phone is reached at
  with the exact coordinates of a village. The point is snapped to a ~10 km cell, the name is dropped, and
  rows written before this are rewritten at startup. The proximity test is widened by half a cell so nobody
  is missed, and the push says "within your N km" instead of a distance the stored point can no longer
  support.

### Added
- **The dashboard speaks Ukrainian.** An EN / UA switch in the corner, remembered per browser. Every label
  lives in one table in both languages, the way the app's own strings do. The posts under review are
  Ukrainian and whoever reviews them may not be — and somebody reviewing *in* Ukrainian should not have to
  read an English interface to do it.
- **A reading can now be checked against its source.** Each case in **Review readings** carries the original
  post, an English translation, and a link straight to the post on Telegram. The list ships the offline
  glossary so the panel is never empty, and the case actually on screen gets a real translation — once, cached,
  with a *translate again* control, because a stored translation can be a glossary fallback too and nobody can
  judge a reading against transliterated Ukrainian.
- **`/api/version` answers "what is actually running".** It reports the app version, and the build id is now a
  hash of the front-end and service **files' contents** rather than their timestamps — so the same id here and
  in production means the same code, which was not previously a question anyone could settle without squinting
  at a screenshot. A test pins the version in the page, the server and the changelog to each other.

### Changed
- **The Shahed looks like a Shahed.** The plain delta triangle is replaced by the real airframe seen from
  above — nose cone, slim fuselage, the big delta, fins at the wingtips, engine at the tail — drawn as vector
  shapes rather than a sprite so it still takes a colour (orange, amber for the jet, white in blackout) and
  stays sharp at every zoom. The Shahed-238 is the same airframe with the turbojet's dorsal intake, a fatter
  nozzle and a longer flame, because that is what actually distinguishes them.
  - It flies a figure of eight inside the loiter ring, nose on the tangent, banking into its own turns —
    a circle read as orbiting a fixed point, which is not what a Shahed does. The one glyph on the map that
    turns, and it muddles nothing: the reported course is still the chevron.
- **One weapon, one symbol — and it never turns.** A rotating symbol has to point somewhere, so a target
  reported with no course forced a choice between inventing a heading and drawing a different icon for the
  same weapon; the app did both, and a Banderol was an arrow in one place and a diamond in another. Every
  weapon now has a single silhouette drawn at a fixed angle, and the chevron, ray and cone carry the whole
  direction story — present when a post gave a course, absent when it did not. The Banderol gets its own
  straight-winged airframe so it can never be read as a Kalibr.

### Fixed
- **An outcome with no place named no longer lands on the oblast centre.** "Київщина - вибухи" was drawn as a
  pin near Vasylkiv — a report about a whole region shown as an explosion in one village. The region is
  outlined and labelled instead; a label is not a position and cannot be mistaken for one.
- **"Clear somewhere in the oblast" is no longer drawn.** An all-clear is not an event with a place — it is a
  state of the whole region, which the region's own colour already shows — and neither is a track that simply
  stopped being reported. Only things that happened get a region mark, and it is a count beside the region
  now, not a sentence in a pill stretched across the map.
- **An explosion somewhere in a whole oblast clears after 5 minutes.** It says far less than a located one
  and should not outstay it.
- **An explosion disappears after 10 minutes, not 25.** A burst still drawn reads as still happening there,
  and during a raid the map filled with ones that had already finished. A fire keeps its hour.
- **"Heading to your village" now has to come from the post.** It used to mean "the reported course passes
  within 25° of it" — from 80 km away that cone is 35 km wide, so the most alarming sentence in the app was
  being produced by arithmetic. It is said only when the post names that town; otherwise the app shows the
  distance in kilometres and nothing more.
- **A missing translation is now a failing test.** 400-odd strings are maintained by hand in three blocks, and
  a key missing from Ukrainian renders as a blank label on the phone of the person who most depends on it.
  The new check found one straight away (`u_offline`, the report's offline line, absent in all three).
- **The direction arrows on the map were wrong — one of them exactly backwards.** The missile glyph was drawn
  with flared tail fins, and at marker size the eye takes the widest part for the head: a missile flying
  south-west read as an arrow pointing north-east. The ballistic glyph was worse — its spike sat at the
  bottom, so once rotated by the reported course it pointed a clean 180° the wrong way. Both now carry their
  mass at the nose.
- **A target with no reported course no longer points north.** It was drawn pointing up, which reads as a
  heading and is an invented one. It now gets a mark with no front, and grows a nose the moment a post gives
  it a course.
- **"Бандероль" is its own weapon.** Added ahead of cruise missiles in the type table, with its own icon,
  name and speed. A bare 🚀 now means "a missile", not "a ballistic missile" — reading an emoji as ballistic
  handed the loudest treatment in the app (white spike, one-second refresh) to a piece of punctuation.
- **An oblast heading was drawn as a sighting.** "🛵 Київщина" over a list of towns put a phantom marker on
  the oblast centre — near Vasylkiv, 100 km from the Chornobyl zone the next line was about. A line that is
  only an oblast name, with lines under it, now sets the context and draws nothing. "КАБи на Сумщину та
  Донеччину" is still two reports: a heading has to be a whole line.
- **The weapon type leaked across a post.** It was resolved once over the whole text, so one word anywhere
  retyped every line: a jet drone over Kaharlyk was drawn as a Banderol because another line mentioned one.
  Each line is typed from its own words; only a line that names no weapon inherits the post's.
- **"Далі Київщина" was read as a position.** It is the next leg of the route. Three Banderols reported
  north of Nizhyn were also drawn at the centre of Kyiv oblast, 150 km away — one flight, two markers, the
  second over a region nothing had been reported in. An oblast introduced by далі / потім / згодом / надалі /
  курсом на is where it is going, never where it is.
- **The destination oblast is named.** "Neighbouring oblast" hid the one thing the channel had been precise
  about; the card now says *towards Kyiv oblast* (in Ukrainian, in the genitive).
- **A side of an oblast in an arrow line is no longer its centre.** "Одещина: ➡️Південь/Одеса" landed on the
  oblast centre, 90 km north of the south the channel named, and every line of that shape piled onto the same
  pixel. Only exact compass words count — Південне is a town, not "the south".
- **A morning tally is no longer drawn as a live sky.** "В ніч на 17.09 … противник застосував … 8×
  балістичних ракет по Києву" counts what was fired last night; it was drawn as eight ballistic missiles over
  Kyiv for as long as the post stayed in the feed.
- **The device counter inflated itself at every restart.** The daily salt and the set of hashes seen under it
  were rebuilt in memory at every process start, so each deploy, crash and auto-stop counted every returning
  reader as somebody new — 62 "devices" for a handful of people. Both now live on the volume, keyed by day, and
  yesterday's are destroyed when the day turns, which is what the privacy claim rests on. A restart no longer
  recounts anybody; `tests/test_usage.py` pins it with four simulated restarts.
- **"devices · 7 days" was a sum of daily counts, not a number of people** — somebody opening the app every day
  for a week counted seven times. Renamed **device-days**, with a note saying why there is no unique-visitor
  figure and why there cannot be one: the hash is regenerated every midnight precisely so the same person
  cannot be recognised tomorrow. That is the cost of not tracking anybody.
- **The dashboard said `UK` for Ukrainian.** UK is the United Kingdom; Ukraine is **UA**. The app had been
  fixed long ago — the dashboard was building its label with a bare `toUpperCase()` on the language code.
- The dashboard footer still told you to set `ACCESS_KEY`. It says `ADMIN_KEY`, and explains the difference.

## 1.10.1 — 2026-09-17

### Fixed (outage)
- **`ACCESS_KEY` locks the whole app, not just the dashboard.** Setting it on a public instance puts a
  password box in front of an air-raid map for every reader — police, military, anyone. That is what happened
  here, on my advice, and it is the worst thing this server can do during a raid.
  - **`ADMIN_KEY` is new**: it protects `/admin`, `/api/usage` and `/api/flags`, and nothing else. The map
    stays public. This is what a public deployment should set.
  - `ACCESS_KEY` keeps its old meaning — a login form in front of everything — for a genuinely private
    deployment, and it still opens the dashboard on its own so existing installs keep working.
  - The dashboard cookie (`uadm`) grants the dashboard only; it is never a way past the app-wide gate.
  - With neither key set, the dashboard is not served at all: it cannot be exposed by accident.
  - `tests/test_keys.py` pins every combination, including the one that caused this.

- **`deploy-fly.bat` was still asking for an ACCESS_KEY** at step 4 — which is where the confusion started,
  since that prompt is the only place the key is ever entered. It now asks for a **dashboard key**, prints the
  secrets already set on the app before asking, explains in the prompt itself that the map stays public, and
  ends by showing the `/admin?key=…` link. No terminal involved: it is the same file that deploys.

## 1.10.0 — 2026-09-17

### Added
- **A ⚑ button on every marker: "this reading is wrong".** The person who notices a bad marker is holding a
  phone, looking at the map, during a raid. Every capture path that needed a terminal was a capture path that
  never happened, so the corpus was only ever going to be fed by one person with a keyboard. Now it is one tap:
  pick what is wrong (wrong place · wrong threat type · not a threat at all · already gone · something else),
  add a line if you want, send.
  - It changes **nothing** on the map, and says so on the confirmation. A button that silently moved markers
    would be a way to lie to everyone else looking at the same screen.
  - Flags appear on `/admin` under **Flagged readings**, with the original post beside the complaint, and
    become regression cases with `python scripts/corpus.py flags --import`.
  - **Nothing identifying is stored**: the post, the reading, the reason, the optional note. No address, no
    location. The 40-a-day rate limit reuses the usage counter's throwaway daily hash — regenerated every
    midnight, not reversible, never returned by the API.
  - `/api/flags` needs `ACCESS_KEY` and refuses to serve anything when none is set, like the dashboard.
  - EN / UA / FR.

The point of this one is not the feature. It is that the people reading this map know the ground far better
than any parser does, and until now there was no way for them to say so.

## 1.9.1 — 2026-09-17

### Fixed (safety)
Three misreads in one post — an oblast administration's account of a working visit to a forestry enterprise,
drawn as a **fire, 9 km from Kyiv, at high confidence**.

- **A fire needs a fire, not a fire station.** The post was about a *new fire station* and its *fire engines*.
  The root `пожеж` is in the name of every fire service, engine and brigade in the country, so it can never by
  itself mean something is burning. A fire is now only drawn when the sentence says one happened — виникла /
  сталася / спалахнула пожежа, пожежа в …, горить, займання.
- **A post that says there is no fire no longer draws one.** "Пожежі попередньо немає" drew a fire. Worse,
  fixing that naively would have cost the post its damage marker — rejecting the fire reading now falls
  through to the next rule instead of abandoning the post, so the damage it does report still appears.
- **The news guard covers every status, not only the two caught first.** The fire rule ran before the check,
  so a 900-character press release sailed past it.
- **An oblast adjective is not the Kyiv place of the same name.** "Житомирська" is a metro station on Kyiv's
  red line *and* how every post names Zhytomyr oblast — which is why a post about Olevsk, 150 km away, planted
  a marker beside Kyiv. When an oblast noun follows (область, обласна рада, ОВА), the word is the oblast.

All four are in the corpus as verified cases, plus seven hand-written tests. The corpus caught the second one
by itself: it surfaced as drift on a real post nobody had labelled yet.

## 1.9.0 — 2026-09-17

### Added
- **A regression corpus** (`scripts/corpus.py`, `data/corpus.jsonl`, `docs/CORPUS.md`). Real posts plus
  the parse they must produce, replayed on every test run. The parser is patterns over free text in two
  languages with declensions; it produces a steady trickle of misreads, and until now every one of them was
  found by a person looking at the map — a detection method that does not work at three in the morning during
  a mass attack.
  - `harvest` takes posts the app has already collected (no network), capped per channel.
  - `review` walks them: **verified** is enforced, **known_bad** is enforced in reverse so a fix gets noticed
    and promoted instead of forgotten, **pending** is only reported — capturing a bug must never freeze it as
    the expected answer.
  - `replay` is the regression run, and `tests/test_corpus.py` puts it in the ordinary suite.
  - What is compared is a deliberate projection: status, type, place, oblast, coordinates, count, altitude,
    **position confidence**, quadrant, and the post's feed tags. Not the evidence wording — a corpus that
    fails on rephrasing is one somebody switches off within a week.
  - Seeded with 279 cases: every misread found today (each as the *correct* reading), the doctrine rules
    they came from, and a real sample from 36 channels.

## 1.8.1 — 2026-09-17

### Fixed (safety)
- **A government press release removed a live Shahed from the map.** "Уряд розширив програму страхування
  воєнних ризиків … за пошкодження або знищення якого можна отримати компенсацію" — an announcement about
  business insurance — was read as damage on the ground, drawn over Kyiv, and then **closed a live drone track
  with it**. Two rules now stand there:
  - Policy vocabulary (уряд, кабмін, законопроєкт, страхування, компенсація, відшкодування, бюджет, пільговий
    кредит, млн/млрд грн) or a post longer than 700 characters disqualifies an outcome entirely. No marker, no
    status, whatever destruction words the text happens to contain.
  - **Only an outcome that ends a flight may close a track** — shot down, arrived, lost, area clear. Damage and
    fire never close anything: they are what a strike left on the ground, and a burning roof says nothing about
    whether the drone above it is still flying.
  The second rule is the important one. A missed damage marker costs some information; a live target removed
  from the map by a press release is the failure the safety doctrine exists to prevent.
- **The last two "undefined" leaks** — the detail sheet's title and the share text — now use the same labelled
  fallback as the card. Every status, including any added later, has a name.

## 1.8.0 — 2026-09-17

Four misreads spotted on the live map, all the same failure underneath: the app stated more than its source
supported. All four are pinned in `tests/test_misreads.py`.

### Fixed (safety)
- **A destroyed building was drawn as a target shot down.** "Склад гуманітарного фонду … знищено" put a green
  interception tick over a strike site — the opposite meaning — and padded the shoot-down count with somebody's
  ruined warehouse. A destruction word now only reads as a shoot-down when the sentence is about something that
  was flying. Otherwise it is **damage on the ground**: its own muted brick marker, its own column, never added
  to shoot-downs. "Збито 5 БпЛА, уламки пошкодили будинок" is still a shoot-down.
- **Five Shaheds were drawn 700 km from where they were.** Stemming cut *Коломия* to `колом`, which swallowed
  **Коломак** — another town, another oblast. Two guards now: an over-stemmed name must still agree with the
  full name one character past the stem, and **a marker's oblast is the oblast of the place it matched**, never
  the one the sentence mentions. That contradiction — Kharkiv's oblast id with Ivano-Frankivsk's coordinates —
  was visible inside the app before it was visible on the map. No real declension was lost; the whole list is
  tested.
- **"На півночі Київщини" was drawn at the oblast centre**, which sits near Vasylkiv, in the south. A stated
  part of an oblast now places the marker there and the card says *north of the oblast*. Confidence stays low —
  a quadrant is not a position — and course words ("у західному напрямку") still never move anything.
- **A status with no label printed the words "undefined undefined"** on the card. Every status now has a name
  in all three languages, and an unknown one falls back to a plain label instead of leaking a variable.

### Added
- **Damage** as a first-class outcome: `▣` marker, own chip, own column in the report and the statistics,
  labels in EN / UA / FR.

## 1.7.0 — 2026-09-17

### Added
- **A history report behind the counter chips.** The map now carries **the last 24 h only** — beyond that the
  history layer buries the live picture, which is the one thing somebody opening the app during an attack needs
  to see. Tapping the ✸ / ✕ / 🔥 chips opens a report with a 24 h / 72 h / 7 d selector: totals per kind, then
  a list grouped by place — "Kyiv ×12 · last 03:41" says what two hundred dots were trying to say. It fetches
  its own window, so the live layer is never reloaded at seven days, and it repeats under its own figures that
  these count posts, not events.
- **Fires are drawn as fires.** A post that says only *пожежа / горить / загорання* is a fire, not an
  explosion: a small amber flame, drawn quietly, counted in its own column and never added to the explosion
  total. The rule sits below the impact rule on purpose — "внаслідок влучання виникла пожежа" is a strike that
  started a fire and still reads as a strike, and a shoot-down whose debris is burning stays a shoot-down.
- **A fire leaves the live map after an hour** (`FIRE_TTL_MIN`). After that it is either out or it has been
  burning all night; a new post about the same place brings it back, because that post carries a fresh
  timestamp.

### Fixed
- **The livebar chips were not tappable at all.** The bar carries `pointer-events:none` so the map can be
  dragged through it — which silently disabled every button placed inside. Only the chips take taps now; the
  gaps between them still pass through to the map.

### Changed
- The Ukrainian and English chips say *reports* rather than a bare count of explosions, matching the stats
  panel.
- `/api/impacts` accepts up to 7 days (was 96 h) for the report; the map never asks for more than 24 h.

## 1.6.1 — 2026-09-17

### Changed
- **"Confirmed shot down: 310" was claiming more than the app can know.** It counts the monitoring posts the
  parser could read and tie to a named town — every shoot-down never posted, posted without a place, or
  written in a form the parser missed is missing from it. The two figures are now **Explosion reports** and
  **Shoot-down reports**, with the caveat directly under the numbers instead of in a footnote at the bottom
  of the panel: what this app read, not official totals, and the real numbers are higher, never lower. The
  Air Force summary table below them is unchanged — those *are* counts of targets. The map chips say
  "reported" too. A floor presented as a total is false precision in the same family as an invented
  trajectory, and `docs/SAFETY.md` now says so.

## 1.6.0 — 2026-09-17

### Added
- **Odesa live tracking — @xydessa_live.** A local channel that posts the way people watching the sky actually
  write: a bare district name, a count, *реактивний* for a jet Shahed, half of it in Russian, and `-1` when one
  comes down. It is registered as a live-position channel for Odesa oblast, with the safety rules that implies:
  - a **bare district name is a position, never a threat type** — it draws the amber *type not stated* triangle,
    with "most likely a drone" carried separately as a guess;
  - **Russian spellings resolve to the same place** (черноморск → Чорноморськ, Аркадия → Аркадія, поскот →
    Селище Котовського), because half the posts are in Russian;
  - **`-1` is never read as anything.** It means one was brought down, but with no place attached — and a
    shoot-down drawn at a guessed position is worse than no shoot-down at all;
  - the channel's promo tail (one of the two lines is profane) is stripped before anything reaches a warning.
- **Nine Odesa places in the gazetteer**, coordinates from GeoNames: Пересип, Лузанівка, Селище Котовського,
  Аркадія, Хаджибейський лиман, Санжійка, Татарбунари, Тузли, Маяки.
- `tests/test_odesa.py` — 14 tests pinning all of the above, including what must *not* be concluded.

### Changed
- **MiG-31K is recognised however the channel declines it** — "Мігну31к в небе" is the same warning as
  "МіГ-31К". The pattern stays tight (міг/миг/mig, then 31 within three letters) because it raises the loudest
  banner in the app; ordinary words like *мігрант* and *мигдаль* are tested not to.
- Kalibrs are recognised in the Russian spelling as well (*калибы*).

### Known gaps in Odesa coverage
- **Південне is deliberately not matched.** It is both a town near Odesa and the adjective *southern*, and the
  channel uses both. Until a post can be told apart from "курс південний", neither draws a marker: a wrong pin
  30 km up the coast is worse than a missing one.
- **Слобідка, Іллічанка, Латівка and Паланка are not in the gazetteer** — no authoritative coordinate was
  found for them. Their posts stay in the feed with no marker until someone supplies one.

## 1.5.1 — 2026-09-17

### Fixed
- **The MiG-31K banner stopped shouting in the present tense long after the last report.** It is the loudest
  thing in the app, so it now only speaks in the present while the report behind it is fresh: for the first
  8 minutes it reads *MiG-31K airborne — ballistic risk · 02:33 · 4 min ago*, and after that it switches to the
  past tense, loses the alarm colours and the pulse, and says *not confirmed for 16 min*. It still disappears
  at 20 minutes. It is demoted rather than deleted, because a sortie can still end in a launch and silence is
  not an all-clear. **The age is now always on its face** — a banner with only a start time reads as *now*,
  whatever the clock says. Freshness also outranks type in the sort, so an unconfirmed MiG from a quarter of an
  hour ago can no longer sit on top of a ballistic warning that came in a minute ago.
- **The 24-hour history no longer looks like fireworks at the all-Ukraine view.** The merge distance and the
  glyph size now both follow the zoom (26→42 px, full size→50 %), so a heavy night's hundred reports become
  about thirty dots carrying their counts instead of a hundred full-size starbursts. History markers are also
  no longer flung onto a decluttering ring: at that zoom 26 px is 90 km, and a dot that far from the town it
  happened in is worse than a slight overlap. They nudge at most 13 px now, and otherwise stay where they were
  reported.
- **The safety ticker was clipped and unreadable.** The 55-second marquee is gone. It is now one short sentence
  at a time, cross-fading every 7 seconds, in a fixed two-line box that cannot clip its own descenders or make
  the header jump. Tapping it opens the full disclaimer. The five lines were rewritten in all three languages
  (the Ukrainian ones want a native review).

### Changed
- **The menu is grouped instead of a flat list of seventeen rows**: Alerts · Map · Display · About, with
  Sound/Vibration on one row and the three zoom levels on another. It scrolls if it does not fit the screen,
  and the version and build are on one line.
- **Community on Telegram** in the menu and the footers, pointing at t.me/blackflamestudio.

## 1.5.0 — 2026-09-17

### Changed
- **Missiles are no longer aged like drones.** Going grey after five minutes of silence is honest for a Shahed
  (~3 km/min); for a cruise missile (~13 km/min) or a ballistic one (~35 km/min) a two-minute-old pin is already
  tens of kilometres from the truth, and leaving it there is a lie with a precise point in it. So a missile never
  gets the grey *stale* flag at all. For a short window after the report — 2.5 min cruise, 1.5 min ballistic — the
  position still counts as a point. After that the marker grows a ring at that family's speed and reads
  **"could be anywhere within N km · last seen \<place\> at HH:MM"**. The ring is capped at 260 km, and missiles
  are dropped from the map at 12 minutes instead of 15, because past that even a circle says nothing.
- **Ballistic now looks different from cruise at a glance.** A white-hot downward spike, blinking twice as fast,
  with no course ray — a lofted trajectory cannot justify one — against the red cruise arrow with its capped ray
  and uncertainty cone. The time you have is different for the two; the marker should say so without being read.
- The threat sheet explains both, in all three languages: what the circle means, why a missile has no "last
  updated" state, and that nothing on the screen estimates where a missile *is*.
- **One-second refresh while a ballistic threat is open.** The cadence is now a level the server decides
  (`/api/version.msl`): 15 s normally, 5 s for cruise missiles or a MiG-31K, **1 s for ballistic**. The server
  speeds its own sources up with it — Telegram and the alert APIs go to 5 s at that level — because a
  one-second client in front of a fifteen-second poller only refreshes a stale answer faster. At 1 s the
  countdown is replaced by a pulsing **LIVE**, since a number flickering between 1 and 0 reads as a fault.
- **The uncertainty ring now grows every second**, not only when new data arrives. A ballistic missile adds
  about half a kilometre of doubt per second; a circle that sat still between updates would read as a known
  position. Only missile markers are repainted on that tick — a phone on 2G does not re-lay out forty markers
  a second.
- **Overlapping explosions are grouped instead of stacked.** Anything closer than one glyph-width on screen
  becomes a single dot with the total (**×8**), anchored and labelled by its most recent member — never a
  centroid, which would put a dot where nobody reported anything. Explosions and confirmed shoot-downs are
  grouped apart from each other; they mean opposite things. It is a function of zoom, so zooming in pulls the
  group back into its separate reports, and tapping one opens the full list — place, time, channel and post for
  every report behind it, with a Zoom in button. The ticker and statistics are counted before grouping, so what
  is drawn never changes a number. This replaces the old behaviour of fanning them onto a ring, which moved
  each dot off the place it was reported.

### Added
- A **Missiles are treated differently** section in *How Clear Sky works*, in all three languages.
- `docs/SAFETY.md`: why missiles are aged apart from drones, what the uncertainty ring claims, and the
  refresh-level table.
- `poll_telegram_ballistic_seconds` (default 5) in `config.example.json`.
- Regression tests: a missile never receives `stale`, always carries `fast`, and is gone at 12 minutes
  (`tests/test_prune.py`); the missile level, the source-poll shortening and its failure behaviour, and that
  pings are batched rather than committed one by one (`tests/test_cadence.py`).

### Fixed
- **Usage counting could have become the bottleneck it was measuring.** Every ping committed its own SQLite
  transaction; at one ping a second per device that is thousands of writes a second through a single
  connection, during a ballistic alert, competing with the alert path. Pings are now counted in memory and
  written in batches (at 200, or every 20 s), with the unwritten tail included in the dashboard's numbers.

## 1.3.0 — 2026-09-17

### Added
- **A private usage dashboard at `/admin`** — devices per day, app opens, push subscribers, language split,
  how many run it as an installed app. It needs `ACCESS_KEY` and is not served at all when no key is set.
  **Nothing identifies anybody**: a device is counted once a day through a one-way hash of address and browser,
  salted with a value thrown away and regenerated every midnight, so the same person cannot be followed from one
  day to the next and no hash can be reversed. No address is stored, no location, no path through the app, no
  per-person history — only the daily totals. `tests/test_usage.py` pins those properties.
- The footer now sits under every tab of the panel, not only the Map tab: the free-to-use line, the two support
  destinations, the community link once configured, and © 2026 Black Flame Studio & NGO 07300 · Developed by
  Dread92 · v1.2.

### Changed
- **The welcome screen now uses proper native wording in all three languages**, replacing my own translation:
  the unofficial-volunteer framing, "these are NOT radar data", the main rule about city sirens and the official
  app, and the line about never sharing air-defence footage or impact locations during an attack.

## 1.2.1 — 2026-09-17

### Fixed
- **Updates could stop altogether.** Every request now has a deadline, so a fetch stalled on a weak cell can no
  longer wedge the poller with `pulseBusy` stuck true — the failure nobody would notice until it mattered. A
  watchdog checks every second that a round actually completed, and restarts one if not; coming back to the app,
  regaining network or refocusing the tab all trigger an immediate refresh. The countdown turns red when the last
  round failed. Cadence measured: 15 s normally, 5 s while missiles are up.
- **Markers stacked on top of each other.** Anything landing within 26 px of something already drawn steps onto a
  ring around it — 6 slots, then 12, then 18 — with a thin leader line back to a dot at the true position, so the
  glyph moves but the reported place stays honest. Live targets keep their spot first; history gives way.
- **The same village hit nine times is one marker with ×9**, not nine glyphs buried on top of each other.
- The drawer's open/close tab is centred and in the app's yellow; it was tucked in a corner over the map icons.

### Changed
- **Explosions are brighter**: a white-edged glyph with a red glow, and a shockwave on the freshest ones.
- **Altitude is read the way the channels write it** — "2200 висота" as well as "висота 2200", and a follow-up
  post that is only a number and a place ("1600, Вороньків"). A stated height is treated as a strong hint of a
  drone, shown as *likely a drone*, never as the type itself. A road number or a small count is not a height.
- **Footer**: hosting & development and NGO 07300 as separate destinations, a community link that only appears
  once configured, and a version tag — © 2026 Black Flame Studio & NGO 07300 · Developed by Dread92 · v1.2.
  Contacts live in one `CONTACT` block at the top of the page script.

## 1.2.0 — 2026-09-17

### Fixed (safety)
- **A threat is no longer invented when the post does not name one.** A post that says only where —
  "Васильків увага ‼️", "Лісники" — used to be drawn as a Shahed. It is now an amber warning triangle labelled
  *type not stated*, counted separately from drones. The channels' own shorthand still counts as naming it:
  🛸 / 🛵 / 🏍 / 🅿 is a strike drone, 🚀 a missile, 💣 a KAB. The sign stays upright and blinks red, lives five
  minutes and then disappears outright — no grey fade, because there is no target type to keep half-remembered.
  Where the channel's own habits make one type likely it says so as a guess — "⚠ likely a drone", with the reason —
  rather than either hiding the context or stating it as fact.
- **No marker where the source said the sky is clear.** "Чисте небо Київська область та Київ. Васильків увага"
  produced threat markers over Kyiv — a false alarm on a city that had just been declared clear. Clear sentences
  are now removed before anything is parsed, and "чисте небо" is recognised as an all-clear.
- **The stylus no longer moves the map on its own.** A hovering pen sends pointer moves with no contact; the map
  panned on them. Nothing moves now unless something is actually pressed.
- **The details card stayed inside the map.** It flipped left past the middle of a phone screen and was cut off.
  Below 560 px it docks full width at the top or bottom, away from the target; above that it follows the cursor,
  clamped on both axes.

### Changed
- **Cruise and ballistic missiles are the loudest thing on the map**: brighter red with a white edge, larger
  glyph, a double pulse, a faster course ray, and a label that never hides. They fly further, arrive faster and
  carry far more than a Shahed.
- **Channel advertising is stripped from every post** ("Купуємо контент | ❤️", "➡️Оперативно про…", subscribe
  and donation lines). The warning is kept, the ad is not — it was taking the space a warning needs.
- **The feed is condensed**: identical warnings repeated district by district collapse into one card listing the
  places, and a long post shows two lines with *more* to expand.
- **Statistics reduced to what is real**: explosions recorded and confirmed shoot-downs (24 h / 72 h — the window
  the parsing actually covers), what the Air Force reported as launched and shot down (24 h / 7 d / 30 d), and
  explosions per day. The "alerts / 24 h", "under alert" and per-oblast figures are gone; they were double
  counting and nobody used them.
- The drawer opens and closes with a proper tab on its top edge instead of a 3-px pill.
- Ukrainian wording corrected throughout, using the terms the people reading it actually use: *Збито / Приземлено*,
  *Залишив область / Вийшов із зони*, *Локаційно втрачено*, *Позначка не фіксується*. Several strings were plainly
  ungrammatical ("Позиції — де сказав допис"); a glossary of the status words is now in the help page.
- Credit: built by **Dread92**.

## 1.1.0 — 2026-09-17

### Fixed (safety)
- **A descending drone was shown as "confirmed shot down".** `зниження / знижується` — the word the monitoring
  channels use for a drone diving on its target — was matched by the shoot-down keywords, so the most dangerous
  moment of a target's flight was painted green and its track was closed. It is now a live target carrying the
  altitude state `descending`, drawn crimson with a ↓ and a label that survives every zoom level. Only an explicit
  `збито` / `знищено` / `мінус` makes a shoot-down.

### Added
- **Altitude, when the post states it** — descending, climbing, low, high, or a value in metres, with the words it
  came from. Never inferred: no public source publishes altitude.
- **"You are on an old build" notice.** `/api/version` carries a build id; a page that has been open for days
  offers a one-tap reload when the server has moved on.
- **Install as an app (PWA)** — a discreet prompt on Android, the Share → Add to Home Screen hint on iPhone,
  snoozed for 14 days if dismissed, never shown over the welcome screen.
- **Share a target in one tap** — the system share sheet, or the clipboard: type, count, place, time, descent,
  heading, distance from your place, the source channel, the "not radar" caveat and the link.
- **Proximity notifications** — allow your location, choose a radius (5–50 km), and get a push when something is
  reported inside it. One push per target per device, at most one every two minutes, live targets only.
- **Blackout mode** for 2G and weak signal: pure black and white, no map tiles, no images, a much smaller feed
  payload. One accent colour survives — what is heading at you.
- **"How this app works"** — twelve sections explaining the map, the markers, the grey targets, the warning
  banner, the statistics and the notifications, in all three languages.
- **Support the project** — the donation address, a polite line on the welcome screen, and a reminder at most
  once a fortnight that never appears while an alert is running.
- Credits: Black Flame Studio & NGO 07300.

## 1.0.0 — 2026-09-16

First tagged version: the app as it runs today.

### Coverage
- All of Ukraine: 27 oblasts, 136 raions, 36 Telegram channels including the city-siren network,
  єТривога and єРадар.
- Kyiv has its own simplified 10-district map from OSM boundaries.
- Crimea drawn hatched as temporarily occupied, with a pixel-art Cossack and a waving flag.

### Map
- Oblast-wide alerts always paint the whole oblast; raion alerts can only add to them.
- Shaheds drawn loitering with a heading chevron; no trajectory extrapolation unless EST is on;
  no ETA anywhere.
- Co-located targets cluster into one glyph with a count badge; labels de-collide in screen space;
  off-screen targets get edge indicators.
- Stale targets go grey with a `?`, fade in steps and disappear after 15 minutes.
- Street and building tiles from OSM below 150 km width.
- History layer: explosions ✸ and confirmed shoot-downs ✕ over 24 / 48 / 72 h.

### Warnings
- Preventive banner for MiG-31K take-off and ballistic threats, with cancellation and a 20-minute
  cap.
- Nightly threat *assessments* are classified as forecasts: they never raise the banner and never
  place a marker. Stored posts from the last 6 hours are re-tagged at startup.
- Missile mode: 5-second refresh while a ballistic or cruise-missile threat is open.
- Web Push (VAPID / RFC 8291) for the watched oblast and the chosen place.

### Interface
- Full UI in English, Ukrainian and French, including place, raion, district and channel names.
- The entry screen asks for the language, the oblast and, optionally, a precise place to watch.
- Compact status band; scrolling ticker with the basic rules; disclaimer on every open.
- Stats: alerts per day and by time of day, longest alert, explosions and shoot-downs by oblast, and
  what the Air Force reported as launched over Ukraine (24 h / 7 d / 30 d) — kept separate from the
  count of monitoring reports.

### Project
- Restructured into `app/` + `static/` + `tests/` + `docs/`, with VS Code configuration, pytest
  suite, ruff, GitHub Actions CI and an optional Fly.io deploy workflow.
