"""Tests for week-of-month calculation (Monday-Sunday, first Monday rule)."""
from datetime import date, timedelta
from backend.app.domain.calendars.weeks import compute_weeks


def test_may_2026_first_monday_is_may_4():
    """May 2026: first Monday = May 4. 4 full weeks, ends Sunday 31."""
    weeks = compute_weeks(year=2026, month=5)
    assert len(weeks) == 4
    assert weeks[0] == (1, "1RA SEMANA", 2026, 5, 4,  2026, 5, 10)
    assert weeks[1] == (2, "2DA SEMANA", 2026, 5, 11, 2026, 5, 17)
    assert weeks[2] == (3, "3RA SEMANA", 2026, 5, 18, 2026, 5, 24)
    assert weeks[3] == (4, "4TA SEMANA", 2026, 5, 25, 2026, 5, 31)


def test_april_2026_extends_into_may():
    """April 2026: first Monday = Apr 6, week 4 extends into May."""
    weeks = compute_weeks(year=2026, month=4)
    assert len(weeks) == 4
    assert weeks[3] == (4, "4TA SEMANA", 2026, 4, 27, 2026, 5, 3)


def test_month_starts_on_monday():
    """When the 1st is Monday, Week 1 starts on day 1."""
    weeks = compute_weeks(year=2026, month=6)  # June 2026: 1st = Monday
    assert weeks[0] == (1, "1RA SEMANA", 2026, 6, 1, 2026, 6, 7)


def test_days_before_first_monday_not_included():
    """Days before the first Monday belong to the previous month's last week."""
    weeks = compute_weeks(year=2026, month=4)
    # April 1-5 (Wed-Sun) are NOT in any April week
    all_covered_days = set()
    for w in weeks:
        d = date(w[2], w[3], w[4])
        end = date(w[5], w[6], w[7])
        while d <= end:
            if d.month == 4:
                all_covered_days.add(d.day)
            d += timedelta(days=1)
    assert 1 not in all_covered_days  # April 1 is NOT covered
    assert 2 not in all_covered_days  # April 2 is NOT covered
    assert 6 in all_covered_days      # April 6 (Monday) IS covered


def test_5_weeks_when_month_spans_5_mondays():
    """Some months span 5 Mondays, producing 5 calendar weeks."""
    weeks = compute_weeks(year=2026, month=3)
    # Mar 2026: first Monday = Mar 2. Weeks: 2-8, 9-15, 16-22, 23-29, 30-Apr 5
    assert len(weeks) == 5
