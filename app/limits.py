"""1.58.17 — limits on abuse of the public API.

The audit of map.war-monitor.org (14 October): "today anyone can scrape or hammer it during a mass alert". The owner
picked "limit the abuse" over signed tokens or Cloudflare Turnstile — because in Ukraine a mobile operator puts
thousands of phones behind one address (carrier-grade NAT), and a strict limit by address would turn real readers away
in the middle of a mass attack.

So what is limited is what COSTS the server, never what a reader needs:
- `build` — an answer the server must compute because no copy of it is fresh: a replay window, statistics, a history,
  a tag's trail, the events log. Every reader asking the usual questions shares one cached copy; a reader whose
  allowance is spent is still given the last copy there is (stale by a few seconds or minutes) — only an answer that
  was never built, with parameters nobody else asks for, is refused (429 with Retry-After);
- `write` — a reading flagged as wrong;
- `push` — subscribing to notifications, generously (a whole carrier's NAT subscribing in a raid stays under it);
- `stream` — open live lines from one address, at most STREAMS at a time.
Never limited: the official alert status (/api/state), the marks (/api/markers), the feed, the pages, the version.

A client is a salted hash of its address (Fly-Client-IP, set by Fly's proxy; not X-Forwarded-For, which a client
writes itself), kept in memory only, never stored or logged; the salt changes every day. The dashboard and this
machine itself (no proxy header, a loopback address) are not limited.
"""
import hashlib
import ipaddress
import os
import threading
import time

# kind: (burst, refill per second)
RULES = {"build": (60, 1.0), "write": (20, 1 / 30), "push": (300, 5.0),
         "login": (5, 1 / 120)}     # 1.58.21: the dashboard's key — 5 tries, then one every two minutes
STREAMS = 200          # open live lines from one client
MAX_CLIENTS = 50_000   # buckets kept; full ones are forgotten first


class Limits:
    def __init__(self, rules=None, clock=time.monotonic):
        self.rules = dict(rules or RULES)
        self.clock = clock
        self.lock = threading.Lock()
        self.b = {}
        self.refused = {k: 0 for k in self.rules}
        self.refused["stream"] = 0
        self._salt, self._day = os.urandom(16), None

    def who(self, ip):
        """A salted, daily hash of an address — the only form it is held in."""
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if day != self._day:
            self._salt, self._day = os.urandom(16), day
        return hashlib.sha256(self._salt + (ip or "").encode("utf-8")).hexdigest()[:16]

    def take(self, who, kind):
        """0 when allowed (and counted), else the seconds until one is allowed again."""
        burst, rate = self.rules[kind]
        now = self.clock()
        with self.lock:
            tok, t = self.b.get((who, kind), (burst, now))
            tok = min(burst, tok + (now - t) * rate)
            if tok >= 1:
                self.b[(who, kind)] = (tok - 1, now)
                if len(self.b) > MAX_CLIENTS:
                    self._prune(now)
                return 0
            self.b[(who, kind)] = (tok, now)
            self.refused[kind] += 1
            return max(1, int((1 - tok) / rate + 0.999))

    def _prune(self, now):
        for k, (tok, t) in list(self.b.items()):
            burst, rate = self.rules[k[1]]
            if tok + (now - t) * rate >= burst:
                del self.b[k]

    def report(self):
        """For the dashboard: how many requests were refused, by kind, since the start — nothing about who."""
        with self.lock:
            return dict(self.refused)


def client_ip(headers, peer):
    """The reader's address for the limits: on Fly, Fly's own header; elsewhere the connection's. None — never
    limited — for this machine and for a proxy in front of it.

    1.58.24: the header is believed on Fly alone, where Fly's proxy writes it. Anywhere else a client writes it
    himself (a new value, a new allowance), and behind another host's proxy (Render, a reverse proxy before Docker)
    the connection comes from a private address: every reader at once, limited as one — never limit that."""
    if os.environ.get("FLY_APP_NAME"):
        return (headers.get("Fly-Client-IP") or "").strip() or None    # without it the peer is Fly's proxy
    if not peer:
        return None
    try:
        a = ipaddress.ip_address(peer.split("%")[0])
    except ValueError:
        return None
    if a.is_loopback or a.is_private or a.is_link_local:
        return None
    return peer
