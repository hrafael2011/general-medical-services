"""Tests for week-of-month calculation (Monday-Sunday, Sunday ownership rule)."""
from datetime import date, timedelta
from backend.app.domain.calendars.weeks import compute_weeks


def test_may_2026_starts_with_week_ending_in_may():
    """May 2026 owns Apr 27-May 3 because that Sunday's month is May."""
    weeks = compute_weeks(year=2026, month=5)
    assert len(weeks) == 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 4, 27, 2026, 5, 3)
    assert weeks[1] == (2, "2DA SEMANA", 2026, 5, 4, 2026, 5, 10)
    assert weeks[4] == (5, "5TA SEMANA", 2026, 5, 25, 2026, 5, 31)


def test_april_2026_does_not_duplicate_week_ending_in_may():
    """April 2026 excludes Apr 27-May 3 because that Sunday belongs to May."""
    weeks = compute_weeks(year=2026, month=4)
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 3, 30, 2026, 4, 5)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 4, 20, 2026, 4, 26)


def test_month_starts_on_monday():
    """When the 1st is Monday, weeks still stop at the last Sunday in month."""
    weeks = compute_weeks(year=2026, month=6)  # June 2026: 1st = Monday
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 6, 1, 2026, 6, 7)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 6, 22, 2026, 6, 28)


def test_days_before_first_monday_are_included_when_their_sunday_is_in_month():
    """April 1-5 belong to April because the Sunday ending the week is Apr 5."""
    weeks = compute_weeks(year=2026, month=4)
    all_covered_days = set()
    for w in weeks:
        d = date(w[2], w[3], w[4])
        end = date(w[5], w[6], w[7])
        while d <= end:
            if d.month == 4:
                all_covered_days.add(d.day)
            d += timedelta(days=1)
    assert 1 in all_covered_days
    assert 2 in all_covered_days
    assert 26 in all_covered_days
    assert 27 not in all_covered_days


def test_month_starts_on_sunday_keeps_the_full_week():
    """March 2026 owns Feb 23-Mar 1 because Sunday Mar 1 ends that week."""
    weeks = compute_weeks(year=2026, month=3)
    assert len(weeks) == 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 2, 23, 2026, 3, 1)
    assert weeks[4] == (5, "5TA SEMANA", 2026, 3, 23, 2026, 3, 29)


def test_adjacent_months_do_not_duplicate_weeks():
    """A Monday-Sunday range can belong to exactly one calendar month."""
    april_ranges = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, 4)}
    may_ranges = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, 5)}
    assert april_ranges.isdisjoint(may_ranges)


def test_all_weeks_are_monday_to_sunday_seven_day_ranges():
    """Every operational week is exactly Monday through Sunday."""
    for year, month in [(2026, 3), (2026, 4), (2026, 5), (2026, 6)]:
        for week in compute_weeks(year, month):
            start = date(week[2], week[3], week[4])
            end = date(week[5], week[6], week[7])
            assert start.weekday() == 0
            assert end.weekday() == 6
            assert end - start == timedelta(days=6)
