"""Tests for week-of-month calculation (Sunday-Saturday, week-touches-month rule)."""
from datetime import date, timedelta
from backend.app.domain.calendars.weeks import compute_weeks


# ---------------------------------------------------------------------------
# New rule: Sunday-Saturday weeks, includes any week touching the month
# ---------------------------------------------------------------------------

def test_june_2026_has_five_weeks():
    """June 2026: 1st is Monday. First week Sun May 31-Sat Jun 6 (touches Jun).
    Last week Sun Jun 28-Sat Jul 4 (touches Jun + Jul). Total = 5."""
    weeks = compute_weeks(2026, 6)
    assert len(weeks) == 5, f"Expected 5 weeks, got {len(weeks)}"
    # Week 1: Sun May 31 - Sat Jun 6
    assert weeks[0] == (1, "1RA SEMANA", 2026, 5, 31, 2026, 6, 6)
    # Week 5: Sun Jun 28 - Sat Jul 4
    assert weeks[4] == (5, "5TA SEMANA", 2026, 6, 28, 2026, 7, 4)


def test_march_2026_has_five_weeks():
    """March 2026: 1st is Sunday. First week Sun Mar 1-Sat Mar 7.
    Last week Sun Mar 29-Sat Apr 4 (touches Mar + Apr). Total = 5."""
    weeks = compute_weeks(2026, 3)
    assert len(weeks) == 5, f"Expected 5 weeks, got {len(weeks)}"
    # Week 1: Sun Mar 1 - Sat Mar 7
    assert weeks[0] == (1, "1RA SEMANA", 2026, 3, 1, 2026, 3, 7)
    # Week 5: Sun Mar 29 - Sat Apr 4
    assert weeks[4] == (5, "5TA SEMANA", 2026, 3, 29, 2026, 4, 4)


def test_february_2026_has_four_weeks():
    """February 2026: 1st is Sunday. 28 days. First week Sun Feb 1.
    Last week Sun Feb 22-Sat Feb 28. Total = 4."""
    weeks = compute_weeks(2026, 2)
    assert len(weeks) == 4, f"Expected 4 weeks, got {len(weeks)}"
    # Week 1: Sun Feb 1 - Sat Feb 7
    assert weeks[0] == (1, "1RA SEMANA", 2026, 2, 1, 2026, 2, 7)
    # Week 4: Sun Feb 22 - Sat Feb 28
    assert weeks[3] == (4, "4TA SEMANA", 2026, 2, 22, 2026, 2, 28)


def test_december_2026_has_five_weeks():
    """December 2026: 1st is Tuesday. First week Sun Nov 29-Sat Dec 5."""
    weeks = compute_weeks(2026, 12)
    assert len(weeks) == 5, f"Expected 5 weeks, got {len(weeks)}"
    # Week 1: Sun Nov 29 - Sat Dec 5
    assert weeks[0] == (1, "1RA SEMANA", 2026, 11, 29, 2026, 12, 5)
    # Week 5: Sun Dec 27 - Sat Jan 2
    assert weeks[4] == (5, "5TA SEMANA", 2026, 12, 27, 2027, 1, 2)


def test_january_2026_has_five_weeks():
    """January 2026: 1st is Thursday. First week Sun Dec 28-Sat Jan 3."""
    weeks = compute_weeks(2026, 1)
    assert len(weeks) == 5, f"Expected 5 weeks, got {len(weeks)}"
    # Week 1: Sun Dec 28 - Sat Jan 3
    assert weeks[0] == (1, "1RA SEMANA", 2025, 12, 28, 2026, 1, 3)
    # Week 5: Sun Jan 25 - Sat Jan 31
    assert weeks[4] == (5, "5TA SEMANA", 2026, 1, 25, 2026, 1, 31)


def test_adjacent_months_share_boundary_weeks():
    """A week spanning two months appears in BOTH calendars.
    e.g., Mar 29-Apr 4 is in March (Sunday in March) AND April (touches April)."""
    march_weeks = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, 3)}
    april_weeks = {(w[2], w[3], w[4], w[5], w[6], w[7]) for w in compute_weeks(2026, 4)}
    # The week Mar 29-Apr 4 should be in BOTH
    overlap = march_weeks & april_weeks
    assert len(overlap) >= 1, "Expected at least one shared week between March and April"


def test_all_weeks_are_sunday_to_saturday_seven_day_ranges():
    """Every operational week is exactly Sunday through Saturday."""
    for year, month in [(2026, 3), (2026, 4), (2026, 5), (2026, 6)]:
        for week in compute_weeks(year, month):
            start = date(week[2], week[3], week[4])
            end = date(week[5], week[6], week[7])
            assert start.weekday() == 6, f"Expected Sunday (6), got {start.weekday()} for {start}"
            assert end.weekday() == 5, f"Expected Saturday (5), got {end.weekday()} for {end}"
            assert end - start == timedelta(days=6)


def test_all_days_of_month_covered_by_at_least_one_week():
    """Every day of the month must appear in at least one week."""
    for month in range(1, 13):
        weeks = compute_weeks(2026, month)
        covered = set()
        for w in weeks:
            d = date(w[2], w[3], w[4])
            end = date(w[5], w[6], w[7])
            while d <= end:
                if d.month == month:
                    covered.add(d.day)
                d += timedelta(days=1)
        from calendar import monthrange
        last_day = monthrange(2026, month)[1]
        missing = set(range(1, last_day + 1)) - covered
        assert not missing, f"Month {month}: missing days {missing}"
