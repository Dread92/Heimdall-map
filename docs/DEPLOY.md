# Deploying

## Fly.io (what this repo is set up for)

One `performance-1x` machine (a dedicated CPU, 2 GB) in Amsterdam with a 1 GB volume for the history —
about $34 a month in Amsterdam (Fly's price list, Oct 2026). Until 1.41.1 it was a `shared-cpu-1x` / 256 MB machine
(a few dollars), whose CPU Fly throttles once its burst is spent: the pages timed out on busy nights. The size is
`[[vm]]` in `fly.toml`; `fly deploy` applies it. Fly requires a payment method on the account.

### First time

Windows: double-click **`deploy-fly.bat`** — it installs `flyctl`, logs you in, creates the app and
the volume, asks for the dashboard key (`ADMIN_KEY`) and, optionally, a DeepL key for EN/FR translation,
then deploys.

Manually, anywhere:

```bash
fly auth login
fly apps create my-heimdall --org personal
fly volumes create data --size 1 --region ams --yes -a my-heimdall
fly secrets set ADMIN_KEY=a-long-random-string -a my-heimdall     # protects /admin only; the map stays public
fly secrets set DEEPL_KEY=your-deepl-key -a my-heimdall            # optional: clear EN/FR translation
fly secrets set UKRAINEALARM_KEY=your-key -a my-heimdall           # optional: official API instead of the proxy
fly deploy -a my-heimdall --ha=false
```

Change `app = "…"` in `fly.toml` to your app name.

### The satellite layer (once)

The satellite imagery is a file on the volume, not part of the image. Build it with `python scripts/build_imagery.py
imagery/sat-ua.mbtiles` (needs `pip install rasterio numpy pillow scipy matplotlib`; zoom 13, the full 10 m: ~1.5 h,
reads every cell at full resolution from the public ESA bucket, makes 406 MB — `--maxzoom 12` is ~45 minutes and
~130 MB), then
double-click **`scripts/upload-imagery.bat`**: it shows the volume's free space and uploads the file
(`fly ssh sftp put`). Without the file the map simply does not offer the layer. Every new build takes a new
`--version` (the default is 2): the browsers keep the tiles a year under that version.

The upload goes next to the old file before replacing it, so the volume needs ~0.45 GB free for the zoom-13 file
(`upload-imagery.bat` shows it first; the 1 GB volume has it). If not: `fly volumes list -a kyiv-air-watch-gb`, then
`fly volumes extend <volume id> -s 2 -a kyiv-air-watch-gb` (once; $0.15 per GB a month).

**The closest zooms (1.48, optional)**: Esri World Imagery from zoom 14. Create an account on ArcGIS Location
Platform (location.arcgis.com), an API key with the *Basemaps* privileges (both: basemap styles and static basemap
tiles — 1.49's streets use the second) and **no referrer restriction** (the server
asks Esri, not the browser), then double-click **`scripts/set-esri-key.bat`** and paste it. 2 M tiles a month are
free, then $0.15 per 1,000; the server stops at `esri_monthly_tiles` (1.8 M) and a tenth of it a day. The month's
count is on the dashboard. Without the key the satellite layer is Sentinel alone, enlarged when zoomed in.

**The AI reader (1.50, optional)**: a language model reads the channels' posts beside the rules, in **shadow mode** —
nothing it says reaches the map; the dashboard's *AI reader* tab shows where it and the rules disagree. Create an
account on openrouter.ai, add a few dollars of credit, create an API key with a **credit limit** (10 dollars), then
double-click **`scripts/set-openrouter-key.bat`** and paste it. The server also stops itself at
`ai_reader_monthly_usd` (10 dollars a month, config.json). Only public post text is sent.

### Secrets

| Secret | Needed | What it does |
|---|---|---|
| `ADMIN_KEY` | recommended | Protects `/admin` (usage, flagged readings, corpus review). |
| `DEEPL_KEY` | optional | EN/FR machine translation of the feed. Free plan keys end in `:fx`. |
| `GOOGLE_TRANSLATE_KEY` | optional | Alternative translator (Google Cloud Translation). |
| `UKRAINEALARM_KEY` | optional | Reads api.ukrainealarm.com directly instead of the keyless siren.pp.ua proxy. |
| `ALERTS_IN_UA_TOKEN` | optional | Makes alerts.in.ua the primary alert source. |
| `ESRI_KEY` | optional | The satellite layer's closest zooms (Esri World Imagery). Set with `scripts/set-esri-key.bat`. |
| `OPENROUTER_API_KEY` | optional | The AI reader in shadow mode (dashboard only, never the map). Set with `scripts/set-openrouter-key.bat`. |
| `TG_API_ID`, `TG_API_HASH`, `TG_SESSION` | optional | Read chyste_nebo through the Telegram API. Set by `scripts\telegram-login.bat`, never by hand. |
| `ACCESS_KEY` | **never on the public app** | Locks the whole map behind a key. |

Without any of the optional ones the app is complete: official alerts by raion come from the keyless proxy,
and English uses the offline glossary. The full list of settings is in
[TECHNICAL.md §5](TECHNICAL.md#5-runtime-configuration-and-secrets).

### Updating

Windows: double-click **`scripts\release.bat`** — it checks everything is committed, deploys, pushes to
GitHub and shows the live version. Anywhere else:

```bash
fly deploy && git push
```

**If a deploy does not seem to change anything**, check the build tag at the bottom of the More panel (⋯) in
the app (`build YYYY-MM-DD HH:MM UTC`) against the one in `static/kyiv.html`. If they differ, the
files on the machine you deployed from were not the ones you edited — `git status` and `git log -1`
tell you which version you actually shipped. This is much more often the cause than a Fly caching
problem.

Useful:

```bash
fly logs -a kyiv-air-watch-gb                              # live logs
fly status -a kyiv-air-watch-gb                            # machine state
fly ssh console -a kyiv-air-watch-gb                       # shell inside the machine
fly ssh console -a kyiv-air-watch-gb -C "ls -la /data"     # the database on the volume
```

### Its own address (domain)

Fly cannot rename an app, and a new `*.fly.dev` name would be one more move for everybody who installed the
app. Give it a real domain instead (for example `heimdall.com.ua`, open to anyone, ~700 UAH a year):

> **Done, 18 October 2026 (1.58.34): `heimdall.com.ua`**, registered at NIC.UA, on NIC.UA's name servers, with
> `A` and `AAAA` records for `@` and `www` to the app's Fly addresses (`fly ips list`); Fly's certificate was
> issued within the hour and `CANONICAL_HOST` is set. Two renewals to keep in mind at NIC.UA: the free name-server
> service (first due mid-January 2027 — "Extend nameservers"; without it the DNS zone, and the site, stop) and the
> domain itself (October 2027; auto-renew is off). `www` uses `A` + `AAAA` rather than the `CNAME` below: Fly
> recommends either, and NIC.UA's editor cannot change a record's type in place.

1. Buy the domain at any registrar.
2. Double-click `scripts\set-domain.bat`. It adds the free HTTPS certificates on Fly (`fly certs add`), shows
   the DNS records to create at the registrar (A and AAAA for the domain, CNAME for `www`), and checks the
   certificate.
3. When the certificate is issued, the script offers to set `CANONICAL_HOST`: pages still opened on
   `kyiv-air-watch-gb.fly.dev` then show "Heimdall has moved to …" with a button to the new address. The old
   address keeps working; the reader's settings follow in the link (never the watched places — they are set
   again there). An installed app has to be added to the home screen again from the new address: a browser
   ties an installed app to its address, nothing can move it.

### Access key

With `ACCESS_KEY` set, every page shows a sign-in form until the key is typed once on that phone
(1.58.35: `POST /access/login`, a session cookie for 180 days — the key never goes in the address, and
`?key=` is refused). Scripts send it in an `X-Access-Key` header. Without it the deployment is public.
`ADMIN_KEY` is a different key, for the dashboard only (§the two keys of the README).

## GitHub Actions (optional automatic deploy)

`.github/workflows/fly-deploy.yml` deploys on every push to `main` **if** the repository secret
`FLY_API_TOKEN` exists. Create one with:

```bash
fly tokens create deploy -a kyiv-air-watch-gb
```

then add it under *Settings → Secrets and variables → Actions → New repository secret*. Without the
secret the job is skipped, so the workflow is harmless until you want it.

## Render.com

`render.yaml` is a Blueprint: *New → Blueprint → point at this repo*. The free instance sleeps after
15 minutes idle, which is not what you want for an alert app — use a paid instance, or ping
`/healthz` on a schedule.

## Docker anywhere

```bash
docker build -t heimdall .
docker run -d --name heimdall -p 8080:8080 \
  -v heimdall-data:/data \
  -e ACCESS_KEY=a-long-random-string \
  -e ALERTS_IN_UA_TOKEN=your-token \
  heimdall
```

The image contains `app/` and `static/` only; the database lives on the volume at `/data`.

## On your own PC

`start.bat` (Windows) or `scripts/start.sh`. To reach it from your phone on the same Wi-Fi, use the
LAN address the service prints at startup. To reach it from outside without opening a port,
`scripts/tunnel.bat` runs a Cloudflare quick tunnel.

Running at home means the app stops when the PC sleeps — which is exactly when you need it. Fly is
the better home for it; keep the local copy for development.

## Web Push

Push needs `cryptography` (installed by `start.bat`, in `requirements.txt`, and in the Docker image)
and HTTPS — so it works on a Fly deployment, not on plain `http://localhost` except in Chrome, which
treats localhost as secure.

VAPID keys are generated on first use and stored in the `kv` table, so they survive restarts as long
as the volume does. Losing them means every device has to subscribe again.

On iPhone the page must be added to the home screen before notifications can be granted.
