# Safety rules the code follows

People may look at this map while deciding whether to go to a shelter. That single fact decides most
of the design. These rules are not style preferences — breaking one is a bug of the worst kind, and
a pull request that breaks one will not be merged.

## The app is never the primary warning

The official *Повітряна тривога* app and the sirens come first, always. Heimdall adds detail to a
warning that has already been given; it never replaces it. The disclaimer is shown on **every**
open, not once. Since 1.36 the rotating ticker is gone and the essentials sit where they apply, without moving:
"unofficial · not radar" at the foot of the card whenever it is open (a tap opens the full notice); "nothing reported
within 30 km — that is not the same as safe, the siren decides" in the card whenever nothing is near; "do not
publish air-defence or impact locations" at the top of the feed, where posts are read and shared.

## No liberties with trajectories

A target is drawn **where a post said it was**. Nothing else.

- A Shahed wanders a figure of eight inside a dashed ring rather than sitting on a point, because its real
  path is erratic and a marker pinned to one spot would imply a precision nobody has. It flies that pattern
  nose-first, banking into its own turns. This is the one glyph on the map that turns, and it does not muddle
  what the map claims: the **reported** course is the chevron, pinned to the heading in the post. A moving
  aircraft reads as movement; a still one pointing somewhere nobody named would read as a bearing, which is
  the thing being avoided.
- Dead reckoning along a heading exists only behind the explicit **EST** switch, off by default,
  labelled as an estimate. A drone that turned after the report would otherwise be drawn somewhere
  it is not. 1.45.1: the switch is suspended — hidden, and the estimate off for everybody — until it is
  reconsidered.
- **No ETA is ever displayed.** "Arrives in 4 minutes" is a number the data cannot support, and
  someone would wait for it.
- The course ray is capped and drawn with an uncertainty cone, never as a line to a destination.

## Stale is never shown as active

Silence is not safety, and it is not danger either — it is silence, and it must look like it.

| Age without a new report | What the map shows |
|---|---|
| < 5 min (`track_stale_minutes`) | Live: coloured, animated, labelled |
| ≥ 5 min | Grey, a `?` above the marker, "not updated for N min", animation stopped |
| ≥ 8 min, ≥ 11 min | Fades further, labels drop away |
| ≥ 15 min (or the oblast's alert ends) | Removed |

A grey marker is a record of the last thing known, not a target's current position, and the sheet
says so in those words.

**A regional tracker's report (1.43.1)** keeps on a longer clock — grey at 10 min, fainter at 15, "contact lost" at
20, removed at 25 (or at once when its oblast's alert ends). The Kyiv channels report a target every minute; the
Chernihiv, Odesa or Kharkiv trackers every five to twenty, and their last report is the last thing anyone said. It is
grey and labelled with its age for most of that time — never shown as a live position.

## A missile is not aged like a drone

The table above is written for a Shahed: about 3 km a minute, so a five-minute-old dot is still worth
something, and going grey is an honest way to say *this is the last thing anyone reported*. Applying the
same rule to a missile would be a lie with a precise pin in it. A Kalibr or a Kh-101 covers roughly 13 km
a minute and turns as it goes; a ballistic covers around 35 and is on its terminal leg before a second
report could exist. Two minutes of silence already puts the marker tens of kilometres from the truth.

So missiles are handled apart:

- **They never get the grey `stale` flag.** There is no age at which "last seen here, not updated" is a
  useful thing to say about something moving that fast.
- **The pin becomes a circle.** For a short window after the report — 2.5 min for cruise, 1.5 for
  ballistic — the position is still worth a point. Past that, the marker keeps the last reported position
  as its origin and grows a ring at the speed of that missile family, labelled *could be anywhere within
  N km · last seen <place> at HH:MM*. The ring is the claim; the point underneath it is only where the
  post put it. The ring is capped at 260 km, because past that it covers half the country and stops
  meaning anything.
- **They are dropped at 12 minutes** (`MISSILE_TTL_MIN`), not 15. By then the last position tells you
  nothing at all, even as an uncertainty circle.
- **No course ray on a ballistic.** A cruise missile flying a reported heading can justify a capped ray
  with a cone; a ballistic one on a lofted trajectory cannot, and the ray is hidden for that type.

Ballistic and cruise are also drawn differently on purpose — a white-hot fast-blinking spike against the
red cruise arrow — because the time you have is different and the marker should say so at a glance,
without being read.

Everything on the screen still comes from a post. Nothing here estimates where a missile *is*; the circle
is an explicit statement of how little the last report now constrains it. It also keeps growing between
server updates — at ballistic speed a circle that only moved when new data arrived would sit perfectly
still exactly when it matters, and a still circle reads as a known position.

### How often the app looks

Refresh rate is a level, not a setting:

| Level | When | Client | Telegram and the alert APIs |
|---|---|---|---|
| 0 | nothing missile-shaped | 15 s | 30 s / 15 s |
| 1 | cruise missiles or a MiG-31K up | 5 s | 10 s |
| 2 | a ballistic threat is open | **1 s** | 5 s |

Both ends move together on purpose. A client polling every second in front of a server that last read its
sources fifteen seconds ago is theatre: the app can only ever be as fresh as the slowest link, and that
link is the source poll. Level 2 is rare and lasts minutes, which is the only reason a one-second cadence
is affordable at all — and the ping counters are batched in memory rather than committed one by one, so
counting usage can never be what stalls the alert path during an attack.

At that cadence the countdown is replaced by **LIVE**, because a number flickering between 1 and 0 reads
as a fault rather than as speed. It turns red the moment a round actually fails, which is the only thing
there worth noticing.

## A new source is on trial until a person trusts it

Channels can be added from the dashboard (1.31). An added channel starts on **trial**: its posts are shown in
the feed, marked as such, and nothing else — no mark on the map, no banner, no sound, no push, no count. Only
the admin, after reading what it posts, puts it on the map. A channel that starts posting rumours can be put
back on trial or switched off in one click, and its posts leave the map at once.

## A village is read only where it is (1.43)

A regional tracker names villages, and a village's name is rarely unique: there are dozens of Іванівка in Ukraine and
six in Odesa oblast alone. So the villages of an oblast are matched only in a post from that oblast's own tracker, or
a sentence that names the oblast — a Kyiv channel's "Іванівка" is nothing. Inside the oblast, a name several villages
share is placed only when something says which: another place the same post names, the channel's own report of the
last half hour nearby, or a clear choice (the only city district, the only raion centre, by far the largest). With
none of those, nothing is drawn — a mark in the wrong village is worse than no mark. A destination nobody can tell
apart gets no course drawn to it. "In the area of A - B" is an area, never a route.

## Two channels' reports are one target only when they could be (1.43.1)

A report continues another channel's track only within 15 minutes and at a speed a drone can fly; a report that
names only the oblast never replaces one that named a place, and a destination is never handed to it. Joining two
targets into one hides one of them — on 7 October the Kyiv channels' place names were taking over every Odesa and
Chernihiv report within 475 km, and those oblasts' targets were not drawn at all. A drone or aircraft the post calls
ours ("нашего БпЛА", "то наш") is not a target.

## A post in Russian says the same thing (1.43)

The Kharkiv and Odesa trackers write in Russian. Their posts are read through the same rules as Ukrainian ones, after
their words are turned into the Ukrainian ones those rules know; nothing is added that the post did not say, and the
text the reader sees is the post as written.

## A regional warning is for that oblast (1.43)

A regional tracker's ballistic or MiG-31K report raises the warning strip only for readers in that oblast — the one
they picked, or one of their watched places. Kharkiv hears ballistic launches from Belgorod every day; Kyiv must not
be told to take cover for each of them by a Kharkiv channel. The country-wide channels and the Air Force still warn
everyone, and the official alerts are unaffected.

## The nuclear event cannot be switched on by accident

The dashboard can cover the map on every page with the radiation symbol (1.32). A false one would be the worst
thing this app could ever show — people leaving shelters, or panicking in a city at night — so it sits behind
three locks: folded away in a danger zone; armed first, which makes the **server** issue a one-time code valid two
minutes with one attempt, right or wrong; then the code and the phrase `NUCLEAR EVENT` (or `ЯДЕРНА ПОДІЯ`) typed in
full and the button held for three seconds. It is never tested on the live service: the dashboard's **Preview** shows
what the readers would see, on that screen only. It is for a nuclear or radiological emergency **confirmed by the authorities or by certain
evidence**, never a rumour in a channel. Its banner says the app is unofficial and sends the reader to ДСНС and
the local authorities; the prefilled advice (go indoors, close up, iodine only on official instruction) is the
authorities' standard advice and is meant to be edited. It pulses once every 1.6 s — a flash rate that can
trigger seizures is three a second — and holds still for anybody whose phone asks for less motion. It covers the
map without blocking it: the live marks underneath still work.

## A warning is only raised when something was actually reported

The preventive banner (MiG-31K airborne, ballistic threat) is the loudest thing in the app, so what
raises it is deliberately narrow:

- **Raises it:** an official alert carrying that threat type; a post that says a launch was recorded
  (`пуск`, `запуск Іскандер/Кинджал`), a fast target (`швидкісна ціль`), ballistics named against a
  city, or a MiG-31K take-off.
- **Never raises it:** a nightly *assessment* — "Загальна оцінка загроз на ніч…", "#обстановка",
  "Запуск може відбутись у будь-який момент", "ймовірні додаткові запуски". These are forecasts.
  They are tagged `forecast`, stripped of their threat tags on the server, and filtered again on the
  client. Tested in `tests/test_tagging.py`. What the enemy is said to *plan* ("ворог планує запустити …") is
  a forecast too (1.41.2).
- **Never raises it, never draws anything:** a live tracker explaining rather than reporting — an example
  ("до прикладу — напрямок Бровари …"), a lesson ("розповім про балістику"), the channel describing its own
  method ("якщо ціль знищена над Києвом …"). On 6 Oct 2026 such an example became a ballistic missile at
  Brovary and the region's "shelter now" push. Tested in `tests/test_talk_about_the_sky.py`.
- The banner **cancels itself** as soon as a later post lifts it (`відбій`, `посадка`, "загроза
  минула") and never outlives 20 minutes without a new report.

The same logic applies to markers: an *announcement* of an alert never becomes a target on the map,
and a missile is only drawn if a place or a heading was actually reported.

## Alert colours must match the official app

If the government app shows an oblast under alert, this map shows the whole oblast under alert. An
oblast-wide alert always paints the oblast; raion-level alerts can only **add** to it (a red raion
inside a yellow oblast), never reduce or replace it. Getting this wrong — showing "clear" where the
state says "alert" — is the single most dangerous bug this app can have.

## Altitude is read, never guessed

No public source publishes target altitude. So the app shows it **only when a post states it in words**, and
shows nothing at all otherwise — never a default, never an estimate, never "level flight".

What the channels do say is read and shown:

| The post says | The map shows |
|---|---|
| `знижується`, `зниження`, `заходить на ціль` | ↓ **DESCENDING** — the marker turns crimson and keeps its label at every zoom |
| `набирає висоту` | climbing |
| `низько`, `на малій висоті` | low |
| `на висоті 2000м` | ~2000 m |

A descending drone is the most dangerous state there is: it is diving at something. Until version 1.1 the word
`зниження` was matched by the *shoot-down* keywords, so a drone in its attack dive was drawn green as "confirmed
shot down". It is now a live target, and a post has to say `збито` / `знищено` before anything is called a
shoot-down. `tests/test_geo.py` pins both halves of that.

## A threat type is never invented

If the post does not say what is flying, the map does not say it either: the marker is an amber warning triangle
labelled *type not stated*, counted apart from drones and missiles. "Васильків увага ‼️" tells you where to worry,
not what to worry about, and a Shahed icon there would be a claim nobody made.

Its sign stands upright and blinks red, and it never turns with the reported heading — a warning sign that is
rotated 200° reads as a decoration, not a warning; the heading is shown by the chevron beside it. It lives five
minutes and then disappears outright, with none of the grey fading a drone track gets: there is no target type
to keep half-remembered.

The channels' shorthand does count as naming it — 🛸 🛵 🏍 🅿 for a strike drone, 🚀 for a missile, 💣 for a KAB —
because that is how those channels write, every night.

## A fire is not an explosion, and it does not last all night

A burning roof reported an hour after a raid is a consequence somebody saw, not a strike. Drawing it as the
red starburst inflates the explosion count and puts a strike marker where no strike was reported. So a post
that says only fire — *пожежа*, *горить*, *загорання* — gets its own small amber flame, drawn quietly, counted
in its own column and never added to explosions. The rule sits **below** the impact rule on purpose: "внаслідок
влучання виникла пожежа" is a strike that started a fire and reads as a strike, and a shoot-down whose debris
is burning stays a shoot-down. The more serious reading always wins.

A fire also **leaves the live map after an hour** (`FIRE_TTL_MIN`). After that it is either out or it has been
burning all night, and neither belongs on a live map as though it had just happened. A new post about the same
place brings it back, because that post carries a fresh timestamp.

## A carrier is never a mark

A Tu-95, a Tu-160, a Tu-22M3 or a MiG-31K is over Russia, Crimea or the sea when the channels report it. Any
Ukrainian place name in such a post is something else — "борти Ту-160 з «Українки»" is an airbase in the Amur
region, and it was drawn as strategic aviation 40 km south of Kyiv. Their posts raise their banners; they place
nothing on the map (1.33).

## A reply is its own message

On the channels' web pages a reply shows the message it answers first. Read carelessly, the Air Force's "all clear
for the MiG-31K" became a second take-off at the very minute the danger was called off. A post is read as what it
says itself, never as what it quotes.

## What was carried is as old as where it came from

A live tracker's next line often says only where the target is going ("На Таращу") or what happened to it ("Вибух").
The app places such a line at the channel's last reported position — and until 1.38 it gave that old position the
new line's time. On 5 October a jet drone destroyed at Vydubychi at 20:25 stood there as a live target, "1 min ago",
until 20:37, carried by lines about another target 100 km south; it lit two bridges. Now a carried position keeps the
time it was reported at and goes grey, then away, on that clock; a line saying the target fell, was lost or that the
sky is clear ends it; and the **official** all-clear for Kyiv city ends everything reported in the city before it.
Telegram still cannot end an alert; the official all-clear can end what Telegram said before it.

## A bridge with nothing reported is not a safe bridge

The bridge alerts (1.34) say what the channels reported on or near each bridge, from the places they named — a
district is a kilometre wide, and a post comes a minute or more after the sighting, in which a jet drone covers 6 km.
So a bridge is "target at the bridge", "target 2.3 km away", "hit reported" — or nothing. Nothing is never written
as "clear" or "safe", the texts say "from channel posts, not radar", and the official alert still comes first. A
post that names only the city, or a bank of the river, is 2–4 km from several bridges at once: it lights none.

"Hit reported" is said only when a post names the bridge and says the bridge was hit (влучання, пошкоджено, приліт).
An explosion near a bridge is not a hit: most explosions over Kyiv are interceptions. On 5 October a bare "Вибух",
placed at the tracker's last position near two bridges, made "hit reported" on both for half an hour; nobody had
reported a hit, and the app does not draw that conclusion for anyone (1.38).

## The card says what is known about your place, and nothing more

The card at the top of the Tactical page (1.36) is the first thing read, so it is held to the strictest rules. Its
colour block is the **official** status of the watched place's own raion — the government app's data, by raion,
the same rule as the Light page — and each place's chip carries only that. The target under it is one the map
already shows, chosen by a fact: a post said it is heading for the place, or it is the nearest reported within
30 km; its distance is between two reported points, never a projection, and no time of arrival is ever written.
When nothing is near it says so, and that this is not the same as safe. The escalation level that colours its edge
and picks the tone (0–4) is computed from those same facts — an official alert, a reported distance, a bridge "at",
a ballistic or MiG-31K warning — never from a guess about where something is going. The one instruction it gives,
under a fresh ballistic or MiG-31K warning ("little time — go to a shelter now, do not wait for the siren"), is the
guide's own rule, taken from the official guidance, with the guide one tap away. The card sits in the header, in the
page's flow: it never covers the map.

The reader may fold it to one line (1.37), because on a quiet night a third of a phone screen spent on "nothing
reported" is a third of the map nobody can read. The folded line still says the place's **official** status, and
the card opens by itself — not on the reader's next tap — when something new matters: the level rises above the one
it was folded at, or a preventive warning or a bridge bar appears; while a fresh warning is on, the line is that
warning. Folding hides detail, never the official status and never a new warning.

## The heat map is statistics, and says so

Where drones were reported (1.34) is a record of the past, under every mark, with "not live, not alerts" in its
legend. Since 1.40 its colour says how many reports a place had — pale yellow for a few, red for the most — because a
heat map people can read at a glance is worth more than one they have to decode. Red and yellow are also the alert
colours, so two rules keep them apart: the heat map is soft discs around places, never a filled raion; and while it
is on, the official alerts are drawn as outlines over a faint fill, and its legend says so. The card above the map
still gives the place's official status in words. It counts the places posts named for drones and unidentified targets — never the
shoot-downs or the hits, which would map where the air defence works. It is off at every opening of the app:
nobody should open the map at 3 a.m. and see last week.

## A ballistic report is not an official alert, and a retraction ends it

On 7 Oct 2026 at 01:14 three channels relayed a ballistic launch "towards Kyiv" that the military's own system had
shown by mistake (a speed of 6000, "probably a system lag"). Kyiv city was never under an official alert; the app said
"shelter now, do not wait for the siren" for eight minutes and drew the missile "0 km from Kyiv". Now: with no official
alert over the reader's place, the warning says exactly that and asks the reader to be ready and to go at the siren,
then turns grey after four minutes; a mark at the town a missile is heading for is "heading for", never a position;
and a channel's retraction ("лаг системи", "не підтвердився пуск") ends the channels' ballistic marks and warnings of
the 20 minutes before it — never an official alert, which only the official data ends.

## The replay is the past, and looks like it

The replay (1.42) puts a past night on the map. It must never be read as the present, nor say more about the past than
the posts did. So: a red "REPLAY" tag, the replayed date and time in large type, and the bar under the map for as long
as it is on; nothing live on the map meanwhile (no live mark, history, heat or bridge) — and the band at the top stays
live, so an alert that starts during a presentation is still seen. The alert colours are the official ones of that
moment. A target stands where a post put it — never moved along a course, never joined into a route across a leap no
drone could fly — and points only where a post stated a course; outcomes are not drawn. The posts are read with
today's rules, so a reading corrected since (a lesson read as a missile, "next: Nyvky" read as a shoot-down) is corrected
in the replay too. Nothing personal is drawn — no watched place, pin or ring — because the replay is made to be shown.

## The guide says what the official guidance says

The what-to-do page (1.35, `/guide`) is the one place where the app tells people how to act, so it carries nothing
of its own invention. Every rule is taken from guidance the ДСНС, the National Police, the Ministry of Health or an
oblast administration published, and those sources are listed on the page; what is not taken from them is said there
too (the bridge advice applies the police's advice for drivers to the bridges; a card with a parent's number in a
child's pocket is common sense). Warning times and speeds are written as typical values, never as a promise —
"2–4 minutes" for a ballistic missile is what it usually is, not what it will be. It never says that a place, a
floor or a bridge is safe — only what is safer, and what to avoid. And it puts the official siren first, in its
opening lines.

When the official guidance changes, the page changes with it, and its "checked" date moves.

## The history layer never buries the live picture

The map carries the last 24 hours and nothing more. Beyond that the dots are denser than the thing somebody
opened the app to see, and a person deciding whether to go to a shelter should not have to read three days of
history to find what is flying now. Longer windows — 24 h, 72 h, 7 days — live in a report behind the counter
chips, grouped by place: "Kyiv ×12, last at 03:41" says what two hundred dots were trying to say. The report
repeats, under its own figures, that they count posts and not events.

1.54, the owner: the layer (the ✸ button, 24 hours of explosions and shoot-downs) "does not help much for now" and is
gone, with its report. The live outcomes stay on the map, on their own short clocks (see "An explosion is a moment, not
a state"). Should a history layer come back, this rule and the next ones are what it has to meet.

## What was destroyed decides what it means

"Склад гуманітарного фонду … знищено" is a warehouse on the ground. Read as a shoot-down it became a green
tick over a strike site — the opposite of what happened — and it padded the interception count with somebody's
ruined building. A destruction word only reads as a shoot-down when the sentence is about something that was
flying (`ціль`, `БпЛА`, `шахед`, `ракета`). Otherwise it is **damage on the ground**: its own muted marker, its
own column, never added to shoot-downs. "Збито 5 БпЛА, уламки пошкодили будинок" is still a shoot-down; debris
damaging a roof, with nothing said about what was intercepted, is damage.

## A press release is not an observation of the sky

"Уряд розширив програму страхування воєнних ризиків … за **пошкодження** або **знищення** якого можна отримати
компенсацію" is a government announcement about insurance. It put a damage marker over Kyiv and — worse —
**closed a live Shahed track with it**, because anything carrying an outcome was allowed to end a flight.

Three rules now:

- **An article produces no outcome of any kind.** Policy vocabulary — уряд, кабмін, законопроєкт, страхування,
  компенсація, відшкодування, бюджет, пільговий кредит, млн/млрд грн — never appears in somebody reporting what
  is overhead, and neither does a post of more than 700 characters. Such a post produces no marker and no
  status, whatever destruction words it contains. The guard covers **every** status: a visit to a new fire
  station drew a fire marker beside Kyiv because the fire rule ran before the news check.
- **A fire needs a fire, not a fire station.** The root `пожеж` is in the name of every fire service, engine
  and brigade in the country, so it cannot by itself mean something is burning. A fire is only drawn when the
  sentence says one happened — *виникла / сталася / спалахнула пожежа*, *пожежа в …*, *горить*, *займання*. A
  post that says **"Пожежі попередньо немає"** draws no fire — and still keeps the damage marker its text
  earns, because rejecting the fire reading falls through to the next rule rather than abandoning the post.
- **Only an outcome that ends a flight may close a track**: shot down, arrived, lost from tracking, area
  declared clear. **Damage and fire never close anything** — they are what a strike left on the ground, and a
  burning roof says nothing about whether the drone above it is still flying. A live target must never vanish
  from the map because of something that happened underneath it.

The second rule matters more than the first. A missed damage marker costs a user some information; a live
target removed from the map by a press release is the failure this whole document exists to prevent.

## A name that merely starts the same is not a match

Stemming strips trailing vowels, so *Коломия* was indexed as `колом` — which quietly swallowed **Коломак**, a
different town 700 km east. Five Shaheds were drawn over Ivano-Frankivshchyna from a post about Kharkiv oblast.
Two guards now stand there:

- When the stem gave up two or more letters, the matched word must still agree with the full name one
  character past the stem. *коломиї* does; *коломак* does not. Alternation spellings (*фастів→фастов*,
  *Київ→києв*) are explicit entries and are trusted as written, so no real declension was lost.
- **An oblast adjective is not the Kyiv place of the same name.** "Житомирська" is a metro station on Kyiv's
  red line *and* how every post names Zhytomyr oblast. Read as the station, a forestry post about Olevsk —
  150 km away — planted a marker 9 km from Kyiv. When an oblast noun follows the word (область, обласна рада,
  ОВА), the word is the oblast and nothing matches.
- **A marker's oblast is the oblast of the place it actually matched**, never the one the sentence mentions.
  The Kolomyia marker carried Kharkiv's oblast id and Ivano-Frankivsk's coordinates at once; that contradiction
  was visible inside the app before it was visible on the map.

## A stated part of an oblast is not the oblast centre

"Реактивні БпЛА **на півночі** … Київщини" was dropped on the oblast centre, which for Kyiv oblast sits near
Vasylkiv — in the south, on the wrong side of the city from the reported drones. When a post names a part of an
oblast, the marker goes there and the card says *north of the oblast* instead of *oblast centre*. The
confidence stays **low**, because a quadrant is still not a position.

Only locative phrasing counts. "У західному напрямку" is a course, not a place, and never moves a marker —
discarding a stated quadrant and inventing one are the same failure in opposite directions.

Some channels write that part where the town would go: "Одещина: ➡️**Південь**/Одеса". With no town to match,
the line landed on the oblast centre — 90 km north of the south the channel had named, and on the same pixel as
every other line of that shape during a raid. Those lines now place in the named part. Only exact compass words
count: **Південне is a town**, not "the south", and a name that merely begins like a direction never moves a
marker.

1.45: a part of an oblast is still not a point. Such a report is now drawn on the region like any report that names
the oblast and no town — its outline, the weapon and the count — and its card says *north of the oblast*. And when
the same sentence names the town it is heading for ("на півночі Чернігівщини ➡️ курсом на Славутич"), it is drawn as
an approach to that town: the one place the post did name. A raion named as where it is ("залітає у Гайсинський
район … курсом на Теплик") is the same: an approach to Теплик, with no course drawn from the raion's centre.

## A side of a town is not the town (1.45.1)

"БпЛА на півночі від Миколаєва" — north of Mykolaiv — was drawn on Mykolaiv itself, "±5 km, high confidence". The
post named the city as a reference and gave no distance. Now: with a distance ("за 20 км на північ від …") the mark
goes that far that way; from an oblast's capital without one, the oblast is marked, as for any report with no town,
and the card says *north of Mykolaiv*; from any other town, the mark stays at the town with **low** confidence and
the card says *north-west of Brovary*.

## Where it is, and where it is going, are different facts

"3х мгКР Бандероль у напрямку Ніжин. **Далі Київщина**" says the missiles are heading for Nizhyn and will carry
on into Kyiv oblast. Reading "Київщина" as their position put a second marker at the centre of Kyiv oblast,
150 km from the only place the post actually named — one flight drawn twice, the second time over a region
nothing had been reported in. An oblast introduced by *далі / потім / згодом / надалі / курсом на* is the route
ahead and never a position.

The reverse also holds: when the post does name the oblast it is heading for, the card says which one. Writing
"neighbouring oblast" threw away the one thing the channel had been precise about.

## A glyph points where the post said, or it does not point at all

The missile glyph was drawn with flared tail fins, and at marker size the eye takes the widest part for the
head: a missile flying south-west read as an arrow pointing north-east. The ballistic glyph was worse — its
spike was at the bottom, so once rotated by the reported course it pointed a clean 180° wrong. Both now carry
their mass at the nose, so `rotate(heading)` means what it says.

A target reported with **no course at all** gets a mark with no front. A pointed glyph left at 0° reads as
"heading north", which is an invented heading — the one thing this app must never publish.

## A heading over a list is not a sighting

The monitoring channels write a region on a line of its own and the sightings under it:

    🛵 Київщина
    - реактивний на Кагарлик
    - 7 бандеролей на зону ЧАЕС повз Остер/Десна

The heading was being drawn as a report of its own, on the oblast centre — for Kyiv oblast that is near
Vasylkiv, 100 km south of the Chornobyl zone the very next line was actually about. Every post of this shape
produced one phantom marker in the middle of the region. A line that is **nothing but an oblast name, with
lines under it**, now sets the context and draws nothing.

It has to be a whole line with something under it: "КАБи на Сумщину **та** Донеччину" is a list of two places,
and its second half is a report in its own right.

## The weapon belongs to the line that names it

The threat type used to be resolved once for the whole post and applied to every line in it, so one word
anywhere coloured everything: in the post above, the jet drone over Kaharlyk was drawn as a Banderol — a
different weapon, at a different speed, with a different uncertainty ring. Each line is typed from its own
words, and only a line that names no weapon inherits the post's.

## A tally of the night is not a sky

The Air Force's summaries are the one tally the app **keeps** (1.32): read weapon by weapon into its statistics
and the dashboard's Analytics, never onto the map. A weapon the summary names without a number is shown as
"used" — never counted as zero, and never given a number the Air Force did not give.

"В ніч на 17.09.26 … противник застосував … 8× балістичних ракет по Києву" counts what was fired **last
night**. It was being drawn as eight ballistic missiles over Kyiv, right now, for the whole time the post
stayed in the feed. A retrospective summary produces no markers at all — same rule as a press release, for the
same reason.

## One weapon, one symbol — and it never turns

A symbol that rotates has to point somewhere, so a target reported without a course forced a choice between
inventing a heading and drawing a second, different icon for the same weapon. The app did both at different
times: a Banderol was an arrow in one place and a diamond in another, on the same map.

Air-defence displays settled this long ago. **The symbol says what it is; the leader line says where it is
going.** Every weapon has one silhouette, drawn at the same fixed angle everywhere on the map — so its nose
cannot be read as a course, because every marker's nose points the same way. The chevron, the ray and the
uncertainty cone carry the whole direction story, and they are simply **absent** when the post gave no course.
Nothing has to be invented, and nothing has to be explained away.

## An outcome with no place named belongs to the region, not to its centre

"Київщина - вибухи" names an oblast and no town. Drawn as a pin it landed on the oblast centre, which for Kyiv
oblast is near Vasylkiv — so a report about a region of three million people read as an explosion in one
village, at high precision, in the wrong place.

These no longer produce a marker at all. The **region itself** is outlined and tinted, and a label inside it
says what was reported and that it was somewhere in the oblast. A label is not a position, and it cannot be
mistaken for one.

1.45: **the same for a target still in the air.** "Чернігівщина: 3 реакти" drew three jet drones in the middle of
Chernihiv oblast, a hundred kilometres from anything the post said, and somebody living near that point took it for
a position. A target reported for a whole oblast is drawn on the region — its outline, the weapon's silhouette and
the count — never as a pin; the Near list gives it no distance and it never raises the level; a push never says
"within 15 km of you" about it. And **a town it is heading for is never the oblast centre**: "3 реакти на Славутич з
півночі" under a Chernihiv heading is an approach to Slavutych, from the north — what the post said, and nothing
more.

## An explosion is a moment, not a state

Outcome markers stayed on the live map for 25 minutes. During a raid that filled the map with bursts that had
already finished, and a burst that is still drawn reads as *still happening there*. Ten minutes, then it
belongs to the history layer — which is where you go to ask what happened, not what is happening. A fire keeps
its hour, because a fire really does last.

## "Heading to your village" is a thing the post has to say

The priority location alert used to mean "the reported course passes within 25° of it". From 80 km away a 25°
cone is 35 km wide, so the app told people a drone was coming to their village when the post had said nothing
of the kind — the single most alarming sentence in the app, produced by arithmetic on a bearing.

It is now said only when the source said it: the target's place, or the destination the post named, is that
town. Everything else gets a **distance in kilometres**, which is a fact, and nothing more.

## A push that cannot be acted on costs the ones that can

Siren-start and all-clear pushes are gone. "Kyiv oblast — alert" says nothing a person can do anything with:
not what, not where, not how far — and the siren itself already said that much, louder. It still wakes
somebody at three in the morning, and after enough of those the notification that *does* matter gets swiped
away with the rest. What is left is what is specific: a MiG-31K or a ballistic launch, and a target actually
near the reader.

## The one row that could say where somebody sleeps

A push subscription paired the address a phone can be reached at with the exact coordinates of the village its
owner had chosen. Nothing in the app needs that: a proximity alert asks whether anything is within N km, and N
is never smaller than 10. The point is snapped to a **~10 km cell** and the name is dropped, existing rows are
rewritten at startup, and the radius test is widened by half a cell so nobody is missed because their village
was rounded.

The push text changed with it. "23 km from you" was precision the stored point no longer has, so the reader
gets the radius they chose and the place *the post* named — both of which are true.

## What the app said is kept, not just what it was told

Markers were recomputed from the feed on every request, and the feed prunes. So "what did the map show at
02:14 last Tuesday" had no answer; neither did "how much warning did this give over the siren", which is the
app's whole reason to exist. Every marker is now written once, as computed, with the evidence that produced
it, and outcomes have a table of their own. The numbers on the statistics tab are measured against that
record — not against anybody's claim, including this app's.

## "High confidence" says how sharply it was read, not that it is true

Confidence used to be one word with no stated meaning. Each reading method has a known sharpness, and the app
now spells it out beside the word: a named town pins a position to **±5 km**, an oblast name pins it to nothing
smaller than **the whole oblast**, a bearing between two named places is good to about **±10°**, a compass word
to about **±30°**.

These are the app's own reading tolerances. They are **not** a probability that the report is true: no channel
publishes such a number, and this app does not invent one.

## Nothing is drawn where the source said it is clear

Posts mix an all-clear and a warning in one breath: "Чисте небо Київська область та Київ. Васильків увага ‼️".
Clear sentences are removed before parsing, so only Vasylkiv gets a marker. A false alarm over a city that was
just declared clear is the fastest way to make people stop trusting the map — and then stop reading it at all.

## Overlapping explosions are grouped, never stacked

At a 300 km view two explosions 3 km apart are the same eleven pixels. Drawing both put two glyphs on top of
each other and two labels in the same space; pushing them onto a ring, the earlier fix, moved each dot off the
place it was actually reported. Both are worse than one dot saying **×8**.

So at draw time anything closer than one glyph-width merges into a single marker carrying the total:

- The group is **anchored and labelled by its most recent member**, never by a centroid. A centroid puts a dot
  on a spot where nobody reported anything, which is exactly the kind of invented precision this map avoids.
- **Explosions and confirmed shoot-downs are never merged into each other.** They mean opposite things, and are
  grouped separately even when they sit on the same street.
- It is purely a function of zoom. Zooming in pulls the group apart into its separate reports, and a tap lists
  every one of them with its own place, time, channel and post — no single report ever stands in for the others.
- The counts in the live tally and the statistics are computed before grouping, so what is on the screen never
  changes a number.

## Every number is traceable

Tap any marker and you see the sentence it came from, the channel, the time, and how position,
heading and count were read, each with a confidence. If a value has no evidence, it is not shown.
"Machine-read — always check the sentence" is on the sheet, because the source can be wrong too.

In the statistics, **launches** (from Air Force summaries) and **reports** (a count of posts) are
never mixed and never added together. A number that counts posts is labelled as counting posts.

That labelling is not cosmetic. "Confirmed shot down: 310" reads as *310 things were shot down*, which the
app has no way to know: it counts the monitoring posts it could parse and tie to a named town. Every
shoot-down that was never posted, posted without a place, or written in a form the parser missed is absent
from it. So these figures are named **explosion reports** and **shoot-down reports**, and the caveat sits
directly under the numbers rather than in a footnote at the bottom of the panel: what the app read, not
official totals, and the real numbers are higher — never lower. A floor presented as a total is a false
precision in the same family as an invented trajectory.

## The AI writes bulletins, and puts nothing on the map (1.54)

The owner (9 Oct 2026): "instead of all that on the map, summaries of the activity of the last hour / the last 24
hours, a bit like a weather bulletin — the AI placing things on the map, we forget it". So since 1.54 nothing the AI
says reaches the map, the tags, the alerts, the feed or a push. It writes **bulletins** (TECHNICAL.md §7.11), and they
are held to this document like everything else on the screen:

- **Written from the server's own record**, never from a post: the official alerts, the targets the rules drew, the
  outcomes, the heights, the Air Force's figures — counts, place names and times. What it is given is stored with what
  it wrote, so every sentence can be checked against its record.
- **"Reported", always.** Channel reports, not radar and not a count of drones; the card says "written by AI from the
  channels' posts and the official alerts — not radar".
- **Never "safe"**, never that the danger is over, never shelter advice, **never a forecast** — a trend the record shows
  ("fewer reports in the last 20 minutes") is a fact and may be said; "they will" is not.
- **Never where targets came from or where they are heading**: the posts' origins were wrong too often to show on the
  map (1.53.2), and a bulletin is no place to bring them back. A followed target's reported places, in order, may be told.
- Alerts are named only from the official data, and only the official data sets a colour — a bulletin starts and ends
  nothing.
- **Behind the dashboard's switch**, off until the owner turns it on; and a bulletin the server can no longer stand by —
  the AI off, out of budget, failing — goes stale and leaves the app rather than describing an hour that has moved on.
- A quiet window is said by the server itself, in fixed words, without asking the model anything.

The sections below describe the AI reading posts for the map (1.50–1.53); none of it runs any more.

## A language model is a second opinion, never a source (1.50)

The AI reader (TECHNICAL.md §7.7) reads the same posts as the rules: what it says is stored for the dashboard and
compared with the rules, and it never places, moves or removes a mark, and never reaches the alerts, a banner or a
push. 1.51, the owner's decision (9 Oct 2026), under a kill switch on the dashboard: the facts it **quoted** that the
rules did not read — where a target comes from, its height, its speed — fill the target tags, marked as the AI's. A model writes fluent, confident answers whether or not the post supports them — exactly the confidently wrong
marker this document exists to prevent. So it is held to the same rules as the parser, and checked rather than
trusted: it may only state what the post states, with the post's own words as the quote for every fact; it may only
name places this server offers it from its own gazetteer, by id, never coordinates; Banderol is a jet drone to it as
to everything else; whatever the server cannot find in the post is dropped before anyone sees it. Its use is to
show where the rules are wrong, so that the rules are fixed. Letting it place anything, ever, is a separate decision
taken on its measured record — never a default, and never for a post the rules already read.

Only public posts are sent to it: a channel's text, its name, our place names. Never a reader, a watched place, an
address or a device.

## A target only the AI reader found (1.52)

(Until 1.54 — no such target is drawn any more.)

The owner's decision (9 Oct 2026): a target missed is worse than a duplicate — a "ghost" ten kilometres from a real
target is better than a target nobody drew because a post was worded loosely. So a target the AI reader found that the
rules did not read is drawn, marked "AI" on the map and in its card (1.53: never pushed "near you" — see below). What
does not change: it is placed only at a place the post itself names, one the server offered from its gazetteer —
loose wording is read, a place is never made up; never at an official alert message's district; never at
coordinates of the model's own. When the rules and the AI read a post's one target more than 30 km apart, both are
drawn ("біля Сомкової Долини" was read by the rules as Dolyna, 500 km off). The dashboard's switch takes every such
target off the map within ten seconds.

## The AI reads every 10 minutes and writes up the night (1.53)

(1.54: the 10-minute check is stopped; the report on each night stays, for the dashboard.)

The owner's decision (9 Oct 2026), on cost: the AI reads the posts of each ten minutes in one call, beside what the
rules drew and what the map shows, and reports only where the rules are wrong or incomplete. The rules stay the reader
of the map: what the AI finds fills the tags (quoted, checked against the post) and a target only it found is drawn,
marked AI — but it can be ten minutes old, so **it is never pushed "near you"**. A namesake is never a second target:
where the post names one place, the rules' choice of it stands. Its notes and its report on each night are the
dashboard's alone — counts and the places the posts named, "reported", never a forecast stated as a fact; they are
there to find patterns and to fix the rules, not to tell anyone what to do.

A tag no longer changes under a target being followed: a track keeps the number it was last shown with, and a second
channel's report of the same target at the same time takes the same number.

## A target's tag is a number, not a designation (1.51)

1.53.2: the tag is the number alone — "#07". Where a target came from is no longer shown anywhere a reader sees: read
from the posts, it was wrong too often (a track takes the first origin any of its reports stated, often another
target's), and a wrong "from the east" over a drone coming from Belarus is worse than nothing. What follows describes
the letter as it is still kept, unseen, for the record.

"S-07 ×2" is Heimdall's own count of the targets the channels reported tonight, and a letter for where a post **said**
it came from — N north or Belarus, E east or Russia, S south, the sea or Crimea, W west, ? not said. The letter is
not worked out from a position, with one exception the owner made (1.52): a target first reported in Chernihiv oblast
is "probably from Belarus", one first reported in Cherkasy oblast "probably from the south or the east" — shown in
lower case (n-07) and said to be a guess in the card; a stated origin always replaces it. "з Чернігівщини" is a place
it passed, not an origin. A target reported for a whole oblast gets no tag at all: a number only when it is sure which
target it is. The bottom line (height, speed) is only
what the target's latest report stated. The format is Heimdall's, not a military one — the card says so — because a
tag that looks like an air-defence designation would be read as coming from air defence. The rules' reading comes
first; until 1.54 the AI's filled what the rules did not read, marked "AI" — since 1.54 a tag is the rules' reading alone.

A target drawn at the town it is heading for ("2 реактиви у бік Києва з півдня") is not at that town. Its glyph stands
off the town on the side the post named, a fixed distance on the screen — not a distance on the ground, which nobody
stated — and its card says where it is now was not given.

## Operational security

The app does not encourage publishing air-defence positions or explosion locations during an
attack — the disclaimer and the top of the feed say so explicitly. The history layer only shows what was
already public, only at the level of a named town, and only after the fact.

## When in doubt

Show less. A missing marker costs a user some information. A confidently wrong marker, a false
all-clear, or an invented trajectory can cost something else.
