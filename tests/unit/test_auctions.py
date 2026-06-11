"""
Tests for the Auction Center feature:
  - GET /auctions → 200, no login required, MSTC link present
  - Superadmin POST to /admin/auctions/update → 200, AuditLog created,
    banner text visible on /auctions
  - Non-superadmin POST to /admin/auctions/update → 403
"""
import pytest

from app import db
from app.models import AuditLog, AuctionStatus, User


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


def _post_update(client, is_live='0', status_text='', status_text_hi=''):
    return client.post('/admin/auctions/update', data={
        'is_live':        is_live,
        'status_text':    status_text,
        'status_text_hi': status_text_hi,
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAuctionsPublicPage:

    def test_auctions_returns_200_without_login(self, client):
        """GET /auctions must be accessible to anonymous users."""
        resp = client.get('/auctions')
        assert resp.status_code == 200

    def test_auctions_contains_mstc_link(self, client):
        """Page must contain the MSTC auction portal URL."""
        resp = client.get('/auctions')
        assert b'mstcecommerce.com' in resp.data

    def test_auctions_contains_dmg_link(self, client):
        """Page must contain the DMG Rajasthan portal URL."""
        resp = client.get('/auctions')
        assert b'mines.rajasthan.gov.in' in resp.data

    def test_auctions_contains_gis_link(self, client):
        """Page must contain the GIS map URL."""
        resp = client.get('/auctions')
        assert b'gis.rajasthan.gov.in' in resp.data

    def test_auctions_default_banner_not_live(self, client):
        """With no AuctionStatus row set, the grey 'not live' banner must show."""
        resp = client.get('/auctions')
        body = resp.data.decode()
        assert 'No auctions currently flagged' in body

    def test_auctions_live_banner_when_is_live(self, app, client):
        """When is_live=True the green live banner must appear."""
        row = AuctionStatus(is_live=True, status_text='ML(03) 2026 — bids close 15 July')
        db.session.add(row)
        db.session.commit()

        resp = client.get('/auctions')
        body = resp.data.decode()
        assert 'Auctions currently open' in body
        assert 'ML(03) 2026' in body


class TestAuctionAdminUpdate:

    def test_superadmin_update_succeeds(self, app, client):
        """Superadmin POST returns 200 JSON with status key."""
        admin = _make_user('+910000000081', role='superadmin')
        _login(client, app, admin)

        resp = _post_update(client, is_live='1', status_text='Test auction open')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'Auction status updated.'

    def test_superadmin_update_writes_audit_log(self, app, client):
        """Every status update must write one AuditLog row."""
        admin = _make_user('+910000000082', role='superadmin')
        _login(client, app, admin)

        before = AuditLog.query.filter_by(action='AUCTION_STATUS_UPDATED').count()
        _post_update(client, is_live='1', status_text='Audit test')
        after = AuditLog.query.filter_by(action='AUCTION_STATUS_UPDATED').count()

        assert after == before + 1

    def test_superadmin_update_changes_banner_on_public_page(self, app, client):
        """After a superadmin update, /auctions must reflect the new text."""
        admin = _make_user('+910000000083', role='superadmin')
        _login(client, app, admin)

        _post_update(client, is_live='1', status_text='ML(07) 2026 LIVE')

        # Fetch public page (no auth required)
        resp = client.get('/auctions')
        body = resp.data.decode()
        assert 'ML(07) 2026 LIVE' in body

    def test_non_superadmin_update_returns_403(self, app, client):
        """Regular user POST to /admin/auctions/update must be rejected with 403."""
        user = _make_user('+910000000084', role='user')
        _login(client, app, user)

        resp = _post_update(client, is_live='1', status_text='Should be blocked')
        assert resp.status_code == 403

    def test_status_text_truncated_at_300_chars(self, app, client):
        """status_text longer than 300 chars must be silently truncated."""
        admin = _make_user('+910000000085', role='superadmin')
        _login(client, app, admin)

        long_text = 'A' * 400
        _post_update(client, is_live='0', status_text=long_text)

        row = AuctionStatus.query.first()
        assert row is not None
        assert len(row.status_text) <= 300
