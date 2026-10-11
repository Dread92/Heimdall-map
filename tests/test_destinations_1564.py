"""1.56.4: a list of destinations is drawn at the one the target reaches first; Bucha in all its cases.

The owner (11 Oct 2026), a jet drone drawn in the middle of Kyiv: "the post is talking about Bucha, yet the drone is
again put randomly in the middle of the city" — monitor: "Реактивний БпЛА на Київ/Ірпінь/Бучу".
"""
import os

import geo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def _one(ch, txt):
    ms = geo.parse_for_channel(ch, txt)
    assert len(ms) == 1, (txt, ms)
    return ms[0]


def test_the_list_is_drawn_at_the_outermost_and_kept_whole():
    for ch in ("war_monitor", "kyiv_airdef", "chyste_nebo"):
        m = _one(ch, "Реактивний БпЛА на Київ/Ірпінь/Бучу.")
        assert (m["place"], m["target"], m["approach"]) == ("→ Буча", "Буча", True) and (m["lon"], m["lat"]) == geo.PLACES["Буча"][:2]
        assert m["targets"] == ["Київ", "Ірпінь", "Буча"]
    assert _one("kyiv_airdef", "БпЛА на Ірпінь/Бучу")["target"] == "Буча"
    assert _one("war_monitor", "Реактивний БпЛА на Київ")["target"] == "Київ" and "targets" not in _one("war_monitor", "Реактивний БпЛА на Київ")
    # outside Kyiv and its oblast: the first named, as before
    m = _one("kpszsu", "БпЛА на Сумщині курсом на Ромни/Липову Долину")
    assert m["target"] == "Ромни" and m["targets"] == ["Ромни", "Липова Долина"]


def test_approach_pick():
    assert geo.approach_pick(["Київ", "Ірпінь", "Буча"]) == "Буча"
    assert geo.approach_pick(["Київ"]) == "Київ" and geo.approach_pick([]) is None
    assert geo.approach_pick(["Оболонь", "Київ"]) in ("Оболонь", "Київ")              # all in the city: the farthest out
    assert geo.approach_pick(["Вишневе", "Боярка"]) == "Боярка"


def test_bucha_in_its_cases():
    for txt in ("БпЛА на Бучу", "Шахед курсом на Бучу", "БпЛА у Бучі", "БпЛА над Бучею"):
        assert _one("kyiv_airdef", txt)["place"].replace("→ ", "") == "Буча", txt
    assert geo.parse_for_channel("kyiv_airdef", "Повідомте мені, якщо щось") == []        # "мені" is not Мена


def test_the_pages_say_the_whole_list():
    i18n, page, light = _read("static/i18n.js"), _read("static/kyiv.html"), _read("static/light.html")
    assert "const apprTo=m=>(m.targets&&m.targets.length>1?m.targets:[m.target||m.place||'']).map(pn).join(' / ');" in i18n
    assert page.count("apprTo(") == 3 and "t('lt_to',apprTo(m))" in light
    assert "approach_pick" in _read("docs/TECHNICAL.md")
