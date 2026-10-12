"""1.57.8 — a raion is named as a raion; the screen says when it is from, as the government app does.

The owner: "it's the Vyshhorod district here, not the Vyshhorod city (which is rightfully placed correctly on the
map)" — the map wrote "ВИШГОРОД" in the middle of the raion, 30 km from the town, and an alert over the whole raion read
"Вишгород". And, showing the government app's header ("Станом на: 12 жовтня о 20:27 (1692 день) · Оновлення через
05 с · ⟳"): "good to have".
"""
import os
import re
from datetime import date

ROOT = os.path.join(os.path.dirname(__file__), "..")
TAC = open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8").read()
I18N = open(os.path.join(ROOT, "static", "i18n.js"), encoding="utf-8").read()


def test_the_raions_of_kyiv_oblast_are_named_as_raions():
    adj = re.search(r"const RAION_ADJ=\{(.*?)\};", TAC).group(1)
    names = dict(re.findall(r"'?([\w-]+)'?:'([^']+)'", adj))
    assert names == {"bucha": "Бучанський", "vyshhorod": "Вишгородський", "brovary": "Броварський",
                     "boryspil": "Бориспільський", "obukhiv": "Обухівський", "bila-tserkva": "Білоцерківський",
                     "fastiv": "Фастівський"}
    # the map's labels, the official status of a place and the list of raions under alert all use the raion's name
    assert "${esc(raionLbl(r))}</text>" in TAC and "${RAION[r]}</text>" not in TAC
    assert "(u.obl==='14'&&RAION_ADJ[u.key])?raionFull(u.key)" in TAC
    assert "const rname=r=>RAION_ADJ[r]?raionFull(r)" in TAC
    assert "uk:(RAION_ADJ[r]||RAION_N[r][1])+' район'" in TAC
    # Ukrainian: "Вишгородський район" (on the map "Вишгородський р-н"); English and French from lt_unit_r
    assert "LANG==='uk'?RAION_ADJ[r]+' район'" in TAC and "LANG==='uk'?RAION_ADJ[r]+' р-н'" in TAC
    assert "lt_unit_r:'{0} raion'" in I18N and "lt_unit_r:'raion de {0}'" in I18N
    assert """.replace(/\\bde ([AEIOUYÉ])/,"d'$1")""" in TAC          # raion d'Obukhiv


def test_the_line_under_the_header_says_when_the_screen_is_from():
    bar = re.search(r'<div class="asof" id="asofbar">.*?</div></div>|<div class="asof" id="asofbar">.*?</button></div>', TAC).group(0)
    assert 'id="asof"' in bar and 'id="upd"' in bar and 'id="rfr"' in bar
    assert TAC.count('id="upd"') == 1                                  # it left the card's foot
    assert TAC.index('id="asofbar"') < TAC.index('<section id="mycard"')   # in the header, above the card: folded too
    for lang in ("aq_asof", "aq_day", "aq_live", "aq_next", "rf_now"):
        assert I18N.count(lang + ":'") == 3, lang
    assert "aq_asof:'Станом на {0} о {1}'" in I18N and "aq_day:'{0}-й день війни'" in I18N
    assert "aq_next:'Оновлення через {0} с'" in I18N
    assert "mc_upd_s" not in I18N and "mc_upd_m" not in I18N         # the old "updated 5 s ago" is gone
    # live: the line says so; without it the next ask is counted down; stale and offline keep their warning
    assert "else if(liveOK()) txt=t('aq_live');" in TAC
    assert "t('aq_next',String(Math.max(0,Math.ceil((nextPulse-Date.now())/1000))).padStart(2,'0'))" in TAC
    assert "txt=t('mc_stale'," in TAC and "t(down?'net_t':'net_wait')" in TAC


def test_the_day_of_the_war_is_counted_as_the_government_app_counts_it():
    assert "const WAR_D0=Date.UTC(2022,1,24);" in TAC
    assert "return Math.floor((Date.UTC(p[0],p[1]-1,p[2])-WAR_D0)/86400000)+1;" in TAC
    # the owner's screenshot: 12 October 2026 is day 1692
    assert (date(2026, 10, 12) - date(2022, 2, 24)).days + 1 == 1692
    assert "timeZone:TZ,year:'numeric'" in TAC                        # Kyiv's date, not the phone's


def test_the_refresh_button_asks_everything_again():
    js = re.search(r"\$\('rfr'\)\.onclick=async\(\)=>\{.*?\};", TAC, re.S).group(0)
    assert "lastFull=0" in js and "await pulse(true)" in js           # a full reload, not just the version ping
    assert "connect();" in js                                         # the live line opened again if it dropped
    assert "classList.add('spin')" in js and "classList.contains('spin')) return" in js
    assert "@media (prefers-reduced-motion:reduce){.rfr.spin svg{animation:none" in TAC
