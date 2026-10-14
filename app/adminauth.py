"""1.58.21 — the dashboard's login. The owner: "we strongly need to secure our dashboard — right now it's very minimal
protection" (picked: "key only, done properly", no second code).

Until 1.58.20 the key was typed into the address (/admin?key=…) — so it sat in the browser's history, in anything that
logged the address — and was then kept for a year in an ordinary cookie (`uadm=<the key itself>`), readable by any script
of the site's pages and sent with every request to the public map. Now:

- the key is typed in a login form and sent once, in a POST body; it is never in an address and never in a cookie;
- a correct key opens a **session**: a random token in a cookie scripts cannot read (HttpOnly), sent to this site only
  (SameSite=Strict), over HTTPS only (Secure), for 12 hours at the most; only the token's SHA-256 is stored;
- wrong keys are limited per client (5 tries, then one every two minutes) and each costs a second;
- the comparison takes the same time whatever the key (hmac.compare_digest);
- logins, failures, log-outs and every dashboard action are kept in a short log the dashboard shows, with the browser
  and a network tag (a keyed hash of the address: the same network shows the same tag, the address is never stored);
- a session can be ended from the dashboard, one or all; 1.58.22: and a new key ends every session opened with the old
  one (each session keeps a fingerprint of the key it was opened with — never the key).

Scripts and tests may send the key in an `X-Admin-Key` header instead (never in the address).
"""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

TTL_S = 12 * 3600          # a session lasts 12 hours at the most
MAX_SESSIONS = 20
MAX_EVENTS = 200
COOKIE = "hsess"


def ua_short(ua):
    """'Mozilla/5.0 (Windows NT 10.0; …) … Chrome/130 …' → 'Chrome · Windows' (for the log: which device, not who)."""
    ua = ua or ""
    br = next((n for p, n in ((r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"), (r"Firefox/", "Firefox"), (r"Chrome/", "Chrome"),
                              (r"Safari/", "Safari"), (r"curl/", "curl"), (r"python", "Python")) if re.search(p, ua)), "other")
    os_ = next((n for p, n in ((r"Android", "Android"), (r"iPhone|iPad", "iOS"), (r"Windows", "Windows"), (r"Mac OS X", "macOS"),
                               (r"Linux", "Linux")) if re.search(p, ua)), "")
    return br + (" · " + os_ if os_ else "")


def net_tag(key, ip):
    """A keyed hash of the address: the same network shows the same 8 characters; the address itself is never kept."""
    if not ip:
        return "local"
    return hmac.new((key or "-").encode(), ip.encode(), hashlib.sha256).hexdigest()[:8]


def key_print(key):
    """A short fingerprint of the key a session was opened with: a new key ends the old sessions."""
    return hashlib.sha256(("heimdall-admin:" + (key or "")).encode()).hexdigest()[:16]


def same_key(given, key):
    """Constant-time comparison: a wrong key takes as long as any other."""
    return bool(key) and hmac.compare_digest((given or "").encode("utf-8"), key.encode("utf-8"))


class AdminSessions:
    def __init__(self, store=None, clock=time.time):
        self.store, self.clock = store, clock
        self.lock = threading.Lock()
        self.s = {}            # sha256(token) → {at, seen, ua, net}
        self.events = []
        self._saved = 0
        if store is not None:
            try:
                self.s = json.loads(store.kv_get("admin_sessions") or "{}") or {}
                self.events = json.loads(store.kv_get("admin_events") or "[]") or []
            except (ValueError, TypeError):
                self.s, self.events = {}, []
        self._expire()

    @staticmethod
    def _h(token):
        return hashlib.sha256((token or "").encode()).hexdigest()

    def _expire(self):
        now = self.clock()
        for k in [k for k, v in self.s.items() if now - v.get("at", 0) > TTL_S]:
            del self.s[k]

    def _save(self):
        if self.store is None:
            return
        try:
            self.store.kv_set("admin_sessions", json.dumps(self.s))
            self.store.kv_set("admin_events", json.dumps(self.events[-MAX_EVENTS:]))
        except Exception:
            pass

    def create(self, ua, net, kp=""):
        token = secrets.token_urlsafe(32)
        with self.lock:
            self._expire()
            while len(self.s) >= MAX_SESSIONS:             # the oldest goes
                del self.s[min(self.s, key=lambda k: self.s[k]["at"])]
            now = self.clock()
            self.s[self._h(token)] = {"at": now, "seen": now, "ua": ua, "net": net, "kp": kp}
            self._save()
        return token

    def check(self, token, kp=None):
        if not token:
            return False
        h = self._h(token)
        with self.lock:
            v = self.s.get(h)
            if not v:
                return False
            now = self.clock()
            if now - v["at"] > TTL_S or (kp is not None and v.get("kp", "") != kp):   # too old, or opened with another key
                del self.s[h]
                self._save()
                return False
            v["seen"] = now
            if now - self._saved > 300:                     # "last seen" is kept, at most every 5 minutes
                self._saved = now
                self._save()
            return True

    def drop(self, token=None, everyone=False, sid=None):
        with self.lock:
            if everyone:
                self.s = {}
            elif sid:
                for k in [k for k in self.s if k.startswith(sid)]:
                    del self.s[k]
            elif token:
                self.s.pop(self._h(token), None)
            self._save()

    def log(self, event, ua="", net="", detail=""):
        with self.lock:
            self.events.append({"t": int(self.clock()), "e": event, "ua": ua, "net": net, "d": (detail or "")[:80]})
            self.events = self.events[-MAX_EVENTS:]
            if event != "action":
                self._save()
            elif self.clock() - self._saved > 60:
                self._saved = self.clock()
                self._save()

    def report(self, mine=None):
        """For the dashboard: the open sessions (`id`: the first 10 characters of the token's hash) and the log."""
        with self.lock:
            self._expire()
            me = self._h(mine) if mine else None
            ss = [{"id": k[:10], "at": int(v["at"]), "seen": int(v["seen"]), "ua": v.get("ua", ""), "net": v.get("net", ""),
                   "mine": k == me} for k, v in sorted(self.s.items(), key=lambda kv: -kv[1]["at"])]
            day = self.clock() - 86400
            return {"sessions": ss, "events": list(reversed(self.events[-60:])),
                    "fails_24h": sum(1 for e in self.events if e["e"] == "login_fail" and e["t"] >= day),
                    "ttl_h": TTL_S // 3600}


def cookie_value(headers, name=COOKIE):
    for c in (headers.get("Cookie") or "").split(";"):
        k, _, v = c.strip().partition("=")
        if k == name:
            return v
    return None
