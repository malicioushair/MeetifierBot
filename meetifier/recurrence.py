from __future__ import annotations

import calendar as cal_mod
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone

from .config import tzinfo_from_offset

MAX_OCCURRENCES = 104


@dataclass
class RecurrenceRule:
    """Materialize occurrence local dates from an anchor local datetime."""

    freq: str = "once"  # once | weekly | monthly_nth
    interval: int = 1
    byweekday: list[int] = field(default_factory=list)  # 0=Mon .. 6=Sun
    bysetpos: int | None = None  # 1..4 or -1 (last) for monthly_nth
    count: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str | None) -> RecurrenceRule | None:
        if not raw:
            return None
        data = json.loads(raw)
        return cls(
            freq=data.get("freq", "once"),
            interval=int(data.get("interval") or 1),
            byweekday=[int(x) for x in (data.get("byweekday") or [])],
            bysetpos=data.get("bysetpos"),
            count=int(data.get("count") or 1),
        )

    @classmethod
    def once(cls) -> RecurrenceRule:
        return cls(freq="once", count=1)

    @classmethod
    def weekly(cls, *, weekdays: list[int], interval: int = 1, count: int = 1) -> RecurrenceRule:
        return cls(freq="weekly", interval=interval, byweekday=sorted(set(weekdays)), count=count)

    @classmethod
    def monthly_nth(cls, *, weekday: int, bysetpos: int, count: int = 1) -> RecurrenceRule:
        return cls(freq="monthly_nth", interval=1, byweekday=[weekday], bysetpos=bysetpos, count=count)

    def validate(self) -> None:
        if self.freq not in {"once", "weekly", "monthly_nth"}:
            raise ValueError("Frequency must be once, weekly, or monthly_nth")
        if not 1 <= self.count <= MAX_OCCURRENCES:
            raise ValueError(f"Count must be 1..{MAX_OCCURRENCES}")
        if self.freq == "once":
            return
        if not 1 <= self.interval <= 12:
            raise ValueError("Interval must be 1..12")
        if self.freq == "weekly":
            if not self.byweekday or any(d < 0 or d > 6 for d in self.byweekday):
                raise ValueError("Pick one or more weekdays (Mon–Sun)")
        elif self.freq == "monthly_nth":
            if self.bysetpos not in {1, 2, 3, 4, -1}:
                raise ValueError("Monthly position must be 1..4 or last (-1)")
            if len(self.byweekday) != 1 or self.byweekday[0] < 0 or self.byweekday[0] > 6:
                raise ValueError("Monthly rule needs exactly one weekday")


def parse_local_naive(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD HH:MM") from exc


def generate_starts_utc(
    rule: RecurrenceRule,
    local_start: str,
    tz_offset_hours: int | str,
    duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Return list of (start_utc, end_utc) naive UTC datetimes."""
    rule.validate()
    if not 1 <= duration_minutes <= 10080:
        raise ValueError("Duration must be 1..10080 minutes")
    anchor = parse_local_naive(local_start)
    local_dates = _generate_local_datetimes(rule, anchor)
    duration = timedelta(minutes=duration_minutes)
    tz = tzinfo_from_offset(tz_offset_hours)
    result: list[tuple[datetime, datetime]] = []
    for local_dt in local_dates:
        start_utc = local_dt.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        result.append((start_utc, start_utc + duration))
    return result


def _generate_local_datetimes(rule: RecurrenceRule, anchor: datetime) -> list[datetime]:
    if rule.freq == "once":
        return [anchor]
    if rule.freq == "weekly":
        return _generate_weekly(rule, anchor)
    return _generate_monthly_nth(rule, anchor)


def _generate_weekly(rule: RecurrenceRule, anchor: datetime) -> list[datetime]:
    weekdays = set(rule.byweekday or [anchor.weekday()])
    results: list[datetime] = []
    day = anchor.date()
    week0_monday = day - timedelta(days=day.weekday())
    guard = 0
    while len(results) < rule.count and guard < MAX_OCCURRENCES * 14 * max(rule.interval, 1):
        guard += 1
        weeks_since = (day - week0_monday).days // 7
        if weeks_since >= 0 and weeks_since % rule.interval == 0 and day.weekday() in weekdays:
            local_dt = datetime(day.year, day.month, day.day, anchor.hour, anchor.minute)
            if local_dt >= anchor:
                results.append(local_dt)
        day += timedelta(days=1)
    if not results:
        raise ValueError("Recurrence produced no dates")
    return results


def _generate_monthly_nth(rule: RecurrenceRule, anchor: datetime) -> list[datetime]:
    weekday = rule.byweekday[0]
    bysetpos = rule.bysetpos if rule.bysetpos is not None else 1
    results: list[datetime] = []
    year, month = anchor.year, anchor.month
    guard = 0
    while len(results) < rule.count and guard < MAX_OCCURRENCES * 2:
        guard += 1
        months_since = (year - anchor.year) * 12 + (month - anchor.month)
        if months_since >= 0 and months_since % rule.interval == 0:
            target = _nth_weekday_of_month(year, month, weekday, bysetpos)
            if target is not None:
                local_dt = datetime(target.year, target.month, target.day, anchor.hour, anchor.minute)
                if local_dt >= anchor:
                    results.append(local_dt)
        month += 1
        if month > 12:
            month = 1
            year += 1
    if not results:
        raise ValueError("Recurrence produced no dates")
    return results


def _nth_weekday_of_month(year: int, month: int, weekday: int, bysetpos: int) -> date | None:
    """weekday: 0=Mon..6=Sun; bysetpos: 1..4 or -1."""
    weeks = cal_mod.monthcalendar(year, month)
    candidates = [week[weekday] for week in weeks if week[weekday] != 0]
    if not candidates:
        return None
    if bysetpos == -1:
        day_num = candidates[-1]
    elif 1 <= bysetpos <= len(candidates):
        day_num = candidates[bysetpos - 1]
    else:
        return None
    return date(year, month, day_num)


def rule_from_legacy_weeks(weeks: int, anchor_weekday: int) -> RecurrenceRule:
    if not 1 <= weeks <= MAX_OCCURRENCES:
        raise ValueError(f"Weeks must be 1..{MAX_OCCURRENCES}")
    if weeks == 1:
        return RecurrenceRule.once()
    return RecurrenceRule.weekly(weekdays=[anchor_weekday], interval=1, count=weeks)
