"""The technical documentation is updated with every patch — and this makes forgetting it fail the build.

docs/TECHNICAL.md is the one complete reference. A reference that drifts from the code is worse than none: it is
read with confidence. So the parts that can be checked mechanically are: the documented version is the running
version and the latest changelog entry, and every route, config key, environment variable and database table
that exists in the code is named in the document."""
import os
import re

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = open(os.path.join(ROOT, "docs", "TECHNICAL.md"), encoding="utf-8").read()
CHANGELOG = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
SRC = "".join(open(os.path.join(ROOT, "app", f), encoding="utf-8").read() for f in ("server.py", "translate.py", "push.py", "geo.py"))


def test_the_documented_version_is_the_running_version():
    m = re.search(r"\*\*Documented version: ([\d.]+)\*\*", DOC)
    assert m, "docs/TECHNICAL.md has no 'Documented version' line"
    assert m.group(1) == server.APP_VERSION, f"docs say {m.group(1)}, the code is {server.APP_VERSION} — update docs/TECHNICAL.md"


def test_the_latest_changelog_entry_is_this_version():
    top = re.search(r"^## ([\d.]+)", CHANGELOG, re.M)
    assert top, "CHANGELOG.md has no version heading"
    assert top.group(1).startswith(server.APP_VERSION + "."), f"CHANGELOG starts at {top.group(1)}, the code is {server.APP_VERSION}"


def test_every_route_is_documented():
    routes = set(re.findall(r'u\.path == "([^"]+)"', SRC))
    for grp in re.findall(r"u\.path in \(([^)]*)\)", SRC):
        routes |= set(re.findall(r'"([^"]+)"', grp))
    missing = sorted(r for r in routes if not re.search(r"(?<![\w/.-])" + re.escape(r) + r"(?![\w/-])", DOC))
    assert not missing, f"routes missing from docs/TECHNICAL.md §12: {missing}"


def test_every_config_key_is_documented():
    missing = sorted(k for k in server.DEFAULT_CONFIG if f"`{k}`" not in DOC)
    assert not missing, f"config keys missing from docs/TECHNICAL.md §5.2: {missing}"


def test_every_environment_variable_is_documented():
    env = set(re.findall(r'os\.environ\.get\("([A-Z_]+)"', SRC)) | set(re.findall(r'os\.environ\["([A-Z_]+)"\]', SRC))
    missing = sorted(e for e in env if f"`{e}`" not in DOC)
    assert not missing, f"environment variables missing from docs/TECHNICAL.md §5.3: {missing}"


def test_every_table_is_documented():
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SRC))
    missing = sorted(t for t in tables if f"`{t}`" not in DOC)
    assert not missing, f"tables missing from docs/TECHNICAL.md §13: {missing}"


def test_the_default_channels_are_the_documented_ones():
    for ch in server.AUTHORITATIVE_CHANNELS:
        assert f"`{ch}`" in DOC, ch
