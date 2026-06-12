"""
Tests for the superadmin-only Admin nav link in base.html.

The Admin link must appear ONLY when the authenticated user has
role='superadmin'. Regular users and anonymous visitors must not see it.
"""
from app import db
from app.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAdminNavLink:

    def test_superadmin_sees_admin_link(self, app, client):
        """Superadmin user must see an Admin link pointing to /admin."""
        admin = _make_user('+910000000071', role='superadmin')
        _login(client, app, admin)

        resp = client.get('/')
        body = resp.data.decode()
        assert '/admin' in body
        assert 'nav_admin' in body or 'Admin' in body

    def test_regular_user_does_not_see_admin_link(self, app, client):
        """Authenticated user with role='user' must NOT see an Admin link."""
        user = _make_user('+910000000072', role='user')
        _login(client, app, user)

        resp = client.get('/')
        body = resp.data.decode()
        assert 'nav_admin' not in body
        # The /admin URL should not appear in the nav
        assert 'href="/admin"' not in body

    def test_anonymous_does_not_see_admin_link(self, client):
        """Unauthenticated visitors must not see any Admin link."""
        resp = client.get('/')
        body = resp.data.decode()
        assert 'nav_admin' not in body
        assert 'href="/admin"' not in body

    def test_staff_role_does_not_see_admin_link(self, app, client):
        """Staff users (role='staff') are not superadmin and must not see Admin."""
        staff = _make_user('+910000000073', role='staff')
        _login(client, app, staff)

        resp = client.get('/')
        body = resp.data.decode()
        assert 'nav_admin' not in body
        assert 'href="/admin"' not in body
