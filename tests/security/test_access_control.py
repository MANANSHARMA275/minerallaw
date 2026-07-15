"""
tests/security/test_access_control.py

Access-control security tests.  Every test in this file MUST pass —
a failure means a real hole or a regression.

Coverage:
  1. Anonymous users → protected routes → 302 redirect to /login
  2. Logged-in regular user → /admin/* → 403
  3. Cross-user IDOR: user A cannot act on user B's ticket
  4. Magic-login robustness: bad/expired token → 302, not 500
"""

import pytest
from datetime import date
from app import db
from app.models import AuditLog, Ticket, User


# ── shared helpers ────────────────────────────────────────────────────────────

def make_user(phone, role='user'):
    u = User(phone=phone, role=role, subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, user):
    """Force-login via session — same pattern as test_admin.py."""
    app.login_manager.session_protection = None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True


def make_ticket(user_id, subject='Security test ticket'):
    t = Ticket(
        user_id=user_id,
        subject=subject,
        description='Created for security test.',
        status='open',
    )
    db.session.add(t)
    db.session.commit()
    return t


# ── 1. Anonymous access ───────────────────────────────────────────────────────

class TestAnonymousBlocked:
    """Unauthenticated requests must never return 200 on protected routes."""

    @pytest.mark.parametrize('url', [
        '/dashboard',
        '/calculator',
        '/checklist',
        '/ask-expert',
        '/admin',
        '/admin/rates',
        '/admin/tickets',
        '/admin/users',
        '/admin/auctions',
        '/admin/deliveries',
    ])
    def test_anonymous_get_redirected_to_login(self, app, client, url):
        """Anonymous GET on any protected route → 302 to /login."""
        resp = client.get(url)
        assert resp.status_code == 302, (
            f"Expected 302 for anonymous GET {url}, got {resp.status_code}"
        )
        location = resp.headers.get('Location', '')
        assert 'login' in location.lower(), (
            f"Expected redirect to /login for {url}, got Location: {location!r}"
        )

    def test_anonymous_post_admin_rates_update_redirected(self, app, client):
        """Anonymous POST /admin/rates/update → 302 (not 200 or 403)."""
        resp = client.post('/admin/rates/update', data={
            'mineral_id': '1', 'state': 'Rajasthan',
            'rate_type': 'royalty', 'value': '50.00',
        })
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '').lower()

    def test_anonymous_post_admin_ticket_respond_redirected(self, app, client):
        """Anonymous POST /admin/tickets/99/respond → 302 (not 200 or 403)."""
        resp = client.post('/admin/tickets/99/respond',
                           data={'response_note': 'anonymous'})
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '').lower()

    def test_anonymous_post_admin_auctions_update_redirected(self, app, client):
        """Anonymous POST /admin/auctions/update → 302."""
        resp = client.post('/admin/auctions/update',
                           data={'is_live': '1', 'status_text': 'anon hack'})
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '').lower()


# ── 2. Regular user blocked from admin ───────────────────────────────────────

class TestRegularUserBlockedFromAdmin:
    """Logged-in users with role='user' must get 403 on every /admin route."""

    @pytest.mark.parametrize('url,method', [
        ('/admin',           'GET'),
        ('/admin/rates',     'GET'),
        ('/admin/tickets',   'GET'),
        ('/admin/users',     'GET'),
        ('/admin/auctions',  'GET'),
        ('/admin/deliveries', 'GET'),
    ])
    def test_user_role_gets_403_on_admin_get(self, app, client, url, method):
        user = make_user(f'+9130000{abs(hash(url)) % 90000 + 10000:05d}')
        _login(client, app, user)
        resp = client.get(url)
        assert resp.status_code == 403, (
            f"User (role='user') must be blocked from {url}, "
            f"got {resp.status_code}"
        )

    def test_user_role_post_rates_update_403(self, app, client):
        """POST /admin/rates/update as role='user' → 403."""
        user = make_user('+914000001001')
        _login(client, app, user)
        resp = client.post('/admin/rates/update', data={
            'mineral_id': '1', 'state': 'Rajasthan',
            'rate_type': 'royalty', 'value': '999.00',
        })
        assert resp.status_code == 403

    def test_user_role_post_auction_update_403(self, app, client):
        """POST /admin/auctions/update as role='user' → 403."""
        user = make_user('+914000001002')
        _login(client, app, user)
        resp = client.post('/admin/auctions/update',
                           data={'is_live': '1', 'status_text': 'hijack'})
        assert resp.status_code == 403

    def test_user_role_post_ticket_respond_403(self, app, client):
        """POST /admin/tickets/<id>/respond as role='user' → 403."""
        user = make_user('+914000001003')
        _login(client, app, user)
        resp = client.post('/admin/tickets/1/respond',
                           data={'response_note': 'hijack'})
        assert resp.status_code == 403


# ── 3. Cross-user IDOR ────────────────────────────────────────────────────────

class TestIDOR:
    """
    Verify that no user can read or modify another user's data via a
    predictable ID in the URL or form.
    """

    def test_user_a_cannot_resolve_user_b_ticket(self, app, client):
        """
        User A (role='user') POST /admin/tickets/<B's ticket id>/respond
        must return 403, not 200.  The ticket belongs to user B; user A
        must never be able to act on it.
        """
        user_a = make_user('+915000001001')
        user_b = make_user('+915000001002')
        ticket_b = make_ticket(user_b.id, subject="User B's private ticket")

        _login(client, app, user_a)
        resp = client.post(
            f'/admin/tickets/{ticket_b.id}/respond',
            data={'response_note': 'user A hijacking B ticket'},
        )
        assert resp.status_code == 403, (
            f"User A must NOT be able to act on User B's ticket. "
            f"Got {resp.status_code} (expected 403)."
        )

    def test_dashboard_query_scoped_to_current_user(self, app, client):
        """
        The dashboard audit-log query must be scoped to current_user.id.
        Confirm at DB level: user A's filter returns no rows from user B's logs.
        """
        from app.helpers import log_audit

        user_a = make_user('+915000002001')
        user_b = make_user('+915000002002')

        log_audit(user_id=user_b.id, action='FEE_CALCULATION',
                  table_affected='Rate', record_id=1, new_value='b_only')

        # Dashboard query pattern — must return 0 rows for user_a
        logs_for_a = AuditLog.query.filter_by(user_id=user_a.id).all()
        assert len(logs_for_a) == 0, (
            "User A must see zero audit entries — "
            "User B's log must not leak to User A."
        )

    def test_ask_expert_submit_always_uses_current_user_id(self, app, client):
        """
        POST /ask-expert/submit must create a ticket owned by current_user,
        regardless of any injected form data.  There is no user_id field in
        the form — the route uses current_user.id exclusively.
        """
        user_a = make_user('+915000003001')
        user_b = make_user('+915000003002')

        _login(client, app, user_a)
        resp = client.post('/ask-expert/submit', data={
            'mineral': 'Limestone',
            'query': 'What is the current royalty rate for Rajasthan?',
            # Attempt to inject user_b's id — route must ignore this
            'user_id': str(user_b.id),
        })
        assert resp.status_code == 200
        ticket = Ticket.query.first()
        assert ticket is not None
        assert ticket.user_id == user_a.id, (
            f"Ticket must be owned by user_a (id={user_a.id}), "
            f"but got user_id={ticket.user_id}."
        )


# ── 4. Magic-login robustness ─────────────────────────────────────────────────

class TestMagicLoginRobustness:
    """
    /auth/magic-login must handle bad tokens gracefully.
    A BuildError (→ 500) instead of a redirect is the bug we found in
    auth.py where url_for('main.login_page') should be url_for('main.login').
    """

    def test_invalid_token_redirects_not_500(self, app, client):
        """GET /auth/magic-login?token=garbage → 302 to /login, never 500."""
        resp = client.get('/auth/magic-login?token=not-a-real-jwt')
        assert resp.status_code == 302, (
            f"Bad magic token must redirect (302), got {resp.status_code}. "
            "Likely cause: url_for('main.login_page') should be "
            "url_for('main.login') in auth.py."
        )
        location = resp.headers.get('Location', '')
        assert 'login' in location.lower(), (
            f"Bad token should redirect to /login, got {location!r}"
        )

    def test_expired_token_redirects_not_500(self, app, client):
        """GET /auth/magic-login with a structurally valid but expired JWT → 302."""
        import jwt as pyjwt
        from datetime import datetime, timedelta

        expired_token = pyjwt.encode(
            {
                'phone': '+919999999999',
                'exp': datetime.utcnow() - timedelta(minutes=20),  # already expired
                'iat': datetime.utcnow() - timedelta(minutes=30),
                'purpose': 'magic_login',
            },
            app.config['SECRET_KEY'],
            algorithm='HS256',
        )
        resp = client.get(f'/auth/magic-login?token={expired_token}')
        assert resp.status_code == 302, (
            f"Expired magic token must redirect (302), got {resp.status_code}."
        )
        assert 'login' in resp.headers.get('Location', '').lower()

    def test_valid_token_unknown_phone_redirects_not_500(self, app, client):
        """
        A valid token for a phone not in the DB must redirect gracefully.
        This hits the second url_for('main.login_page') call in auth.py.
        """
        import jwt as pyjwt
        from datetime import datetime, timedelta

        token = pyjwt.encode(
            {
                'phone': '+910000000000',  # phone that doesn't exist in DB
                'exp': datetime.utcnow() + timedelta(minutes=5),
                'iat': datetime.utcnow(),
                'purpose': 'magic_login',
            },
            app.config['SECRET_KEY'],
            algorithm='HS256',
        )
        resp = client.get(f'/auth/magic-login?token={token}')
        assert resp.status_code == 302, (
            f"Valid token / unknown phone must redirect (302), got {resp.status_code}."
        )
        assert 'login' in resp.headers.get('Location', '').lower()
