"""1.58.24: the old name is gone. Heimdall was called Clear Sky until 1.29; what still carried that name — a docstring,
two User-Agents, the push contact, the Telegram device name, the package name, the deployment examples, six unused
icons, an old master logo and a stale review sheet — was renamed or removed. CHANGELOG.md keeps the history.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = re.compile(r"Clear ?Sky|clear[-_]?sky", re.I)
TEXT = (".py", ".js", ".html", ".json", ".webmanifest", ".md", ".bat", ".toml", ".yml", ".yaml", ".txt", ".css", ".svg")
ROOT_FILES = ("README.md", "CLAUDE.md", "CONTRIBUTING.md", "SECURITY.md", "Dockerfile", "fly.toml", "render.yaml",
              "pyproject.toml", "deploy-fly.bat", "start.bat", "config.example.json", "requirements.txt")
SKIP = {os.path.join("tests", "test_old_name_15824.py")}
# The owner's working folder keeps its name until he renames it (TECHNICAL §15); a post that reports a clear sky is
# the weather, not the app ("чисте небо" — app/geo.py reads it).
ALLOWED = ("clear-sky-main", "reports clear sky")


def _files():
    for d in ("app", "static", "scripts", "tests", "docs", ".github"):
        for base, dirs, names in os.walk(os.path.join(ROOT, d)):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", "fixtures", "data")]
            for n in names:
                yield os.path.relpath(os.path.join(base, n), ROOT)
    for n in ROOT_FILES:
        if os.path.isfile(os.path.join(ROOT, n)):
            yield n


def test_the_old_name_is_nowhere_but_in_the_history():
    seen = []
    for rel in _files():
        if rel in SKIP or not (rel.endswith(TEXT) or "." not in os.path.basename(rel)):
            continue
        with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                for a in ALLOWED:
                    line = line.replace(a, "")
                if OLD.search(line):
                    seen.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not seen, "\n".join(seen)


def test_no_file_carries_the_old_name_and_the_old_icons_are_gone():
    names = [rel for rel in _files() if OLD.search(os.path.basename(rel)) or os.path.basename(rel).startswith("logo-cs")]
    assert not names, names
    for man in ("manifest.json", "light.webmanifest"):
        with open(os.path.join(ROOT, "static", man), encoding="utf-8") as f:
            assert "logo-cs" not in f.read()


def test_the_push_contact_and_the_telegram_device_say_heimdall():
    with open(os.path.join(ROOT, "app", "push.py"), encoding="utf-8") as f:
        push = f.read()
    assert 'SUBJECT = "mailto:heimdall@example.com"' in push
    assert push.count("subject=SUBJECT") == 2                # send() and the pool use the one contact
    with open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8") as f:
        assert 'device_model="Heimdall server"' in f.read()   # the same name scripts/telegram_login.py gives the session
    with open(os.path.join(ROOT, "scripts", "telegram_login.py"), encoding="utf-8") as f:
        assert 'device_model="Heimdall server"' in f.read()
