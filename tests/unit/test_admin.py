"""
Tests for app/admin.py — role_required decorator and rate update logic.
"""
import pytest
from datetime import date

from flask_login import login_user

from app import db
from app.models import AuditLog, Mineral, Rate, User


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_user(phone, role='user'):
    u = User(phone=phone, role=role, subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def seed_limestone_royalty_rate(mineral_id=1):
    """Insert one active royalty rate for mineral_id; return the Rate object."""
    rate = Rate(
        mineral_id=mineral_id,
        state='Rajasthan',
        rate_type='royalty',
        value='90.00',
        unit='per_tonne',
        effective_from=date(2022, 1, 1),
        effective_to=None,
        notification_number='DMG/2022/01',
    )
    db.session.add(rate)
    db.session.commit()
    return rate


def _login(client, app, user):
    """Force-login a user via session in test context."""
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestRoleRequired:

    def test_blocks_regular_user(self, app, client):
        """GET /admin must return 403 for role='user'."""
        user = make_user('+910000000001', role='user')
        _login(client, app, user)
        resp = client.get('/admin')
        assert resp.status_code == 403

    def test_allows_superadmin(self, app, client):
        """GET /admin must return 200 for role='superadmin'."""
        admin = make_user('+910000000002', role='superadmin')
        _login(client, app, admin)
        resp = client.get('/admin')
        assert resp.status_code == 200


class TestRateUpdate:

    def _seed_mineral(self):
        mineral = Mineral(name='Limestone', category='minor')
        db.session.add(mineral)
        db.session.commit()
        return mineral

    def test_creates_new_row_not_overwrite(self, app, client):
        """POST /admin/rates/update must insert a new row and close the old one."""
        mineral = self._seed_mineral()
        seed_limestone_royalty_rate(mineral.id)
        assert Rate.query.count() == 1

        admin = make_user('+910000000003', role='superadmin')
        _login(client, app, admin)

        resp = client.post('/admin/rates/update', data={
            'mineral_id': mineral.id,
            'state': 'Rajasthan',
            'rate_type': 'royalty',
            'value': '100.00',
            'unit': 'per_tonne',
            'notification_number': 'DMG/2026/01',
        })
        assert resp.status_code == 200
        assert Rate.query.count() == 2

        old_rate = Rate.query.filter(Rate.effective_to.isnot(None)).first()
        assert old_rate is not None
        assert old_rate.effective_to == date.today()

        new_rate = Rate.query.filter_by(effective_to=None).first()
        assert new_rate is not None
        assert str(new_rate.value) == '100.00'

    def test_rate_update_logged_in_audit(self, app, client):
        """POST /admin/rates/update must write exactly one RATE_UPDATED AuditLog."""
        mineral = self._seed_mineral()
        seed_limestone_royalty_rate(mineral.id)

        admin = make_user('+910000000004', role='superadmin')
        _login(client, app, admin)

        client.post('/admin/rates/update', data={
            'mineral_id': mineral.id,
            'state': 'Rajasthan',
            'rate_type': 'royalty',
            'value': '110.00',
            'unit': 'per_tonne',
            'notification_number': 'DMG/2026/02',
        })

        count = AuditLog.query.filter_by(action='RATE_UPDATED').count()
        assert count == 1
