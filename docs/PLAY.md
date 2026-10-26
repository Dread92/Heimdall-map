# Heimdall on Google Play — the listing, the data-safety form, the beta

1.58.59. What to paste into the Play Console (the Heimdall Google account), and how the native app (Expo, project
`dread92s-team/heimdall`) gets from a build to beta testers. Checked against Google's and Expo's pages on 26 October
2026 (the sources are at the bottom); the Console's wording changes — the facts below are what to look for.

## 0. Before anything

- **Play Console account** on the Heimdall Google account (25 USD once, identity check). A **personal** account created
  after 13 November 2023 must run a **closed test with at least 12 testers, opted in for 14 days in a row**, before it
  may publish to production (§5). Internal testing has no such rule.
- **Package name**: `com.blackflamestudio.heimdall` — the one the server already names in
  `/.well-known/assetlinks.json` (§12, `ANDROID_PACKAGE_DEFAULT`). It can never change once a build is uploaded. If the
  app opens heimdall.com.ua links, add the **app signing key's** SHA-256 (Play Console → Test and release → App
  integrity) to the Fly secret `ANDROID_CERT_SHA256` with `scripts\set-android-key.bat` — the server takes several,
  comma-separated.
- **No donation buttons in the Play build.** Google Play's Payments policy: payments for an app go through Google
  Play's billing, except *tax-exempt donations*, and Google accepts those only for an organisation it can verify as
  tax-exempt (a 501(c)(3) "or the local equivalent"). Heimdall's own fundraiser is not one; the NGO's PUMB page is a
  person's account. So the app on Play has no support sheet, no jar, no link to a payment page — not even through the
  website. The website keeps them.
- **Target API**: from 31 August 2026 a new app and its updates must target **Android 16 (API 36)** — take an Expo SDK
  that targets it (an extension to 1 November 2026 can be asked in the Console).
- **Privacy policy URL**: `https://heimdall.com.ua/privacy` (static/privacy.html, live once 1.58.59 is released).

## 1. Store listing

**App name** (30 max) · **Short description** (80 max) · **Full description** (4,000 max). Ukrainian is the default
language; English as a translation (Play shows it to English-speaking phones).

The texts describe the app as the website is today: trim what the native app does not do yet.

### Українська (uk-UA, за замовчуванням)

Назва: `Heimdall — мапа загроз`

Короткий опис: `Неофіційна мапа повітряних загроз з дописів каналів. Не радар. Сирена — першою.`

Повний опис:

```
Heimdall — неофіційна волонтерська мапа повітряних загроз Києва та України.

Застосунок збирає відкриті дані — офіційні тривоги «Повітряна тривога» та дописи публічних моніторингових каналів — і показує на мапі, де повідомили про шахеди, реактивні дрони, ракети та КАБи, куди вони, за дописами, рухаються, і що з ними стало.

⚠️ Це НЕ дані радара. Позначки — з повідомлень, вони можуть бути неточними або запізнюватися. Завжди орієнтуйтеся на сирени та офіційний застосунок «Повітряна тривога». Почули тривогу — одразу в укриття.

Що вміє Heimdall:
• Офіційна тривога для вашого району, кольором як в офіційному застосунку.
• До чотирьох міток (дім, робота, діти…) — кожна зі своєю близькою зоною: 10, 15 або 20 км.
• Список «Поруч»: цілі від найближчої, з відстанню до вашої мітки.
• Сигнал наближення: короткий звук, частіший, коли за дописами ціль ближче до мітки.
• Окремі сигнали для балістики та МіГ-31К.
• Мости Києва: попередження, коли ціль біля мосту.
• Найближчі укриття Києва.
• «Що робити»: пам'ятка за офіційними рекомендаціями, працює без інтернету.
• Heimdall Light — лише ваше місце, для слабкого зв'язку.
• Три мови: українська, англійська, французька.

Приватність: без облікового запису, без реклами, без трекерів. Ваші мітки ніколи не залишають телефон.

Не поширюйте кадри роботи ППО та місця влучань під час атаки.

Зроблено Black Flame Studio та ГО «07300 — Люди для людей».
```

### English (en-US)

Name: `Heimdall — air threat map`

Short description: `Unofficial map of air threats, from monitoring channels' posts. Not radar.`

Full description:

```
Heimdall is an unofficial, volunteer-run map of air threats over Kyiv and Ukraine.

It gathers open data — the official “Povitryana Tryvoha” air-raid alerts and the posts of public monitoring channels — and shows on a map where Shahed drones, jet drones, missiles and guided bombs were reported, where the posts say they are heading, and what became of them.

⚠️ This is NOT radar data. The marks come from posts; they can be inaccurate or late. Always follow the sirens and the official air-raid alert app. When the alert sounds, go to a shelter.

What Heimdall does:
• The official alert for your own district, in the official app's colours.
• Up to four pins (home, work, school…), each with its own near zone: 10, 15 or 20 km.
• The Near list: targets nearest first, with the distance to your pin.
• An approach signal: a short beep, more often as the posts place a target closer to your pin.
• Distinct alerts for ballistic missiles and MiG-31K take-offs.
• Kyiv bridges: a warning when a target is near a bridge.
• The nearest shelters in Kyiv.
• “What to do”: a guide from the official recommendations, available offline.
• Heimdall Light — only your place, for weak connections.
• Three languages: Ukrainian, English, French.

Privacy: no account, no ads, no trackers. Your pins never leave your phone.

Do not share footage of air defence at work or the locations of impacts during an attack.

Made by Black Flame Studio and the NGO “07300 — People for People”.
```

### Graphics, category, contact

- **Icon** 512×512: `static/heimdall-512.png`. **Feature graphic** 1024×500 and **2–8 phone screenshots**: to make
  from the app (the map with marks, the Near list, a pin's zone, the guide).
- **Category**: Maps & Navigation (or News & Magazines — the owner's call). **Tags**: maps, safety.
- **Contact email**: the app's own contact today is `nomakievip@gmail.com` (`CONTACT.hosting`); put the Heimdall
  account's address there if it should be another one. Website: `https://heimdall.com.ua`.

## 2. App content (Policy → App content)

- **Privacy policy**: `https://heimdall.com.ua/privacy`.
- **App access**: everything works without signing in.
- **Ads**: no.
- **Content rating** (IARC questionnaire): no violence shown (map symbols, no images of harm), no user-to-user
  communication (feedback goes to the team only), no sharing of the user's location with other users, no purchases,
  no gambling. Answer as the app is.
- **Target audience**: 13 and over (not designed for children; choosing an under-13 group brings the Families policy).
- **Government apps**: not affiliated with a government — and the listing says "unofficial".
- **News app**: the owner's call. Heimdall is a safety map whose feed quotes public channels; declaring it a news app
  brings that policy's requirements (publisher, contact, sources) — which the listing and the privacy page already give.
- **Financial features, health**: none.

## 3. Data safety form

The answers for **the app as the website works today** (the same server, docs/TECHNICAL.md §11, static/privacy.html).
**Check them again once the native code exists**: a push token through Expo's or Firebase's push service, a crash
reporter or an update service each change an answer.

| Question | Answer |
|---|---|
| Does the app collect or share user data? | Yes — collects; shares none (push services, Telegram and the host act for us) |
| Encrypted in transit? | Yes (HTTPS only) |
| Can users ask for deletion? | Yes — in the app (push off, pins on the phone), the bot's /stop, or by email |
| **Location → Approximate location** | Collected, **optional** ("Warn me near my location" only: a ~10 km grid square), not shared, for **App functionality** |
| Location → Precise location | Not collected (the pins and GPS stay on the phone) |
| **Device or other IDs** | Collected, **optional** (the push address, only when notifications are on), for **App functionality** |
| **App activity → Other user-generated content** | Collected, **optional** (feedback text, a misreading report), for **App functionality** and **Developer communications** |
| **Personal info → Email address / other** | Collected, **optional** (a contact the user may add to a feedback message), for **Developer communications** |
| **App info and performance → Diagnostics** | Collected, **optional** (with a feedback message: the system, the screen size, the app's version) |
| **App activity → App interactions** | Collected (the daily usage count: a hash renewed every day, totals kept), for **Analytics**, not linked to the user |
| Everything else (name, contacts, photos, files, messages, health, finance, web history) | Not collected |
| Is the data processed ephemerally? | No for the rows above (kept as the privacy page says) |
| Is data collection required? | No — every item above is optional except the daily count |

## 4. Build and send (Expo, EAS)

`app.json` (or `app.config.js`), the Android part — the rest is the app's:

```json
{
  "expo": {
    "name": "Heimdall",
    "slug": "heimdall",
    "owner": "dread92s-team",
    "android": {
      "package": "com.blackflamestudio.heimdall",
      "permissions": ["POST_NOTIFICATIONS"]
    }
  }
}
```

Ask for a permission only when the app uses it (for "Where I am now": `ACCESS_COARSE_LOCATION`, asked at the tap,
never at start) — every permission is a line in the data-safety form and a question in review.

`eas.json` at the root of the Expo project:

```json
{
  "cli": { "version": ">= 16.0.0", "appVersionSource": "remote" },
  "build": {
    "preview": { "distribution": "internal", "android": { "buildType": "apk" } },
    "production": { "autoIncrement": true }
  },
  "submit": {
    "internal": { "android": { "serviceAccountKeyPath": "./play-service-account.json", "track": "internal", "releaseStatus": "draft" } },
    "beta": { "android": { "serviceAccountKeyPath": "./play-service-account.json", "track": "alpha", "releaseStatus": "draft" } },
    "production": { "android": { "serviceAccountKeyPath": "./play-service-account.json", "track": "production", "releaseStatus": "draft" } }
  }
}
```

- `preview`: an APK to install on your own phone. `production`: the `.aab` Google Play takes, its version code raised
  by EAS at every build (`appVersionSource: remote` + `autoIncrement`).
- `track`: `internal` (internal testing), `alpha` (closed testing), `production`. `releaseStatus: draft` uploads
  without rolling out — until a new app's first release is rolled out, Google accepts only drafts; you press "Roll
  out" in the Console. After that, `completed` can roll out by itself.
- `play-service-account.json` is a key to the Play account: never in git (add it to `.gitignore`), never in a chat.
  Created by you: Google Cloud (the Heimdall account) → a project → enable the Google Play Android Developer API →
  IAM → Service accounts → create one → Keys → JSON; then Play Console → Users and permissions → invite the service
  account's address, with the right to release to testing tracks (production later). Expo's guide:
  https://expo.fyi/creating-google-service-account
- Signing: let EAS make and keep the upload key, and **Play App Signing** keep the app's key (Google's, recommended).

Commands, from the Expo project:

```
eas build -p android --profile production
eas submit -p android --profile internal      (later: --profile beta, then --profile production)
```

The very first `.aab` can also go in by hand: Console → Test and release → Testing → Internal testing → Create new
release → drop the file.

## 5. From beta to the store

1. **Internal testing** — up to 100 testers, no review wait: Testing → Internal testing → Testers → an email list (their
   Google accounts) → copy the **join link** and send it. They install from the Play Store.
2. **Closed testing** (`alpha`) — the one that counts for production: a closed track, at least **12 testers opted in
   for 14 days in a row** (aim for 15–20; leaving and rejoining restarts their 14 days), through the Play Store link,
   not a sideloaded APK. Ship at least one update during the 14 days and read their feedback.
3. **Apply for production** — Dashboard → "Apply for production" (three parts: the closed test, the app, its
   readiness). Google usually answers within 7 days.
4. **Production** (or open testing first).

## Sources

- Google Play — testing requirements for new personal developer accounts:
  https://support.google.com/googleplay/android-developer/answer/14151465
- Google Play — Payments policy (tax-exempt donations): https://support.google.com/googleplay/android-developer/answer/9858738
- Android — Google Play's target API level: https://developer.android.com/google/play/requirements/target-sdk
- Expo — first Android submission: https://docs.expo.dev/submit/android-manual/
- Expo — EAS Submit for Android: https://docs.expo.dev/eas/submit/android/
- A case of the donation rule applied (AnkiDroid, 2026): https://github.com/ankidroid/Anki-Android/issues/21656
