from __future__ import annotations

from typing import Any

LOCALES = ("en", "ru", "sr")
DEFAULT_LOCALE = "en"

LOCALE_LABELS = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "sr": "🇷🇸 Srpski",
}

# Reply-keyboard action keys -> per-locale labels
ORG_BTN = {
    "calendars": {"en": "📅 Calendars", "ru": "📅 Календари", "sr": "📅 Kalendari"},
    "new_calendar": {"en": "➕ New calendar", "ru": "➕ Новый календарь", "sr": "➕ Novi kalendar"},
    "new_event": {"en": "➕ New event", "ru": "➕ Новое событие", "sr": "➕ Novi događaj"},
    "events": {"en": "📋 Events", "ru": "📋 События", "sr": "📋 Događaji"},
    "invite": {"en": "🔗 Invite", "ru": "🔗 Пригласить", "sr": "🔗 Pozovi"},
    "reschedule": {"en": "✏️ Reschedule", "ru": "✏️ Перенести", "sr": "✏️ Pomeri"},
    "cancel_event": {"en": "❌ Cancel event", "ru": "❌ Отменить событие", "sr": "❌ Otkaži događaj"},
    "confirmations": {"en": "✅ Confirmations", "ru": "✅ Подтверждения", "sr": "✅ Potvrde"},
    "google_link": {"en": "🔗 Link Google", "ru": "🔗 Связать Google", "sr": "🔗 Poveži Google"},
    "google_map": {"en": "📎 Map to Google", "ru": "📎 Привязать к Google", "sr": "📎 Mapiraj na Google"},
    "google_import": {"en": "⬇️ Import Google", "ru": "⬇️ Импорт Google", "sr": "⬇️ Uvoz Google"},
    "google_sync": {"en": "🔄 Sync Google", "ru": "🔄 Синхронизация Google", "sr": "🔄 Sinhronizuj Google"},
    "google_adopt": {"en": "📣 Invite Google guests", "ru": "📣 Пригласить гостей Google", "sr": "📣 Pozovi Google goste"},
    "language": {"en": "🌐 Language", "ru": "🌐 Язык", "sr": "🌐 Jezik"},
    "help": {"en": "❓ Help", "ru": "❓ Помощь", "sr": "❓ Pomoć"},
}

PAR_BTN = {
    "upcoming": {"en": "📅 Upcoming", "ru": "📅 Ближайшие", "sr": "📅 Predstojeći"},
    "confirm": {"en": "✅ Confirm", "ru": "✅ Подтвердить", "sr": "✅ Potvrdi"},
    "subscriptions": {"en": "📋 Subscriptions", "ru": "📋 Подписки", "sr": "📋 Pretplate"},
    "timezone": {"en": "🌍 Timezone", "ru": "🌍 Часовой пояс", "sr": "🌍 Vremenska zona"},
    "reminders": {"en": "⏰ Reminders", "ru": "⏰ Напоминания", "sr": "⏰ Podsetnici"},
    "mute": {"en": "🔇 Mute", "ru": "🔇 Без звука", "sr": "🔇 Isključi"},
    "unmute": {"en": "🔊 Unmute", "ru": "🔊 Включить звук", "sr": "🔊 Uključi"},
    "unsubscribe": {"en": "🚫 Unsubscribe", "ru": "🚫 Отписаться", "sr": "🚫 Otkaži pretplatu"},
    "language": {"en": "🌐 Language", "ru": "🌐 Язык", "sr": "🌐 Jezik"},
    "help": {"en": "❓ Help", "ru": "❓ Помощь", "sr": "❓ Pomoć"},
}

NAV_BTN = {
    "back": {"en": "⬅️ Back", "ru": "⬅️ Назад", "sr": "⬅️ Nazad"},
    "cancel": {"en": "✖️ Cancel", "ru": "✖️ Отмена", "sr": "✖️ Otkaži"},
}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "org.welcome": "Welcome to Meetifier Organizer!",
        "par.welcome": "Welcome to Meetifier Participant!",
        "org.onboarding": (
            "Typical flow\n"
            "1. Create a calendar\n"
            "2. Add events\n"
            "3. Send an invite link\n"
            "4. Participants subscribe in the Participant Bot and get reminders\n"
            "5. Reschedule or cancel when plans change; check confirmations\n\n"
            "Menu features\n"
            "📅 Calendars — list your calendars\n"
            "➕ New calendar — name + UTC offset hours (e.g. 1 for UTC+1)\n"
            "➕ New event — title, start, duration, recurrence (once / weekly / monthly)\n"
            "📋 Events — next event or this week\n"
            "🔗 Invite — share a Telegram link so people can subscribe\n"
            "✏️ Reschedule — pick an event and set a new start time\n"
            "❌ Cancel event — cancel and notify subscribers\n"
            "✅ Confirmations — who confirmed attendance\n"
            "🔗 Link Google / 📎 Map / ⬇️ Import / 🔄 Sync / 📣 Invite Google guests — optional Google Calendar sync\n"
            "🌐 Language — switch en / ru / sr\n"
            "❓ Help — command examples\n\n"
            "Tip: most actions use buttons; you can also type commands from Help."
        ),
        "par.onboarding": (
            "Typical flow\n"
            "1. Open an invite link from an organizer (or tap Subscribe)\n"
            "2. Set your UTC offset in hours (e.g. 1 for UTC+1)\n"
            "3. Optionally set reminder times per calendar\n"
            "4. Check upcoming events and confirm attendance\n"
            "5. Mute or unsubscribe when you no longer need a calendar\n\n"
            "Menu features\n"
            "📅 Upcoming — next event or this week\n"
            "✅ Confirm — mark that you will attend\n"
            "📋 Subscriptions — calendars you follow\n"
            "🌍 Timezone — UTC offset in hours used for how times are shown to you\n"
            "⏰ Reminders — minutes before the event (e.g. 1440,30 = 1 day and 30 min)\n"
            "🔇 Mute / 🔊 Unmute — pause or resume reminders for a calendar\n"
            "🚫 Unsubscribe — leave a calendar and stop jobs\n"
            "🌐 Language — switch en / ru / sr\n"
            "❓ Help — command examples\n\n"
            "You must Start this bot before Telegram can deliver reminders."
        ),
        "choose_language": "Choose your language:",
        "language_updated": "Language updated.",
        "main_menu": "Main menu:",
        "cancelled": "Cancelled.",
        "flow_cancelled": "Cancelled. All progress for this action was discarded.",
        "nothing_to_cancel": "Nothing to cancel.",
        "nothing_to_cancel_event": "Nothing to cancel. Use ❌ Cancel event to cancel an event.",
        "btn_back": "⬅️ Back",
        "btn_flow_cancel": "✖️ Cancel",
        "error": "Error: {error}",
        "try_again": "Please try again:",
        "wrong_command": "Wrong command format. Send /help for examples.",
        "no_calendars": "No calendars yet.",
        "no_calendars_create": "No calendars yet. Create one first.",
        "calendar_created": "Calendar created: {name} (ID {id})",
        "enter_calendar_name": "Enter calendar name:",
        "enter_timezone": "Enter UTC offset in hours (e.g. 3 for UTC+3, -5 for UTC-5):",
        "what_to_see": "What would you like to see?",
        "choose_calendar": "Choose a calendar:",
        "choose_calendar_invite": "Choose a calendar to invite to:",
        "choose_calendar_event": "Choose a calendar for the new event:",
        "choose_calendar_reschedule": "Choose a calendar to reschedule an event in:",
        "choose_calendar_confirmations": "Choose a calendar to view confirmations:",
        "choose_calendar_sync": "Choose a calendar to sync:",
        "choose_calendar_map": "Choose a Meetifier calendar to map:",
        "choose_calendar_adopt": "Choose the calendar whose Google attendees should be invited:",
        "choose_event": "Choose an event:",
        "choose_occurrence": "Choose a date:",
        "choose_occurrence_cancel": "Choose a date to cancel:",
        "choose_occurrence_confirm": "Choose a date to confirm:",
        "choose_event_cancel": "Choose an event to cancel:",
        "event_dates_header": "{title}:",
        "no_future_events": "No future events in this calendar.",
        "no_events_week": "No events for this week.",
        "no_events_upcoming": "No upcoming events.",
        "enter_event_title": "Enter event title:",
        "enter_start_time": "Pick a start date (or type YYYY-MM-DD HH:MM):",
        "pick_start_hour": "Pick hour for {date} (or type YYYY-MM-DD HH:MM):",
        "pick_start_minute": "Pick minutes for {date} {hour}:xx (or type YYYY-MM-DD HH:MM):",
        "enter_duration": "Duration in minutes:",
        "enter_weeks": "Number of weeks (1 for one-time, 2..52 for weekly):",
        "choose_pattern": "Choose a recurrence pattern:",
        "choose_weekdays": "Choose weekdays (tap to toggle), then Done:",
        "enter_interval_weeks": "Repeat every how many weeks? (1 = every week, 2 = every second week, …):",
        "choose_monthly_pos": "Which occurrence in the month?",
        "choose_monthly_weekday": "Which weekday?",
        "enter_occurrence_count": "How many occurrences to create? (1..104):",
        "choose_edit_scope": "Apply to this date only, or this and all following dates?",
        "enter_new_start": "Pick a new start date (or type YYYY-MM-DD HH:MM):",
        "events_created": "Created {count} event(s). IDs: {ids}",
        "event_cancelled_notified": "Event cancelled and subscribers notified.",
        "event_rescheduled_notified": "Event rescheduled and subscribers notified.",
        "events_updated_count": "Updated {count} occurrence(s) and notified subscribers.",
        "events_cancelled_count": "Cancelled {count} occurrence(s) and notified subscribers.",
        "cancel_this_event": "Cancel this date?",
        "cancel_following_events": "Cancel this and all following dates?",
        "btn_pattern_once": "One-time",
        "btn_pattern_weekly": "Weekly / multi-day week",
        "btn_pattern_monthly": "Monthly (e.g. first Tuesday)",
        "btn_weekdays_done": "Done",
        "btn_nth_1": "1st",
        "btn_nth_2": "2nd",
        "btn_nth_3": "3rd",
        "btn_nth_4": "4th",
        "btn_nth_last": "Last",
        "btn_scope_one": "This date only",
        "btn_scope_following": "This and following",
        "wd_0": "Mon",
        "wd_1": "Tue",
        "wd_2": "Wed",
        "wd_3": "Thu",
        "wd_4": "Fri",
        "wd_5": "Sat",
        "wd_6": "Sun",
        "month_1": "January",
        "month_2": "February",
        "month_3": "March",
        "month_4": "April",
        "month_5": "May",
        "month_6": "June",
        "month_7": "July",
        "month_8": "August",
        "month_9": "September",
        "month_10": "October",
        "month_11": "November",
        "month_12": "December",
        "cancellation_aborted": "Cancellation aborted.",
        "share_invite": "Share this link:\n{url}",
        "no_confirmations": "No confirmations yet for {title}.",
        "confirmations_for": "Confirmations for {title} ({time}):\n{names}",
        "participant_fallback": "Participant",
        "google_not_configured": "Google sync is not configured on this server.",
        "google_link_first": "Link Google first using 🔗 Link Google.",
        "google_open_link": "Open this link to connect Google Calendar:\n{url}",
        "google_linked": "Google account linked: {email}. Use 📎 Map to Google to choose a calendar.",
        "google_connected": "connected",
        "google_load_failed": "Could not load Google calendars: {error}",
        "google_none_found": "No Google calendars found.",
        "google_none_writable": "No writable Google calendars found.",
        "google_choose": "Choose a Google calendar:",
        "google_choose_import": "Choose a filled Google calendar to import:\n{names}",
        "google_map_expired": "Selection expired. Start again with 📎 Map to Google.",
        "google_import_expired": "Selection expired. Start Import Google again.",
        "google_mapped": "Mapped to Google calendar: {name}\nImported {created} existing event(s); updated {updated}.",
        "google_imported": (
            "Imported {name} as Meetifier calendar #{id}.\n"
            "Created {created} event(s); updated {updated}; cancelled {cancelled}.\n"
            "Future Google changes will sync automatically."
        ),
        "google_import_failed": "Google import failed: {error}",
        "google_no_linked": "No calendars are linked to Google.",
        "google_sync_complete": "Google sync complete: {created} new, {updated} updated, {cancelled} cancelled.",
        "google_sync_failed": "Google sync failed: {error}",
        "google_adopt_first": "Import or map a Google calendar first.",
        "google_adopt_confirm": (
            "This will add a Meetifier subscription link to upcoming events in {name} and ask "
            "Google to email their attendees. Existing event details and invitations are preserved."
        ),
        "google_adopt_confirm_short": (
            "This will update upcoming events in {name} and ask Google to email their attendees. Continue?"
        ),
        "google_adopt_done": (
            "Google attendee migration enabled. Updated {updated} of {total} event or series invitation(s).\n"
            "Participant link: {url}"
        ),
        "google_adopt_failed": "Could not notify Google attendees: {error}",
        "google_adopt_cancelled": "Google attendee invitation cancelled.",
        "calendar_not_owned": "Calendar not found or not owned by you.",
        "btn_next_event": "Next event",
        "btn_this_week": "This week",
        "btn_google_cal": "Google calendar #{n}",
        "btn_notify_attendees": "Notify Google attendees",
        "btn_cancel": "Cancel",
        "btn_confirm_attendance": "✅ Confirm attendance",
        "btn_yes_cancel": "Yes, cancel",
        "btn_no": "No",
        "heading_new_event": "New event",
        "heading_event_updated": "Event updated",
        "heading_event_rescheduled": "Event rescheduled",
        "heading_event_cancelled": "Event cancelled",
        "notify_event": "{heading}: {title}\n{time}\nCalendar: {calendar}",
        "reminder": "Reminder ({minutes} min): {title}\n{time}\nCalendar: {calendar}",
        "organizer_confirmed": (
            "✅ {name} confirmed attendance:\n{title}\n{time}\nCalendar: {calendar}"
        ),
        "invite_invalid": "This invitation is invalid or expired.",
        "invited_to": "You were invited to {name} ({timezone}).",
        "btn_subscribe": "Subscribe to {name}",
        "subscribed": "Subscribed to {name}. Tap 📅 Upcoming to see events.",
        "usage_upcoming": "Usage: /upcoming [next|week]",
        "no_pending_confirm": "No events waiting for confirmation.",
        "tap_to_confirm": "Tap a date to confirm attendance:",
        "choose_calendar_confirm": "Choose a calendar to confirm attendance:",
        "confirmed": "Confirmed: {title}\n{time}",
        "already_confirmed": "Already confirmed: {title}",
        "no_subscriptions": "No subscriptions.",
        "sub_muted": "muted",
        "sub_active": "active",
        "timezone_updated": "Timezone updated (UTC offset).",
        "choose_mute": "Choose a calendar to mute:",
        "choose_unmute": "Choose a calendar to unmute:",
        "choose_unsubscribe": "Choose a calendar to unsubscribe from:",
        "choose_reminders": "Choose a calendar:",
        "updated": "Updated.",
        "subscription_not_found": "Subscription not found.",
        "usage_action": "Usage: /{action} CALENDAR_ID",
        "muted": "Muted.",
        "unmuted": "Unmuted.",
        "unsubscribed": "Unsubscribed.",
        "reminders_saved": "Reminder preference saved for future jobs.",
        "enter_reminders": "Enter reminder minutes (comma-separated, e.g. 1440,30):",
        "usage_reminders": "Usage: /reminders CALENDAR_ID 1440,30",
        "org.help": (
            "Use the menu buttons below, or type commands directly:\n\n"
            "/newcalendar Name | 3\n"
            "/calendars\n"
            "/newevent CALENDAR_ID | Title | 2026-09-01 18:30 | DURATION_MINUTES | WEEKS\n            (WEEKS kept for simple weekly; use the menu for Mon+Wed, every 2nd week, first Tuesday, …)\n"
            "/events CALENDAR_ID [next|week]\n"
            "/invite CALENDAR_ID\n"
            "/reschedule EVENT_ID | 2026-09-02 19:00\n"
            "/cancel EVENT_ID\n"
            "/confirmations CALENDAR_ID\n"
            "/language\n\n"
            "Google (optional): Link Google, then import a filled calendar or map an existing Meetifier calendar.\n"
            "Mapped calendars sync both ways. Use Invite Google guests to add the participant-bot link to upcoming events.\n\n"
            "Use WEEKS=1 for one-time events or 2..52 for weekly recurrence."
        ),
        "par.help": (
            "Use the menu buttons below, or type commands directly:\n\n"
            "/upcoming [next|week] - upcoming events\n"
            "/confirm EVENT_ID - confirm attendance\n"
            "/timezone 3\n"
            "/reminders CALENDAR_ID 1440,30\n"
            "/mute CALENDAR_ID\n"
            "/unmute CALENDAR_ID\n"
            "/unsubscribe CALENDAR_ID\n"
            "/subscriptions\n"
            "/language"
        ),
        "cmd.calendars": "List calendars",
        "cmd.newevent": "Create event",
        "cmd.googleimport": "Import a Google calendar",
        "cmd.googlesync": "Sync Google now",
        "cmd.googleinvite": "Invite Google attendees",
        "cmd.help": "Show help",
        "cmd.upcoming": "Upcoming events",
        "cmd.confirm": "Confirm attendance",
        "cmd.subscriptions": "My calendars",
        "cmd.language": "Change language",
    },
    "ru": {
        "org.welcome": "Добро пожаловать в Meetifier Organizer!",
        "par.welcome": "Добро пожаловать в Meetifier Participant!",
        "org.onboarding": (
            "Обычный сценарий\n"
            "1. Создайте календарь\n"
            "2. Добавьте события\n"
            "3. Отправьте ссылку-приглашение\n"
            "4. Участники подписываются в Participant Bot и получают напоминания\n"
            "5. Переносите или отменяйте события; смотрите подтверждения\n\n"
            "Кнопки меню\n"
            "📅 Календари — список ваших календарей\n"
            "➕ Новый календарь — название и смещение UTC в часах (например 3 для UTC+3)\n"
            "➕ Новое событие — название, время начала, длительность, недели (1 — разово, 2–52 — еженедельно)\n"
            "📋 События — следующее или на этой неделе\n"
            "🔗 Пригласить — ссылка в Telegram для подписки\n"
            "✏️ Перенести — выбрать событие и новое время\n"
            "❌ Отменить событие — отмена и уведомление подписчиков\n"
            "✅ Подтверждения — кто подтвердил участие\n"
            "🔗 Связать Google / 📎 Привязать / ⬇️ Импорт / 🔄 Синхронизация / 📣 Пригласить гостей Google — опциональный синк\n"
            "🌐 Язык — en / ru / sr\n"
            "❓ Помощь — примеры команд\n\n"
            "Подсказка: почти всё делается кнопками; команды есть в Помощи."
        ),
        "par.onboarding": (
            "Обычный сценарий\n"
            "1. Откройте ссылку от организатора (или нажмите Подписаться)\n"
            "2. Укажите смещение UTC в часах (например 3 для UTC+3)\n"
            "3. При желании настройте напоминания для календаря\n"
            "4. Смотрите ближайшие события и подтверждайте участие\n"
            "5. Отключайте звук или отписывайтесь, когда календарь больше не нужен\n\n"
            "Кнопки меню\n"
            "📅 Ближайшие — следующее событие или эта неделя\n"
            "✅ Подтвердить — отметить, что вы придёте\n"
            "📋 Подписки — календари, на которые вы подписаны\n"
            "🌍 Часовой пояс — смещение UTC в часах для отображения времени\n"
            "⏰ Напоминания — минуты до события (например 1440,30 = день и 30 мин)\n"
            "🔇 Без звука / 🔊 Включить звук — пауза или возобновление напоминаний\n"
            "🚫 Отписаться — уйти с календаря и остановить задачи\n"
            "🌐 Язык — en / ru / sr\n"
            "❓ Помощь — примеры команд\n\n"
            "Нужно нажать Start в этом боте, иначе Telegram не доставит напоминания."
        ),
        "choose_language": "Выберите язык:",
        "language_updated": "Язык обновлён.",
        "main_menu": "Главное меню:",
        "cancelled": "Отменено.",
        "flow_cancelled": "Отменено. Весь прогресс этого действия сброшен.",
        "nothing_to_cancel": "Нечего отменять.",
        "nothing_to_cancel_event": "Нечего отменять. Используйте ❌ Отменить событие.",
        "btn_back": "⬅️ Назад",
        "btn_flow_cancel": "✖️ Отмена",
        "error": "Ошибка: {error}",
        "try_again": "Попробуйте ещё раз:",
        "wrong_command": "Неверный формат команды. Отправьте /help для примеров.",
        "no_calendars": "Календарей пока нет.",
        "no_calendars_create": "Календарей пока нет. Сначала создайте календарь.",
        "calendar_created": "Календарь создан: {name} (ID {id})",
        "enter_calendar_name": "Введите название календаря:",
        "enter_timezone": "Введите смещение UTC в часах (например 3 для UTC+3, -5 для UTC-5):",
        "what_to_see": "Что показать?",
        "choose_calendar": "Выберите календарь:",
        "choose_calendar_invite": "Выберите календарь для приглашения:",
        "choose_calendar_event": "Выберите календарь для нового события:",
        "choose_calendar_reschedule": "Выберите календарь, чтобы перенести событие:",
        "choose_calendar_confirmations": "Выберите календарь для просмотра подтверждений:",
        "choose_calendar_sync": "Выберите календарь для синхронизации:",
        "choose_calendar_map": "Выберите календарь Meetifier для привязки:",
        "choose_calendar_adopt": "Выберите календарь, гостей Google которого нужно пригласить:",
        "choose_event": "Выберите событие:",
        "choose_occurrence": "Выберите дату:",
        "choose_occurrence_cancel": "Выберите дату для отмены:",
        "choose_occurrence_confirm": "Выберите дату для подтверждения:",
        "choose_event_cancel": "Выберите событие для отмены:",
        "event_dates_header": "{title}:",
        "no_future_events": "В этом календаре нет будущих событий.",
        "no_events_week": "На этой неделе событий нет.",
        "no_events_upcoming": "Нет ближайших событий.",
        "enter_event_title": "Введите название события:",
        "enter_start_time": "Выберите дату начала (или введите ГГГГ-ММ-ДД ЧЧ:ММ):",
        "pick_start_hour": "Выберите час для {date} (или введите ГГГГ-ММ-ДД ЧЧ:ММ):",
        "pick_start_minute": "Выберите минуты для {date} {hour}:xx (или введите ГГГГ-ММ-ДД ЧЧ:ММ):",
        "enter_duration": "Длительность в минутах:",
        "enter_weeks": "Число недель (1 — разово, 2..52 — еженедельно):",
        "choose_pattern": "Выберите правило повторения:",
        "choose_weekdays": "Выберите дни недели (нажмите, чтобы отметить), затем Готово:",
        "enter_interval_weeks": "Повторять каждые сколько недель? (1 — каждую неделю, 2 — через неделю, …):",
        "choose_monthly_pos": "Какое вхождение в месяце?",
        "choose_monthly_weekday": "Какой день недели?",
        "enter_occurrence_count": "Сколько дат создать? (1..104):",
        "choose_edit_scope": "Только эту дату или эту и все следующие?",
        "enter_new_start": "Выберите новую дату начала (или введите ГГГГ-ММ-ДД ЧЧ:ММ):",
        "events_created": "Создано событий: {count}. ID: {ids}",
        "event_cancelled_notified": "Событие отменено, подписчики уведомлены.",
        "event_rescheduled_notified": "Событие перенесено, подписчики уведомлены.",
        "events_updated_count": "Обновлено дат: {count}. Подписчики уведомлены.",
        "events_cancelled_count": "Отменено дат: {count}. Подписчики уведомлены.",
        "cancel_this_event": "Отменить эту дату?",
        "cancel_following_events": "Отменить эту и все следующие даты?",
        "btn_pattern_once": "Разово",
        "btn_pattern_weekly": "Еженедельно / несколько дней в неделю",
        "btn_pattern_monthly": "Ежемесячно (напр. первый вторник)",
        "btn_weekdays_done": "Готово",
        "btn_nth_1": "1-й",
        "btn_nth_2": "2-й",
        "btn_nth_3": "3-й",
        "btn_nth_4": "4-й",
        "btn_nth_last": "Последний",
        "btn_scope_one": "Только эту дату",
        "btn_scope_following": "Эту и следующие",
        "wd_0": "Пн",
        "wd_1": "Вт",
        "wd_2": "Ср",
        "wd_3": "Чт",
        "wd_4": "Пт",
        "wd_5": "Сб",
        "wd_6": "Вс",
        "month_1": "Январь",
        "month_2": "Февраль",
        "month_3": "Март",
        "month_4": "Апрель",
        "month_5": "Май",
        "month_6": "Июнь",
        "month_7": "Июль",
        "month_8": "Август",
        "month_9": "Сентябрь",
        "month_10": "Октябрь",
        "month_11": "Ноябрь",
        "month_12": "Декабрь",
        "cancellation_aborted": "Отмена прервана.",
        "share_invite": "Отправьте эту ссылку:\n{url}",
        "no_confirmations": "Пока нет подтверждений для «{title}».",
        "confirmations_for": "Подтверждения для «{title}» ({time}):\n{names}",
        "participant_fallback": "Участник",
        "google_not_configured": "Синхронизация Google на этом сервере не настроена.",
        "google_link_first": "Сначала свяжите Google через 🔗 Связать Google.",
        "google_open_link": "Откройте ссылку, чтобы подключить Google Calendar:\n{url}",
        "google_linked": "Google аккаунт связан: {email}. Используйте 📎 Привязать к Google.",
        "google_connected": "подключено",
        "google_load_failed": "Не удалось загрузить календари Google: {error}",
        "google_none_found": "Календари Google не найдены.",
        "google_none_writable": "Нет доступных для записи календарей Google.",
        "google_choose": "Выберите календарь Google:",
        "google_choose_import": "Выберите заполненный календарь Google для импорта:\n{names}",
        "google_map_expired": "Выбор устарел. Начните снова через 📎 Привязать к Google.",
        "google_import_expired": "Выбор устарел. Начните импорт Google снова.",
        "google_mapped": "Привязано к Google: {name}\nИмпортировано существующих: {created}; обновлено: {updated}.",
        "google_imported": (
            "Импортирован «{name}» как календарь Meetifier #{id}.\n"
            "Создано: {created}; обновлено: {updated}; отменено: {cancelled}.\n"
            "Дальнейшие изменения Google будут синхронизироваться автоматически."
        ),
        "google_import_failed": "Импорт Google не удался: {error}",
        "google_no_linked": "Нет календарей, связанных с Google.",
        "google_sync_complete": "Синхронизация Google: новых {created}, обновлено {updated}, отменено {cancelled}.",
        "google_sync_failed": "Синхронизация Google не удалась: {error}",
        "google_adopt_first": "Сначала импортируйте или привяжите календарь Google.",
        "google_adopt_confirm": (
            "В предстоящие события календаря «{name}» будет добавлена ссылка подписки Meetifier, "
            "и Google отправит письма участникам. Существующие детали и приглашения сохранятся."
        ),
        "google_adopt_confirm_short": (
            "Будут обновлены предстоящие события «{name}», и Google отправит письма участникам. Продолжить?"
        ),
        "google_adopt_done": (
            "Миграция участников Google включена. Обновлено {updated} из {total} приглашений.\n"
            "Ссылка участника: {url}"
        ),
        "google_adopt_failed": "Не удалось уведомить участников Google: {error}",
        "google_adopt_cancelled": "Приглашение участников Google отменено.",
        "calendar_not_owned": "Календарь не найден или вам не принадлежит.",
        "btn_next_event": "Следующее",
        "btn_this_week": "Эта неделя",
        "btn_google_cal": "Календарь Google #{n}",
        "btn_notify_attendees": "Уведомить участников Google",
        "btn_cancel": "Отмена",
        "btn_confirm_attendance": "✅ Подтвердить участие",
        "btn_yes_cancel": "Да, отменить",
        "btn_no": "Нет",
        "heading_new_event": "Новое событие",
        "heading_event_updated": "Событие обновлено",
        "heading_event_rescheduled": "Событие перенесено",
        "heading_event_cancelled": "Событие отменено",
        "notify_event": "{heading}: {title}\n{time}\nКалендарь: {calendar}",
        "reminder": "Напоминание ({minutes} мин): {title}\n{time}\nКалендарь: {calendar}",
        "organizer_confirmed": (
            "✅ {name} подтвердил(а) участие:\n{title}\n{time}\nКалендарь: {calendar}"
        ),
        "invite_invalid": "Это приглашение недействительно или истекло.",
        "invited_to": "Вас пригласили в «{name}» ({timezone}).",
        "btn_subscribe": "Подписаться на {name}",
        "subscribed": "Вы подписались на «{name}». Нажмите 📅 Ближайшие, чтобы увидеть события.",
        "usage_upcoming": "Использование: /upcoming [next|week]",
        "no_pending_confirm": "Нет событий, ожидающих подтверждения.",
        "tap_to_confirm": "Нажмите на дату, чтобы подтвердить участие:",
        "choose_calendar_confirm": "Выберите календарь для подтверждения участия:",
        "confirmed": "Подтверждено: {title}\n{time}",
        "already_confirmed": "Уже подтверждено: {title}",
        "no_subscriptions": "Нет подписок.",
        "sub_muted": "без звука",
        "sub_active": "активна",
        "timezone_updated": "Часовой пояс обновлён (смещение UTC).",
        "choose_mute": "Выберите календарь для отключения уведомлений:",
        "choose_unmute": "Выберите календарь для включения уведомлений:",
        "choose_unsubscribe": "Выберите календарь для отписки:",
        "choose_reminders": "Выберите календарь:",
        "updated": "Обновлено.",
        "subscription_not_found": "Подписка не найдена.",
        "usage_action": "Использование: /{action} CALENDAR_ID",
        "muted": "Уведомления отключены.",
        "unmuted": "Уведомления включены.",
        "unsubscribed": "Вы отписались.",
        "reminders_saved": "Настройки напоминаний сохранены для будущих задач.",
        "enter_reminders": "Введите минуты напоминаний через запятую (например 1440,30):",
        "usage_reminders": "Использование: /reminders CALENDAR_ID 1440,30",
        "org.help": (
            "Используйте кнопки меню ниже или команды:\n\n"
            "/newcalendar Название | 3\n"
            "/calendars\n"
            "/newevent CALENDAR_ID | Название | 2026-09-01 18:30 | МИНУТЫ | НЕДЕЛИ\n"
            "/events CALENDAR_ID [next|week]\n"
            "/invite CALENDAR_ID\n"
            "/reschedule EVENT_ID | 2026-09-02 19:00\n"
            "/cancel EVENT_ID\n"
            "/confirmations CALENDAR_ID\n"
            "/language\n\n"
            "Google (опционально): свяжите Google, затем импортируйте календарь или привяжите существующий.\n"
            "Привязанные календари синхронизируются в обе стороны.\n\n"
            "НЕДЕЛИ=1 — разовое событие, 2..52 — еженедельно."
        ),
        "par.help": (
            "Используйте кнопки меню ниже или команды:\n\n"
            "/upcoming [next|week] — ближайшие события\n"
            "/confirm EVENT_ID — подтвердить участие\n"
            "/timezone 3\n"
            "/reminders CALENDAR_ID 1440,30\n"
            "/mute CALENDAR_ID\n"
            "/unmute CALENDAR_ID\n"
            "/unsubscribe CALENDAR_ID\n"
            "/subscriptions\n"
            "/language"
        ),
        "cmd.calendars": "Список календарей",
        "cmd.newevent": "Создать событие",
        "cmd.googleimport": "Импорт Google-календаря",
        "cmd.googlesync": "Синхронизировать Google",
        "cmd.googleinvite": "Пригласить гостей Google",
        "cmd.help": "Помощь",
        "cmd.upcoming": "Ближайшие события",
        "cmd.confirm": "Подтвердить участие",
        "cmd.subscriptions": "Мои календари",
        "cmd.language": "Сменить язык",
    },
    "sr": {
        "org.welcome": "Dobrodošli u Meetifier Organizer!",
        "par.welcome": "Dobrodošli u Meetifier Participant!",
        "org.onboarding": (
            "Uobičajeni tok\n"
            "1. Napravite kalendar\n"
            "2. Dodajte događaje\n"
            "3. Pošaljite link pozivnice\n"
            "4. Učesnici se pretplate u Participant Bot-u i dobijaju podsetnike\n"
            "5. Pomerite ili otkažite događaje; proverite potvrde\n\n"
            "Funkcije menija\n"
            "📅 Kalendari — lista vaših kalendara\n"
            "➕ Novi kalendar — naziv i UTC pomeraj u satima (npr. 1 za UTC+1)\n"
            "➕ Novi događaj — naslov, vreme početka, trajanje, nedelje (1 jednokratno, 2–52 nedeljno)\n"
            "📋 Događaji — sledeći ili ova nedelja\n"
            "🔗 Pozovi — Telegram link za pretplatu\n"
            "✏️ Pomeri — izaberite događaj i novo vreme\n"
            "❌ Otkaži događaj — otkazivanje i obaveštavanje pretplatnika\n"
            "✅ Potvrde — ko je potvrdio prisustvo\n"
            "🔗 Poveži Google / 📎 Mapiraj / ⬇️ Uvoz / 🔄 Sinhronizuj / 📣 Pozovi Google goste — opciona Google sinhronizacija\n"
            "🌐 Jezik — en / ru / sr\n"
            "❓ Pomoć — primeri komandi\n\n"
            "Savet: većina akcija ide preko dugmadi; komande su u Pomoći."
        ),
        "par.onboarding": (
            "Uobičajeni tok\n"
            "1. Otvorite link od organizatora (ili dodirnite Pretplati se)\n"
            "2. Podesite UTC pomeraj u satima (npr. 1 za UTC+1)\n"
            "3. Po želji podesite podsetnike po kalendaru\n"
            "4. Pregledajte predstojeće događaje i potvrdite prisustvo\n"
            "5. Isključite obaveštenja ili otkažite pretplatu kad kalendar više nije potreban\n\n"
            "Funkcije menija\n"
            "📅 Predstojeći — sledeći događaj ili ova nedelja\n"
            "✅ Potvrdi — označite da ćete doći\n"
            "📋 Pretplate — kalendari koje pratite\n"
            "🌍 Vremenska zona — UTC pomeraj u satima za prikaz vremena\n"
            "⏰ Podsetnici — minuti pre događaja (npr. 1440,30 = 1 dan i 30 min)\n"
            "🔇 Isključi / 🔊 Uključi — pauza ili nastavak podsetnika\n"
            "🚫 Otkaži pretplatu — napustite kalendar i zaustavite poslove\n"
            "🌐 Jezik — en / ru / sr\n"
            "❓ Pomoć — primeri komandi\n\n"
            "Morate pokrenuti ovaj bot (Start) da bi Telegram mogao da šalje podsetnike."
        ),
        "choose_language": "Izaberite jezik:",
        "language_updated": "Jezik je ažuriran.",
        "main_menu": "Glavni meni:",
        "cancelled": "Otkazano.",
        "flow_cancelled": "Otkazano. Sav napredak ove akcije je odbačen.",
        "nothing_to_cancel": "Nema šta da se otkaže.",
        "nothing_to_cancel_event": "Nema šta da se otkaže. Koristite ❌ Otkaži događaj.",
        "btn_back": "⬅️ Nazad",
        "btn_flow_cancel": "✖️ Otkaži",
        "error": "Greška: {error}",
        "try_again": "Pokušajte ponovo:",
        "wrong_command": "Pogrešan format komande. Pošaljite /help za primere.",
        "no_calendars": "Još nema kalendara.",
        "no_calendars_create": "Još nema kalendara. Prvo napravite jedan.",
        "calendar_created": "Kalendar kreiran: {name} (ID {id})",
        "enter_calendar_name": "Unesite naziv kalendara:",
        "enter_timezone": "Unesite UTC pomeraj u satima (npr. 1 za UTC+1, -5 za UTC-5):",
        "what_to_see": "Šta želite da vidite?",
        "choose_calendar": "Izaberite kalendar:",
        "choose_calendar_invite": "Izaberite kalendar za pozivnicu:",
        "choose_calendar_event": "Izaberite kalendar za novi događaj:",
        "choose_calendar_reschedule": "Izaberite kalendar da pomerite događaj:",
        "choose_calendar_confirmations": "Izaberite kalendar za pregled potvrda:",
        "choose_calendar_sync": "Izaberite kalendar za sinhronizaciju:",
        "choose_calendar_map": "Izaberite Meetifier kalendar za mapiranje:",
        "choose_calendar_adopt": "Izaberite kalendar čije Google goste treba pozvati:",
        "choose_event": "Izaberite događaj:",
        "choose_occurrence": "Izaberite datum:",
        "choose_occurrence_cancel": "Izaberite datum za otkazivanje:",
        "choose_occurrence_confirm": "Izaberite datum za potvrdu:",
        "choose_event_cancel": "Izaberite događaj za otkazivanje:",
        "event_dates_header": "{title}:",
        "no_future_events": "Nema budućih događaja u ovom kalendaru.",
        "no_events_week": "Nema događaja za ovu nedelju.",
        "no_events_upcoming": "Nema predstojećih događaja.",
        "enter_event_title": "Unesite naslov događaja:",
        "enter_start_time": "Izaberite datum početka (ili unesite GGGG-MM-DD ČČ:MM):",
        "pick_start_hour": "Izaberite sat za {date} (ili unesite GGGG-MM-DD ČČ:MM):",
        "pick_start_minute": "Izaberite minute za {date} {hour}:xx (ili unesite GGGG-MM-DD ČČ:MM):",
        "enter_duration": "Trajanje u minutima:",
        "enter_weeks": "Broj nedelja (1 jednokratno, 2..52 nedeljno):",
        "choose_pattern": "Izaberite obrazac ponavljanja:",
        "choose_weekdays": "Izaberite dane (dodirnite da označite), zatim Gotovo:",
        "enter_interval_weeks": "Ponavljati svake koliko nedelja? (1 = svake nedelje, 2 = svake druge, …):",
        "choose_monthly_pos": "Koje pojavljivanje u mesecu?",
        "choose_monthly_weekday": "Koji dan u nedelji?",
        "enter_occurrence_count": "Koliko datuma kreirati? (1..104):",
        "choose_edit_scope": "Samo ovaj datum ili ovaj i svi naredni?",
        "enter_new_start": "Izaberite novi datum početka (ili unesite GGGG-MM-DD ČČ:MM):",
        "events_created": "Kreirano {count} događaja. ID: {ids}",
        "event_cancelled_notified": "Događaj otkazan i pretplatnici obavešteni.",
        "event_rescheduled_notified": "Događaj pomeren i pretplatnici obavešteni.",
        "events_updated_count": "Ažurirano {count} datuma. Pretplatnici obavešteni.",
        "events_cancelled_count": "Otkazano {count} datuma. Pretplatnici obavešteni.",
        "cancel_this_event": "Otkazati ovaj datum?",
        "cancel_following_events": "Otkazati ovaj i sve naredne datume?",
        "btn_pattern_once": "Jednokratno",
        "btn_pattern_weekly": "Nedeljno / više dana u nedelji",
        "btn_pattern_monthly": "Mesečno (npr. prvi utorak)",
        "btn_weekdays_done": "Gotovo",
        "btn_nth_1": "1.",
        "btn_nth_2": "2.",
        "btn_nth_3": "3.",
        "btn_nth_4": "4.",
        "btn_nth_last": "Poslednji",
        "btn_scope_one": "Samo ovaj datum",
        "btn_scope_following": "Ovaj i naredni",
        "wd_0": "Pon",
        "wd_1": "Uto",
        "wd_2": "Sre",
        "wd_3": "Čet",
        "wd_4": "Pet",
        "wd_5": "Sub",
        "wd_6": "Ned",
        "month_1": "Januar",
        "month_2": "Februar",
        "month_3": "Mart",
        "month_4": "April",
        "month_5": "Maj",
        "month_6": "Jun",
        "month_7": "Jul",
        "month_8": "Avgust",
        "month_9": "Septembar",
        "month_10": "Oktobar",
        "month_11": "Novembar",
        "month_12": "Decembar",
        "cancellation_aborted": "Otkazivanje prekinuto.",
        "share_invite": "Podelite ovaj link:\n{url}",
        "no_confirmations": "Još nema potvrda za {title}.",
        "confirmations_for": "Potvrde za {title} ({time}):\n{names}",
        "participant_fallback": "Učesnik",
        "google_not_configured": "Google sinhronizacija nije konfigurisana na ovom serveru.",
        "google_link_first": "Prvo povežite Google preko 🔗 Poveži Google.",
        "google_open_link": "Otvorite ovaj link da povežete Google Calendar:\n{url}",
        "google_linked": "Google nalog povezan: {email}. Koristite 📎 Mapiraj na Google.",
        "google_connected": "povezano",
        "google_load_failed": "Nije moguće učitati Google kalendare: {error}",
        "google_none_found": "Nisu pronađeni Google kalendari.",
        "google_none_writable": "Nema Google kalendara sa dozvolom pisanja.",
        "google_choose": "Izaberite Google kalendar:",
        "google_choose_import": "Izaberite popunjen Google kalendar za uvoz:\n{names}",
        "google_map_expired": "Izbor je istekao. Počnite ponovo sa 📎 Mapiraj na Google.",
        "google_import_expired": "Izbor je istekao. Ponovo pokrenite uvoz Google.",
        "google_mapped": "Mapirano na Google kalendar: {name}\nUvezeno postojećih: {created}; ažurirano: {updated}.",
        "google_imported": (
            "Uvezen {name} kao Meetifier kalendar #{id}.\n"
            "Kreirano {created}; ažurirano {updated}; otkazano {cancelled}.\n"
            "Buduće Google izmene će se sinhronizovati automatski."
        ),
        "google_import_failed": "Google uvoz nije uspeo: {error}",
        "google_no_linked": "Nema kalendara povezanih sa Google-om.",
        "google_sync_complete": "Google sync završen: {created} novih, {updated} ažuriranih, {cancelled} otkazanih.",
        "google_sync_failed": "Google sync nije uspeo: {error}",
        "google_adopt_first": "Prvo uvezite ili mapirajte Google kalendar.",
        "google_adopt_confirm": (
            "Ovo će dodati Meetifier link za pretplatu u predstojeće događaje u {name} i zatražiti "
            "da Google pošalje email učesnicima. Postojeći detalji i pozivnice se čuvaju."
        ),
        "google_adopt_confirm_short": (
            "Ovo će ažurirati predstojeće događaje u {name} i zatražiti da Google pošalje email učesnicima. Nastaviti?"
        ),
        "google_adopt_done": (
            "Migracija Google učesnika omogućena. Ažurirano {updated} od {total} pozivnica.\n"
            "Link učesnika: {url}"
        ),
        "google_adopt_failed": "Nije moguće obavestiti Google učesnike: {error}",
        "google_adopt_cancelled": "Pozivanje Google učesnika otkazano.",
        "calendar_not_owned": "Kalendar nije pronađen ili vam ne pripada.",
        "btn_next_event": "Sledeći događaj",
        "btn_this_week": "Ova nedelja",
        "btn_google_cal": "Google kalendar #{n}",
        "btn_notify_attendees": "Obavesti Google učesnike",
        "btn_cancel": "Otkaži",
        "btn_confirm_attendance": "✅ Potvrdi prisustvo",
        "btn_yes_cancel": "Da, otkaži",
        "btn_no": "Ne",
        "heading_new_event": "Novi događaj",
        "heading_event_updated": "Događaj ažuriran",
        "heading_event_rescheduled": "Događaj pomeren",
        "heading_event_cancelled": "Događaj otkazan",
        "notify_event": "{heading}: {title}\n{time}\nKalendar: {calendar}",
        "reminder": "Podsetnik ({minutes} min): {title}\n{time}\nKalendar: {calendar}",
        "organizer_confirmed": (
            "✅ {name} je potvrdio/la prisustvo:\n{title}\n{time}\nKalendar: {calendar}"
        ),
        "invite_invalid": "Ova pozivnica je nevažeća ili je istekla.",
        "invited_to": "Pozvani ste u {name} ({timezone}).",
        "btn_subscribe": "Pretplati se na {name}",
        "subscribed": "Pretplaćeni ste na {name}. Dodirnite 📅 Predstojeći da vidite događaje.",
        "usage_upcoming": "Upotreba: /upcoming [next|week]",
        "no_pending_confirm": "Nema događaja koji čekaju potvrdu.",
        "tap_to_confirm": "Dodirnite datum da potvrdite prisustvo:",
        "choose_calendar_confirm": "Izaberite kalendar za potvrdu prisustva:",
        "confirmed": "Potvrđeno: {title}\n{time}",
        "already_confirmed": "Već potvrđeno: {title}",
        "no_subscriptions": "Nema pretplata.",
        "sub_muted": "isključeno",
        "sub_active": "aktivno",
        "timezone_updated": "Vremenska zona ažurirana (UTC pomeraj).",
        "choose_mute": "Izaberite kalendar za isključivanje obaveštenja:",
        "choose_unmute": "Izaberite kalendar za uključivanje obaveštenja:",
        "choose_unsubscribe": "Izaberite kalendar za otkazivanje pretplate:",
        "choose_reminders": "Izaberite kalendar:",
        "updated": "Ažurirano.",
        "subscription_not_found": "Pretplata nije pronađena.",
        "usage_action": "Upotreba: /{action} CALENDAR_ID",
        "muted": "Obaveštenja isključena.",
        "unmuted": "Obaveštenja uključena.",
        "unsubscribed": "Pretplata otkazana.",
        "reminders_saved": "Podešavanje podsetnika sačuvano za buduće poslove.",
        "enter_reminders": "Unesite minute podsetnika odvojene zarezom (npr. 1440,30):",
        "usage_reminders": "Upotreba: /reminders CALENDAR_ID 1440,30",
        "org.help": (
            "Koristite dugmad menija ispod ili komande:\n\n"
            "/newcalendar Naziv | 1\n"
            "/calendars\n"
            "/newevent CALENDAR_ID | Naslov | 2026-09-01 18:30 | MINUTI | NEDELJE\n"
            "/events CALENDAR_ID [next|week]\n"
            "/invite CALENDAR_ID\n"
            "/reschedule EVENT_ID | 2026-09-02 19:00\n"
            "/cancel EVENT_ID\n"
            "/confirmations CALENDAR_ID\n"
            "/language\n\n"
            "Google (opciono): povežite Google, zatim uvezite ili mapirajte kalendar.\n"
            "Mapirani kalendari se sinhronizuju u oba smera.\n\n"
            "NEDELJE=1 jednokratno, 2..52 nedeljno."
        ),
        "par.help": (
            "Koristite dugmad menija ispod ili komande:\n\n"
            "/upcoming [next|week] - predstojeći događaji\n"
            "/confirm EVENT_ID - potvrdi prisustvo\n"
            "/timezone 1\n"
            "/reminders CALENDAR_ID 1440,30\n"
            "/mute CALENDAR_ID\n"
            "/unmute CALENDAR_ID\n"
            "/unsubscribe CALENDAR_ID\n"
            "/subscriptions\n"
            "/language"
        ),
        "cmd.calendars": "Lista kalendara",
        "cmd.newevent": "Kreiraj događaj",
        "cmd.googleimport": "Uvezi Google kalendar",
        "cmd.googlesync": "Sinhronizuj Google",
        "cmd.googleinvite": "Pozovi Google goste",
        "cmd.help": "Pomoć",
        "cmd.upcoming": "Predstojeći događaji",
        "cmd.confirm": "Potvrdi prisustvo",
        "cmd.subscriptions": "Moji kalendari",
        "cmd.language": "Promeni jezik",
    },
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    code = value.strip().lower().replace("_", "-")
    if code in LOCALES:
        return code
    primary = code.split("-", 1)[0]
    return primary if primary in LOCALES else DEFAULT_LOCALE


def t(locale: str | None, key: str, **kwargs: Any) -> str:
    code = normalize_locale(locale)
    template = MESSAGES.get(code, MESSAGES[DEFAULT_LOCALE]).get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LOCALE].get(key, key)
    return template.format(**kwargs) if kwargs else template


def btn(labels: dict[str, dict[str, str]], action: str, locale: str | None) -> str:
    return labels[action][normalize_locale(locale)]


def all_btn_texts(labels: dict[str, dict[str, str]], *actions: str) -> set[str]:
    texts: set[str] = set()
    selected = actions or tuple(labels)
    for action in selected:
        texts.update(labels[action].values())
    return texts


def action_for_text(labels: dict[str, dict[str, str]], text: str) -> str | None:
    for action, variants in labels.items():
        if text in variants.values():
            return action
    return None
