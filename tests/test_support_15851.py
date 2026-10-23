"""1.58.51 — the support page gives the NGO's fundraiser: one link to its payment page, and its QR code for a computer's
screen. Its head, 23 Oct: "for Heimdall we use the link, the QR code… the official bank account is too long and asks a lot
of the user; the link takes them straight to the payment page". The owner: "replace it with this — but keep PayPal"."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = "https://mobile-app.pumb.ua/1c8Ic"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N, QR = _read("static", "kyiv.html"), _read("static", "i18n.js"), _read("static", "pumb-qr.svg")
SUP = PAGE[PAGE.index("function supportSheet(){"):PAGE.index("$('supbtn').onclick")]


def test_the_fundraiser_link_and_its_qr():
    assert f"fund:'{LINK}'," in I18N
    assert "/^https:\\/\\/mobile-app\\.pumb\\.ua\\/[A-Za-z0-9]{4,32}$/.test(CONTACT.fund||'')" in SUP
    assert '<a class="supqrb supfund" href="${esc(fund)}" target="_blank" rel="noopener noreferrer">' in SUP
    assert '<img src="/static/pumb-qr.svg" width="132" height="132" alt="">' in SUP
    assert QR.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 33 33"') and "<script" not in QR
    for k in ("sup_fund", "sup_fund_for", "sup_fund_qr", "sup_fund_btn"):
        assert len(re.findall(r"\b" + k + r":'", I18N)) == 3, k
    # what the fundraiser is for, in its own words — not "the servers"
    assert "sup_fund_for:'На підтримку військових підрозділів, мобільних груп ППО та медиків" in I18N


def test_the_bank_block_is_gone_and_paypal_stays():
    for gone in ("iban:", "ibanLink", "ibanPurpose", "sup_bank:", "sup_recipient:", "sup_purpose:", "sup_qr:", "sup_qr_btn:"):
        assert gone not in I18N, gone
    assert "CONTACT.iban" not in PAGE and "nbu-qr.svg" not in PAGE
    assert not os.path.exists(os.path.join(ROOT, "static", "nbu-qr.svg"))
    assert "${pp?`<div class=\"suph\">${esc(t('sup_paypal'))}</div>" in SUP


def test_no_card_number_anywhere():
    # a card number in a post is never repeated: the payment page holds it, not Heimdall
    for txt in (I18N, PAGE):
        assert not re.search(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", txt)
