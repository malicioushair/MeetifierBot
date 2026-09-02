from datetime import date

from meetifier.i18n import t
from meetifier.keyboards import (
    DT_IGNORE,
    DT_PREFIX,
    date_calendar_keyboard,
    hour_keyboard,
    minute_keyboard,
    shift_month,
)


def test_shift_month():
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2025, 12, 1) == (2026, 1)
    assert shift_month(2026, 9, 0) == (2026, 9)


def test_date_calendar_keyboard_structure():
    markup = date_calendar_keyboard(2026, 9, "en")
    rows = markup.inline_keyboard
    # header + weekdays + 5 or 6 week rows + flow nav
    assert len(rows) >= 7
    header = rows[0]
    assert header[0].callback_data == f"{DT_PREFIX}:nav:2026-08"
    assert header[1].text == f"{t('en', 'month_9')} 2026"
    assert header[1].callback_data == DT_IGNORE
    assert header[2].callback_data == f"{DT_PREFIX}:nav:2026-10"
    assert [btn.text for btn in rows[1]] == [t("en", f"wd_{i}") for i in range(7)]
    day_callbacks = [
        btn.callback_data
        for row in rows[2:-1]
        for btn in row
        if btn.callback_data and btn.callback_data.startswith(f"{DT_PREFIX}:day:")
    ]
    assert f"{DT_PREFIX}:day:2026-09-01" in day_callbacks
    assert f"{DT_PREFIX}:day:2026-09-30" in day_callbacks
    assert all(len(cb) <= 64 for cb in day_callbacks)
    nav = rows[-1]
    assert any(btn.callback_data == "flow:back" for btn in nav)
    assert any(btn.callback_data == "flow:cancel" for btn in nav)


def test_date_calendar_marks_today():
    today = date.today()
    markup = date_calendar_keyboard(today.year, today.month, "ru")
    labels = {btn.text for row in markup.inline_keyboard for btn in row}
    assert f"·{today.day}·" in labels


def test_hour_and_minute_keyboards():
    hours = hour_keyboard("sr")
    hour_cbs = [btn.callback_data for row in hours.inline_keyboard[:-1] for btn in row]
    assert hour_cbs == [f"{DT_PREFIX}:hr:{h}" for h in range(24)]
    minutes = minute_keyboard("en")
    minute_cbs = [btn.callback_data for row in minutes.inline_keyboard[:-1] for btn in row]
    assert minute_cbs == [f"{DT_PREFIX}:mn:{m}" for m in range(0, 60, 5)]
    assert all(len(cb) <= 64 for cb in hour_cbs + minute_cbs)
