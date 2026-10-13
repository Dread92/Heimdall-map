"""1.56.3: in Chernihiv oblast a drone faces into Ukraine; no course from another line of the same post.

The owner (10 Oct 2026), a screenshot of two drones near Liubech drawn heading north-west: "in the Chernihiv region, by
default the drones must always face into Ukraine when no direction is given — it is extremely unlikely that the drone
goes back to Belarus or Russia." The course was Kiptiv → Liubech: two targets of one @chernihiv_nebo post.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.now(timezone.utc)


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def _marks(posts):
    st = server.State(server.Store(":memory:"), {})
    return {m["id"]: m for m in st._marks_from_posts(posts, [], {}, evidence=True)}


POSTS = [{"post_id": "chernihiv_nebo/100", "channel": "chernihiv_nebo", "ts": (NOW - timedelta(minutes=10)).isoformat(),
          "text": "1 біля Кіптів\n1 Любеч\n1 Сеньківка", "tags": []},
         {"post_id": "chernihiv_nebo/101", "channel": "chernihiv_nebo", "ts": (NOW - timedelta(minutes=5)).isoformat(),
          "text": "1 Любеч", "tags": []}]


def _post(n, minutes, text):
    return {"post_id": f"chernihiv_nebo/{n}", "channel": "chernihiv_nebo", "ts": (NOW - timedelta(minutes=minutes)).isoformat(),
            "text": text, "tags": []}


def test_no_course_between_two_targets():
    with mock.patch.object(server, "outward", lambda m, b: False):            # the border rule aside
        ms = _marks(POSTS)
        one = _marks([_post(200, 10, "Сеньківка"), _post(201, 5, "Любеч")])
    assert ms["chernihiv_nebo/100#1"]["place"] == "Любеч" and all(m.get("heading") is None for m in ms.values())
    assert one["chernihiv_nebo/201#0"].get("heading") is not None             # one target each time: its course


def test_a_course_worked_out_back_across_the_border_is_not_kept():
    ms = _marks([_post(200, 10, "Козелець"), _post(201, 5, "Любеч")])
    m = ms["chernihiv_nebo/201#0"]                                             # Kozelets → Liubech: north, to Belarus
    assert m["place"] == "Любеч" and m.get("heading") is None
    back = _marks([_post(300, 10, "Любеч"), _post(301, 5, "Козелець")])["chernihiv_nebo/301#0"]
    assert back.get("heading") is not None                                    # into Ukraine: kept
    liubech = {"oblast_uid": "25", "lon": 30.65, "lat": 51.70}
    assert server.outward(liubech, 324) and server.outward(liubech, 0) and not server.outward(liubech, 190)
    assert not server.outward(dict(liubech, oblast_uid="14"), 324)           # Chernihiv oblast only (INWARD)


def test_a_drone_with_no_course_faces_into_ukraine():
    m = {"type": "unknown", "oblast_uid": "25", "lon": 30.65, "lat": 51.70}
    server.inward_face(m)
    assert 170 <= m["face"] <= 200                                              # towards Kyiv: south
    for other in ({"type": "drones", "oblast_uid": "25", "lon": 31.3, "lat": 51.5, "heading": 330},     # a course: its own
                  {"type": "drones", "oblast_uid": "25", "lon": 31.3, "lat": 51.5, "status": "down"},
                  {"type": "cruise_missiles", "oblast_uid": "25", "lon": 31.3, "lat": 51.5},
                  {"type": "drones", "oblast_uid": "14", "lon": 30.8, "lat": 50.5}):
        server.inward_face(other)
        assert "face" not in other, other
    ms = _marks(POSTS)
    assert all(server.inward_face(x) is None and x.get("face") is not None for x in ms.values())


def test_the_pages_turn_the_glyph_only():
    page, light, doc, safety = _read("static/kyiv.html"), _read("static/light.html"), _read("docs/TECHNICAL.md"), _read("docs/SAFETY.md")
    assert "const fc=m.face!=null?m.face:0;\n  if(m.heading==null) return fc;" in page and "'face_track':m.face_by==='south'?'face_south':'face_note'" in page
    assert "const markOrient=m=>(m.type!=='unknown'||lDr(m))?(statedCourse(m)?m.heading:m.face||0):0;" in light
    assert "inward_face(m)" in _read("app/server.py") and "INWARD" in doc and "a drone faces into Ukraine" in safety
    # no course is made of it: the course ray, the heading text and the ETA read `heading`, never `face`
    assert "m.face" not in page.split("function inboundInfo")[1][:600]


def test_the_patterns_count_only_stated_courses():
    assert "evidence NOT LIKE '%bearing between the two latest reports%'" in _read("app/server.py")


def test_the_gazetteer_is_where_openstreetmap_puts_it():
    import geo
    assert geo.PLACES["Гнідин"][:2] == (30.7058, 50.3287)                    # it was 5.8 km east: "never reported there"
    assert geo.PLACES["Березань"][:2] == (31.4689, 50.3133)                   # 11 km
