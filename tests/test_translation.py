"""Translations that read as English (and French), and never slow the alerts down.

24 Sep 2026: the feed on the server read "oblast zahalom clear, poky dykhaiemo" and "explosion prolunav in
kvartyri". The free Google endpoint refuses a data-centre address, so every post fell back to the offline
glossary, which transliterated every word it did not know — and each refusal was retried at ingest, ~3 s per
post, in front of the drone reports in the same poll."""
import io
import json
import urllib.error

import server
import translate as T

SRC = open(server.__file__, encoding="utf-8").read()


def test_the_offline_fallback_translates_the_everyday_words():
    assert T.translate_offline("Область загалом чисто, поки дихаємо") == "Oblast overall clear, breathing easy for now"
    out = T.translate_offline("Ударний йде далі на захід, ще один кружляє в районі Бучі")
    assert "heading further west" in out and "one more circling" in out and "Bucha" in out


def test_banderol_is_a_jet_drone_in_english_too():
    out = T.translate_offline("1х бандероль на Житомирщині")
    assert "Banderol (jet drone)" in out and "cruise" not in out.lower()


def test_the_most_frequent_leftovers_are_gone():
    # the words the glossary used to leave in Cyrillic most often, in their usual company
    for uk in ("йде далі", "керований", "звичайний", "відмічено декілька", "кружляє", "вилітають", "десяток", "щонайменше"):
        out = T.translate_offline(uk)
        assert not any(bad in out.lower() for bad in ("yde", "kerovan", "zvychain", "vidmich", "kruzhl", "vylitai", "desiat", "shchonai")), (uk, out)


def test_ingest_never_waits_for_a_machine_translator():
    i = SRC.index("class Telegram(threading.Thread)")
    body = SRC[i:SRC.index("\nclass ", i + 10)]
    assert "translate_offline(text)" in body
    assert "to_en(text)" not in body


def test_a_refusing_translator_is_left_alone_for_half_an_hour(monkeypatch):
    calls = []

    def refuse(text, target="en"):
        calls.append(text)
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b""))
    monkeypatch.setattr(T, "_google", refuse)
    monkeypatch.setattr(T, "MODE", "google")
    monkeypatch.setattr(T, "KEYS", {"deepl": "", "google_cloud": ""})
    monkeypatch.setattr(T, "_DOWN", {})
    assert T.machine("Бровари", "en") == (None, None)
    assert T.machine("Бровари", "en") == (None, None)
    assert len(calls) == 1               # the second post did not pay for the refusal again
    assert T.translate("Бровари чисто") and T.LAST_OK[0] is False


def test_french_has_no_offline_stand_in(monkeypatch):
    monkeypatch.setattr(T, "backends", lambda: [])
    assert T.translate_to("Бровари чисто", "fr") == (None, False)
    out, ok = T.translate_to("Бровари чисто", "en")
    assert ok is False and "clear" in out


def test_deepl_is_asked_for_french_from_ukrainian(monkeypatch):
    seen = {}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=0, context=None):
        seen["url"], seen["auth"], seen["body"] = req.full_url, req.headers.get("Authorization"), json.loads(req.data)
        return R(json.dumps({"translations": [{"text": "Brovary : dégagé"}]}).encode())
    monkeypatch.setattr(T._ur, "urlopen", fake)
    monkeypatch.setattr(T, "KEYS", {"deepl": "abc:fx", "google_cloud": ""})
    monkeypatch.setattr(T, "_DOWN", {})
    out, name = T.machine("Бровари: чисто", "fr")
    assert name == "deepl" and out == "Brovary : dégagé"
    assert seen["url"].startswith("https://api-free.deepl.com/") and seen["auth"] == "DeepL-Auth-Key abc:fx"
    assert seen["body"]["source_lang"] == "UK" and seen["body"]["target_lang"] == "FR"


def test_translations_are_made_only_for_a_language_someone_reads(monkeypatch):
    st = server.State(server.Store(":memory:"), {})
    tr = server.Translations(st)
    assert not tr.wanted("fr")
    tr.want("fr")
    assert tr.wanted("fr") and not tr.wanted("en")
    tr.want("uk")
    assert not tr.wanted("uk")


def test_a_translation_lands_in_the_feed_and_tells_the_pages(monkeypatch):
    st = server.State(server.Store(":memory:"), {})
    st.store.add_feed([{"post_id": "c/1", "channel": "kyiv_airdef", "ts": server.now_iso(), "text": "Бровари чисто",
                        "tags": [], "text_en": "Brovary clear", "en_fallback": True}])
    events = []
    monkeypatch.setattr(st, "publish", lambda ev: events.append(ev))
    monkeypatch.setattr(server._tr, "backends", lambda: [("fake", None)])
    monkeypatch.setattr(server._tr, "translate_to", lambda text, lang: ("Brovary : dégagé", True))
    tr = server.Translations(st)
    tr.add([{"post_id": "c/1", "text": "Бровари чисто"}], "fr")
    pid, text, lang = tr.q.popleft()
    out, ok = server._tr.translate_to(text, lang)
    st.store.set_translation(pid, lang, out)
    st.publish({"kind": "tr", "post_id": pid, "lang": lang})
    p = st.store.feed(5)[0]
    assert p["text_fr"] == "Brovary : dégagé" and p["en_mt"] is False
    assert events and events[0]["kind"] == "tr"


def test_the_page_asks_for_its_language_and_shows_french_when_there_is_some():
    html = open(server.os.path.join(server.STATIC, "kyiv.html"), encoding="utf-8").read()
    assert "'&lang='+LANG" in html                    # the feed request
    assert "qs.push('lang='+LANG)" in html             # the live stream (1.29: /api/stream?sync=…&lang=…)
    assert "(LANG==='fr'&&p.text_fr)||p.text_en" in html
