"""
Unit tests for app/fee_calculator.py

Tests run against an in-memory SQLite DB (via conftest.py fixtures).
No HTTP requests — pure function + ORM-level testing.
"""

from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import Mineral, Rate
from app.fee_calculator import (
    get_rate_for_date,
    calculate_royalty,
    get_calculation_disclaimer,
)


# ── helpers ──────────────────────────────────────────────────

def _make_limestone(app_ctx):
    """Insert a Limestone mineral row and return it."""
    mineral = Mineral(name='Limestone', category='minor')
    db.session.add(mineral)
    db.session.flush()
    return mineral


def _make_rate(mineral_id, value, notif, eff_from, eff_to=None, rate_type='royalty'):
    rate = Rate(
        mineral_id=mineral_id,
        state='Rajasthan',
        rate_type=rate_type,
        value=value,
        unit='per_tonne',
        effective_from=eff_from,
        effective_to=eff_to,
        notification_number=notif,
    )
    db.session.add(rate)
    db.session.flush()
    return rate


# ── tests ─────────────────────────────────────────────────────

def test_historical_rate_returns_2019_rate(app):
    """A lease date of 2019-03-15 must return the 2019 rate, not the 2022 rate."""
    with app.app_context():
        mineral = _make_limestone(app)
        _make_rate(mineral.id, 70, 'DMG/2019/01',
                   date(2019, 1, 1), date(2021, 12, 31))
        _make_rate(mineral.id, 90, 'DMG/2022/01',
                   date(2022, 1, 1), None)
        db.session.commit()

        result = get_rate_for_date(mineral.id, 'Rajasthan', 'royalty', date(2019, 3, 15))

        assert result is not None
        assert result.value == 70
        assert result.notification_number == 'DMG/2019/01'


def test_current_rate_returns_active_rate(app):
    """Querying with today's date must return the rate with effective_to=None."""
    with app.app_context():
        mineral = _make_limestone(app)
        _make_rate(mineral.id, 70, 'DMG/2019/01',
                   date(2019, 1, 1), date(2021, 12, 31))
        _make_rate(mineral.id, 90, 'DMG/2022/01',
                   date(2022, 1, 1), None)
        db.session.commit()

        result = get_rate_for_date(mineral.id, 'Rajasthan', 'royalty', date.today())

        assert result is not None
        assert result.value == 90


def test_no_rate_before_history_returns_none(app):
    """A date before all recorded rates must return None."""
    with app.app_context():
        mineral = _make_limestone(app)
        _make_rate(mineral.id, 70, 'DMG/2019/01',
                   date(2019, 1, 1), date(2021, 12, 31))
        _make_rate(mineral.id, 90, 'DMG/2022/01',
                   date(2022, 1, 1), None)
        db.session.commit()

        result = get_rate_for_date(mineral.id, 'Rajasthan', 'royalty', date(2015, 1, 1))

        assert result is None


def test_royalty_calculation_is_correct(app):
    """50 000 TPA × ₹90/t must equal ₹45 00 000 exactly."""
    with app.app_context():
        result = calculate_royalty(50_000, 90.00)
        assert result == Decimal('4500000')


def test_disclaimer_contains_notification_number(app):
    """Disclaimer must include the notification number and the word 'SEIAA'."""
    with app.app_context():
        mineral = _make_limestone(app)
        rate = _make_rate(mineral.id, 90, 'DMG/2022/01',
                          date(2022, 1, 1), None)
        db.session.commit()

        disclaimer = get_calculation_disclaimer(rate)

        assert 'DMG/2022/01' in disclaimer
        assert 'SEIAA' in disclaimer
