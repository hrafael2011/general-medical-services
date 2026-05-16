"""Week calculation logic for calendar months (Monday-Sunday weeks)."""

from datetime import date, timedelta

_WEEK_LABELS: dict[int, str] = {
    1: "1RA",
    2: "2DA",
    3: "3RA",
    4: "4TA",
    5: "5TA",
}


def compute_weeks(
    year: int, month: int
) -> list[tuple[int, str, int, int, int, int, int, int]]:
    """Compute all Monday-Sunday weeks for a given month.

    Returns one tuple per Monday that falls within the month. Each tuple:
    (week_number, label, start_year, start_month, start_day,
     end_year, end_month, end_day)

    Weeks that start in the previous month (i.e., the first Monday is before
    month start) are not included — they belong to the previous month's week set.
    """
    first_day = date(year, month, 1)
    # weekday(): Monday = 0, Sunday = 6
    days_until_monday = (0 - first_day.weekday()) % 7
    first_monday = first_day + timedelta(days=days_until_monday)

    weeks: list[tuple[int, str, int, int, int, int, int, int]] = []
    current_monday = first_monday
    week_num = 1

    while current_monday.month == month:
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
