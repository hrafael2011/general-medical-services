"""Week calculation logic for calendar months (Sunday-Saturday weeks).

Every operational week is exactly seven days, Sunday through Saturday.
A month's calendar includes every week that contains at least one day
of that month. Weeks that span two months appear in both calendars.
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
    """Compute all Sunday-Saturday weeks that contain ≥1 day of the month.

    Returns one tuple per week. Each tuple:
    (week_number, label, start_year, start_month, start_day,
     end_year, end_month, end_day)
    """
    first_day = date(year, month, 1)
    # Find the first Sunday that is ≤ the 1st of the month.
    # weekday(): Monday=0 ... Sunday=6.
    # days_since_sunday = (weekday + 1) % 7:
    #   Sunday (6) → 0, Monday (0) → 1, Tuesday (1) → 2, ...
    days_since_sunday = (first_day.weekday() + 1) % 7
    current_sunday = first_day - timedelta(days=days_since_sunday)

    weeks: list[tuple[int, str, int, int, int, int, int, int]] = []
    week_num = 1

    while True:
        current_saturday = current_sunday + timedelta(days=6)
        # Stop when the week no longer contains ANY day of the target month.
        if current_sunday.month != month and current_saturday.month != month:
            break

        label = f"{_WEEK_LABELS.get(week_num, f'{week_num}TA')} SEMANA"
        weeks.append(
            (
                week_num,
                label,
                current_sunday.year,
                current_sunday.month,
                current_sunday.day,
                current_saturday.year,
                current_saturday.month,
                current_saturday.day,
            )
        )
        current_sunday += timedelta(days=7)
        week_num += 1

    return weeks
