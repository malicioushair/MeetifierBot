from meetifier.i18n import LOCALES, MESSAGES, LOCALE_LABELS, NAV_BTN, ORG_BTN, PAR_BTN, normalize_locale, t
from meetifier.keyboards import (
    calendars_keyboard, locale_keyboard, organizer_main_menu, participant_main_menu, flow_nav_keyboard,
)
from meetifier.service import get_or_create_user, set_locale


def test_flow_nav_keyboard_and_inline_row():
    markup = flow_nav_keyboard("en")
    assert {btn.text for row in markup.keyboard for btn in row} == {
        NAV_BTN["back"]["en"], NAV_BTN["cancel"]["en"],
    }
    from meetifier.db import Calendar
    calendars = [Calendar(id=1, owner_user_id=1, name="Math", timezone=0)]
    inline = calendars_keyboard(calendars, "o_invite", "ru", show_back=True)
    flat = [btn for row in inline.inline_keyboard for btn in row]
    assert any(btn.callback_data == "flow:back" for btn in flat)
    assert any(btn.callback_data == "flow:cancel" for btn in flat)
    assert flat[-1].text == t("ru", "btn_flow_cancel")


def test_normalize_locale():
    assert normalize_locale(None) == "en"
    assert normalize_locale("ru") == "ru"
    assert normalize_locale("SR-Latn") == "sr"
    assert normalize_locale("de") == "en"


def test_onboarding_covers_flow_and_features():
    for locale in LOCALES:
        org = t(locale, "org.onboarding")
        par = t(locale, "par.onboarding")
        assert len(org) < 4096 and len(par) < 4096
        assert "1." in org and "5." in org
        assert "1." in par and "5." in par
        assert "Google" in org
        assert "1440" in par


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
        user = await get_or_create_user(session, 42, 0)
        await session.commit()
        assert user.locale == "en"
    async with db.sessions() as session:
        user = await set_locale(session, 42, "ru", 0)
        assert user.locale == "ru"
    async with db.sessions() as session:
        user = await get_or_create_user(session, 42, 0)
        assert user.locale == "ru"
    await db.close()
