"""1.58.49 — the support page with the NGO's official account. Its head: "only with official data" — "only the IBAN",
"and ГО "07300"", and the payment purpose; "is it possible to make it one button, or press and hold to copy?"; "better with
a link of course… or a QR" (the link tested by him: it works). The jar (once set) and PayPal for donors abroad stay."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, SITE_QR = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "nbu-qr.svg")
LINK = ("https://bank.gov.ua/qr/QkNECjAwMgoxClVDVAoK0JPQniAiMDczMDAt0JvQrtCU0Jgg0JTQm9CvINCb0K7QlNCV0JkiClVBOTczMjIwMDEw"
        "MDAwMDI2MDA2NzAwMDAwMjkxCgozOTE4NTgzMgoKCgoK")


def test_the_official_data():
    assert "iban:'UA973220010000026006700000291'," in I18N and "ibanName:'ГО \"07300\"'," in I18N
    assert "ibanPurpose:'Добровільний внесок на здійснення статутної діяльності ГО «07300 — Люди для людей»'," in I18N
    assert f"ibanLink:'{LINK}'," in I18N
    import base64
    payload = base64.urlsafe_b64decode(LINK.rsplit("/", 1)[1] + "==").decode("utf-8").split("\n")
    assert payload[:4] == ["BCD", "002", "1", "UCT"] and payload[6] == "UA973220010000026006700000291" and payload[8] == "39185832"
    for k in ("sup_bank", "sup_recipient", "sup_purpose", "sup_paypal", "sup_qr", "sup_qr_btn"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k


def test_one_button_a_row_and_press_and_hold():
    sup = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]
    assert '<button type="button" class="sup supb${cls?\' \'+cls:\'\'}" data-copy="${esc(addr)}"' in sup
    assert "btn.onclick=go; btn.oncontextmenu=e=>{ e.preventDefault(); go(); };" in sup
    assert "-webkit-touch-callout:none" in PAGE
    assert ".sup.supi b{flex:1 1 100%;white-space:nowrap}" in PAGE   # the IBAN on one line, never broken
    # PayPal for donors abroad: its donation page ("two options — the monobank link, the PayPal link"), the address if none
    assert "paypal:'https://www.paypal.com/donate/?hosted_button_id=2KGHU5SWLAALE'," in I18N
    assert "/^https:\\/\\/www\\.paypal\\.com\\/donate\\/\\?hosted_button_id=[A-Z0-9]{8,20}$/.test(CONTACT.paypal||'')" in sup
    assert '<a class="supqrb suppp" href="${esc(pp)}" target="_blank" rel="noopener noreferrer">' in sup
    assert ":row(t('sup_paypal'),CONTACT.ngo,'cp1')}" in sup and len(re.findall(r"\bsup_pp_btn:'", I18N)) == 3
    assert "/^https:\\/\\/bank\\.gov\\.ua\\/qr\\/[A-Za-z0-9_-]{20,600}$/.test(CONTACT.ibanLink||'')" in sup


def test_the_link_and_its_qr():
    sup = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]
    assert '<a class="supqrb" href="${esc(qr)}" target="_blank" rel="noopener noreferrer">' in sup
    assert '<img src="/static/nbu-qr.svg" width="132" height="132" alt="">' in sup
    assert SITE_QR.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 57 57"') and "<script" not in SITE_QR


def test_the_jar_on_a_phone_is_one_more_map_control():
    # the owner, on a phone: "the jar takes too much space, and it stands out too much"
    ph = PAGE[PAGE.index("/* 1.58.49, the owner (on a phone)"):]
    ph = ph[:ph.index("\n}\n")]
    assert "@media (max-width:999px){" in ph
    assert ".jarbtn{width:44px;height:44px;padding:0;gap:0;border:1px solid var(--line2);background:rgba(11,13,17,.92);animation:none}" in ph
    assert ".jarcap{display:none}" in ph and ".jarhint{bottom:64px}" in ph
    assert '<span class="jarcap" data-t="jar_cap" aria-hidden="true">' in PAGE and 'data-t-aria="jar_aria"' in PAGE   # still named
