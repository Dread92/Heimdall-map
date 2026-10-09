"""1.52.1: a target's whole path for the night, and hatching that no longer hides the targets.

The owner: "what about the trajectory of the threat — the history of its movement for the same id". 1.52 drew the
places the posts reported a target at, but only those still in the map's 45-minute window: a Shahed tracked from the
Belarusian border for two hours kept its tag while its first hour vanished from its path. Every point of a tagged track
is now kept with its tag (`target_points`) and served for a tag (`/api/trail`); a tap draws the older part fainter,
and the card says how many reports the tag had tonight and since when. Points are where the posts put it — a
destination ("на Бровари") or a whole oblast is no point — and between two reports nobody saw it.

And the owner, on the hatching of an oblast with a target somewhere in it: "it hurts readability, above all once the
drones start being placed on the map" — it is drawn only on the whole-region view, in fine lines a few pixels apart,
and never over an oblast with a target placed in it.
"""
import os
from datetime import datetime, timedelta, timezone

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, DOC, SRC = _read("static/kyiv.html"), _read("static/i18n.js"), _read("docs/TECHNICAL.md"), _read("app/server.py")
NOW = datetime.now(timezone.utc)


def ago(m):
    return (NOW - timedelta(minutes=m)).isoformat()


def test_the_tags_path_outlives_the_window():
    st = server.State(server.Store(":memory:"), {"marker_ttl_minutes": 45})
    tg = server.Telegram(st, {})
    tg.ingest("chernihiv_nebo", [("chernihiv_nebo/1521", ago(40), "Шахед над Ріпками"),
                                 ("chernihiv_nebo/1522", ago(26), "Шахед над Черніговом, висота 1500"),
                                 ("chernihiv_nebo/1523", ago(12), "Шахед на Козелець"),
                                 ("chernihiv_nebo/1524", ago(10), "Шахед над Козельцем")], "tg:c")
    (m,) = [m for m in st.markers() if m["id"] == "chernihiv_nebo/1524#0"]
    tag = m["tag"]
    assert [h["place"] for h in m["history"]] == ["Ріпки", "Чернігів"]
    # the window shrinks to 20 minutes: Ripky and Chernihiv leave the map, the tag and its path stay
    st.cfg["marker_ttl_minutes"] = 20
    st._marker_cache.clear()
    (m2,) = [x for x in st.markers() if x["id"] == "chernihiv_nebo/1524#0"]
    assert m2["tag"]["id"] == tag["id"] and not m2.get("history")
    pts = st.tags.trail(tag["night"], tag["n"])
    assert [p["place"] for p in pts] == ["Ріпки", "Чернігів", "Козелець"]           # "на Козелець" is a destination
    assert pts[1]["alt"] == 1500 and pts[0]["ts"] < pts[1]["ts"] < pts[2]["ts"]
    assert st.tags.trail(tag["night"], tag["n"] + 1) == []


def test_the_route_and_the_page():
    assert 'u.path == "/api/trail"' in SRC and '`target_points`' in DOC and "/api/trail" in DOC
    assert "fetch(`/api/trail?night=${encodeURIComponent(tg.night)}&n=${tg.n}`)" in PAGE
    assert "setTimeout(()=>loadTrail(m),0);" in PAGE and '<div id="shtrail"></div>' in PAGE
    assert "#selpath .old{opacity:.55}" in PAGE and "const k=pts.findIndex(o=>!o.old);" in PAGE
    assert I18N.count("sh_trail:'") == 3


def test_the_hatching_stays_off_the_targets():
    assert "svg:not(.veryfar) #oblevt .obhatch{display:none}" in PAGE
    assert "${anyLive&&!placed.has(uid)?`<path class=\"obhatch\"" in PAGE
    assert 'patternTransform="rotate(45) scale(${kx(KPX*1.4)})"' in PAGE
    assert "hp.setAttribute('patternTransform',`rotate(45) scale(${kx(KPX*1.4)})`)" in PAGE


def test_an_answer_cut_off_says_so_and_is_allowed_twice_the_length():
    import json
    from unittest import mock

    import ai_reader as A
    r = A.AIReader({"openrouter_key": "sk-or-test"}, server.Store(":memory:"), None, rules_fn=lambda *a: [], oblast_names={})

    class Resp:
        def __init__(self, b):
            self.b = b

        def read(self):
            return self.b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    cut = {"choices": [{"message": {"content": '{"targets": [{"kind": "shah'}, "finish_reason": "length"}],
           "usage": {"prompt_tokens": 9000, "completion_tokens": 2400, "cost": 0.0012}}
    with mock.patch.object(A.urllib.request, "urlopen", lambda *a, **k: Resp(json.dumps(cut).encode())):
        res = r._request([{"role": "user", "content": "x"}], 0)
    assert res["error"] == "cut off at 2400 tokens" and res["tok_out"] == 2400
