# Heimdall — single-process Python service, no build step, no framework.
FROM python:3.12-slim

WORKDIR /srv

# Optional dependencies (requirements.txt): cryptography for Web Push, telethon, tzdata, Pillow for the private channel's
# map picture (1.58) — with DejaVu, a font that has Cyrillic, for its names.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
# The regression corpus: the server serves it to the review panel on /admin, so it has to be in the image.
COPY data ./data

# The database lives on the mounted volume, never in the image.
ENV PORT=8080 \
    DB_PATH=/data/alerts.sqlite \
    PYTHONUNBUFFERED=1
# 1.58.35 (the audit): the service runs as its own user, not root. The volume is mounted root-owned, so the entry
# script hands /data to that user first, then drops privileges (docker-entry.sh, at the root: .dockerignore leaves scripts/ out).
RUN mkdir -p /data && useradd --system --uid 10001 --user-group --shell /usr/sbin/nologin heimdall
COPY docker-entry.sh ./docker-entry.sh
RUN chmod 0755 ./docker-entry.sh

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/api/version',timeout=4)"

CMD ["./docker-entry.sh"]
