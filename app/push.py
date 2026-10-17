"""Web Push (RFC 8291 aes128gcm + RFC 8292 VAPID) with only the `cryptography` package.
Used by server.py to wake the phone even when the page is closed (Android Chrome / desktop; iOS needs the
page added to the home screen). If `cryptography` is missing, push is simply disabled."""
import base64
import http.client
import json
import os
import ssl
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# The VAPID "sub" claim: a contact for the push services (Apple wants a mailto: or https: one). It is not part of
# a subscription, so changing it (1.58.24: it named the old app) keeps every phone subscribed.
SUBJECT = "mailto:heimdall@example.com"

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    AVAILABLE = True
except Exception:   # pragma: no cover
    AVAILABLE = False


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s):
    s = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def generate_vapid():
    """Returns (private_key_b64url_raw32, public_key_b64url_uncompressed65)."""
    k = ec.generate_private_key(ec.SECP256R1())
    priv = k.private_numbers().private_value.to_bytes(32, "big")
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return b64u(priv), b64u(pub)


def _load_priv(priv_b64):
    return ec.derive_private_key(int.from_bytes(b64u_dec(priv_b64), "big"), ec.SECP256R1())


def vapid_headers(endpoint, priv_b64, pub_b64, subject):
    u = urlparse(endpoint)
    aud = f"{u.scheme}://{u.netloc}"
    header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    claims = b64u(json.dumps({"aud": aud, "exp": int(time.time()) + 12 * 3600, "sub": subject}).encode())
    signing = f"{header}.{claims}".encode()
    der = _load_priv(priv_b64).sign(signing, ec.ECDSA(hashes.SHA256()))
    r, s_ = decode_dss_signature(der)
    sig = b64u(r.to_bytes(32, "big") + s_.to_bytes(32, "big"))
    return {"Authorization": f"vapid t={header}.{claims}.{sig}, k={pub_b64}"}


def encrypt(payload, p256dh_b64, auth_b64):
    """RFC 8291 aes128gcm content encoding. Returns the body bytes (salt|rs|idlen|pubkey|ciphertext)."""
    ua_pub = b64u_dec(p256dh_b64)
    auth = b64u_dec(auth_b64)
    as_key = ec.generate_private_key(ec.SECP256R1())
    as_pub = as_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = HKDF(hashes.SHA256(), 32, salt=auth, info=b"WebPush: info\x00" + ua_pub + as_pub).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)
    rs = 4096
    ct = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)     # single record, padding delimiter 0x02
    return salt + struct.pack(">I", rs) + bytes([len(as_pub)]) + as_pub + ct


def send(subscription, payload, priv_b64, pub_b64, subject=SUBJECT, ttl=300, urgency="high"):
    """subscription: the browser's PushSubscription JSON. Returns (status_code, gone) — gone=True when the
    subscription is dead (404/410) and should be deleted."""
    endpoint = subscription["endpoint"]
    keys = subscription.get("keys") or {}
    body = encrypt(json.dumps(payload).encode("utf-8"), keys["p256dh"], keys["auth"])
    headers = {"Content-Type": "application/octet-stream", "Content-Encoding": "aes128gcm", "TTL": str(ttl), "Urgency": urgency}
    headers.update(vapid_headers(endpoint, priv_b64, pub_b64, subject))
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, False
    except urllib.error.HTTPError as e:
        return e.code, e.code in (404, 410)
    except Exception:
        return 0, False



# 1.58.35, the audit: a subscription is kept only when it is one — until then any string was stored as an endpoint, and
# every notification then waited on it (a connect timeout each), while the same field let the server be pointed at any
# host. A real subscription comes from one of the browsers' push services, over https, with a 65-byte P-256 point and a
# 16-byte auth secret; that, and nothing else, is what gets stored (never the client's whole object).
PUSH_HOSTS = ("fcm.googleapis.com", "android.googleapis.com", "updates.push.services.mozilla.com", "notify.windows.com",
              "push.apple.com", "web.push.apple.com", "push.services.mozilla.com")
ENDPOINT_MAX = 1024


def _b64u_len(v):
    try:
        v = str(v or "")
        return len(base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)))
    except (ValueError, TypeError):
        return -1


def push_host_ok(host):
    host = (host or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def clean_subscription(sub):
    """{endpoint, keys:{p256dh, auth}} when `sub` is a browser's push subscription, else None."""
    if not isinstance(sub, dict):
        return None
    ep = sub.get("endpoint")
    if not isinstance(ep, str) or not (20 <= len(ep) <= ENDPOINT_MAX) or any(c.isspace() for c in ep):
        return None
    try:
        u = urllib.parse.urlsplit(ep)
    except ValueError:
        return None
    if u.scheme != "https" or not u.hostname or u.username or u.password or not push_host_ok(u.hostname) or not u.path:
        return None
    keys = sub.get("keys") if isinstance(sub.get("keys"), dict) else {}
    p, a = keys.get("p256dh"), keys.get("auth")
    if _b64u_len(p) != 65 or _b64u_len(a) != 16:
        return None
    out = {"endpoint": ep, "keys": {"p256dh": str(p), "auth": str(a)}}
    if isinstance(sub.get("expirationTime"), (int, float)):
        out["expirationTime"] = sub["expirationTime"]
    return out


class Sender:
    """One notification to many phones at once (1.29).

    It used to be one phone at a time, each on a new HTTPS connection: ~0.15 s per Android phone and up to
    ~0.5 s per iPhone, so with a thousand subscribers the last phone heard of a ballistic missile minutes after
    the first — possibly after it had landed. Now `workers` sends are in flight together, and each worker keeps
    one open connection per push service (Google's for Android and Chrome, Apple's for iPhones, Mozilla's…), so
    after the first message a push costs one round trip, not a TLS handshake. The VAPID signature depends only
    on the push service and is valid for 12 h, so it is signed once an hour per service, not once per phone.
    Encryption stays per phone: every phone has its own keys, and nothing is shared between them."""

    def __init__(self, priv_b64, pub_b64, subject=SUBJECT, workers=32, timeout=10):
        self.priv, self.pub, self.subject = priv_b64, pub_b64, subject
        self.timeout = timeout
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="push")
        self.local = threading.local()
        self._jwt = {}
        self._jwt_lock = threading.Lock()
        self._ctx = ssl.create_default_context()

    def _auth(self, scheme, host):
        aud = f"{scheme}://{host}"
        now = time.time()
        with self._jwt_lock:                  # signed under the lock: 32 workers starting together sign once
            hit = self._jwt.get(aud)
            if hit and hit[0] > now:
                return hit[1]
            h = vapid_headers(aud + "/", self.priv, self.pub, self.subject)
            self._jwt[aud] = (now + 3600, h)
            return h

    def _conn(self, scheme, host):
        conns = getattr(self.local, "conns", None)
        if conns is None:
            conns = self.local.conns = {}
        c = conns.get((scheme, host))
        if c is None:
            # 1.58.35: a push service is always https; plain http only to this machine itself (the tests' fake service)
            if scheme != "https" and host.split(":")[0].strip("[]") not in ("127.0.0.1", "localhost", "::1"):
                raise ValueError("push endpoint must be https")
            c = (http.client.HTTPSConnection(host, timeout=self.timeout, context=self._ctx) if scheme == "https"
                 else http.client.HTTPConnection(host, timeout=self.timeout))
            conns[(scheme, host)] = c
        return c

    def _drop(self, scheme, host):
        c = (getattr(self.local, "conns", None) or {}).pop((scheme, host), None)
        if c:
            try:
                c.close()
            except Exception:
                pass

    def send_one(self, subscription, data, ttl=300, urgency="high"):
        """(status, gone) for one phone; `data` is the JSON payload, already encoded."""
        endpoint = subscription["endpoint"]
        keys = subscription.get("keys") or {}
        u = urlparse(endpoint)
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        body = encrypt(data, keys["p256dh"], keys["auth"])
        headers = {"Content-Type": "application/octet-stream", "Content-Encoding": "aes128gcm", "TTL": str(ttl),
                   "Urgency": urgency, "Content-Length": str(len(body))}
        headers.update(self._auth(u.scheme, u.netloc))
        for attempt in (0, 1):
            c = self._conn(u.scheme, u.netloc)
            reused = c.sock is not None
            if not reused:
                try:
                    c.connect()
                except OSError:
                    # nothing was sent yet, so trying again cannot deliver twice
                    self._drop(u.scheme, u.netloc)
                    if attempt:
                        return 0, False
                    continue
            try:
                c.request("POST", path, body=body, headers=headers)
                r = c.getresponse()
                r.read()
                if r.will_close:
                    self._drop(u.scheme, u.netloc)
                return r.status, r.status in (404, 410)
            except (http.client.HTTPException, OSError):
                self._drop(u.scheme, u.netloc)
                # A kept-open connection the push service closed while it sat idle fails on first use: once,
                # on a fresh connection. A fresh connection that fails is a real failure — no second try.
                if not reused or attempt:
                    return 0, False
        return 0, False

    def send_many(self, subscriptions, payload, ttl=300, urgency="high"):
        """[(subscription, status, gone)] for every phone, all at once."""
        data = json.dumps(payload).encode("utf-8")

        def one(s):
            try:
                code, gone = self.send_one(s, data, ttl, urgency)
            except Exception:           # a malformed subscription must not stop the others
                code, gone = 0, False
            return s, code, gone
        return list(self.pool.map(one, subscriptions))


if __name__ == "__main__":
    priv, pub = generate_vapid()
    print("VAPID public:", pub)
    print("encrypt ok:", len(encrypt(b'{"a":1}', b64u(ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)), b64u(os.urandom(16)))))
