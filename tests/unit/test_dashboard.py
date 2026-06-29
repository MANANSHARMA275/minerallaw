"""
Tests for the authenticated /dashboard route:
  - Authenticated user receives 200 with page title present.
  - Anonymous GET redirects to login (Flask-Login 302).
"""
import pytest

from app import db
from app.models import User


def _make_user(phone, role='user'):
    u = User(phone=phone, role=role, subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, user):
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


class TestDashboardAccess:

    def test_dashboard_returns_200_when_authenticated(self, app, client):
        """Authenticated GET /dashboard must return 200 with 'Dashboard' in title."""
        user = _make_user('+919900000001')
        _login(client, app, user)
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data

    def test_dashboard_redirects_anonymous_to_login(self, client):
        """Anonymous GET /dashboard must redirect to login (Flask-Login 302)."""
        resp = client.get('/dashboard')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']
