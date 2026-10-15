"""1.58.29 — a trajectory as the posts gave it, in one piece.

The owner (15 Oct 2026, 03:28, two screenshots: another map drawing one jet drone from Pyriatyn past Borshchiv towards
Stare, and Heimdall's): "it would be cool to define the trajectories properly", then "despite the channels placing it, the
app did not place the drone". @chyste_nebo had written, among its other targets: "Від Пирятина реактивний на Яготин" (03:12),
"Яготин північ на малу супоївку", "Не спостерігається", "Березань реактивний зі сходу", "Борщів", "На любарці", "На
Сошників", "На Кийлів", "На Українку" (03:28). Heimdall had it in three pieces: the jet at Berezan (closed by "Не
спостерігається", posted before it), and two marks of no type at Borshchiv and Liubartsi — a bare place name never
continued a drone's track; "На любарці" was read as being at Liubartsi; Borshchiv was given a course from Slavutych, 140
km away, the channel's report of another target 20 s before.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import geo
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "tests", "data", "chyste_nebo_2026_10_15_0328.json"), encoding="utf-8") as _f:
    NIGHT = json.load(_f)["posts"]


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def _marks():
    now = datetime.now(timezone.utc)
    st = server.State(server.Store(":memory:"), {"track_stale_minutes": 5, "marker_ttl_minutes": 45})
    server.Telegram(st, {}).ingest("chyste_nebo", [(p["id"], (now - timedelta(seconds=p["ago"])).isoformat(), p["text"])
                                                   for p in NIGHT], "tg:chyste_nebo")
    st.markers()
    return {m["id"]: m for m in st.markers()}


def test_the_jet_drone_is_one_track_from_yahotyn_to_borshchiv_heading_for_ukrainka():
    ms = _marks()
    jet = ms["chyste_nebo/232480#0"]                                      # "На Українку", the last post
    assert jet["type"] == "drones" and jet["jet"]                         # "реактивний", as its Berezan report said
    assert jet["place"] == "Борщів" and jet["target"] == "Українка"       # where it was last said to be, and where to
    assert 200 <= jet["heading"] <= 270
    hist = [h["place"] for h in jet["history"]]
    assert "Березань" in hist and "Яготин" in hist                         # Yahotyn, Berezan, Borshchiv: one target
    assert "as this track's report at" in jet["evidence"]["type"]["method"]
    # nothing of it left as a mark of its own: no second piece at Berezan, Liubartsi or Borshchiv
    assert not [m for m in ms.values() if m["id"] != jet["id"] and m.get("place") in ("Березань", "Любарці", "Борщів")]


def test_the_regular_shahed_is_another_target():
    ms = _marks()
    lk = [m for m in ms.values() if str(m.get("place", "")).startswith("Лук'янівка")]
    assert lk and all(not m.get("jet") for m in lk)                        # "звичайний" never continued by a jet
    jet = ms["chyste_nebo/232480#0"]
    assert not any(str(h["place"]).startswith("Лук'янівка") for h in jet["history"])


def test_na_liubartsi_is_where_it_goes_and_no_course_from_another_target():
    (m,) = geo.parse_for_channel("chyste_nebo", "На любарці")
    assert m["place"] == "→ Любарці" and m["dest_only"]
    assert [x["place"] for x in geo.parse_for_channel("chyste_nebo", "на Позняках")] == ["Позняки"]   # still: it is there
    st = server.State(server.Store(":memory:"), {})
    now = datetime.now(timezone.utc)
    posts = [{"post_id": f"chyste_nebo/{p['id'].split('/')[1]}", "channel": "chyste_nebo", "ts": (now - timedelta(seconds=p["ago"])).isoformat(),
              "text": p["text"], "tags": []} for p in NIGHT]
    raw = {m["id"]: m for m in st._marks_from_posts(sorted(posts, key=lambda p: p["ts"]), [], {})}
    assert raw["chyste_nebo/232472#0"]["place"] == "Борщів" and raw["chyste_nebo/232472#0"].get("heading") is None   # not from Slavutych


def test_a_target_reported_after_lost_is_found_again():
    assert "if(dt<(s.status==='lost'?0:-2)||dt>40) continue;" in _read("static", "kyiv.html")
    assert "if(dt<(s.status==='lost'?0:-2)||dt>40) continue;" in _read("static", "light.html")
    assert 'if dt < (0 if s_.get("status") == "lost" else -2) or dt > 40:' in _read("app", "chanpost.py")
