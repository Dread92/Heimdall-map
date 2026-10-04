"""Every inline script of the two pages parses. A missing brace is not caught by any other test — the page
simply does not run at all, on every phone, until someone opens it."""
import os
import re
import shutil
import subprocess
import tempfile
import textwrap

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


@pytest.mark.skipif(not NODE or not shutil.which("bash"), reason="node or bash is not installed")
def test_the_ci_front_end_job_passes_here_too():
    """1.36 and 1.37 passed every test here and failed on GitHub: the CI's own key check did not know that a
    Ukrainian plural is _1 / _2 / _5 where English says _1 / _n. The front-end job's steps are run here as written,
    so that job can no longer fail only on GitHub."""
    yml = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
    lines = yml[yml.index("\n  frontend:"):].split("\n")
    steps, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)run: \|\s*$", lines[i])
        i += 1
        if not m:
            continue
        body = []
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > len(m.group(1))):
            body.append(lines[i])
            i += 1
        steps.append(textwrap.dedent("\n".join(body)))
    assert len(steps) >= 2
    for step in steps:
        r = subprocess.run(["bash", "-e", "-c", step], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, f"{step.strip().splitlines()[0]} … → {(r.stderr or r.stdout).strip()[:400]}"
