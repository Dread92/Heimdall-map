"""1.58.51 — the support page's IBAN block went: its NGO's head, 23 Oct: "the official bank account is too long and asks a
lot of the user; the link takes them straight to the payment page". (1.58.52 made the page Heimdall's first:
tests/test_support_15852.py.)"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


PAGE, I18N = _read("static", "kyiv.html"), _read("static", "i18n.js")


def test_the_bank_block_is_gone():
    for gone in ("iban:", "ibanLink", "ibanPurpose", "sup_bank:", "sup_recipient:", "sup_purpose:", "sup_qr:", "sup_qr_btn:"):
        assert gone not in I18N, gone
    assert "CONTACT.iban" not in PAGE and "nbu-qr.svg" not in PAGE
    assert not os.path.exists(os.path.join(ROOT, "static", "nbu-qr.svg"))


def test_no_card_number_anywhere():
    # a card number in a post is never repeated: the payment page holds it, not Heimdall
    for txt in (I18N, PAGE):
        assert not re.search(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", txt)
