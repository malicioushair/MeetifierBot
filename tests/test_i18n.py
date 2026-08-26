from meetifier.i18n import LOCALES, MESSAGES, LOCALE_LABELS, ORG_BTN, PAR_BTN, normalize_locale, t
from meetifier.keyboards import locale_keyboard, organizer_main_menu, participant_main_menu
from meetifier.service import get_or_create_user, set_locale


def test_normalize_locale():
    assert normalize_locale(None) == "en"
    assert normalize_locale("ru") == "ru"
    assert normalize_locale("SR-Latn") == "sr"
    assert normalize_locale("de") == "en"


def test_translation_parity_and_format():
    assert set(MESSAGES) == set(LOCALES)
    keys = set(MESSAGES["en"])
    for locale in LOCALES:
        assert set(MESSAGES[locale]) == keys
        assert t(locale, "choose_language")
        assert "{name}" not in t(locale, "calendar_created", name="Math", id=1)
    assert "Напоминание" in t("ru", "reminder", minutes=30, title="X", time="T", calendar="C")
    assert "Podsetnik" in t("sr", "reminder", minutes=30, title="X", time="T", calendar="C")


def test_button_labels_cover_all_locales():
    for labels in (ORG_BTN, PAR_BTN):
        for action, variants in labels.items():
            assert set(variants) == set(LOCALES)
            assert len(set(variants.values())) >= 1


def test_locale_keyboard_buttons():
    markup = locale_keyboard("o_locale")
    assert len(markup.inline_keyboard) == 3
    assert [row[0].callback_data for row in markup.inline_keyboard] == [
        "o_locale:en", "o_locale:ru", "o_locale:sr"
    ]
    assert markup.inline_keyboard[1][0].text == LOCALE_LABELS["ru"]


def test_menus_change_with_locale():
    en = organizer_main_menu("en")
    ru = organizer_main_menu("ru")
    assert en.keyboard[0][0].text != ru.keyboard[0][0].text
    assert ORG_BTN["language"]["en"] in {btn.text for row in en.keyboard for btn in row}
    assert ORG_BTN["language"]["ru"] in {btn.text for row in ru.keyboard for btn in row}
    par = participant_main_menu("sr")
    assert any(btn.text == PAR_BTN["language"]["sr"] for row in par.keyboard for btn in row)


async def test_set_locale_persists(tmp_path):
    from meetifier.db import Database

    db = Database(f"sqlite+aiosqlite:///{tmp_path}/locale.db")
    await db.init()
    async with db.sessions() as session:
        user = await get_or_create_user(session, 42, "UTC")
        await session.commit()
        assert user.locale == "en"
    async with db.sessions() as session:
        user = await set_locale(session, 42, "ru", "UTC")
        assert user.locale == "ru"
    async with db.sessions() as session:
        user = await get_or_create_user(session, 42, "UTC")
        assert user.locale == "ru"
    await db.close()
