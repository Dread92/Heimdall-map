"""1.58.52 — the support page puts Heimdall first. The owner: "inside the Heimdall app the top priority should definitely be
supporting Heimdall … clean and straightforward": the main card (Heimdall's fundraiser — what it pays for, its QR code, the
one bright button), the NGO's fundraiser under it as a quiet banner, PayPal for donations from abroad at the bottom; clear
primary and secondary buttons, one yellow; each button names where it goes."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HD, NGO = "https://mobile-app.pumb.ua/1c8LW", "https://mobile-app.pumb.ua/1c8Ic"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, QR = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "heimdall-qr.svg")
SUP = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]


def test_heimdall_first_the_ngo_second_paypal_last():
    assert f"fundHd:'{HD}'," in I18N and f"fundNgo:'{NGO}'," in I18N
    assert "const pumb=u=>/^https:\\/\\/mobile-app\\.pumb\\.ua\\/[A-Za-z0-9]{4,32}$/.test(u||'')?u:'';" in SUP
    i, j, k = SUP.index('<div class="payc">'), SUP.index('<a class="payngo"'), SUP.index('<a class="payb sec pp"')
    assert i < j < k
    assert '<a class="payb pri" href="${esc(hd)}" target="_blank" rel="noopener noreferrer">' in SUP
    assert SUP.count('class="payb pri"') == 1                       # one bright button on the page
    assert '<img src="/static/heimdall-qr.svg" width="96" height="96" alt="">' in SUP
    assert QR.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 33 33"') and "<script" not in QR
    assert not os.path.exists(os.path.join(ROOT, "static", "pumb-qr.svg"))
    assert "footerHTML(" not in SUP                                # the cards alone: no footer under them


def test_the_owner_s_words():
    assert ("sup_hd_b:'Внески забезпечують безперебійну роботу серверів, покривають хостинг, підписки, тестування, підтримку "
            "команди та весь цикл розробки, щоб застосунок завжди залишався доступним та не містив рекламних інтеграцій.'") in I18N
    assert "sup_hd_h:'Збір на розвиток Heimdall'" in I18N and "sup_ngo_h:'Збір ГО «07300»:'" in I18N
    assert ("sup_ngo_b:'логістика, перегон, ремонт, пальне, шини, запчастини й розхідники для авто ЗСУ. Закупівля дронів, оптики, "
            "генераторів, павербанків, зарядних станцій, обігрівачів, інструментів та матеріалів. Оформлення документів й "
            "операційна діяльність.'") in I18N
    for k in ("sup_hd_h", "sup_hd_b", "sup_hd_btn", "sup_qr_pc", "sup_ngo_h", "sup_ngo_b", "sup_abroad", "sup_pumb", "sup_pp_btn"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k
    for gone in ("sup_fund:", "sup_fund_for:", "sup_fund_btn:", "sup_paypal:", "fund:'"):
        assert gone not in I18N, gone


def test_one_yellow_and_the_names_on_the_buttons():
    assert ".payb.pri{background:var(--ua-yellow);border:1px solid var(--ua-yellow);color:#111!important}" in PAGE
    assert ".payb.sec{background:transparent;border:1px solid var(--line2);color:var(--ink)!important}" in PAGE
    assert "#ffc439" not in PAGE and "#f2c14e;color:#12161c!important" not in PAGE       # PayPal's own and the jar's yellows
    # 1.58.57: the names became the bank's and PayPal's own logos (tests/test_logos_15857.py), their names the alt text
    assert "${esc(t('sup_hd_btn'))}</span>${lgP}</a>" in SUP and "${esc(t('sup_pp_btn'))}</span>${lgPP}</a>" in SUP
    assert "body.lite .payqr{display:none}" in PAGE
