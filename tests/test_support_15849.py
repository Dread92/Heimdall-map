"""1.58.49 — the support page: one button a row (a tap or a long press copies), PayPal for donors abroad, and the jar on a
phone as one more map control. (Its bank-transfer block — the IBAN, the purpose, the NBU link — was replaced in 1.58.51
by the NGO's fundraiser link: tests/test_support_15851.py.)"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N = _read("static", "kyiv.html"), _read("static", "i18n.js")


def test_one_button_a_row_and_press_and_hold():
    sup = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]
    assert '<button type="button" class="sup supb${cls?\' \'+cls:\'\'}" data-copy="${esc(addr)}"' in sup
    assert "btn.onclick=go; btn.oncontextmenu=e=>{ e.preventDefault(); go(); };" in sup
    assert "-webkit-touch-callout:none" in PAGE
    # PayPal for donors abroad: its donation page ("two options — the monobank link, the PayPal link"), the address if none
    assert "paypal:'https://www.paypal.com/donate/?hosted_button_id=2KGHU5SWLAALE'," in I18N
    assert "/^https:\\/\\/www\\.paypal\\.com\\/donate\\/\\?hosted_button_id=[A-Z0-9]{8,20}$/.test(CONTACT.paypal||'')" in sup
    assert '<a class="payb sec pp" href="${esc(pp)}" target="_blank" rel="noopener noreferrer">' in sup   # 1.58.52's button
    assert ":row('PayPal',CONTACT.ngo,'cp1')}" in sup and len(re.findall(r"\bsup_pp_btn:'", I18N)) == 3


def test_the_jar_on_a_phone_is_one_more_map_control():
    # the owner, on a phone: "the jar takes too much space, and it stands out too much"
    ph = PAGE[PAGE.index("/* 1.58.49, the owner (on a phone)"):]
    ph = ph[:ph.index("\n}\n")]
    assert "@media (max-width:999px){" in ph
    assert ".jarbtn{width:44px;height:44px;padding:0;gap:0;border:1px solid var(--line2);background:rgba(11,13,17,.92);animation:none}" in ph
    assert ".jarcap{display:none}" in ph and ".jarhint{bottom:64px}" in ph
    assert '<span class="jarcap" data-t="jar_cap" aria-hidden="true">' in PAGE and 'data-t-aria="jar_aria"' in PAGE   # still named
