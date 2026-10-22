"""Two keys, and confusing them takes the map away from everybody.

ACCESS_KEY was written for a private deployment: it puts a login form in front of the whole app. Told to set
it so the dashboard would work, a public instance locked out every reader of an air-raid map — police,
military, anyone — and the only symptom was a password box where the map used to be.

ADMIN_KEY protects the dashboard and nothing else. These tests pin the difference.
"""
import os
import sys
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import adminauth  # noqa: E402
import server  # noqa: E402


class _H:
    """Just enough of the request handler to exercise the two gates."""
    def __init__(self, cfg=None, cookie="", key=None, header=None):
        self.state = type("S", (), {"cfg": cfg or {}, "admin": adminauth.AdminSessions(),
                                    "access": adminauth.AdminSessions(name="access", ttl=adminauth.ACCESS_TTL_S)})()
        self.headers = {"Cookie": cookie}
        if header:
            self.headers["X-Admin-Key"] = header
        self.q = {"key": [key]} if key else {}

    client_address = ("127.0.0.1", 0)
    _admin_key = server.Handler._admin_key
    _admin_ok = server.Handler._admin_ok
    _header_key = server.Handler._header_key          # 1.58.46: a key in a header, held to the sign-in rule

    def _sec(self, *a):
        pass

    _access_key = server.Handler._access_key
    _authorized = server.Handler._authorized


def test_with_no_key_at_all_the_map_is_public_and_the_dashboard_does_not_exist():
    with mock.patch.dict(os.environ, {}, clear=True):
        h = _H()
        assert h._authorized(None, {}) is True          # the map is open
        assert h._admin_ok({}) is False                 # the dashboard is never open, it is absent


def test_admin_key_leaves_the_map_public():
    """The failure this file exists for: a dashboard key must never cost a single reader the map."""
    with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm"}, clear=True):
        h = _H()
        assert h._authorized(None, {}) is True
        assert _H(header="adm")._admin_ok({}) is True
        assert _H(header="nope")._admin_ok({}) is False


def test_the_key_in_the_address_or_in_a_cookie_no_longer_opens_anything():
    """1.58.21: /admin?key=… put the key in the browser's history, and `uadm=<key>` kept it a year in a cookie every
    page's script could read. Neither opens the dashboard any more: a session from the login page does."""
    with mock.patch.dict(os.environ, {"ADMIN_KEY": "adm"}, clear=True):
        assert _H()._admin_ok({"key": ["adm"]}) is False
        assert _H(cookie="uadm=adm")._admin_ok({}) is False
        h = _H()
        token = h.state.admin.create("Chrome · Windows", "abcd1234", kp=adminauth.key_print("adm"))
        h.headers["Cookie"] = "other=1; hsess=" + token
        assert h._admin_ok({}) is True
        h.state.admin.drop(token=token)
        assert h._admin_ok({}) is False


def test_a_new_key_ends_the_sessions_opened_with_the_old_one():
    """1.58.22: scripts/set-admin-key.bat puts a new key in Fly's secrets; whoever signed in with the old one is out."""
    with mock.patch.dict(os.environ, {"ADMIN_KEY": "old-key"}, clear=True):
        h = _H()
        token = h.state.admin.create("Chrome · Windows", "abcd1234", kp=adminauth.key_print("old-key"))
        h.headers["Cookie"] = "hsess=" + token
        assert h._admin_ok({}) is True
    with mock.patch.dict(os.environ, {"ADMIN_KEY": "new-key"}, clear=True):
        assert h._admin_ok({}) is False
        assert not h.state.admin.s                      # and it is gone, not just refused
    bat = open(os.path.join(ROOT, "scripts", "set-admin-key.bat"), encoding="utf-8").read()
    assert "RandomNumberGenerator" in bat and "| fly secrets import" in bat     # made on the PC, stored from stdin
    assert "fly secrets set ADMIN_KEY" not in bat and "?key=" not in bat


def test_access_key_still_locks_the_whole_app_for_a_private_deployment():
    """1.58.35: the lock is a session from its login page (app/adminauth.py, `hacc`), or the key in an X-Access-Key
    header for scripts — never the key in the address, never the key itself in a cookie (`uak=`, until 1.58.34)."""
    with mock.patch.dict(os.environ, {"ACCESS_KEY": "priv"}, clear=True):
        assert _H()._authorized(None, {}) is False
        assert _H()._authorized(None, {"key": ["priv"]}) is False
        assert _H(cookie="uak=priv")._authorized(None, {}) is False
        h = _H(); h.headers["X-Access-Key"] = "priv"
        assert h._authorized(None, {}) is True
        h = _H()
        token = h.state.access.create("Chrome · Android", "abcd1234", kp=adminauth.key_print("priv"))
        h.headers["Cookie"] = "hacc=" + token
        assert h._authorized(None, {}) is True
        h.headers["Cookie"] = "hsess=" + token             # the dashboard's cookie name does not open the app
        assert h._authorized(None, {}) is False
    with mock.patch.dict(os.environ, {"ACCESS_KEY": "other"}, clear=True):
        h.headers["Cookie"] = "hacc=" + token             # a new key ends the sessions of the old one
        assert h._authorized(None, {}) is False


def test_access_key_alone_still_opens_the_dashboard_so_old_deployments_keep_working():
    with mock.patch.dict(os.environ, {"ACCESS_KEY": "priv"}, clear=True):
        assert _H(header="priv")._admin_ok({}) is True


def test_admin_key_wins_when_both_are_set():
    with mock.patch.dict(os.environ, {"ACCESS_KEY": "priv", "ADMIN_KEY": "adm"}, clear=True):
        assert _H(header="adm")._admin_ok({}) is True
        assert _H(header="priv")._admin_ok({}) is False


def test_the_admin_cookie_never_unlocks_the_app():
    """A dashboard session must not become a way past the app-wide gate."""
    with mock.patch.dict(os.environ, {"ACCESS_KEY": "priv"}, clear=True):
        assert _H(cookie="uadm=priv")._authorized(None, {}) is False
        h = _H()
        token = h.state.admin.create("Chrome · Windows", "abcd1234", kp=adminauth.key_print("priv"))
        h.headers["Cookie"] = "hsess=" + token             # a real dashboard session, still not the app's lock
        assert h._authorized(None, {}) is False
        assert _H(cookie="hsess=whatever")._authorized(None, {}) is False


def test_the_spaces_around_a_key_are_not_part_of_it():
    """1.58.23, the owner: "it said wrong key while it was the correct one". cmd adds a space before the bracket when it
    pipes a bracketed block, so `(echo ADMIN_KEY=%NEWKEY%)| fly secrets import` stored the key with a trailing space."""
    with mock.patch.dict(os.environ, {"ADMIN_KEY": "Abc123-xyz "}, clear=True):
        assert _H(header="Abc123-xyz")._admin_ok({}) is True
        assert _H(header=" Abc123-xyz\r\n")._admin_ok({}) is True
        assert _H(header="Abc123-xy")._admin_ok({}) is False
    assert adminauth.same_key("k ", " k") and not adminauth.same_key("", "  ")
    import glob
    for p in glob.glob(os.path.join(ROOT, "scripts", "set-*.bat")):
        bat = open(p, encoding="utf-8").read()
        assert ")| fly secrets import" not in bat, p        # never a bracketed block piped into fly
