#!/bin/sh
# 1.58.45: static/vendor/three-m3d.min.js — three.js (MIT, static/vendor/three.LICENSE), only the classes
# scripts/three-m3d.entry.js names, as one ES module the 3D models import. Run from the repository's root:
#   sh scripts/build_three.sh
# The page never fetches three.js from anywhere else (CSP: script-src 'self').
set -e
THREE=0.185.1
ESBUILD=0.25.0
BUNDLE_SHA256=439e860badb7c4b80c90a231bcb169b47e69a8f3d09cbf9e0e3d85362b654f3f
TMP=$(mktemp -d)
cp scripts/three-m3d.entry.js "$TMP/entry.js"
# 1.58.46, the audit (I6): no package's install script runs (esbuild works without its own); the result is checked below
cd "$TMP" && npm init -y -q >/dev/null && npm i -q --no-audit --no-fund --ignore-scripts "three@$THREE" "esbuild@$ESBUILD" >/dev/null
npx esbuild entry.js --bundle --format=esm --minify --legal-comments=inline --outfile=three-m3d.min.js
cd - >/dev/null
# the bundle these versions make — a different one means a different input: not copied (tests/test_audit_15846.py checks it too)
SHA=$(sha256sum "$TMP/three-m3d.min.js" | cut -c1-64)
if [ "$SHA" != "$BUNDLE_SHA256" ]; then echo "three-m3d.min.js: sha256 $SHA, expected $BUNDLE_SHA256 — not copied" >&2; rm -rf "$TMP"; exit 1; fi
cp "$TMP/three-m3d.min.js" static/vendor/three-m3d.min.js
cp "$TMP/node_modules/three/LICENSE" static/vendor/three.LICENSE
rm -rf "$TMP"
echo "static/vendor/three-m3d.min.js: three.js $THREE"
