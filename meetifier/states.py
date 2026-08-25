from aiogram.fsm.state import State, StatesGroup


class OrganizerNewCalendar(StatesGroup):
    name = State()
    timezone = State()


class OrganizerNewEvent(StatesGroup):
    title = State()
    start = State()
    duration = State()
    weeks = State()


class OrganizerReschedule(StatesGroup):
    new_start = State()


class ParticipantTimezone(StatesGroup):
    timezone = State()


class ParticipantReminders(StatesGroup):
    minutes = State()
