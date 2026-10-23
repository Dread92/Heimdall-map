"""1.58.51 — the owner's Ukrainian wording for the feedback form and the shelter row ("some automated translations in the
forms and cards sound a bit clunky"), string by string. English and French are unchanged."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


I18N, SH = _read("static", "i18n.js"), _read("static", "shelters.js")


def test_the_feedback_form():
    assert ("fb_text_ph:'Опишіть проблему або вашу ідею. Якщо це стосується позначки на мапі — вкажіть, де і коли ви її "
            "бачили.'") in I18N
    assert "fb_contact:'Контакт для зворотного зв’язку (Telegram @username або email)'" in I18N
    assert ("fb_noplace:'Не вказуйте свою адресу чи поточне місцеперебування. Разом із текстом передаються лише сторінка, "
            "її мова, версія та модель телефону. Ваша геопозиція ніколи не передається.'") in I18N
    for old in ("Про позначку: коли й де", "Контакт, якщо хочете відповідь", "ніколи ваші місця"):
        assert old not in I18N
    for k in ("fb_text_ph:", "fb_contact:", "fb_noplace:"):
        assert I18N.count(k) == 3, k                       # still in the three languages


def test_the_shelter_row():
    assert "any1:'найближче укриття:'" in SH and "будь-яке" not in SH
    assert "any1:'nearest of any kind:'" in SH and "any1:'le plus proche, tout type :'" in SH
