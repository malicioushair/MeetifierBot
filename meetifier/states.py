from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrganizerNewCalendar(StatesGroup):
    name = State()
    timezone = State()


class OrganizerNewEvent(StatesGroup):
    calendar = State()
    title = State()
    start = State()
    duration = State()
    weeks = State()


class OrganizerReschedule(StatesGroup):
    calendar = State()
    event = State()
    new_start = State()


class OrganizerCancelEvent(StatesGroup):
    calendar = State()
    event = State()
    confirm = State()


class OrganizerInvite(StatesGroup):
    calendar = State()


class OrganizerEvents(StatesGroup):
    range_pick = State()
    calendar = State()


class OrganizerConfirmations(StatesGroup):
    calendar = State()
    event = State()


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


class ParticipantConfirmPick(StatesGroup):
    pick = State()


class ParticipantMute(StatesGroup):
    calendar = State()


class ParticipantUnmute(StatesGroup):
    calendar = State()


class ParticipantUnsubscribe(StatesGroup):
    calendar = State()
