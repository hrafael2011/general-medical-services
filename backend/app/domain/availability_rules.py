"""Shared date rules for doctor availability."""

from calendar import monthrange
from datetime import date, timedelta


def matches_recurring_monthly_rule(target_date: date, weekday: int | None, week_number: int | None) -> bool:
    """Return True when target_date matches an nth-weekday monthly rule.

    week_number uses the persisted convention:
    0=first, 1=second, 2=third, 3=fourth, -1=last.
    """
    if weekday is None or week_number is None:
        return False
    if target_date.weekday() != weekday:
        return False

    if week_number == -1:
        last_day = date(target_date.year, target_date.month, monthrange(target_date.year, target_date.month)[1])
        current = last_day
        while current.weekday() != weekday:
            current -= timedelta(days=1)
        return target_date == current

    if week_number not in (0, 1, 2, 3):
        return False

    first_day = date(target_date.year, target_date.month, 1)
    days_until_weekday = (weekday - first_day.weekday()) % 7
    occurrence = first_day + timedelta(days=days_until_weekday + (week_number * 7))
    return target_date == occurrence


def belongs_to_operational_month(target_date: date, year: int, month: int) -> bool:
    """Return True when target_date belongs to the Sunday-owned calendar month."""
    sunday = target_date + timedelta(days=6 - target_date.weekday())
    return sunday.year == year and sunday.month == month
