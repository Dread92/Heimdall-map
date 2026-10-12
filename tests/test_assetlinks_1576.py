"""1.57.6: the Android app (heimdall-android, a Trusted Web Activity) opens this site full screen only when the site says
the app is its own — /.well-known/assetlinks.json, from the fingerprint of the owner's signing key (a Fly secret)."""
import os

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = "97:C0:00:63:0D:1A:8F:8D:C5:96:8E:A0:98:41:2F:57:C0:35:79:00:ED:BF:45:14:62:B6:2F:A0:1A:66:94:B0"


def test_no_key_no_claim(monkeypatch):
    monkeypatch.delenv("ANDROID_CERT_SHA256", raising=False)
    assert server.android_asset_links() == []


def test_the_owner_s_key(monkeypatch):
    # as keytool prints it, with its label
    monkeypatch.setenv("ANDROID_CERT_SHA256", "SHA256: " + FP)
    monkeypatch.delenv("ANDROID_PACKAGE", raising=False)
    links = server.android_asset_links()
    assert links == [{"relation": ["delegate_permission/common.handle_all_urls"],
                      "target": {"namespace": "android_app", "package_name": "com.blackflamestudio.heimdall",
                                 "sha256_cert_fingerprints": [FP]}}]
    # as apksigner prints it, and a second key (a new one, or Google Play's), in one secret
    monkeypatch.setenv("ANDROID_CERT_SHA256", FP.replace(":", "").lower() + ", " + "AA" * 32)
    assert server.android_asset_links()[0]["target"]["sha256_cert_fingerprints"] == [FP, ":".join(["AA"] * 32)]
    monkeypatch.setenv("ANDROID_CERT_SHA256", "not a fingerprint")
    assert server.android_asset_links() == []


def test_the_route_the_script_and_the_docs():
    src = open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8").read()
    assert 'if u.path == "/.well-known/assetlinks.json":\n                return self._json(android_asset_links())' in src
    bat = open(os.path.join(ROOT, "scripts", "set-android-key.bat"), encoding="utf-8").read()
    assert "ANDROID_CERT_SHA256=%FP%" in bat and "fly secrets import" in bat
    doc = open(os.path.join(ROOT, "docs", "TECHNICAL.md"), encoding="utf-8").read()
    assert "### 10.8 The Android app (1.57.6)" in doc and "heimdall-android" in doc
