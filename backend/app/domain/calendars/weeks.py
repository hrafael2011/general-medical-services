"""Week-of-month calculation (Monday-Sunday, first Monday rule)."""
from datetime import date, timedelta

_WEEK_LABELS = {
    1: "1RA SEMANA",
    2: "2DA SEMANA",
    3: "3RA SEMANA",
    4: "4TA SEMANA",
    5: "5TA SEMANA",
}


def compute_weeks(year: int, month: int) -> list[tuple]:
    """Compute calendar weeks for a month (Monday-Sunday).

    The first Monday of the month starts Week 1. Days before the first Monday
    belong to the previous month's last week. Weeks may extend into the next
    month if the month does not end on a Sunday.

    Returns a list of tuples:
        (week_number, label, start_year, start_month, start_day,
         end_year, end_month, end_day)
    """
    def _first_monday(y: int, m: int) -> date:
        d = date(y, m, 1)
        while d.weekday() != 0:  # Monday = 0
            d += timedelta(days=1)
        return d

    def _last_day(y: int, m: int) -> date:
        if m == 12:
            return date(y + 1, 1, 1) - timedelta(days=1)
        return date(y, m + 1, 1) - timedelta(days=1)

    start = _first_monday(year, month)
    month_end = _last_day(year, month)

    weeks: list[tuple] = []
    current = start
    week_num = 1

    while True:
        week_end = current + timedelta(days=6)
        weeks.append((
            week_num,
            _WEEK_LABELS[week_num],
            current.year, current.month, current.day,
            week_end.year, week_end.month, week_end.day,
        ))
        current = week_end + timedelta(days=1)
        if current > month_end:
            break
        week_num += 1

    return weeks
