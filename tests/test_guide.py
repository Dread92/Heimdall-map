"""1.35: what to do, weapon by weapon (/guide). The one page where the app tells people how to act — so it says only
what the official guidance says, in three languages that say the same thing, with the emergency numbers a tap away,
and it opens with no network. These tests hold the shape; docs/SAFETY.md says why the content is what it is."""
import gzip
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGE = _read("static/guide.html")
SW = _read("static/sw.js")
SRC = _read("app/server.py")
TAC = _read("static/kyiv.html")
LIGHT = _read("static/light.html")
NUKE = _read("static/nuke.js")
I18N = _read("static/i18n.js")


def _block(i):
    return json.loads(re.search(r'<script type="application/json" id="' + i + r'">(.*?)</script>', PAGE, re.S).group(1))


GD = _block("gd")
SOURCES = _block("gsrc")


def _shape(x):
    if isinstance(x, dict):
        return {k: _shape(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_shape(v) for v in x]
    return type(x).__name__


def _texts(x):
    if isinstance(x, dict):
        return [t for v in x.values() for t in _texts(v)]
    if isinstance(x, list):
        return [t for v in x for t in _texts(v)]
    return [x]


def test_three_languages_that_say_the_same_number_of_things():
    assert set(GD) == {"uk", "en", "fr"}
    assert _shape(GD["uk"]) == _shape(GD["en"]) == _shape(GD["fr"])
    for lang, T in GD.items():
        assert all(t.strip() for t in _texts(T)), lang                      # nothing left empty
        assert [c["id"] for c in T["weapons"]["cards"]] == ["shahed", "jet", "cruise", "ballistic", "kab", "debris"]
        assert [s["id"] for s in T["sit"]] == ["car", "out", "home", "kids", "after", "rad"]
        for c in T["weapons"]["cards"]:
            assert c["warn"] and c["see"] and c["do"], (lang, c["id"])
        # the same markup in each language: a <b> in one is a <b> in the others
        assert sorted(re.findall(r"</?\w+", json.dumps(T))) == sorted(re.findall(r"</?\w+", json.dumps(GD["uk"]))), lang


def test_the_official_siren_comes_first_and_the_numbers_are_a_tap_away():
    assert "«Повітряна тривога»" in GD["uk"]["intro"] and "«Повітряна тривога»" in GD["en"]["intro"]
    assert "« Повітряна тривога »" in GD["fr"]["intro"]
    for T in GD.values():
        assert list(T["num"]["n"]) == ["101", "102", "103", "104", "112"]
    assert "'<a href=\"tel:'+n+'\">" in PAGE and "NUMS=['101','102','103','104','112']" in PAGE
    assert "101" in PAGE.split("<noscript>")[1].split("</noscript>")[0]      # even with no script


def test_it_never_calls_a_place_safe_and_never_promises_a_time():
    for lang, word in (("uk", r"\bбезпечн\w*"), ("en", r"\bsafe\b"), ("fr", r"\bsûrs?\b")):
        for t in _texts(GD[lang]):
            for m in re.finditer(word, t, re.I):
                around = t[max(0, m.start() - 40):m.end() + 40]
                # allowed: "safer than", "if it is safe" (to help), and "nothing reported does not mean safe"
                assert re.search(r"безпечніш|safer|plus sûrs|лише якщо це безпечно|only if it is safe|не означає|does not mean|ne veut pas dire",
                                 around, re.I), (lang, around)
    for T in GD.values():                                                      # typical values, said so
        assert re.search(r"типов|typical|typiques", T["weapons"]["note"], re.I)


def test_every_rule_has_its_sources_listed_and_they_are_official_guidance():
    assert len(SOURCES) >= 8
    for pub, title, url in SOURCES:
        assert url.startswith("https://") and pub and title
    pubs = " ".join(p for p, _, _ in SOURCES)
    for who in ("ДСНС", "поліція", "МОЗ", "ОВА"):
        assert who in pubs, who
    # what is not taken from them is said on the page
    for T in GD.values():
        assert re.search(r"поліці|police", T["src"]["note"], re.I)


def test_the_bridges_and_the_radiation_section_the_rest_of_the_app_links_to():
    for T in GD.values():
        car = next(s for s in T["sit"] if s["id"] == "car")
        assert any("Heimdall" in i for i in car["items"])                     # "nothing reported" is not safe
    assert "id=\"'+s.id+'\"" in PAGE                                          # #rad is a real anchor
    assert 'href="/guide#rad"' in NUKE and "T.g" in NUKE and "'.hnkc.min .hnkt,.hnkc.min .hnkf,.hnkc.min .hnkg{display:none}'" in NUKE
    assert 'href="/guide" data-t="m_guide"' in TAC and '<a class="gdl" href="/guide">' in TAC
    assert '<a href="/guide" id="gdl"></a>' in LIGHT and "$('gdl').textContent=t('m_guide')" in LIGHT
    assert len(re.findall(r"(?<![A-Za-z_])m_guide:", I18N)) == 3


def test_it_asks_for_nothing_and_loads_nothing_from_elsewhere():
    scripts = re.findall(r"<script[^>]*\bsrc=\"([^\"]+)\"", PAGE)
    assert scripts == ["/static/glyphs.js"]
    assert "<link rel=\"stylesheet\"" not in PAGE and "@import" not in PAGE
    assert "fetch(" not in PAGE and "XMLHttpRequest" not in PAGE and "/api/" not in PAGE
    assert "localStorage.setItem('lang'" in PAGE and "getItem('lang')" in PAGE  # the app's own language, nothing else


def test_it_is_served_and_kept_for_when_there_is_no_network():
    i = SRC.index('if u.path == "/guide":')
    assert 'self._file("guide.html", "text/html; charset=utf-8")' in SRC[i:i + 120]
    # the worker keeps the guide's three paths (1.41: and the two pages), GET only, network first
    assert "const GUIDE = ['/guide', '/static/glyphs.js', '/static/heimdall-64.png'];" in SW
    assert "e.request.method !== 'GET'" in SW and "if (!KEEP.includes(key)) return;" in SW and "GUIDE.concat(SHELL" in SW
    assert SW.index("fetch(e.request)") < SW.index("caches.match(key)")
    assert ".catch(() => {})" in SW.split("addEventListener('install'")[1].split("});")[0]   # never blocks the install
    assert "navigator.serviceWorker.register('/sw.js')" in PAGE and "caches.match('/guide')" in PAGE


def test_it_stays_small_enough_for_2g():
    assert len(gzip.compress(PAGE.encode("utf-8"), 6)) < 21_000
