"""
Tests for Rate Date validation in the /calculator/calculate route
and the validate_rate_date() helper in app/validators.py.

MUST FAIL on the old code (no date sanity checks).
"""
import datetime

import pytest

from app import db
from app.models import Mineral, Rate, User
from app.validators import validate_rate_date


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(phone='+910000000099'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, user):
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def _seed_mineral_and_rate():
    """Insert Limestone + an active royalty + DMF rate and return the mineral."""
    mineral = Mineral(name='Limestone', category='minor')
    db.session.add(mineral)
    db.session.flush()

    for rtype in ('royalty', 'dmf'):
        db.session.add(Rate(
            mineral_id=mineral.id,
            state='Rajasthan',
            rate_type=rtype,
            value='90.00' if rtype == 'royalty' else '10.00',
            unit='per_tonne',
            effective_from=datetime.date(2019, 1, 1),
            effective_to=None,
            notification_number='DMG/2019/01',
        ))
    db.session.commit()
    return mineral


def _post(client, mineral_id, target_date=''):
    return client.post('/calculator/calculate', data={
        'mineral_id':     str(mineral_id),
        'area_ha':        '10',
        'production_tpa': '50000',
        'lease_years':    '5',
        'target_date':    target_date,
    })


# ── Unit tests for validate_rate_date() ──────────────────────────────────────

class TestValidateRateDate:

    def test_blank_returns_none_date(self):
        ok, d, err = validate_rate_date('')
        assert ok is True
        assert d is None
        assert err == ''

    def test_whitespace_treated_as_blank(self):
        ok, d, err = validate_rate_date('   ')
        assert ok is True
        assert d is None

    def test_valid_past_date_accepted(self):
        ok, d, err = validate_rate_date('2019-03-15')
        assert ok is True
        assert d == datetime.date(2019, 3, 15)

    def test_today_accepted(self):
        today = datetime.date.today().isoformat()
        ok, d, err = validate_rate_date(today)
        assert ok is True

    def test_far_future_rejected(self):
        ok, d, err = validate_rate_date('4332-03-23')
        assert ok is False
        assert 'future' in err.lower()

    def test_tomorrow_rejected(self):
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        ok, d, err = validate_rate_date(tomorrow)
        assert ok is False
        assert 'future' in err.lower()

    def test_pre_1950_rejected(self):
        ok, d, err = validate_rate_date('1923-01-01')
        assert ok is False
        assert 'past' in err.lower()

    def test_exactly_1950_accepted(self):
        ok, d, err = validate_rate_date('1950-01-01')
        assert ok is True

    def test_unparseable_rejected(self):
        ok, d, err = validate_rate_date('not-a-date')
        assert ok is False
        assert d is None


# ── Route-level tests (POST /calculator/calculate) ────────────────────────────

class TestCalculateRouteDateValidation:

    def test_far_future_date_returns_400(self, app, client):
        """POST with year 4332 must return 400 with a message mentioning future."""
        mineral = _seed_mineral_and_rate()
        user = _make_user('+910000000091')
        _login(client, app, user)

        resp = _post(client, mineral.id, target_date='4332-03-23')
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'future' in body['error'].lower()

    def test_pre_1950_date_returns_400(self, app, client):
        """POST with 1923-01-01 must return 400 with a message mentioning past."""
        mineral = _seed_mineral_and_rate()
        user = _make_user('+910000000092')
        _login(client, app, user)

        resp = _post(client, mineral.id, target_date='1923-01-01')
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'past' in body['error'].lower()

    def test_tomorrow_returns_400(self, app, client):
        """POST with tomorrow's date must return 400."""
        mineral = _seed_mineral_and_rate()
        user = _make_user('+910000000093')
        _login(client, app, user)

        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = _post(client, mineral.id, target_date=tomorrow)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'future' in body['error'].lower()

    def test_blank_date_uses_today_and_returns_200(self, app, client):
        """POST with blank date must succeed (regression guard — existing behaviour)."""
        mineral = _seed_mineral_and_rate()
        user = _make_user('+910000000094')
        _login(client, app, user)

        resp = _post(client, mineral.id, target_date='')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'royalty_annual' in body

    def test_valid_2019_date_returns_200(self, app, client):
        """POST with a valid historical date (2019) must succeed."""
        mineral = _seed_mineral_and_rate()
        user = _make_user('+910000000095')
        _login(client, app, user)

        resp = _post(client, mineral.id, target_date='2019-06-01')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'royalty_annual' in body
