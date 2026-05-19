"""Week calculation logic for calendar months (Monday-Sunday weeks).

A week belongs to the month whose calendar generated it. The first week of
a month is always the Monday-Sunday week that CONTAINS the 1st (the Monday
of that week may fall in the previous month). Exception: if the 1st is
Sunday, that week has only 1 day in the new month and belongs instead to
the previous month — the new month starts on the following Monday.

This logic is deterministic for any year/month and matches the reference
spreadsheet (Calendario Servicios Médicos) used by the hospital.
"""

from datetime import date, timedelta

_WEEK_LABELS: dict[int, str] = {
    1: "1RA",
    2: "2DA",
    3: "3RA",
    4: "4TA",
    5: "5TA",
    6: "6TA",
}


def compute_weeks(
    year: int, month: int
) -> list[tuple[int, str, int, int, int, int, int, int]]:
    """Compute all Monday-Sunday weeks that overlap with a given month.

    Returns one tuple per week. Each tuple:
    (week_number, label, start_year, start_month, start_day,
     end_year, end_month, end_day)
    """
    first_day = date(year, month, 1)

    # Monday of the week containing the 1st (goes back if 1st is not Monday)
    first_monday = first_day - timedelta(days=first_day.weekday())

    # If the 1st is Sunday, that week has only 1 day in this month — skip it
    if first_day.weekday() == 6:  # Sunday
        first_monday += timedelta(days=7)

    weeks: list[tuple[int, str, int, int, int, int, int, int]] = []
    current_monday = first_monday
    week_num = 1

    # Allow the first week even if its Monday is in the previous month
    # (cross-boundary week containing the 1st). Stop when the Monday is
    # on or after the 1st and in a different month (the next month's
    # first-week marker).
    while current_monday.month == month or current_monday < first_day:
        sunday = current_monday + timedelta(days=6)
        label = f"{_WEEK_LABELS.get(week_num, f'{week_num}TA')} SEMANA"
        weeks.append(
            (
                week_num,
                label,
                current_monday.year,
                current_monday.month,
                current_monday.day,
                sunday.year,
                sunday.month,
                sunday.day,
            )
        )
        current_monday += timedelta(days=7)
        week_num += 1

    return weeks
