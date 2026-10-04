"""Every inline script of the two pages parses. A missing brace is not caught by any other test — the page
simply does not run at all, on every phone, until someone opens it."""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node is not installed")
@pytest.mark.parametrize("page", ["kyiv.html", "light.html", "admin.html", "guide.html"])
def test_the_inline_scripts_parse(page):
    src = open(os.path.join(ROOT, "static", page), encoding="utf-8").read()
    for i, body in enumerate(re.findall(r"<script>(.*?)</script>", src, re.S)):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(body)
        try:
            r = subprocess.run([NODE, "--check", f.name], capture_output=True, text=True)
        finally:
            os.unlink(f.name)
        assert r.returncode == 0, f"{page} script {i}: {r.stderr.strip()[:400]}"


@pytest.mark.skipif(not NODE, reason="node is not installed")
@pytest.mark.parametrize("js", ["i18n.js", "glyphs.js", "sw.js", "nuke.js"])
def test_the_shared_scripts_parse(js):
    r = subprocess.run([NODE, "--check", os.path.join(ROOT, "static", js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:400]
