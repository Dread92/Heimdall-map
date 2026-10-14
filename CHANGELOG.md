# Changelog

Every patch adds an entry here and updates [docs/TECHNICAL.md](docs/TECHNICAL.md) — see its §18.

## 1.58.20 — 2026-10-14

### Changed
- **An oblast's badge counts the drones reported in it, as an estimate** — the owner: "for the number of drones in an
  oblast we go by how many are currently reported within the oblast, with a '~' to show it is an estimate". Mykolaiv
  oblast's badge said ×3 (the one post about the oblast as a whole) with thirty drones placed inside it. It now shows the
  larger of the drones placed in the oblast and those reported for it as a whole — never both added, they are often the
  same — written "~29", with "reported in the oblast now" under it and, in its card, "an estimate, not a count".
- **The oblast names step back zoomed out** — the owner: "honestly we don't need it zoomed out, or make it more
  discreet: it takes all the room". Zoomed out they are smaller, letter-spaced and half-toned over the satellite; on a
  phone over the whole country only the names of the oblasts with a target stay.

## 1.58.19 — 2026-10-14

### Changed
- **Less on the screen** — the owner, of Kyiv oblast on a phone: "even there the visibility could be better, there is
  too much information on the screen". The raions' names are smaller and quieter, and give way to every other name: no
  more "BUCHA RAION" written across Bucha. No name is written under the place's own name or under the map's buttons,
  and a town whose name has no room no longer leaves a bare dot. With a place chosen, its 10 / 30 / 60 km zones are the
  only circles: the oblast centre's rings and the pin's own two are gone.

## 1.58.18 — 2026-10-14

### Changed
- **The icons follow the zoom** — the owner, of the whole country on a phone: "a visibility problem — ideally the icons
  scale with the zoom out / zoom in". A target kept the same size on the screen at every zoom, so zoomed out its
  silhouettes covered whole oblasts. Now it shrinks as you zoom out (to a little over half its size over the whole
  country) and grows a little close in, with its course arrow, halo, count and labels; the oblast badges and the
  Crimea figure shrink too. Words shrink less, so they stay legible, and a target stays as easy to tap.

## 1.58.17 — 2026-10-14

### Added
- **Limits on abuse of the public API** — the first of the audit's recommendations; the owner picked "limit the abuse"
  over signed tokens or Cloudflare Turnstile, because a mobile operator puts thousands of phones behind one address.
  What costs the server is limited per client — an answer nobody else asked for (a replay window, statistics, a
  history), a flag, a flood of push requests, more than 200 live lines — and a usual question never is: a client past
  its allowance is given the last copy there is, and only an answer never built is refused (429, try again in a
  moment). The official alerts, the marks, the feed and the pages are never limited. Kept answers, oblast lists, the
  events log and request bodies are bounded. The dashboard counts the refusals; nothing about who is kept.

## 1.58.16 — 2026-10-14

### Changed
- **The hromadas on the map** — the owner gave OCHA's administrative boundaries "to help with the districts on the
  map". The official data names some alerts by hromada ("м. Нікополь та Нікопольська територіальна громада"): until
  now such an alert coloured its whole raion, a place anywhere in that raion read "alert in part of your raion", and
  Kharkiv's city hromada coloured nothing. Now the alert is painted on the hromada itself (Tactical, Light, the
  replay, the channel's picture), a place in that hromada — or within 1.5 km of it — reads it as its own alert, and a
  place in another hromada of the raion still reads "alert in part of your raion", the hromada named. The band counts
  hromadas as hromadas ("1 hromada red"), no longer as raions. The outlines (1,456 of the 1,457 official hromadas) are
  fetched for an oblast only while an alert there names a hromada, about 30 KB.

## 1.58.15 — 2026-10-14

### Fixed
- **@kudy_letyt places its targets** — the owner: "I added this channel for all of Ukraine and allowed it on the map,
  but it places nothing". Its posts are lists — an oblast heading, then a target a line ("2х БпЛА курсом на Кременчук")
  — of up to 1,500 characters, and every post over 700 was read as news and never stored. A list of targets, a line
  each, is no longer news by its length (an article still is).
- **"Залітає на Чернігівщину" is in Chernihiv oblast** — "Новий реактивний БпЛА з Брянщини залітає на Чернігівщину"
  placed nothing: flying into an oblast was read as where it goes next. Flying into it ("залітає", "залетів",
  "перелітає") is being in it now; flying out to it ("вилітає") is still where it goes. "Група БпЛА залітає на
  Полтавщину з Сумщини" is in Poltava oblast, no longer in Sumy.
- **"По межі з Харківщиною" is not in Kharkiv oblast** — fifteen drones "along the border with Kharkiv oblast", under
  "Полтавщина:", were drawn in Kharkiv oblast.

## 1.58.14 — 2026-10-13

### Fixed
- **The Map background on a phone that crashed with it** — a reader, through the owner (Oppo Reno 15 Pro): "with the
  Map background it crashes — solid artifacts, and it falls out to the lock screen". Not reproduced (no such phone
  here); the Map is made lighter and can no longer crash the app at every opening: the older street-map tiles kept while
  new ones load are counted by their memory (37 of Esri's 512-pixel tiles at most, not 150), the night mode dims the
  map tile by tile instead of filtering it as one picture, and a page that died on the screen with the Map background
  opens next time on the satellite, saying so — the Map is one tap away in Layers.

## 1.58.13 — 2026-10-13

### Changed
- **The channel's picture focuses on the activity** — the owner, of the whole-oblast picture: "the image is too zoomed
  out — ideally a bit more focus on where the activity is". Still only Kyiv oblast and the city, but framed on the target,
  the places it was reported at, the other targets within 60 km of it and Kyiv when it is near: at least 110 km, up to
  the whole oblast when the activity spreads that wide.

## 1.58.12 — 2026-10-13

### Changed
- **The private channel follows the three Kyiv trackers again** — the owner: "no screenshot is published on the
  Telegram bot any more". It was working, and following @chyste_nebo alone (1.58.9): @chyste_nebo had posted nothing since
  03:59 ("Не спостерігається"), while kyiv_airdef and kievinfo_kyiv reported a drone towards Boryspil at 04:25–04:32. His
  pick: "all the Kyiv sources" — @chyste_nebo, @kyiv_airdef and @kievinfo_kyiv, their reports and their outcomes; the Air
  Force and the regional channels stay out of the channel.

## 1.58.11 — 2026-10-13

### Changed
- **Smaller names on the channel's picture** — the owner, of the whole-oblast picture: "excellent — but the towns' and
  raions' names a bit smaller, please". Kyiv 22 px, a town 16, a raion 14 (26, 19 and 17 before), the towns' dots a
  little smaller too.

## 1.58.10 — 2026-10-13

### Changed
- **The channel's picture is the whole of Kyiv oblast, and only it** — the owner: "a change of tactics, it's too
  unreadable — we'll take a snapshot of the oblast and show the whole oblast on the screenshot (but ONLY Kyiv oblast and
  the city of Kyiv)". Every post now shows the same view: Kyiv oblast and the city whole, in a portrait picture
  (1080 × 1350), with the target, its reported path, the other targets of the moment, the official alerts by raion and
  the oblast's towns. Nothing of the oblasts around is drawn — no shape, no tint, no town, no satellite picture. The
  per-target zoom and the village names are gone.

## 1.58.9 — 2026-10-13

### Changed
- **The private channel has one source: @chyste_nebo** — the owner: "for the Telegram bot we'll take a single source:
  t.me/chyste_nebo". It posts that channel's reports and outcomes alone; the official alerts and all-clears are still
  the official data's. The posts still name no channel.
- **The height is shown far more often** — the owner: "I see the altitude is not shown most of the time". @chyste_nebo
  gives a height in a post of its own ("3800", "Бондарня другий 4600") and then names only places, so the next post had
  none. A height the same track was given at most 4 minutes before is now carried, with its time ("~4600 м (у дописі о
  00:44)", on the picture "↕ ~4600 м · 00:44") — older, none, as on the maps. Never guessed.

### Fixed
- **"на 300 метрах" is a height** — "Від Пирятина йде повільна на 300 метрах" (@chyste_nebo, 12 Oct, 21:55) was read
  with no height at all; "на 300 метрах", "на 400 м" now are ("на 300 м від мосту" is a distance and stays one). On the
  maps too.

## 1.58.8 — 2026-10-13

### Changed
- **North of Kyiv, a drone with no course faces south** — the owner, with two drones over the Kyiv reservoir, one drawn
  facing north: "for those drones here, take the habit by default to make them face south — it's the most likely
  direction they will go anyway". In Kyiv oblast north of Vyshhorod, a drone (or a weapon not stated) with no course
  and no reported track now faces south, on the Tactical and Light maps and in the private channel's picture; its card
  says why. The icon only — no course, no ray, no time. A course a post gave, or the way its reports moved, still wins.

## 1.58.7 — 2026-10-13

### Changed
- **The private channel keeps track: a new post for each new report** — the owner: "instead of editing the post, we
  need to add a screenshot every time — it's better to keep track of what's going on". A target reported again gets a
  new post with its new picture, in reply to its last one (at most one a minute per target, never a report older than
  5 min); nothing is edited any more.
- **What became of it is marked** — the owner: "when the alarm is over, or it exploded or fell, or the threat is no
  longer here, we should mark it too". A closing line, in reply to the target's last post: the outcome a post reported,
  linked as the Tactical page links it and in its words ("⬇️ Збито / Приземлено — так у дописі о 21:47", "💥 Вибух
  (влучання або перехоплення — невідомо)", "❔ Локаційно втрачено", "✅ Повідомлено: у районі чисто") — never where it
  happened, never a picture of it —; the **official all-clear** of the target's area ("✅ Відбій тривоги о 22:10 ·
  Броварський район (офіційно)", once per area, after a minute without the alert, only for an alert the running server
  saw); or "⏹ Нових дописів після HH:MM немає".
- **The closer view again, with the villages named** — the owner: "it needs to be zoomed as it was before, but mark
  the name of the villages at least so people can orient themselves". The picture is 50 km of the oblast again (30 km
  of the city, Kyiv in it when near), and names a few villages to orient by — then the owner: "far too many places
  named, it's unreadable": at most 10, the nearest to the target first (the places the channels name before the
  others), well apart.
- **A smaller target** — the owner: "the Shahed is far too big". The silhouette is two thirds of its old size, the halo
  and the course ray shorter, the other targets of the moment smaller too.
- **The height on the picture** — the owner: "display altitude on the screenshot". The height a post gave stands under
  the place's name ("↕ ~150 м", "↕ низько").
- **No channel named** — the owner: "no need to say the source of info". "за @channel" is gone from the posts;
  "from channel posts, not radar" stays.
- **A drone said only to be heading somewhere is off the map until that place is under alert** — the owner's choice
  after 1.58.6 ("alarm ALWAYS is better … why put a drone icon here, it's dangerous"). A drone, a weapon not stated or a
  Banderol whose post said only where it is heading (shown at that place, as an approach) is `held` while the place has
  no official alert: the Tactical and Light maps do not draw it, the Near list keeps it ("position not stated — on the
  map once that place is under alert"), no "near you" push is sent for it, and the channel posts it without its
  silhouette, saying why — then again, drawn, when the alert starts. Missiles are never held. New `app/areas.py`:
  which official alert area a point is in, shared by the server and the channel.

## 1.58.6 — 2026-10-13

### Fixed
- **"In the east of Kyiv oblast, heading for the capital" is in the east, not on Kyiv** — the owner, with the Air
  Force's jet drone drawn on Kyiv as "→ Київ" (and turned east) while Kyiv had no alert: "placement here is obviously
  wrong, it's towards Kyiv but not in Kyiv at least yet… alarm ALWAYS is better… it's dangerous". A post that places a
  target in a part of an oblast and names where it is heading now puts it in that part (low confidence, "east of the
  oblast"), its course toward the destination; the side is no longer read as its course (it pointed east, away from
  Kyiv). Only a post that says nothing of where it is is still drawn at its destination. The private channel posts
  such a target as "Схід Київщини", with the area it is somewhere in.

## 1.58.5 — 2026-10-13

### Changed
- **The channel's picture shows the situation, not one field** — the owner, of a post with a target "→ Переяслав"
  alone on fields: "the map isn't zoomed out enough, we get no situational awareness from this screenshot". Kyiv is
  always in the picture now, at least 90 km of the oblast (the whole city for a target in it), up to 220 km; the other
  targets of the moment are drawn too, smaller and fainter; a town name beside a target moves aside instead of
  disappearing.

## 1.58.4 — 2026-10-13

### Fixed
- **Time under alert, alert by alert** — found reading the dashboard for the owner's pattern analysis: every oblast
  "under alert 168 hours a week", Kyiv city 1,440 minutes a day since mid-September, and on the app's statistics "the
  longest alert: 20,131 minutes, from 24 September to 12 October". The alerts table keeps one row per region and alert
  type, and a region's new alert only rewrote its end: its start stayed the region's first, and read as a history every
  alert ran from that first start to the last end. The stats, the dashboard's analytics (Kyiv's minutes, the alerts'
  starts, the oblasts' hours), the lead times, the nights' summaries, the digests and the records the AI writes its
  bulletins and night reports from now read each alert from its start and end events (`State.alert_rows`), as the
  replay does; and a region's new alert now starts its row again. An "alert" over within a minute is left out of that
  history: an official channel read from 15 to 24 September flipped Kyiv's alert 1,290 times, ~17 s each.

## 1.58.3 — 2026-10-13

### Added
- **The private channel's kill switch** — the owner: "il faudrait faire un killswitch dans le analytic board". Dashboard
  → Live: "Private Telegram channel — ON / OFF", with a confirmation. Off, the server makes no call to the channel from
  its next pass (≤ 5 s): no post, no redraw, no closing line. On again, it carries on with what is reported from then
  (nothing older than 5 minutes is posted late) and closes the posts of targets gone meanwhile. The secrets stay.

### Changed
- **The server panel says why the server restarted** — the owner, of "Starts in 7 days: 58 · without a new version
  (crash, out of memory, watchdog): 10": "should I worry". A restart with the same code was counted as a crash, though
  a secret set, a deploy of the docs alone and Fly moving the machine restart it the same way. A stop signal is now
  written down (`last-exit.json`, beside the database), and so is the watchdog's exit; the panel counts the week's starts
  as a new version · a clean restart · the watchdog · unexpected (crash, out of memory), red only for the last two.
  Starts recorded before this version say their cause was not recorded. The CPU line turns red over 50 % on average,
  not 6 %: that was a shared CPU's baseline, and the machine has had a dedicated one since 1.41.1 — every start (a minute
  or two at full CPU, reading back the stored data) turned it red.

### Fixed
- The first `/api/stats` after a start took 16.6 s (four days of posts parsed for their explosions while a reader
  waited): it is computed once in the background 45 s after the start.

## 1.58.2 — 2026-10-13

### Changed
- **The channel's picture over the satellite view** — the owner: "il faudrait idéalement la vision map satellite". The
  map around each target is now drawn over the app's own Sentinel-2 picture (the file on the volume — no map provider
  is asked), dimmed as the Tactical page dims its satellite layer: the raions' outlines, the alerts' tint, the towns,
  the path and the target over the ground. The tint is one layer, so where two shapes meet nothing is tinted twice.
  The credits name the imagery. Without the file, the plain map as before.

## 1.58.1 — 2026-10-13

### Fixed
- **The channel's setup found no channel** — the owner, with the bot an administrator of "Heimdall Kyiv" and a message
  posted: "pourtant le bot est bien sur la chaîne". `scripts/set-telegram-channel.bat` learnt the channel only from the
  bot's updates and said nothing of why there were none. It now says what Telegram answered (its own words, the token
  masked) or how many updates the bot received, and when the bot is told nothing — or another program already reads
  its updates — asks for the channel's id (Telegram Desktop: Settings → Advanced → Experimental settings → "Show Peer
  IDs in Profile"; or the address of the channel in web.telegram.org/a), with or without its -100, and checks it with
  Telegram (`getChat`) before going on.

## 1.58.0 — 2026-10-12

### Added
- **A private Telegram channel** — the owner: "a small private Telegram channel that posts alerts like the channels we
  read, with a 'screenshot' of the app where the drone is (Kyiv + Kyiv oblast only)"; picked: one post per target,
  updated, and the app's style drawn on the server. Each target over Kyiv city or Kyiv oblast gets one post: a
  1080 × 1080 map around it (the raions and the city tinted by the official alerts, its reported path, a course ray only
  when a post stated one, the place in a pill; "Балістика на Київ!" at Kyiv, as an approach, "where it is now was not
  said") and a caption — type, count, place, stated course and height, the time,
  the channel, "З дописів каналів, не радар", a link to the map. It is redrawn in the same message as new reports of
  the same target come in (at most every 45 s), and closed with "⏹ Нових дописів після HH:MM немає" once gone from the
  map — never an outcome, never an impact or air-defence position. At most 18 calls a minute; nothing older than
  5 minutes is posted after a restart; the posts survive a deploy. The dashboard's official sources show "telegram
  channel (posting)". `app/chanpost.py`, `app/mapshot.py` (Pillow; the image installs the DejaVu font).
- `scripts/set-telegram-channel.bat`: the bot's token asked hidden and checked, the private channel found, the bot's
  rights checked, a test message, then `TG_BOT_TOKEN` / `TG_CHANNEL_ID` straight into Fly's secrets. Off until then.

### Fixed
- **A ballistic missile on a drone's village** — found while building the channel: "Балістика на Київ!" 20 s after
  "Шахед Княжичі, курсом на Київ" on the same live channel put the ballistic missile at Kniazhychi, the Shahed's place
  (a post naming only where a target goes keeps it at the channel's previous report). Only a report of the same weapon
  is now taken for it; the ballistic missile is drawn at Kyiv as an approach, as the post said.

## 1.57.9 — 2026-10-12

### Fixed
- **A strike told after it happened is no threat** — the owner, with a screenshot of ballistic missiles over Kyiv,
  "launch completed", at 23:48: "encore une news détectée comme une menace". The Air Force's flash report ("❗️О 22.10
  ворог завдав удару по столиці … 6-ма балістичними ракетами … Інформації щодо пусків … не поступало") was drawn as a
  live ballistic attack 98 minutes after the strike, by the Air Force's channel and every Kyiv channel that relayed it —
  though the feed had already tagged it the Air Force's summary. "Ворог завдав удару", "О 22.10 ворог атакував …" are
  now read as a report, whoever posts it, and what the feed calls the Air Force's summary never becomes a mark unless
  it says what flies now. A ballistic push may have gone to phones around Kyiv at 23:48.
- **The Air Force's figures**: "9-ма баражуючими боєприпасами S-8000 «Бандероль»" was stored as 8,000 Banderols launched
  (the model's number) — now 9, and the 6 ballistic missiles are counted. A flash report of one strike is kept apart
  ("flash") and never added to a night's or a week's totals: the morning summary counts the same missiles. The stored
  reports are read again once at start.
- "Інформації щодо пусків … не поступало" is no launch; "столиця" is Kyiv with no place in it — the city is marked, not
  a point at its centre ("Stolytsia, high confidence"), and a course to it reads "→ Київ".

## 1.57.8 — 2026-10-12

### Added
- **As of when, the day of the war, and ⟳** — the owner, showing the government app's header ("Станом на: 12 жовтня о
  20:27 (1692 день) · Оновлення через 05 с"): "good to have". A line under the header: "Станом на 12 жовтня о 20:27 ·
  1692-й день війни", then "Наживо — зміни надходять одразу" while the live line is up, or "Оновлення через 05 с"
  counted down without it, and a button that asks everything again at once. It shows with the card folded too, and
  replaces the card's "updated 5 s ago".

### Fixed
- **A raion is named as a raion** — the owner: "it's the Vyshhorod district here, not the Vyshhorod city". The map wrote
  "ВИШГОРОД" in the middle of the raion, 30 km from the town, and an alert over the whole raion read "Вишгород". Kyiv
  oblast's seven raions are now "Вишгородський р-н" on the map and "Вишгородський район" in the status and the list of
  raions under alert ("Vyshhorod raion", "raion de Vychhorod").
- A test of the Air Force history backfill depended on the date: its September posts fell out of the 14-day window on
  12 October. Its window now reaches back to them whatever the day.

## 1.57.7 — 2026-10-12

### Fixed
- **The power plants and airfields are where they are** — the owner, with screenshots: "some icons are shown in the
  wrong place, we need to make sure that it isn't badly placed". The Kyiv oblast landmarks had been typed rounded to
  0.01°: ТЕЦ-6 stood 4.6 km off, in Troieshchyna's flats; ТЕЦ-5 on the Stolychne highway, 2 km from the plant by the
  Southern bridge; Darnytsia TPP, Trypillia TPP and the Kyiv HPP 1.5–2 km off; the Bila Tserkva airfield 10 km east,
  on the far side of the town. Now the plants' own coordinates (Global Energy Monitor, Wikipedia), every one checked
  on the satellite picture: each icon sits on the plant's main building, the dam or the runway. Over the rest of the
  country one was off: the South Ukraine NPP, rounded to the minute by GeoNames (500 m north, in the cooling pond),
  now on its reactors.
- **A post naming ТЕЦ-5 or ТЕЦ-6 marks the plant**: the place list the rules read had the same rounded points
  (ТЕЦ-6 4.6 km away); the two plants and the Boryspil and Zhuliany airports now have their own.
- **A landmark's name stands beside its icon at every zoom.** It was set 2 km off in map units — a few pixels at the
  region view, 200 px at the street view, where "Київська ТЕЦ-5" ended up in the Dnipro. It now stands on the icon's
  point, moved aside in screen pixels like the icon is sized.

## 1.57.6 — 2026-10-12

### Added
- **The Android app can open the site full screen** — the owner: "an app we can really install on the phone, an APK,
  without going through the stores first, in a folder of its own". The app is `heimdall-android` (a separate folder: a
  Trusted Web Activity that shows this web app, with its notifications); this release only lets the site vouch for it:
  `/.well-known/assetlinks.json` names the app and the fingerprint of the owner's signing key, set once with
  `scripts/set-android-key.bat`. Until then the list is empty and the app shows an address bar.

## 1.57.5 — 2026-10-11

### Changed
- **A target faces the way its reports moved** — the owner, a jet drone at Obolon drawn facing north while its path
  came down from above the reservoir: "the drone should face downward when it is possible to guess". With no course
  stated, the icon now turns along the last leg of its own reported track (from the last report at least 1.5 km away,
  within 45 minutes) — on the map and on Light. The icon only: no course ray, no heading, no countdown; the card says
  "drawn facing the way its reports moved: no course was stated". Never back across the border; with no track, a drone
  in Chernihiv oblast still faces into Ukraine, and any other mark north.

## 1.57.4 — 2026-10-11

### Fixed
- **Every popup can be closed** — the owner, the shelter list open on his phone: "there is currently no way to quit this
  popup". Every sheet has a ✕ at the top right, always in view while it scrolls; the shelter sheets end with a Close
  button too; on Light the open shelter list has its ✕.
- **The phone's back button closes what is open** (a card, the shelters, the place sheet, a panel) instead of leaving
  the app; Escape too, on a computer.
- **"What to do" has a back button** — "← Back", always in view at the top: to the page the reader came from (Light or
  the map), or to the map when the guide was opened on its own.

## 1.57.3 — 2026-10-11

### Added
- **"4.5.0" (@vseok450), a live tracker of Kyiv and its oblast** — the owner: "we also add this channel as a source for
  Kyiv and the oblast; it comes from a trustworthy source". Read like the Kyiv trackers (`parse_kyiv_airdef`), in the
  Kyiv compartment, and **on trial** until the owner puts it on the map from the dashboard: its posts are in the feed,
  flagged, and raise nothing. Its posts are short lists of places and counts with no weapon named; on 11 Oct the rules
  read its bare lists ("Яготин / Богуслав") and "1-й до Чабанів", not yet its counts ("3 Чернігівська"), "з півдня"
  after a pair of places, or a list under a sentence — taught from its posts while it is on trial.

## 1.57.2 — 2026-10-11

### Added
- **The Light radar can show the satellite picture or the street map** — the owner: "it'd be good if the light version
  showed the satellite / map too". A layers button on the radar: Background → Plain (the default, as before) /
  Satellite / Map ("uses more data"), kept on the phone. The same pictures as the Tactical map, clipped to the disc,
  under the rings, the outlines and the targets; the source credited under it. Its code is loaded only when asked for,
  so the page stays light for 2G.
- **The pictures do not say where the pin is**: the tiles asked for are those of the ~10 km cell the place is in (the
  cell the push already stores), with a margin — every place of one cell asks for the same ones.

## 1.57.1 — 2026-10-11

### Changed
- **"Shelters around me", within 5 km of the pin** — the owner: "let's change to 'shelters around me' and put a 5 km
  radius based on the pin location". One radius for the card (the nearest metro, underpass or civil-defence shelter
  within 5 km, was 2), the list (was 3 km) and the layer, which now shows only the shelters within 5 km of the pin,
  inside a dashed circle — no longer every shelter of the city. With no pin in Kyiv city the layer shows nothing and
  says why. The list keeps one row per address (a station's entrances are one place).

## 1.57.0 — 2026-10-11

### Added
- **The shelters Kyiv city lists, on the map and on the pin's card** — the owner's colleague: "a layer of the official
  shelters, the government's data only, baked into the app so it works offline"; the owner chose every shelter the
  city lists, each labelled with what it is. 3,878 points from the city's own shelter map (KMDA, ІАС «Майно»,
  gis.kyivcity.gov.ua/shelter, data of 11 Oct 2026): 171 metro stations and entrances, 293 underpasses, 52 civil-defence
  shelters, 476 dual-use structures (parkings, basements), 2,882 simplest shelters (basements, parkings), 4 modular ones.
  - **On the card**, while an alert or a warning concerns a pin in Kyiv city (or the layer is on): the nearest metro,
    underpass or civil-defence shelter within 2 km, with its address and who may come in when — and the nearest of any
    kind when it is nearer. A tap lists the three nearest of the strong kinds and the three nearest basements, parkings and others; a tap on one
    shows it on the map. Light: the same line under the place's status; a tap lists more.
  - **On the map** (Layers → Shelters): a square per shelter, filled for the strong kinds; every kind from 24 km across.
  - **What the city writes is what is shown**: "for the school's pupils and staff during the school day" (841),
    "for them only" (144, never offered as the nearest), "under repair" (7, nor these), the hours where they are given.
  - **Worked out on the phone**, from a file the service worker keeps (it works with no network): no pin leaves it. A
    distance is a straight line — never a route, a walking time or a time to get there — and nothing says a place is
    safe: "Heimdall does not check shelters: one may be closed, locked or full", and outside is dangerous during an
    attack — "two walls between you and the street, away from windows".
  - The city's firewall refuses a script: the owner saves the city's list from a browser and
    `scripts/build_shelters.py` turns it into `static/shelters.json` (§16).

## 1.56.6 — 2026-10-11

### Fixed
- **A missile in another oblast no longer raises the shelter banner here** — the owner, a phone in Vyshenky at 15:34:
  "a ballistic alert for I don't know which oblast, and the banner alarms the user for nothing — it must be fixed at
  all costs, all the more because it changes how the targets are marked". The Air Force had posted "🚀Швидкісна ціль на
  заході Донеччини, курс на північ" — Donetsk oblast, some 600 km away. A missile post now carries the oblasts it names
  (the oblasts written out, and those of the towns it puts a missile at; Kyiv city counts as its oblast), and the
  warning strip raises it only for a reader of one of them. A post naming none ("загроза балістики з північного
  сходу") still warns everyone, a MiG-31K take-off too, and the official alerts are untouched.
- **A missile far away no longer turns the drones here into "drone or missile"** — the Voronkiv target, type not stated,
  became a red ⚠ "drone or missile" because of the Donetsk post. A target is "drone or missile" now only when a missile
  is on the map within 150 km of it, or a missile warning is raised for the reader's own oblast and the target is
  within 300 km of their place; otherwise it stays "probably a drone", drawn as one. Same on the Light page.
- The server's missile level (how fast every page and channel is read) follows the oblasts on the map, Kyiv and the
  favourites; a missile post about an oblast off the map no longer speeds it up.

## 1.56.5 — 2026-10-11

### Changed
- **No target numbers in the app, for now** — the owner: "let's disable the target IDs for now — it doesn't work and
  it's very unreliable". No "#158" on the map, in the tooltip, the card, a whole oblast's chip or the replay, and no
  night's path built from a number. The server still works them out for the dashboard's patterns and the record;
  one switch (`TAGS_SHOWN` in `i18n.js`) brings them back.

## 1.56.4 — 2026-10-11

### Fixed
- **"Jet UAV to Kyiv/Irpin/Bucha" is drawn at Bucha, not in the middle of Kyiv** — the owner: "the post is talking about
  Bucha, yet the drone is again put randomly in the middle of the city". When a post names several places a target is
  heading for and nowhere it is, the mark stands at the one it reaches first: around Kyiv, not the city when its suburbs
  are named with it, and of the rest the farthest out. The card and the label say the whole list ("heading for Київ /
  Ірпінь / Буча").
- **"на Бучу", "у Бучі" were no place at all** — a four-letter name kept its last letter in the search; Bucha's cases
  (and Ichnia's, Kiliia's, Mena's) are read now.

## 1.56.3 — 2026-10-10

### Fixed
- **In Chernihiv oblast a drone faces into Ukraine** — the owner, two drones near Liubech drawn heading north-west: "by
  default the drones must always face into Ukraine when no direction is given; it is extremely unlikely that a drone
  goes back to Belarus or Russia". A drone there with no stated course faces towards Kyiv (the icon only — no course,
  no ray, no countdown; the card says why). The north-west course came from two different targets: the previous
  post's drone near Kiptiv and this post's near Liubech. A course is now worked out from a tracker's two reports only
  when each reported one target, and never when it points back across the border.
- **Hnidyn — and 81 other places — where they are** — "Hnidyn is never reported". The hand-written gazetteer put
  Hnidyn 5.8 km east of the village; checked against OpenStreetMap, 82 places were more than 1.5 km off (Berezan 11 km,
  Olshanytsia 12, Myhalky 14, Kotelva 19) and are now where OSM puts them.
- The patterns' "courses stated" no longer count the courses worked out from two reports.

## 1.56.2 — 2026-10-10

### Fixed
- **A height is never shown more than 4 minutes after it was reported** — the owner: "a drone at low altitude (900 m)
  whose altitude was last reported 10 minutes ago is probably already down, has struck a target, has regained altitude
  or has changed path". Kyiv INFO: 15:48 "900 m Shahed", 15:50 explosions close by — and the map kept "900 m" for
  11 minutes. The height and the descent arrow on the map, an earlier report's height "(3′)", a whole oblast's chip, the
  card's height chip, Light's mark and row and a run of heights ("↓ 2,2 км → 900 м") all go once the report that stated
  them is more than 4 minutes old. The card still shows it as history: "reported 11 min ago — too old to be its height
  now", and its track keeps each report's height with its time.

## 1.56.1 — 2026-10-10

### Changed
- **One AI bulletin an hour** — the owner: "instead of a bulletin every 20 minutes, really only one an hour". The last
  hour and the last 24 hours are both written at :00 (the last hour was at :00, :20 and :40); `ai_bulletin_minutes` is
  gone. A bulletin stays shown 75 minutes unchecked, so the hourly one never drops out between two hours.
- **The patterns start from the first night the posts are kept** — the tags began on 9 Oct, the posts are kept since
  18 Sep: every night before the first tagged one is read again from its posts with today's rules, six nights an hour
  at most and none while Kyiv is under alert, and its moves are kept with the others (marked "replay").
- **Fixes to the patterns' figures**: two places reported at the same moment are no move (a quarter of the first moves
  were 0 minutes long); the Banderol is counted with the jet drones; an area is named by the places most reported in
  it (the Kyiv square is "Київ", not a village one track passed); the destinations the posts named are a share of the
  posts that named one (they read 0%).

### Added
- **The patterns in plain words** — "see whether you can identify patterns, in plain English": the Patterns tab says
  what the figures show, in English and Ukrainian, only where they show something — "Славутич: of the 526 courses the
  posts gave here, 53% were south and 31% north (95% range for the first: 49–57%)" — strongest first, after a line on
  what it is built from. What was reported, never a forecast.

## 1.56.0 — 2026-10-10

### Added
- **Every street and village of Ukraine in the pin pickers** — the owner: "a complete registry of the streets within
  the city / oblast, so the user can set the pin accurately — all the towns and streets of Ukraine". 30,215 settlements
  and 230,814 named streets from OpenStreetMap, one file per oblast. Under the search, "Streets & villages in": Kyiv and
  Kyiv oblast by default, or any oblast. Type "шевченка бровари", "Хрещатик", "khreshchatyk", "лукянівка" or a street's
  old name ("Московський проспект" finds Bandera Avenue): the streets and the villages the list did not have appear
  under the places, each with its town and raion (in Kyiv its district).
- **A pin on a street** (Tactical): the pin goes to the street, the map zooms to it and asks for the exact spot — a tap
  moves the pin there and it keeps the street's name; the street map is shown for it on the plain background. Light
  sets the place on the street.
- **On the phone only**: the list is downloaded once and searched on the phone — what is typed and the street chosen
  never reach the server, which sees only which oblast's list was opened. Data © OpenStreetMap contributors, ODbL.
  `scripts/build_streets.py` rebuilds it from the OSM extracts.

### Changed
- The search's hint names a village or a street ("Search: Obolon, Bucha, a village, a street…").

## 1.55.0 — 2026-10-10

### Added
- **Where the drones go, area by area — on the dashboard only** — the owner: "the pattern of direction of the
  drones, aggregated through time, depending on its location — proper foundations to calculate the % of probability
  that the drone goes to X, Y or Z; not in the app yet, on the admin dashboard". Every tagged target's moves, from one
  reported position to the next (where it was, where the next report put it, how far, how long, the bearing, its kind,
  where a post said it came from), are built every hour into a new table kept for good (`track_moves`; the points it
  is built from go after 60 days); the first build takes the last 58 days. A move keeps the physical check of 1.54.7:
  a report the target could not have reached is another target's.
- **Dashboard → Patterns**: for each area of about 14, 28 or 56 km, over 30 / 90 days, a year or all of it, for all
  drones, propeller, jet or weapon not stated — where the next report put the target, where the tracks that passed
  through it were last reported, the directions of its moves beside the courses the posts stated, the destinations
  the posts named and where they said the tracks came from, the median speed and gap. **Every % comes with its 95%
  range** (Wilson): 2 moves of 3 is 67% (21–94%), 200 of 300 is 67% (61–72%). A flow map (each area shaded by its
  moves, an arrow for their mean direction, lines from the chosen area to where the next report put it), every area
  in a table, and the areas and every move as CSV for any further model. English and Ukrainian. `GET
  /api/admin/patterns` (🔒); no page of the app asks for it.

### Docs
- TECHNICAL.md §7.12 (the patterns), §5.1 (the `patterns` thread), §8c, §12, §13; `marker_log` is in fact kept for
  good — `Store.prune_log` exists but nothing calls it (the table said 120 days). SAFETY.md: where drones usually go is
  the dashboard's, not a reader's — a pattern is what targets did on other nights, never this one's course. The system
  map has the new thread, table and route.

## 1.54.9 — 2026-10-10

### Fixed
- **Sharing a target no longer shares your pin** — the owner: "the location of our pin must NOT be shared, it can be
  sensitive". The shared text said "19 km — Вишеньки": the distance to the reader's own pin and its place. It is gone;
  the text says what the post said. The first push subscription no longer sends the pin's name either.
- **The place search on a phone stays above the keyboard** — "the keyboard overlaps the suggestions". The sheet stands
  on the keyboard and its list takes the room that is left (Tactical and Light).
- The hover card of a target whose weapon was not stated said "type not specified" — it says "probably a drone" too.

### Changed
- **Four numbered pins you name yourself** — "pin one, two, three instead of home, work, kids — let the user rename
  them". "Pin 1" to "Pin 4", or the name typed in the pin's sheet (kept on the phone only). Every pin can be found by
  search or put on the map; places set before are kept.
- **Unstated threats are drawn as Shaheds** — "instead of the triangles, Shahed icons by default; outside a ballistic or
  cruise missile context these threats are treated as drones". The silhouette, colour, course and count of a drone,
  labelled "probably a drone"; the red ⚠ "drone or missile" while missiles are reported. No countdown on a guess.
- **The height is outlined text, not a filled pill** — "just make the characters more visible, with an outline".
  Larger and heavier, sky blue (red while descending) on a dark outline; readable in day, night and light mode.
- **The manual is rebuilt with every patch** — "the manual must be updated with every change". `scripts/build_manual.py`
  writes `docs/manual.html` from the documentation, and a test fails when a document changed without it.

## 1.54.8 — 2026-10-10

### Changed
- **No more "unknown" for what is most likely a drone** — the owner: "'unknown' is badly worded, in the AI summary as
  well as in the app: it's most likely a drone (a jet Shahed); the only exception is when we know ballistic or cruise
  missiles are also coming". A target whose weapon the post did not state is now "probably a drone" on the map, the
  card, the Near list, the counts and the Light page — and "drone or missile" while a missile, a MiG-31K, strategic
  aviation or a cruise-missile warning is reported. The bulletins' record and the night's report use the same words,
  and the AI is told never to write "unknown" nor to turn "probably" into a certainty.
- **The AI is given everything Heimdall knows about the window** — "those data are precious: pattern recognition".
  Besides the counts and places: the raions under alert, the missiles and carriers reported, the courses, every stated
  height (by band and oblast, descending), the speeds, where the posts said targets came from (kept for the record, not
  said in the bulletin), the outcomes' times, the followed tracks in full, and for 24 hours the night's weather. Each
  mark now keeps what it stated too (height, vertical state, speed, origin, destination, tag).
- **More room to write** — "more leeway on the token cutoff": 4,000 / 8,000 tokens a bulletin (was 1,200 / 2,400), a
  2-minute wait for the answer, 90 / 220 words a language (was 60 / 140).
- **The bulletins are kept** — every one for 90 days with the record it was written from, then for good one an hour and
  one a day (the night); it was 30 days.

### Docs
- TECHNICAL.md's overview (§1, §3) brought up to date: 23 channels, three of them through the Telegram API, the Air
  Force's figures, the carriers and the weather, the AI's bulletins, and the system diagram as it runs now. A web page
  of the whole manual, with a map of the system, is built from these files.

## 1.54.7 — 2026-10-10

### Fixed
- **The villages of Kyiv oblast are on the map again** — the owner: "critical data, and it was not displayed".
  @chyste_nebo, 01:21: "Кулажинці", a drone at 400–500 m north-east of Brovary, drew nothing. The ~825 villages of
  Kyiv oblast the gazetteer lacks were the AI reader's alone (1.52), and since 1.54 the AI reads no post. The rules
  read them now, in a Kyiv tracker's posts and in posts about Kyiv oblast (everyday words like "Озеро", "Ферма" kept
  out).
- **"лук'янівка" was the village, not the Kyiv district** — "that's another Lukyanivka, not a district but a village".
  A Kyiv district and villages of its name are now candidates: the district by default, the village when the channel's
  report before or after is next to it — "Кулажинці", nine minutes later, 14 km from the village and 52 km from the
  district, moves the mark there.
- **A height alone ("500", "400")** is the height of the target the channel reported last (within 15 minutes) — it was
  dropped.
- **Glitched satellite tiles on one reader's phone** — a tile the server could not read at that moment was answered with
  a "missing" the browser kept for a day; it is now a short failure nobody keeps, the page asks a missing tile again
  (2, 8, 30 s), the phone's kept tiles are refreshed once, and a browser's "dark theme for sites" can no longer
  recolour the page.

### Changed
- **The physical check** — the owner's idea: "if attaching a new report to a target implies 1,000 km/h, reject the
  match". Two reports are one target only at a speed it can fly: 350 km/h for a Shahed (185 by its specification),
  650 for a jet drone and the Banderol (550–650), plus 8 km for two named places — still never past 80 / 120 km. The
  same check decides between places that share a name, and leaves out a line on the card.
- **The replay says it is loading** — "an obvious loading spinner, people think the feature does not work": a spinner
  over the map and in the bar, with "the night is being read again from its posts — up to half a minute the first
  time", while the controls wait greyed out.

## 1.54.6 — 2026-10-09

### Changed
- **A stated height catches the eye** — the owner: "altitude is critical data… more visible, eye-catching, not super
  flashy, and only when the height was stated; the dark mode must stay readable". The height under a mark is now a
  small pill, white on blue (white on red while it descends), instead of pale blue text; the card's height chip and
  the height in an oblast badge match. Marks with no stated height have none. Night mode keeps it dim (dark blue,
  pale text), the day mode a deeper blue, the light version black on white.

## 1.54.5 — 2026-10-09

### Changed
- **The oblast and Kyiv city badges are a fifth smaller on a phone** — the owner: "nice but too big on phone". 19 px
  high instead of 24, the text and the weapon's silhouette to match; a computer keeps them as they were.

## 1.54.4 — 2026-10-09

### Fixed
- **A drone's path drawn across 150 km and the whole of Kyiv** — the owner: "this line is probably wrong — not 100 %
  sure, but no wild assumption when the gap between two points is so huge". #157 joined "Сквира" (00:29) and "Велика
  Димерка" (00:53), both @kyiv_airdef with no type stated: a bare place name of a channel that tracks drones could be
  continued at 15 km a minute, a missile's pace, and a drone at 7. Now a drone's report continues a track only as far as
  a drone flies between them — a Shahed 3.5 km a minute (210 km/h with a tailwind), never past 80 km; a jet drone 9 km a
  minute, never past 120 km — and a bare place name from a drone tracker is a drone. On the map, the red dots of a
  tapped target leave out the line between two reports too far apart to be one drone's flight; the dots stay.

## 1.54.3 — 2026-10-09

### Added
- **Layers → "Path of a tapped target (red dots)"** — the owner: the path joining a target's reports "should be a
  checkable option". On by default, remembered on the phone.

### Fixed
- **The map flickered when zooming in or out** — black patches, at times the left column blank. While a pinch or the
  wheel lasts the map is one picture the GPU scales, but every mark's halo and blinking glyph redrew all of it at every
  frame, at the scaled size — many screens' worth after a long wheel zoom. During the gesture nothing in the map moves
  now, and past 3× it is redrawn at its own size. The glow of an oblast with a target somewhere in it no longer breathes.

### Removed
- Layers → "History: explosions" and "History: confirmed shot down": they belonged to the explosions layer removed in
  1.54.0.

## 1.54.2 — 2026-10-09

### Changed
- **The heat map** — the owner: "rather bad". Every village named once or twice in the period painted its own pale
  disc, and a busy week spotted the whole region in yellow. Now nothing is painted below about 3 % of the scale, and the
  colour comes in with the count: what stands out is where the reports gather.
- **No more yellow outline on every raion** while the heat map is on ("the yellow outline of every oblast when zoomed
  out is bad"): the official alerts are a faint tint under it; the live status stays in the card.
- **The heat map's legend folds and moves** ("it can't be moved or made smaller — a problem on a phone"): ▾ or a tap on
  its title folds it to "Heat map · 7 days", and its title line drags it anywhere over the map; both remembered. On a
  phone it starts folded, at the top left below the header.

### Fixed
- **A tap on an oblast's badge did nothing on a computer**: the map held the pointer from the press, so the badge never
  got its click. It opens the oblast's card like a tap on a mark.
- **"В Житомирській" drew a drone at the Zhytomyrska metro station, in western Kyiv** (@chyste_nebo, 9 Oct: "В
  Житомирській", "Житомирської може зайти поки Радомишль" — Zhytomyr oblast). The heat map showed it: "Zhytomyrska ·
  117" in Kyiv over a week. A Kyiv tracker's "Житомирська" is the oblast like anyone else's; the station only when the
  post says "метро", "станція" or "ст. м.". And "Шахед над Житомирською" was drawn at the village of Житомирське by
  Ovruch: a feminine form never names a neuter or masculine place ("над", "під", "біля", "поблизу" are read like "в"
  and "з" before an oblast's adjective).

## 1.54.1 — 2026-10-09

### Changed
- **The card of a target on a computer** — the owner: "the UI isn't that great when we click a threat (only on desktop)".
  It took the whole width of the window under the map, lines of a few words across 1,700 px, over the map, the list and
  the feed. It is now a card over the map's lower left, beside the list: 420 px wide, scrolling inside, its buttons
  always in view; the map slides the target out from under it. The phone's card is unchanged.

## 1.54.0 — 2026-10-09

### Added
- **The AI's bulletins** — the owner: "instead of all that on the map, summaries of the activity of the last hour / the
  last 24 hours, a bit like a weather bulletin". Over the Near list (on a computer, in the left column): "Bulletin · AI",
  the last hour or the last 24 hours, in the reader's language, with the time it was written and "written by AI from the
  channels' posts and the official alerts — not radar". The AI writes them in Ukrainian, English and French in one call
  from the server's own record of the window — the official alerts, the targets the rules drew (reports, not drones),
  the outcomes, the heights, the paths followed, the Air Force's figures: counts, places and times, never a post's text.
  The last hour every 20 minutes and the last 24 hours every hour, only while there is activity; a quiet window gets one
  line from the server, without a call; the same record is never written twice. Never "safe", no shelter advice, no
  forecast, no "where they came from". **Behind the dashboard's switch** (off until switched on), and a bulletin the
  server can no longer stand by (the AI off or out of budget) leaves the app.
- Dashboard → AI: the bulletins' switch, "write the last hour / 24 hours now", the month's bulletins and their cost, each
  bulletin in three languages with the record it was written from.

### Changed
- **The AI puts nothing on the map any more** — the owner: "the AI placing things on the map — we forget it". No target
  only the AI found, no AI fact in a tag (height, speed, descent, origin), no "AI" on a label or an oblast's chip; no post
  is handed to it and its 10-minute checks are stopped (the owner's choice). What it read until now stays on the
  dashboard, folded under the bulletins; its reading code is kept, not called.
- **A target reported for a whole oblast**, the owner: "this tiny square marking looks really bad": the oblast's own name
  lights up, a rounded badge under it (the weapon in its colour, ×count, a height), and the oblast's border glows softly
  from the inside — "somewhere in here", the middle left clear for the targets placed in it. Kyiv oblast's badge carries
  its name; two badges never overlap; the town names under them give way; the badge's pieces are measured in the
  phone's own font.
- The night's report no longer reads the AI's checks (there are none).

### Removed
- **The explosions layer of the last 24 hours** (the ✸ button on the map, its key over the map and its report by place)
  — the owner: it "does not help much for now". The live outcomes stay on the map as they were.

## 1.53.4 — 2026-10-09

### Fixed
- **The AI's checks were cut off 10 times in 12** (the dashboard, 18:40–19:41): each finding was written out in full,
  27 fields with their quotes. A finding now carries only what the map uses (18 fields: no origin, course or speed); a
  check records how many findings it gave, and one that still fails shows how its answer began.
- What the checks found in the rules:
  - "🟢 Відбій повітряної тривоги • Коростенський р-н • Житомирський р-н" — an all-clear — was drawn as two targets
    from a channel with an oblast of its own: an alert message now places nothing from any channel.
  - "На Лозовик" (a Kyiv tracker) was drawn at Lozova in Kharkiv oblast: a place name now matches only in its own
    declined forms ("Лозовою", "Оболонню", "Бориспіль"), not as the start of another word.

## 1.53.3 — 2026-10-09

### Changed
- **No more arrows along the edge of the map** for targets off the screen ("ймовірно, дрон 70km ПнЗ"): a good idea when
  the map had little on it, clutter now. A target off the screen is in the Near list and its card.

## 1.53.2 — 2026-10-09

### Changed
- **No more direction on the tags**: a target's tag is its number alone — "#82". The letter for where it came from was
  wrong too often (a drone coming from Belarus over Chernihiv oblast showed "E-82": its track had taken "з брянської"
  from another post), so it is shown nowhere: not on the map, the card, the replay, nor in what the AI is told about the
  map. It is still kept for the record (the night's record says it is what the posts said, often wrong).
- Analytics: the tags per night, as followed over two places or more / reported at one place.

## 1.53.1 — 2026-10-09

### Changed
- **A target reported for a whole oblast, readable at last**: no cyan, no hatching — a white dashed outline of the
  oblast (dark in daylight), fading slowly in and out, and a small chip right under the oblast's name: the weapon, the
  count, a height ("AI" first when only the AI read it). "Somewhere in the oblast" is written under it once zoomed in to
  a region, and in words on a tap.

### Fixed
- **"The last call failed: cut off at 6000 tokens"**: a busy check (60 posts) had more to say than its answer could
  hold. A check now reads at most 30 posts (more → several calls), may answer twice as long, gives its notes first, and
  keeps what came complete of an answer that is still cut off.

## 1.53.0 — 2026-10-09

### Added
- **The AI reads every 10 minutes instead of every post** (the cost: ~150 posts an hour at ~$0.0004 each would have
  spent the month's $10 in a week). One call reads the posts of those minutes, grouped by oblast, with what the rules
  drew from each and what the map shows in each oblast, and answers only where the rules are wrong or incomplete —
  a target they missed or misplaced, the wrong weapon or outcome, a post that is not about the sky, a height or an
  origin they did not read — with a short note per oblast. About $0.001–0.002 a check. The dashboard can switch back
  to one call a post, and "check now".
- **The AI's report on each night** (Analytics): after 09:00 the AI reads the whole record of the night — alerts by
  oblast, every tag with its path, heights, origins, the reports by hour and oblast, outcomes, the Air Force, the
  checks and their notes — and writes what it shows: routes, waves, heights, patterns, and what the map missed. The
  record itself downloads as JSON or text, for any AI to read. "Write it now" for any night.
- Analytics: what the AI's checks found, night by night (CSV); the tags followed over two places or more.
- **Full-screen map** — the last button of the map's column (yellow): the map alone on the whole screen, the alert
  status kept as a chip at the top (a tap, or the phone's Back, leaves).
- **The map opens at once**: the satellite pictures are kept on the phone (the service worker), those of Kyiv and the
  oblasts around it fetched ahead once (never on a phone saving data or on 2G); the map's drawing (borders, towns) is
  shown from the phone at once and refreshed behind. Alerts and targets are never kept — they always come live.

### Changed
- **A target found only by the AI is never pushed "near you"** — it can be ten minutes old. It is still drawn, marked AI.
- **A tag holds under a target**: a track keeps the number it was last shown with, and another channel's report of
  the same target at the same moment (≤ 6 km, ≤ 4 min) takes the same number — the number no longer jumps from N-56 to
  N-23 on the same drone.
- **The card of a target is short on a phone** — what it is, its height, where, its tag and the post in three lines;
  the rest under "More". The map keeps two thirds of the screen. The tag's line lost the empty box round it (it had
  the buttons' style).
- The dashboard's AI reader tab: the checks with their findings and notes; a post's findings with why.
- **Nothing written over a target**: no label is written over a target's height or tag, or over an explosion's
  glyph; an explosion's name gives way to a live target's label; a town name under a target's glyph or height is
  hidden.

### Fixed
- "Буде тривога в столиці. БпЛА на Козин" drew the drone over the centre of Kyiv: an alert said to be coming for a
  place is not the target's position — it is drawn heading for Kozyn.
- "На Козин 900", "З Козина на Ходосівку": the AI took the namesake village in Chernihiv oblast and a second target
  was drawn 150 km away, at the Poltava border. A namesake is now the place the rules read, and of several villages of
  one name the one beside the post's other places (or the channel's own area) is kept.

## 1.52.1 — 2026-10-09

### Added
- **A target's whole path for the night.** Tap a target with a tag: every place the posts reported it at tonight, also
  the ones older than the map's 45 minutes, drawn fainter before the recent ones, and in the card "N-07 tonight: 12
  reports since 19:02: Ріпки 19:02 → … → Вишгород 20:22". The places are where the posts put it; between two reports
  nobody saw it.

### Changed
- **The hatching of an oblast with a target somewhere in it no longer covers the map**: only on the whole-region view,
  in fine lines, and never over an oblast with a target placed in it. The cyan outline and the chip stay.

### Fixed
- **"Call failed · not JSON" on one reading in ten** (the dashboard, 9 Oct: 18 of 160): the AI's answer was cut off at
  1,200 tokens — a busy tracker's post with several targets, each written out with its quotes. It may now be 2,400
  long, and an answer cut off says so ("cut off at 2400 tokens").

## 1.52.0 — 2026-10-09

### Added
- **Targets only the AI reader found are on the map** — marked "AI" (a dashed ring, "AI" on the label, a line in the
  card), with the "near you" alerts of any other target, under the dashboard's kill switch. Placed only at a place the
  post names: loose wording is read, a place is never made up.
- **Tap a target: its path so far** — the places the posts reported it at, joined in red dots with their times.
- The AI reader can name a village of Kyiv oblast the rules do not know ("Сомкова Долина", "Фарбоване") and a misspelt
  place ("Пепеяслав"), among the oblasts in play.
- Where no post says where a target came from: first reported in Chernihiv oblast — probably Belarus (`n-07`); in
  Cherkasy oblast — probably the south or the east (`s-07`). Lower case, and the card says it is a guess.

### Changed
- **No tag for a target reported for a whole oblast** — a number only when it is sure which target it is.
- The AI reader (prompt version 4) gives where a target is AND where it is going ("на Житомирщині в напрямку Житомира"),
  reads the channels' emoji (🛵 🏍 🛸 🚀), takes a tracker's bare place name as a target, and no longer takes an
  official alert message for a drone.
- A height stays shown: an earlier report's height, with its age, when the latest report did not repeat it.

### Fixed
- **A relay's height was lost**: "Вишеньки 2900" (@chyste_nebo) relayed "Вишеньки" (@kyiv_airdef) and was dropped as a
  duplicate with its 2,900 m. A relay still draws nothing twice, but its height, descent, speed and origin now go onto
  the report it relays.
- "Хотів 1200 знижується": the descent replaced the 1,200 m — both are kept.
- Errors the AI reader showed in the rules: a channel's signature ("‼️ RND | Житомир") read as a second jet over
  Zhytomyr; "з Чорного моря в напрямку Миколаївщини" drawn in the middle of the sea (now: Mykolaiv oblast, from the
  south); "З Житомирської" read as the village Житомирське and "через черкаську" as the city of Cherkasy (now: the
  oblasts); power-cut news and an advert drawn as targets over Kyiv and Odesa.
- The target's tag, its height and an oblast-wide target were unreadable in daylight mode.
- **Two targets could show the same tag**: a report heading for a town ("на Бровари") that a target already on the map
  took over could still be continued by a later report, which made a second track out of it — and both showed one tag.
  A report taken over is no longer continued, and two tracks never show one tag.
- "біля Сомкової Долини" was read by the rules as Dolyna (Ivano-Frankivsk oblast, off the map) and nothing was drawn;
  when the rules and the AI read the one target of a post far apart, the AI's reading is drawn too.
- "над Козельцем", "біля Козельця" — Kozelets was not found in its declined forms.
- Zoomed out, a target only the AI found showed its tag alone; it now reads "AI ?-03", and a whole-oblast one
  "AI · somewhere in the oblast".
- Dashboard, AI reader: Kyiv oblast was shown as "oblast 14"; a descent or climb the AI read is now in the summary line.

## 1.51.0 — 2026-10-09

### Added
- **Target tags** — `S-07 Реактивний ×2`, `3500 м · 400 км/год` under it. Every target in the air gets Heimdall's own
  number for the night (counted from 12:00 Kyiv time) and a letter for where a post *said* it came from: **N** north
  or Belarus, **E** east or Russia, **S** south, the sea or Crimea, **W** west, **?** not said. The letter is never
  worked out from where the target was first seen. A tag stays the same while the target is tracked, also after a
  restart. It is Heimdall's number, not an official or military designation — the card says so.
- The card shows the tag, where the target came from in the post's own words and from which channel, and the speed
  when a post stated one. The replay shows the tags the live map gave; the dashboard's Analytics has the tags per
  night by letter (with CSV).
- **The AI reader fills the tags.** Where the rules did not read the origin, the height or the speed, the AI reader's
  quoted, checked reading fills it, with an "AI" chip in the card (italics on the map). It never places, moves or
  removes a target.
- **The AI reader now knows the deterministic reading** (prompt version 3): each post comes with what the rules read in
  it, the targets already on the map from every channel near the places it may name (with their tags), and the oblast
  the channel speaks for and the oblasts its last posts named. It is asked to cross-check, correct, and above all add
  the targets the rules missed — a duplicate is better than a miss — while every fact still quotes the post and every
  place is one of ours. It can say which target on the map a post is about (`same_as`), and whether it is descending,
  climbing, low or high. Targets only the AI found are on the dashboard for now; putting them on the map is next.
- **Height and descent are always shown when a post gave them**: at every zoom, after the mark goes stale, and on the
  chip of a target reported for a whole oblast ("↓2200"). A descent the AI quoted shows like one the rules read.
- **Two switches on the dashboard's AI reader tab**: the AI reader itself (stops every call at once), and its facts in
  the target tags — the kill switch, effective on every open map within 10 seconds.

### Changed
- **A target reported for a whole oblast is now obvious**: the oblast is outlined in cyan over a light hatching and
  blinks, and its chip says "somewhere in the oblast" with the target's tag, weapon, count and any height stated. It
  was orange, and disappeared into the amber and red of the alerts.
- **A target heading for a town from a stated side no longer sits on the town.** "2 реактиви у бік Києва з півдня" drew
  two jets on top of Kyiv. The glyph now stands off the town on the side the post named — a fixed distance on the
  screen, not on the ground, since nobody said how far it is — pointing in along its dashed course.

## 1.50.2 — 2026-10-09

### Fixed
- **The AI reader still read nothing**: "HTTP 400: Provider returned error" on every post. Its answer format had 15
  fields that could be empty (null) — Anthropic's structured outputs take at most 16 such fields, and could not
  compile it. No field can be null any more ("" / 0 / "none" mean "not stated"). If a provider still refuses the
  format, the reader asks once more without it (the prompt and the examples say the same) and keeps the way that
  works; the dashboard shows which, and a refusal now shows the provider's own reason, not only "Provider returned
  error".
- **A height given on the last line of a post went to every target in it.** @monitor_ukr's five jets, from Kyiv to
  Odesa, with "3.5 км висоти" under the Odesa one: the two coming at Kyiv from the south showed "3500 м". A height
  on a line of its own is now the height of the target on the line above it; the whole post's height is used only
  when the post reports a single target.
- The card of a target drawn at the town it is heading for said "spotted near Kyiv". It now says "Heading for Kyiv —
  where it is now was not given".

### Changed
- The AI reader's prompt (version 2) also reads where a target comes from — a direction, Belarus, Russia, the sea,
  Crimea, the occupied territories, never a Ukrainian oblast — and a stated speed; each must quote the post.

## 1.50.1 — 2026-10-09

### Fixed
- **The AI reader read nothing**: every call came back "HTTP 404: No endpoints found that can handle the requested
  parameters". It asked for `temperature` 0, which claude-haiku-5.5 does not take, and it also asks OpenRouter to use
  only providers that honour every parameter (so that the JSON format is never ignored) — so no provider was left.
  The request now carries only the model, the messages, the length and the JSON schema. A 404 also pauses it 10
  minutes, like a refused key, instead of failing on every post.

## 1.50.0 — 2026-10-09

### Added
- **The AI reader, in shadow mode** (dashboard → *AI reader*). A language model, through OpenRouter, reads the
  channels' posts beside the rules. **Nothing it says reaches the map, the alerts, the feed or a push**: its reading
  and the rules' are stored side by side, and the dashboard shows where they part — a place read differently, another
  weapon, a shoot-down one of them missed, a post only one of them found a target in — with the post, both readings
  and the model's quotes. It is there to find what the rules get wrong, so the rules can be fixed.
- Its prompt holds the safety rules (never infer; quote the post; places only from the server's own gazetteer, by id,
  never coordinates; "на X" is heading to X; Banderol is a jet drone), five worked examples and a strict JSON schema.
  Every fact it gives is checked against the post: an unquoted fact, a place the server did not offer, a number the
  words do not hold are dropped.
- Only public post text is sent (the channel's name, its last posts, our place names) — nothing about any reader, and
  a card number in a post is masked. At most $10 a month (`ai_reader_monthly_usd`), 400 posts an hour; paused when
  OpenRouter refuses the key. Off until the owner sets the key with `scripts/set-openrouter-key.bat`.

## 1.49.4 — 2026-10-09

### Changed
- The key's privileges for Esri's names and map are granted, yet the service answers "401 Token Invalid": after
  asking without the language and worldview, the server now also asks with the key in a header (Esri's other
  documented way) before giving up, and keeps whichever way works.

## 1.49.3 — 2026-10-09

### Changed
- Esri's names-and-map service answered "401 Token Invalid" to a key the imagery takes: it is now asked once more
  without the language and worldview preferences. If that works, they are left out from then on (the names come in
  Esri's default language); if not, the dashboard says the key itself is refused for that service.

## 1.49.2 — 2026-10-09

### Fixed
- **The satellite went blurry again after 1.49**: when Esri refused the key for the new names-and-map service, the
  close-zoom imagery was paused with it. The two are now refused and paused apart, and the dashboard and the log say
  which and why, in Esri's own words.
- **A blank map** in Map mode when Esri's tiles failed: the page now falls back to the OSM streets (and to our own
  names over the imagery) as soon as a view's Esri tiles all fail.
- **The picture vanishing for a moment** (a restart of the server, a refused tile): a tile that fails no longer takes
  the previous picture away; it stays until the new tiles have actually arrived.

## 1.49.1 — 2026-10-09

### Changed
- **The main towns of every oblast are an option** (Layers → "Main towns of every oblast"): on by default on a
  computer, off on a phone, where the names made the map unreadable. On a phone they show only once zoomed in to a
  region, and a town whose name has no room no longer leaves a nameless dot.

## 1.49.0 — 2026-10-09

### Added
- **Background: Satellite, Map or Plain** (Layers). The satellite now has the **roads and names on it** from the
  region view in (Esri's labels for imagery), and **Map** is a street map like any phone's (Esri, dark in the dark
  modes), names in the reader's language and Crimea drawn as Ukraine. Plain is our own map with nothing under it.
  Without the Esri key or past its monthly cap, Map falls back to the OSM streets.
- **The main towns of every oblast**: raion centres and every town of 10,000 people or more (352, from GeoNames), so
  a region zoomed out — Kharkiv, Poltava — shows Chuhuiv, Balakliia, Berestyn, Hadiach, Karlivka… and not four names.

### Changed
- **Zooming keeps up**: a pinch or the wheel now scales the picture already drawn and redraws once it rests — 60
  frames a second on a slow phone instead of 20. The names of places hide during the movement; the marks stay.
- **No more black flashes between zoom levels**: the previous picture stays under the new tiles until they arrive.
- **Kyiv named without a place in it** ("над Києвом", "біля Києва", "on the outskirts of the right bank") is marked
  as the city, like an oblast — not as a drone at the city centre. "Right bank" / "left bank" is said when posted.

### Fixed
- **The page could stop responding zoomed in very close** (1.48): dashed and animated rings and lines were drawn
  dash by dash along their whole length. Zoomed in, they are now drawn solid and still.
- **Drone and threat icons vanished at the closest zooms** (1.48): their size was rounded to zero.

## 1.48.0 — 2026-10-09

### Added
- **Much closer satellite imagery**: past street level (zoom 14–18) the satellite layer shows Esri World Imagery
  (Maxar and others) over the Sentinel picture — buildings, roads, a stadium's stands. Heimdall's server asks Esri
  for the tiles with the owner's key, which never reaches a browser; nothing is kept on the server. The month's
  tiles are counted and capped under Esri's free tier (`esri_monthly_tiles`, a tenth of it a day at most, 3,000 an
  hour per reader); past the cap the Sentinel picture is shown alone. The count is on the dashboard (Satellite
  imagery). Turned on once with `scripts/set-esri-key.bat`.
- **The map zooms in to 1 km across** (8 km before).

### Changed
- **Sentinel-2 at its full 10 m**: the imagery file is rebuilt to zoom 13 (twice as sharp as 1.47's, which stopped
  at 12). The page asks for the tiles under the file's own version and deepest zoom, so a browser never keeps the old
  pictures under the new address, whichever is deployed first — the code or the file.
- **Oblast and raion names are readable over the imagery**: light on a dark halo (dark on a light one in day mode).
- A screen that would need too many tiles at its zoom gets the zoom below instead of no picture.

### Fixed
- **Layer choices are remembered again**: since 1.47.1 the line that saved them had ended up inside a comment.

## 1.47.1 — 2026-10-09

### Changed
- **The satellite imagery stays when you zoom in**: it and the OSM streets are now one choice or the other in Layers
  (it is the default) — zooming in used to fall back to the streets every time.
- **On phones too**: the satellite layer is on by default on every device (its tiles are ~7 KB). A saved choice of
  layers is moved to it once; the streets remain one tap away.

## 1.47.0 — 2026-10-08

### Added
- **Satellite imagery of the whole of Ukraine**, served by Heimdall itself: the ESA WorldCover Sentinel-2 composite
  of 2021 (a year of cloud-free pixels, 10 m, CC BY 4.0), as map tiles from the whole country down to about 25 m a
  pixel. Layers → "Satellite imagery"; on by default on a computer, off on a phone; drawn inside Ukraine only,
  under the streets, darkened by mode. No map provider sees which part of the country a reader looks at, and
  nothing is paid per tile. Built once (`scripts/build_imagery.py`), put on the server's volume with
  `scripts/upload-imagery.bat`; until then the layer is not offered.


### Changed — the server's work (nothing the reader sees)
- **One TLS context for every outgoing request.** Each request (the ~20 channel previews, the alert sources) built a
  new one and loaded ~150 root certificates into it: 87 % of the process's CPU in a profile at the attack-night
  cadence. Measured: 10 % of a core → 1.6 %. Very likely what spent the shared CPU's credit on attack nights before
  1.41.1 — a cheaper machine may be enough again once a night has been watched (docs/TECHNICAL.md §5.5).
- **The live line no longer resends the sources' details to every page at every beat** (~80 % of what it carried):
  the pages get whether each source works; the detail stays on the dashboard.
- The oblasts a post names are read once, not at every rebuild of the marks; the place lists are built once an hour
  and sent gzipped; the Tactical page downloads the small places only when the villages layer is on; SQLite syncs at
  checkpoints instead of at every write.

## 1.45.1 — 2026-10-07

### Changed
- **The street tiles are back to "zoomed in only" on a computer too, and drawn inside Ukraine only.** 1.45 laid them
  under the whole country on a desktop, Romania, Moldova and Belarus included, and zoomed out the map was unreadable.
  Every device now shows them below 150 km width, as before 1.45, clipped to Ukraine's border.
- **"Estimate motion along heading" (EST) is suspended**: the switch is hidden and the estimate is off for everybody.

### Fixed
- **"БпЛА на півночі від Миколаєва" is no longer drawn on Mykolaiv.** A side of a town is not the town: with a
  distance the mark goes that far that way; from an oblast's capital without one, the oblast is marked and the card
  says "north of Mykolaiv"; from another town, the mark stays there with low confidence. The translation reads
  "north of Mykolaiv" (it said "in the north of from Mykolaiv").
- **The "villages and small towns" layer shows its names at an oblast's width**: up to 300 km of map on a computer
  (90 km on a phone), hromada centres and the largest first, a village with no room for its name without its dot.
  They appeared only below 90 km (40 on a phone), so on an oblast's view the layer seemed to do nothing.

## 1.45.0 — 2026-10-07

### Added
- **Seven more regional trackers, on the map**: Kherson (@kherson_monitoring), Kirovohrad (@controlkrop), Khmelnytskyi
  (@radarhmel), Ternopil (@radarofternopil), Rivne (@rivne_radar), Lviv (@ppoualviv) and Volyn (@lutsk_radar), with
  their oblasts' villages (about 19,000 places now) and the Light page's raions for a place there.
- **Raions**: "Шепетівський район", "у Самбірському районі" are read, at the raion's centre town.
- **A tracker following its target into the next oblast** ("Це він на Хмельниччині" … "Далі на Плужне") is read in
  the oblast it just named, for 30 minutes.
- **The map's layers work outside Kyiv oblast**: "villages and small towns" for every oblast on the map (about 1,800
  names, loaded only when the layer is on); rivers, main roads, civil airports and power plants for the whole country;
  the 15 / 30 / 50 km rings around the capital of the reader's oblast.
- **On a computer, the street tiles are under the map at every zoom**, not only zoomed in. Phones are unchanged.

### Fixed
- **No more drones in the middle of an oblast.** "Чернігівщина: … 3 реакти на Славутич з півночі" put three jet drones
  at the centre of Chernihiv oblast. A post that names the town a target is heading for is drawn as an approach to
  that town; a target reported for a whole oblast ("БпЛА на Харківщині") is drawn on the region — an outline and the
  weapon with its count — never as a pin at the oblast centre, never with a distance in the Near list, never as
  "within 15 km of you" in a push.
- "вектор" is a course ("2х вектор Велика Димерка/Бровари"). A multi-line post's lines stay separate reports; "‼️Увага!"
  alone is not one. Raion alert notices ("Тривога — Вараський район"), artillery fire and injury reports are not marks.
- A regional tracker's place 300 km and more from its oblast, in an oblast the post does not name, is dropped as a
  misreading ("Велика Бобровиця" by Rivne was the Бобровиця of Chernihiv oblast). Soviet-era names are no longer shown,
  an exact name wins over a near one, "Кропивницького" is Кропивницький, "маякну" is not a village.

## 1.44.1 — 2026-10-07

### Fixed
- **A destination is no longer drawn as a position.** "Курсом в бік Велика Рибиця/Мала Рибиця/Осоївка" (Sumy) put the
  target ON Мала Рибиця; every name of a list after "в бік / курс" is now a place it may be heading for.
- **"Впали" after guided bombs is an impact**, even when the bombs were named a few posts earlier ("Пуски КАБів в
  нашому напрямку") — never a shoot-down. Guided bombs leave the map on the short clock, not the regional one.
- "Реактивний Шахед вилетів з області", "новий підлітає до нас", "Дорозвідка на Вінниччині" no longer put a target in
  the middle of Vinnytsia oblast.
- Odesa: "В. Михайловка" is Велика Михайлівка, "Буялык" is Великий Буялик (not Петрівка), "в сторону Раздельной" is
  Роздільна.

## 1.44.0 — 2026-10-07

### Added
- **Five more regional trackers, on the map**: Sumy (@kabusumy — guided bombs and drones, village by village; read
  through the Telegram API, its web preview is off), Mykolaiv (@air_alert_mk), Poltava (@PoltavaRadar), Vinnytsia
  (@vinnytsiappo) and Zhytomyr (@zt_radar). Every oblast on the map now has its own tracker, Kyiv's aside.
- **Mykolaiv oblast joins the map**; the Light page finds the raion of a place there.
- **Their villages** (GeoNames), read like those of 1.43's oblasts: only in a post from that oblast's tracker or one
  that names the oblast. "🛵 Полтавщина – реактивний Ромодан" is now at Ромодан, not the middle of the oblast.

### Fixed
- A channel's signature under every post ("💪 Телеграм канал ППО Вінниця", "Вінниця Радар | Підписатись") was read
  as a place — a target on Vinnytsia under each report. The line is cut before the post is read.
- "Впали" after guided bombs is where they hit, never "shot down". "Не фіксується" ends a Poltava target. "Летять
  високо" is not the village of Високе. "З Дніпропетровщини на Світлогірське" from Poltava is Poltava's Світлогірське.
- Two pending corpus cases changed reading (Коломак keyed with its raion, Ромодан placed) — to re-verify.

## 1.43.1 — 2026-10-07

### Fixed
- **The regional trackers' reports were hardly ever drawn.** Odesa, Kharkiv and Chernihiv were read and parsed, then
  lost when the reports were joined into tracks: the Kyiv channels' bare place names — one a minute — were taken as
  the same target as any regional report within 475 km and half an hour ("Перший район Ніжина" became the history of
  a target at Vasylkiv; Odesa's villages, Kyiv's), and a report naming only the oblast ("БпЛА на Харківщині") swallowed
  "Реактивный Шахед на Змиев". Another channel now continues a track only within 15 minutes and at a drone's speed,
  and a report with no town never takes over one with a place.
- **A regional tracker's report stays on the map longer** — 10 minutes before it greys ("location not updated"),
  25 before it goes; the Kyiv channels report every minute, the regional ones every five to twenty. The oblast's
  all-clear still removes it at once.
- **Our own drone is no target**: "Акустика нашего БпЛА над Харьковом" was drawn as a Shahed over Kharkiv; "…то наш!!!"
  posts are no longer kept. "Без фиксации" and "Больше не фиксируется" end the Kharkiv tracker's target.
- Misreadings: "По этому отбой будет" as the village Будеї, "З брянської новий буде" as Нова Буда, "Жовтий рівень" as
  Жовте, "Київська область" as the village Київське; "На Таращу" from Cherkasy is the town of Тараща in Kyiv oblast,
  not a hamlet of that name; the Kharkiv tracker's "Даниловка" is Велика Данилівка.

## 1.43.0 — 2026-10-07

### Added
- **Five regional trackers, one per oblast**: Chernihiv (@chernihiv_nebo), Odesa (@monitoringodesa), Cherkasy
  (@chyste_nebocherkasy), Kharkiv (@radar_kharkov) and Dnipro (@RadarDnepr), on the map. Odesa, Kharkiv and Dnipro
  oblasts join the map: a target reported there is drawn, counted, and pushed to the phones whose places are there.
- **Their villages.** Every village and city district of those five oblasts (GeoNames), read only in a post from that
  oblast's own tracker or one that names the oblast — "Іванівка" alone, from Kyiv, is nothing. A name several
  villages share is the one next to the channel's previous report, or the clear choice (the only raion centre, the only
  city district), or nothing at all — never a guess.
- **Posts in Russian.** The Kharkiv and Odesa trackers write in Russian; their posts are read like Ukrainian ones
  ("Шахед отлетел от Харькова снова на Мерефу", "БпЛА на Лесное - Пятихатки"). The text you see is unchanged.
- **The dashboard, oblast by oblast.** The channels are grouped by the oblast they speak for, each oblast with its own
  switch: off, and it leaves the map — its channels are no longer read and nothing reported there is shown. Kyiv is
  always on. Pick an oblast when you add a channel; move one with its Oblast menu. The other oblasts sit under
  "Other oblasts", one tap to put them on the map.
- Routes written with a dash ("Любеч-Славутич", "Лесное - Пятихатки") and lines with several reports
  ("2 реакти від Куликівки на Лихачів 1 реакт на Добрянку") are read as such; "реакт", FPV, "Молния" are drones.

### Changed
- A regional tracker's ballistic or MiG-31K report raises the warning only for readers in that oblast (the one
  picked, or a watched place's) — the country-wide channels still warn everyone.
- The Light page finds the raion of a place in Odesa, Kharkiv or Dnipro oblast, fetching their outlines only then.
- The Near list keeps to 350 km from your place, and a ballistic mark is "the whole region" only within 150 km — a
  target over Odesa is on the map, not in a Kyiv reader's list.
- One verified corpus case changed reading and is back to pending: "в районі Котельва - Коломак" is now at Kolomak,
  the Kharkiv end of the area, under the post's Харківщина heading (Kolomak was not in the gazetteer before).

### Fixed
- Alerts over Samarivskyi raion (Dnipropetrovsk oblast, renamed from Novomoskovskyi) are painted on its outline.

## 1.42.2 — 2026-10-07

### Fixed
- **The nuclear event could fail to switch on.** The one-time code lived only in the server's memory, so a restart
  between arming and firing (every release, and the server's restarts on busy nights) made it answer "not armed". It
  is now kept in the database too — still valid two minutes, still one attempt. Holding the button no longer stops
  when the pointer drifts off it, the phrase can also be typed in Ukrainian (`ЯДЕРНА ПОДІЯ`), and a refusal shows the
  server's exact reason.

### Added
- **Preview** in the nuclear event's danger zone: the radiation symbol and the banner with your text, on your screen
  only — nothing is sent to anyone. Use it to test; never switch the real one on to try it.

## 1.42.1 — 2026-10-07

### Fixed
- **The map comes first on a phone.** A ballistic warning, the admin's message and a mark's details left the map a
  third of the screen — almost nothing with the details open. The card is tighter, the message keeps to two lines (tap
  to read it all), and a mark's details take the lower half while the card folds to one line: the map stays visible.
- **A ballistic report with no official alert where you are says so.** On 7 October at 01:14 the channels relayed a
  ballistic launch "towards Kyiv" that turned out to be a glitch of the military system; Kyiv was never under alert,
  and the app said "shelter now, do not wait for the siren" for eight minutes. Without an official alert over your
  place it now says "no official alert here yet — be ready, go the moment the siren sounds" and greys out after four
  minutes. With an official alert, the full warning, as before.
- **A channel taking it back ends it.** "Probably a system lag", "the launch was not confirmed": the channels'
  ballistic marks and warnings from before it are removed. Never an official alert.
- **"Heading for Kyiv" is not "at Kyiv".** A missile reported only by where it is going no longer shows "0 km from
  Kyiv · near zone".
- **єРадар's towns are used.** "Jet drone past Piskivka towards Kyiv oblast, Makariv / Nalyvaikivka" now points at
  Makariv, not the oblast's centre; "from Boromlia towards Poltava oblast" stands at Boromlia, not the centre of Sumy
  oblast (Boromlia and Nalyvaikivka added to the places).

## 1.42.0 — 2026-10-07

### Added
- **Replay — the last 7 days.** A new button on the Tactical map (⟲, also in Layers) opens a time bar under the map,
  like a weather-radar loop: choose the last 24 hours or one of the last seven nights, drag the slider or press ▶
  (2, 10 or 30 minutes per second), step ±10 minutes. The official alerts colour the raions as they were at that
  moment; the targets appear where the channels' posts put them, with a short trail of their reported positions. A strip
  above the slider shows when there were reports and when Kyiv was under alert, so the attack is easy to find.
  Nothing is extrapolated and no course is drawn that no post stated; it says "not radar". While it is on, the map
  shows nothing live and nothing personal (no watched place, no pin) — safe on a projector; the band at the top stays
  live. `/m#replay` opens it directly.

### Changed
- **Tactical ⇄ Light flips instead of reloading.** After the first switch, both versions stay in the phone's memory and
  the switch goes back and forth between them at once, as they were left; their live line reconnects as they come back.
- **Daylight and night modes are readable everywhere.** In daylight the sheets (how it works, support, choosing a
  place or an oblast, a mark's details) were dark with dark text, and the buttons inside the menus too; links, the
  statistics and some chips used colours made for a dark screen. Night mode's faintest grey was too faint. Every text
  in every panel, sheet, tab and bar now has enough contrast in all four modes.

### Fixed
- The record of official alerts could not say what was on at a given moment: a region's second alert overwrote its
  first. The replay rebuilds the alerts from the start and end events instead (the dashboard's figures are unchanged).

## 1.41.4 — 2026-10-06

### Fixed
- **`release.bat` no longer stops at the first builder failure.** Fly's builder machine sometimes does not answer
  ("failed to get status … unable to upgrade to h2c, received 500"); the release then tries once more with Fly's other
  builder (Depot) before giving up. GitHub is still pushed only after a deploy succeeded.

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
