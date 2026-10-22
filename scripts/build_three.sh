#!/bin/sh
# 1.58.45: static/vendor/three-m3d.min.js — three.js (MIT, static/vendor/three.LICENSE), only the classes
# scripts/three-m3d.entry.js names, as one ES module the 3D models import. Run from the repository's root:
#   sh scripts/build_three.sh
# The page never fetches three.js from anywhere else (CSP: script-src 'self').
set -e
THREE=0.185.1
ESBUILD=0.25.0
TMP=$(mktemp -d)
cp scripts/three-m3d.entry.js "$TMP/entry.js"
cd "$TMP" && npm init -y -q >/dev/null && npm i -q --no-audit --no-fund "three@$THREE" "esbuild@$ESBUILD" >/dev/null
npx esbuild entry.js --bundle --format=esm --minify --legal-comments=inline --outfile=three-m3d.min.js
cd - >/dev/null
cp "$TMP/three-m3d.min.js" static/vendor/three-m3d.min.js
cp "$TMP/node_modules/three/LICENSE" static/vendor/three.LICENSE
rm -rf "$TMP"
echo "static/vendor/three-m3d.min.js: three.js $THREE"
