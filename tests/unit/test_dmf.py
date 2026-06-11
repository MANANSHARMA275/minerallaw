"""
Tests for DMF calculation — convention: Rate.value is a PERCENTAGE (10.00 = 10%).
These tests were written to FAIL on the old code (which divided an already-decimal
multiplier by 100 again, producing a 100× undercount).
"""
import pytest
from datetime import date
from decimal import Decimal

from flask_login import login_user

from app import db
from app.fee_calculator import calculate_dmf
from app.models import Mineral, Rate, User


# ── Shared helpers ──────────────────────────────────────────────────────────────

def make_user(phone='+919900000099'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def seed_limestone(royalty_2019=True, royalty_2022=True, dmf_2019=True, dmf_2022=True):
    """Insert Limestone mineral plus the requested Rate rows."""
    mineral = Mineral(name='Limestone', category='minor')
    db.session.add(mineral)
    db.session.flush()

    if royalty_2019:
        db.session.add(Rate(
            mineral_id=mineral.id, state='Rajasthan', rate_type='royalty',
            value='70.00', unit='per_tonne',
            effective_from=date(2019, 1, 1), effective_to=date(2021, 12, 31),
            notification_number='TEST-DMG/2019/01',
        ))
    if royalty_2022:
        db.session.add(Rate(
            mineral_id=mineral.id, state='Rajasthan', rate_type='royalty',
            value='90.00', unit='per_tonne',
            effective_from=date(2022, 1, 1), effective_to=None,
            notification_number='TEST-DMG/2022/01',
        ))
    if dmf_2019:
        db.session.add(Rate(
            mineral_id=mineral.id, state='Rajasthan', rate_type='dmf',
            value='10.00', unit='percent',
            effective_from=date(2019, 1, 1), effective_to=date(2021, 12, 31),
            notification_number='TEST-DMG-DMF/2019/01',
        ))
    if dmf_2022:
        db.session.add(Rate(
            mineral_id=mineral.id, state='Rajasthan', rate_type='dmf',
            value='10.00', unit='percent',
            effective_from=date(2022, 1, 1), effective_to=None,
            notification_number='TEST-DMG-DMF/2022/01',
        ))
    db.session.commit()
    return mineral


def _login(client, app, user):
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


# ── Unit test ───────────────────────────────────────────────────────────────────

class TestCalculateDmf:

    def test_ten_percent_of_royalty(self):
        """calculate_dmf(4500000, 10.00) must equal 450000 (10% of ₹45,00,000)."""
        result = calculate_dmf(Decimal('4500000'), Decimal('10.00'))
        assert result == Decimal('450000'), f"Expected 450000, got {result}"

    def test_zero_royalty(self):
        """calculate_dmf with zero royalty must return zero DMF."""
        result = calculate_dmf(Decimal('0'), Decimal('10.00'))
        assert result == Decimal('0')

    def test_rounds_half_up(self):
        """Fractional rupees are rounded ROUND_HALF_UP, not truncated."""
        # 100001 × 10% = 10000.1 → rounds to 10000
        result = calculate_dmf(Decimal('100001'), Decimal('10.00'))
        assert result == Decimal('10000')


# ── Integration tests ───────────────────────────────────────────────────────────

class TestCalculatorDmfRoute:

    def test_current_date_dmf_and_total(self, app, client):
        """
        POST /calculator/calculate — Limestone 50000 TPA, current rate.
        royalty = 50000 × 90 = 4500000
        DMF     = 4500000 × 10% = 450000
        total   = 4950000
        """
        seed_limestone()
        user = make_user()
        _login(client, app, user)

        resp = client.post('/calculator/calculate', data={
            'mineral_id': Mineral.query.filter_by(name='Limestone').first().id,
            'area_ha': '10',
            'production_tpa': '50000',
            'lease_years': '5',
            'target_date': str(date(2025, 6, 1)),
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()

        assert int(data['royalty_annual']) == 4_500_000, data
        assert int(data['dmf_annual'])    == 450_000,   data
        assert int(data['total_annual'])  == 4_950_000, data
        assert data['dmf_warning'] is None

    def test_historical_2019_date_dmf(self, app, client):
        """
        POST /calculator/calculate — Limestone 50000 TPA, 2019-03-15.
        royalty = 50000 × 70 = 3500000
        DMF     = 3500000 × 10% = 350000
        """
        seed_limestone()
        user = make_user('+919900000098')
        _login(client, app, user)

        resp = client.post('/calculator/calculate', data={
            'mineral_id': Mineral.query.filter_by(name='Limestone').first().id,
            'area_ha': '10',
            'production_tpa': '50000',
            'lease_years': '5',
            'target_date': '2019-03-15',
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()

        assert int(data['royalty_annual']) == 3_500_000, data
        assert int(data['dmf_annual'])    == 350_000,   data
        assert data['dmf_warning'] is None

    def test_missing_dmf_rate_shows_warning_not_zero(self, app, client):
        """
        When no DMF rate row covers the date, the route must return a
        dmf_warning string — not silently report ₹0.
        """
        seed_limestone(dmf_2019=False, dmf_2022=False)
        user = make_user('+919900000097')
        _login(client, app, user)

        resp = client.post('/calculator/calculate', data={
            'mineral_id': Mineral.query.filter_by(name='Limestone').first().id,
            'area_ha': '10',
            'production_tpa': '50000',
            'lease_years': '5',
            'target_date': str(date(2025, 6, 1)),
        })
        assert resp.status_code == 200
        data = resp.get_json()

        assert data['dmf_warning'] is not None, "Expected a dmf_warning, got None"
        assert 'unavailable' in data['dmf_warning'].lower()
