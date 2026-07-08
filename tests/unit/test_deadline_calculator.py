"""
Tests for app/deadline_calculator.py — pure compliance-deadline calculation.
No app/client fixture: this module has no Flask/DB dependency.
"""
from datetime import date, timedelta

from app.deadline_calculator import (
    calculate_compliance_deadlines,
    _shift_to_next_business_day,
    _six_monthly_due_dates,
    _annual_return_due_dates,
)
import holidays


# ── Feb 29 grant date ──────────────────────────────────────────────────────────

class TestFeb29GrantDate:

    def test_does_not_crash(self):
        """A naive date.replace(year=year+1) on Feb 29 raises ValueError in
        non-leap years — relativedelta must be used instead, which clamps."""
        events = calculate_compliance_deadlines(date(2024, 2, 29), lease_period_years=2)
        assert len(events) > 0

    def test_six_monthly_dates_clamp_correctly(self):
        events = calculate_compliance_deadlines(date(2024, 2, 29), lease_period_years=2)
        six_monthly = sorted(e["due_date"] for e in events if e["event_type"] == "six_monthly_report")
        # Raw anchors: 2024-08-29, 2025-02-28 (clamped, non-leap), 2025-08-29, 2026-02-28
        assert date(2024, 8, 29) in six_monthly
        assert date(2025, 2, 28) in six_monthly
        assert date(2025, 8, 29) in six_monthly


# ── Month-end drift ────────────────────────────────────────────────────────────

class TestMonthEndDrift:

    def test_no_drift_past_month_end(self):
        """Anchor 31 Aug must keep landing on 28/29 Feb and 31 Aug, never
        drifting to 1/2/3 of the following month (a naive timedelta(days=182)
        approach would drift). Tested against the raw (pre-shift) generator
        because 2027-02-28 happens to be a Sunday in this scenario — the
        weekend shift is a separate concern from the anchor-drift being
        pinned here (see TestWeekendShift for shift behaviour)."""
        grant = date(2026, 8, 31)
        lease_end = date(2028, 8, 31)
        six_monthly = _six_monthly_due_dates(grant, lease_end)
        assert date(2027, 2, 28) in six_monthly
        assert date(2027, 8, 31) in six_monthly
        assert date(2028, 2, 29) in six_monthly
        for d in six_monthly:
            assert d.day in (28, 29, 31)


# ── Weekend shift ──────────────────────────────────────────────────────────────

class TestWeekendShift:

    def test_shift_helper_moves_saturday_to_monday(self):
        inh = holidays.country_holidays('IN', years=[2026])
        saturday = date(2026, 7, 4)
        assert saturday.strftime('%A') == 'Saturday'
        assert _shift_to_next_business_day(saturday, inh) == date(2026, 7, 6)

    def test_full_calculation_shifts_weekend_due_date(self):
        # ec_grant_date + 6 months == 2026-07-04 (Saturday, not a holiday)
        events = calculate_compliance_deadlines(date(2026, 1, 4), lease_period_years=1)
        due_dates = [e["due_date"] for e in events]
        assert date(2026, 7, 4) not in due_dates
        assert date(2026, 7, 6) in due_dates


# ── Holiday shift ──────────────────────────────────────────────────────────────

class TestHolidayShift:

    def test_full_calculation_shifts_holiday_due_date(self):
        # ec_grant_date + 6 months == 2028-10-02 (Gandhi Jayanti, a Monday;
        # 2028-10-03 is a plain Tuesday, so the shift is exactly +1 day).
        events = calculate_compliance_deadlines(date(2028, 4, 2), lease_period_years=1)
        due_dates = [e["due_date"] for e in events]
        assert date(2028, 10, 2) not in due_dates
        assert date(2028, 10, 3) in due_dates


# ── Lease-end boundary ─────────────────────────────────────────────────────────

class TestLeaseEndBoundary:

    def test_no_raw_due_date_exceeds_lease_end(self):
        grant = date(2026, 1, 15)
        lease_period_years = 5
        lease_end = date(2031, 1, 15)
        events = calculate_compliance_deadlines(grant, lease_period_years=lease_period_years)
        # Every due_date is within 2 days of lease_end at most (holiday/weekend
        # shift can nudge slightly past it — see test below), never further.
        for e in events:
            assert e["due_date"] <= lease_end + timedelta(days=3)

    def test_shift_can_push_slightly_past_lease_end(self):
        """Documented edge case: shifting is applied after the lease-end
        filter, so when the last raw due date (which always coincides with
        lease_end for whole-year lease periods) is itself a weekend/holiday,
        the shifted date can land a day or two past lease_end. This is
        expected, not a bug — the raw date was within the lease."""
        grant = date(2020, 2, 1)
        lease_end = date(2025, 2, 1)
        assert lease_end.strftime('%A') == 'Saturday'

        events = calculate_compliance_deadlines(grant, lease_period_years=5)
        due_dates = [e["due_date"] for e in events]
        assert date(2025, 2, 1) not in due_dates
        assert date(2025, 2, 3) in due_dates  # shifted 2 days past lease_end


# ── Sorted output ──────────────────────────────────────────────────────────────

class TestSortedOutput:

    def test_events_sorted_ascending_by_due_date(self):
        events = calculate_compliance_deadlines(date(2026, 1, 15), lease_period_years=5)
        due_dates = [e["due_date"] for e in events]
        assert due_dates == sorted(due_dates)


# ── Annual return proximity (Amendment 2 — unverified placeholder) ────────────

class TestAnnualReturnProximity:

    def test_grant_one_day_before_annual_return_yields_next_day_due_date(self):
        """Pins CURRENT placeholder behaviour: a grant on 30 March yields a
        raw annual-return due date on 31 March the same year — one day
        later. This is tested against the raw (pre-shift) generator, not the
        public calculate_compliance_deadlines output, because 31 March lands
        on a movable-calendar Indian holiday in some years (e.g. Mahavir
        Jayanti in 2026), which would obscure the proximity behaviour being
        pinned here with an unrelated holiday shift.
        UNVERIFIED — whether the first annual return should instead roll to
        the following year in this case is an open question for father
        (Phase 0 Interview Session 2); see COMPLIANCE_CONFIG['annual_return_month'].note.
        """
        grant = date(2026, 3, 30)
        lease_end = date(2031, 3, 30)
        raw_dates = _annual_return_due_dates(grant, lease_end)
        assert raw_dates[0] == date(2026, 3, 31)


# ── Full lease happy path ──────────────────────────────────────────────────────

class TestFullLeaseHappyPath:

    def test_exact_expected_deadline_list(self):
        grant = date(2026, 1, 15)
        events = calculate_compliance_deadlines(grant, lease_period_years=5)

        expected = sorted([
            {"event_type": "six_monthly_report", "due_date": date(2026, 7, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2027, 1, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2027, 7, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2028, 1, 17), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2028, 7, 17), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2029, 1, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2029, 7, 16), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2030, 1, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2030, 7, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "six_monthly_report", "due_date": date(2031, 1, 15), "description": "Six-monthly compliance report to Regional Office"},
            {"event_type": "annual_return", "due_date": date(2026, 4, 1), "description": "Annual return filing"},
            {"event_type": "annual_return", "due_date": date(2027, 3, 31), "description": "Annual return filing"},
            {"event_type": "annual_return", "due_date": date(2028, 3, 31), "description": "Annual return filing"},
            {"event_type": "annual_return", "due_date": date(2029, 4, 2), "description": "Annual return filing"},
            {"event_type": "annual_return", "due_date": date(2030, 4, 1), "description": "Annual return filing"},
        ], key=lambda e: (e["due_date"], e["event_type"]))

        assert events == expected
