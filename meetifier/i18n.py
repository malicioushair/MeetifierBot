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

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "org.welcome": "Welcome! Use the buttons below to manage your calendars.",
        "par.welcome": "Welcome! Use the buttons below to manage your subscriptions.",
        "choose_language": "Choose your language:",
        "language_updated": "Language updated.",
        "main_menu": "Main menu:",
        "cancelled": "Cancelled.",
        "nothing_to_cancel": "Nothing to cancel.",
        "nothing_to_cancel_event": "Nothing to cancel. Use ❌ Cancel event to cancel an event.",
        "error": "Error: {error}",
        "wrong_command": "Wrong command format. Send /help for examples.",
        "no_calendars": "No calendars yet.",
        "no_calendars_create": "No calendars yet. Create one first.",
        "calendar_created": "Calendar created: {name} (ID {id})",
        "enter_calendar_name": "Enter calendar name:",
        "enter_timezone": "Enter timezone (e.g. Europe/Moscow):",
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
        "choose_event_cancel": "Choose an event to cancel:",
        "no_future_events": "No future events in this calendar.",
        "no_events_week": "No events for this week.",
        "no_events_upcoming": "No upcoming events.",
        "enter_event_title": "Enter event title:",
        "enter_start_time": "Enter start time (YYYY-MM-DD HH:MM):",
        "enter_duration": "Duration in minutes:",
        "enter_weeks": "Number of weeks (1 for one-time, 2..52 for weekly):",
        "enter_new_start": "Enter new start time (YYYY-MM-DD HH:MM):",
        "events_created": "Created {count} event(s). IDs: {ids}",
        "event_cancelled_notified": "Event cancelled and subscribers notified.",
        "event_rescheduled_notified": "Event rescheduled and subscribers notified.",
        "cancel_this_event": "Cancel this event?",
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
        "tap_to_confirm": "Tap an event to confirm attendance:",
        "confirmed": "Confirmed: {title}\n{time}",
        "already_confirmed": "Already confirmed: {title}",
        "no_subscriptions": "No subscriptions.",
        "sub_muted": "muted",
        "sub_active": "active",
        "timezone_updated": "Timezone updated.",
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
            "/newcalendar Name | Europe/Moscow\n"
            "/calendars\n"
            "/newevent CALENDAR_ID | Title | 2026-09-01 18:30 | DURATION_MINUTES | WEEKS\n"
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
            "/timezone Europe/Moscow\n"
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
        "org.welcome": "Добро пожаловать! Используйте кнопки ниже для управления календарями.",
        "par.welcome": "Добро пожаловать! Используйте кнопки ниже для управления подписками.",
        "choose_language": "Выберите язык:",
        "language_updated": "Язык обновлён.",
        "main_menu": "Главное меню:",
        "cancelled": "Отменено.",
        "nothing_to_cancel": "Нечего отменять.",
        "nothing_to_cancel_event": "Нечего отменять. Используйте ❌ Отменить событие.",
        "error": "Ошибка: {error}",
        "wrong_command": "Неверный формат команды. Отправьте /help для примеров.",
        "no_calendars": "Календарей пока нет.",
        "no_calendars_create": "Календарей пока нет. Сначала создайте календарь.",
        "calendar_created": "Календарь создан: {name} (ID {id})",
        "enter_calendar_name": "Введите название календаря:",
        "enter_timezone": "Введите часовой пояс (например Europe/Moscow):",
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
        "choose_event_cancel": "Выберите событие для отмены:",
        "no_future_events": "В этом календаре нет будущих событий.",
        "no_events_week": "На этой неделе событий нет.",
        "no_events_upcoming": "Нет ближайших событий.",
        "enter_event_title": "Введите название события:",
        "enter_start_time": "Введите время начала (ГГГГ-ММ-ДД ЧЧ:ММ):",
        "enter_duration": "Длительность в минутах:",
        "enter_weeks": "Число недель (1 — разово, 2..52 — еженедельно):",
        "enter_new_start": "Введите новое время начала (ГГГГ-ММ-ДД ЧЧ:ММ):",
        "events_created": "Создано событий: {count}. ID: {ids}",
        "event_cancelled_notified": "Событие отменено, подписчики уведомлены.",
        "event_rescheduled_notified": "Событие перенесено, подписчики уведомлены.",
        "cancel_this_event": "Отменить это событие?",
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
        "tap_to_confirm": "Нажмите на событие, чтобы подтвердить участие:",
        "confirmed": "Подтверждено: {title}\n{time}",
        "already_confirmed": "Уже подтверждено: {title}",
        "no_subscriptions": "Нет подписок.",
        "sub_muted": "без звука",
        "sub_active": "активна",
        "timezone_updated": "Часовой пояс обновлён.",
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
            "/newcalendar Название | Europe/Moscow\n"
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
            "/timezone Europe/Moscow\n"
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
        "org.welcome": "Dobrodošli! Koristite dugmad ispod za upravljanje kalendarima.",
        "par.welcome": "Dobrodošli! Koristite dugmad ispod za upravljanje pretplatama.",
        "choose_language": "Izaberite jezik:",
        "language_updated": "Jezik je ažuriran.",
        "main_menu": "Glavni meni:",
        "cancelled": "Otkazano.",
        "nothing_to_cancel": "Nema šta da se otkaže.",
        "nothing_to_cancel_event": "Nema šta da se otkaže. Koristite ❌ Otkaži događaj.",
        "error": "Greška: {error}",
        "wrong_command": "Pogrešan format komande. Pošaljite /help za primere.",
        "no_calendars": "Još nema kalendara.",
        "no_calendars_create": "Još nema kalendara. Prvo napravite jedan.",
        "calendar_created": "Kalendar kreiran: {name} (ID {id})",
        "enter_calendar_name": "Unesite naziv kalendara:",
        "enter_timezone": "Unesite vremensku zonu (npr. Europe/Belgrade):",
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
        "choose_event_cancel": "Izaberite događaj za otkazivanje:",
        "no_future_events": "Nema budućih događaja u ovom kalendaru.",
        "no_events_week": "Nema događaja za ovu nedelju.",
        "no_events_upcoming": "Nema predstojećih događaja.",
        "enter_event_title": "Unesite naslov događaja:",
        "enter_start_time": "Unesite vreme početka (GGGG-MM-DD ČČ:MM):",
        "enter_duration": "Trajanje u minutima:",
        "enter_weeks": "Broj nedelja (1 jednokratno, 2..52 nedeljno):",
        "enter_new_start": "Unesite novo vreme početka (GGGG-MM-DD ČČ:MM):",
        "events_created": "Kreirano {count} događaja. ID: {ids}",
        "event_cancelled_notified": "Događaj otkazan i pretplatnici obavešteni.",
        "event_rescheduled_notified": "Događaj pomeren i pretplatnici obavešteni.",
        "cancel_this_event": "Otkazati ovaj događaj?",
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
        "tap_to_confirm": "Dodirnite događaj da potvrdite prisustvo:",
        "confirmed": "Potvrđeno: {title}\n{time}",
        "already_confirmed": "Već potvrđeno: {title}",
        "no_subscriptions": "Nema pretplata.",
        "sub_muted": "isključeno",
        "sub_active": "aktivno",
        "timezone_updated": "Vremenska zona ažurirana.",
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
            "/newcalendar Naziv | Europe/Belgrade\n"
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
            "/timezone Europe/Belgrade\n"
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
