"""Week calculation logic for calendar months (Monday-Sunday weeks).

Every operational week is exactly seven days, Monday through Sunday. A week
belongs to the month where its Sunday falls, which avoids duplicating the same
week across adjacent calendar months.
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
    """Compute all Monday-Sunday weeks whose Sunday falls in a given month.

    Returns one tuple per week. Each tuple:
    (week_number, label, start_year, start_month, start_day,
     end_year, end_month, end_day)
    """
    first_day = date(year, month, 1)
    days_until_sunday = (6 - first_day.weekday()) % 7
    current_sunday = first_day + timedelta(days=days_until_sunday)

    weeks: list[tuple[int, str, int, int, int, int, int, int]] = []
    week_num = 1

    while current_sunday.month == month:
        current_monday = current_sunday - timedelta(days=6)
        label = f"{_WEEK_LABELS.get(week_num, f'{week_num}TA')} SEMANA"
        weeks.append(
            (
                week_num,
                label,
                current_monday.year,
                current_monday.month,
                current_monday.day,
                current_sunday.year,
                current_sunday.month,
                current_sunday.day,
            )
        )
        current_sunday += timedelta(days=7)
        week_num += 1

    return weeks
