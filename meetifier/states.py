from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrganizerNewCalendar(StatesGroup):
    name = State()
    timezone = State()
    confirmation = State()


class OrganizerConfirmTiming(StatesGroup):
    calendar = State()
    minutes = State()


class OrganizerNewEvent(StatesGroup):
    calendar = State()
    title = State()
    start = State()
    duration = State()
    pattern = State()
    weekdays = State()
    interval = State()
    monthly_pos = State()
    monthly_weekday = State()
    count = State()


class OrganizerReschedule(StatesGroup):
    calendar = State()
    series = State()
    occurrence = State()
    scope = State()
    new_start = State()


class OrganizerCancelEvent(StatesGroup):
    calendar = State()
    series = State()
    occurrence = State()
    scope = State()
    confirm = State()


class OrganizerInvite(StatesGroup):
    calendar = State()


class OrganizerEvents(StatesGroup):
    range_pick = State()
    calendar = State()
    series = State()


class OrganizerConfirmations(StatesGroup):
    calendar = State()
    series = State()
    occurrence = State()


class OrganizerGoogleMap(StatesGroup):
    calendar = State()
    google_cal = State()


class OrganizerGoogleImport(StatesGroup):
    google_cal = State()


class OrganizerGoogleSync(StatesGroup):
    calendar = State()


class OrganizerGoogleAdopt(StatesGroup):
    calendar = State()
    confirm = State()


class ParticipantTimezone(StatesGroup):
    timezone = State()


class ParticipantReminders(StatesGroup):
    calendar = State()
    minutes = State()


class ParticipantUpcoming(StatesGroup):
    range_pick = State()
    calendar = State()
    series = State()


class ParticipantConfirmPick(StatesGroup):
    calendar = State()
    series = State()
    occurrence = State()


class ParticipantMute(StatesGroup):
    calendar = State()


class ParticipantUnmute(StatesGroup):
    calendar = State()


class ParticipantUnsubscribe(StatesGroup):
    calendar = State()
