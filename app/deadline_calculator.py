# ============================================================
# FILE: app/deadline_calculator.py
# PURPOSE: Pure compliance-deadline calculation from an EC grant date
# LAST UPDATED: Phase 1 — Compliance Automation Chunk 2
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from dataclasses import dataclass
from datetime import date, timedelta

import holidays
from dateutil.relativedelta import relativedelta


# ------------------------------------------------------------
# SECTION 2: CONFIG — ALL FATHER-VERIFY PLACEHOLDERS
# ------------------------------------------------------------
@dataclass(frozen=True)
class ConfigParam:
    """A single tunable compliance parameter, pending father verification."""
    value: object
    verified_by_father: bool
    note: str


COMPLIANCE_CONFIG = {
    "report_cadence_months": ConfigParam(
        value=6,
        verified_by_father=False,
        note=(
            "Six-monthly compliance report cadence — placeholder. Confirm "
            "exact reporting cycle and first-due-date rule with father "
            "(Phase 0 Interview Session 2)."
        ),
    ),
    "annual_return_month": ConfigParam(
        value=3,
        verified_by_father=False,
        note=(
            "Annual return month — placeholder (31 March, typical Indian "
            "financial-year end). Grant dates within ~1 day of 31 March "
            "produce an annual return due almost immediately after grant — "
            "confirm with father whether the first annual return should "
            "instead roll to the following year in this case "
            "(Phase 0 Interview Session 2)."
        ),
    ),
    "annual_return_day": ConfigParam(
        value=31,
        verified_by_father=False,
        note="See annual_return_month note — same open question applies.",
    ),
    "default_lease_period_years": ConfigParam(
        value=5,
        verified_by_father=False,
        note=(
            "Default lease period when not otherwise specified — "
            "placeholder. Confirm typical/default lease duration with "
            "father (Phase 0 Interview Session 2)."
        ),
    ),
    "holiday_shift_rule": ConfigParam(
        value="next_business_day",
        verified_by_father=False,
        note=(
            "Deadlines falling on a weekend or holiday shift FORWARD to the "
            "next business day (never backward) — reasoning: a closed "
            "government office means the filer cannot submit until it "
            "reopens. Holiday calendar used is holidays.country_holidays"
            "('IN') — national/gazetted holidays only; it does NOT include "
            "state-specific DMG office closures. Both the shift direction "
            "and the calendar's completeness are placeholders pending "
            "father verification (Phase 0 Interview Session 2)."
        ),
    ),
}

EVENT_DESCRIPTIONS = {
    "six_monthly_report": "Six-monthly compliance report to Regional Office",
    "annual_return": "Annual return filing",
}


# ------------------------------------------------------------
# SECTION 3: INTERNAL HELPERS
# ------------------------------------------------------------
def _shift_to_next_business_day(d: date, in_holidays: 'holidays.HolidayBase') -> date:
    """
    PURPOSE  : Push a date forward until it is a weekday and not a holiday
    RECEIVES : d — candidate date; in_holidays — holidays.HolidayBase to check against
    RETURNS  : date — the same date if already a business day, else the next one
    SECURITY : n/a — pure date arithmetic, no I/O
    LEGAL    : see calculate_compliance_deadlines LEGAL note
    """
    while d.weekday() >= 5 or d in in_holidays:
        d += timedelta(days=1)
    return d


def _six_monthly_due_dates(ec_grant_date: date, lease_end: date) -> list:
    """
    PURPOSE  : Raw (unshifted) six-monthly report due dates within the lease
    RECEIVES : ec_grant_date — anchor date; lease_end — last valid date
    RETURNS  : list[date] — ascending, each <= lease_end
    SECURITY : n/a — pure date arithmetic, no I/O
    LEGAL    : see calculate_compliance_deadlines LEGAL note
    """
    cadence = COMPLIANCE_CONFIG["report_cadence_months"].value
    dates = []
    n = 1
    while True:
        # Always offset from the original anchor (not the previous result) so
        # relativedelta's month-end clamping can't compound drift across
        # iterations (e.g. anchor 31 Aug must keep landing on 28/29 Feb / 31
        # Aug, never drifting to 1/2/3 of the following month).
        due = ec_grant_date + relativedelta(months=cadence * n)
        if due > lease_end:
            break
        dates.append(due)
        n += 1
    return dates


def _annual_return_due_dates(ec_grant_date: date, lease_end: date) -> list:
    """
    PURPOSE  : Raw (unshifted) annual return due dates within the lease
    RECEIVES : ec_grant_date — anchor date; lease_end — last valid date
    RETURNS  : list[date] — ascending, each <= lease_end
    SECURITY : n/a — pure date arithmetic, no I/O
    LEGAL    : see calculate_compliance_deadlines LEGAL note — first-year
               proximity behaviour is an open father-verify question
    """
    month = COMPLIANCE_CONFIG["annual_return_month"].value
    day = COMPLIANCE_CONFIG["annual_return_day"].value

    first = date(ec_grant_date.year, month, day)
    if first < ec_grant_date:
        first = date(ec_grant_date.year + 1, month, day)

    dates = []
    due = first
    while due <= lease_end:
        dates.append(due)
        due = due + relativedelta(years=1)
    return dates


# ------------------------------------------------------------
# SECTION 4: PUBLIC API
# ------------------------------------------------------------
def calculate_compliance_deadlines(ec_grant_date: date, lease_period_years: int = None) -> list:
    """
    PURPOSE  : Compute the full list of compliance deadlines for a lease
    RECEIVES : ec_grant_date — date the EC was granted;
               lease_period_years — lease duration in years, defaults to
               COMPLIANCE_CONFIG["default_lease_period_years"] when None
    RETURNS  : list[dict] — sorted by due_date, each
               {"event_type": str, "due_date": date, "description": str}
    SECURITY : n/a — pure function, no DB access, no I/O, no side effects
    LEGAL    : All dates are ESTIMATES derived from placeholder parameters in
               COMPLIANCE_CONFIG (verified_by_father=False on every entry) —
               pending father verification at Phase 0 Interview Session 2.
               Do not treat these as authoritative filing deadlines.
    """
    if lease_period_years is None:
        lease_period_years = COMPLIANCE_CONFIG["default_lease_period_years"].value

    lease_end = ec_grant_date + relativedelta(years=lease_period_years)
    in_holidays = holidays.country_holidays(
        'IN', years=range(ec_grant_date.year, lease_end.year + 2)
    )

    raw_events = [
        ("six_monthly_report", d) for d in _six_monthly_due_dates(ec_grant_date, lease_end)
    ] + [
        ("annual_return", d) for d in _annual_return_due_dates(ec_grant_date, lease_end)
    ]

    events = [
        {
            "event_type": event_type,
            "due_date": _shift_to_next_business_day(due_date, in_holidays),
            "description": EVENT_DESCRIPTIONS[event_type],
        }
        for event_type, due_date in raw_events
    ]

    return sorted(events, key=lambda e: (e["due_date"], e["event_type"]))
