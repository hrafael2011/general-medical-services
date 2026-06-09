"""Tests for week-of-month calculation (Monday-Sunday, Monday-ownership rule)."""
from datetime import date, timedelta
from backend.app.domain.calendars.weeks import compute_weeks


def test_june_2026_has_five_weeks():
    """June 2026: 1st is Monday. Weeks: Jun 1, 8, 15, 22, 29."""
    weeks = compute_weeks(2026, 6)
    assert len(weeks) == 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 6, 1, 2026, 6, 7)
    assert weeks[4] == (5, "5TA SEMANA", 2026, 6, 29, 2026, 7, 5)


def test_july_2026_has_four_weeks():
    """July 2026: 1st is Wednesday. First Monday = Jul 6."""
    weeks = compute_weeks(2026, 7)
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 7, 6, 2026, 7, 12)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 7, 27, 2026, 8, 2)


def test_august_2026_has_five_weeks():
    """August 2026: 1st is Saturday. First Monday = Aug 3."""
    weeks = compute_weeks(2026, 8)
    assert len(weeks) == 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 8, 3, 2026, 8, 9)
    assert weeks[4] == (5, "5TA SEMANA", 2026, 8, 31, 2026, 9, 6)


def test_september_2026_has_four_weeks():
    """September 2026: 1st is Tuesday. First Monday = Sep 7."""
    weeks = compute_weeks(2026, 9)
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 9, 7, 2026, 9, 13)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 9, 28, 2026, 10, 4)


def test_march_2026_has_five_weeks():
    """March 2026: 1st is Sunday. First Monday = Mar 2."""
    weeks = compute_weeks(2026, 3)
    assert len(weeks) == 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 3, 2, 2026, 3, 8)
    assert weeks[4] == (5, "5TA SEMANA", 2026, 3, 30, 2026, 4, 5)


def test_january_2026_has_four_weeks():
    """January 2026: 1st is Thursday. First Monday = Jan 5."""
    weeks = compute_weeks(2026, 1)
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 1, 5, 2026, 1, 11)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 1, 26, 2026, 2, 1)


def test_no_duplication_between_adjacent_months():
    """Weeks must never appear in two months."""
    for m in range(1, 12):
        current = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, m)}
        next_month = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, m + 1)}
        assert current.isdisjoint(next_month), f"Months {m} and {m+1} share weeks!"


def test_all_weeks_are_monday_to_sunday():
    """Every week is exactly Monday through Sunday."""
    for month in range(1, 13):
        for week in compute_weeks(2026, month):
            start = date(week[2], week[3], week[4])
            end = date(week[5], week[6], week[7])
            assert start.weekday() == 0, f"Expected Monday, got {start}"
            assert end.weekday() == 6, f"Expected Sunday, got {end}"
            assert end - start == timedelta(days=6)


def test_first_monday_per_month():
    """Verify the first Monday day number for each month of 2026."""
    expected = {1: 5, 2: 2, 3: 2, 4: 6, 5: 4, 6: 1,
                7: 6, 8: 3, 9: 7, 10: 5, 11: 2, 12: 7}
    for month, day in expected.items():
        weeks = compute_weeks(2026, month)
        assert weeks[0][4] == day, f"Month {month}: expected day {day}, got {weeks[0]}"
