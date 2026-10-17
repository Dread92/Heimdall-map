#!/bin/sh
# 1.58.35 (the audit): start the service as the `heimdall` user, not root. The volume (/data) is mounted root-owned by
# Fly, so it is handed to that user first. If anything of this is missing (another base image, no setpriv), the service
# still starts — as before, as root — rather than not at all: a map that is down is worse than a map that runs as root.
set -e
if [ "$(id -u)" = "0" ] && id heimdall >/dev/null 2>&1; then
  chown -R heimdall:heimdall /data 2>/dev/null || true
  if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid=heimdall --regid=heimdall --init-groups python app/server.py
  fi
fi
exec python app/server.py
