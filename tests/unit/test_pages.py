"""
Tests for public page routes — pricing, home, login.
"""


class TestPublicPages:

    def test_pricing_page_loads(self, client):
        """GET /pricing → 200 with both ₹999 and Enterprise tier visible."""
        resp = client.get('/pricing')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert '₹999' in body
        assert 'Enterprise' in body

    def test_home_page_loads(self, client):
        """GET / → 200."""
        resp = client.get('/')
        assert resp.status_code == 200

    def test_home_page_legislation_cta_present(self, client):
        """GET / must contain a link href to /legislation."""
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'/legislation' in resp.data

    def test_home_page_shows_published_legislation(self, client, app):
        """When a published Legislation row exists, its title appears; fallback is absent."""
        with app.app_context():
            from app import db
            from app.models import Legislation
            entry = Legislation(title='Unique Test Entry Title',
                                category='Test', is_published=True)
            db.session.add(entry)
            db.session.commit()
        resp = client.get('/')
        assert b'Unique Test Entry Title' in resp.data
        assert b'being verified by our expert' not in resp.data

    def test_home_page_shows_fallback_when_no_legislation(self, client):
        """With an empty DB (per-function isolation confirmed), fallback copy is shown."""
        resp = client.get('/')
        assert b'/legislation' in resp.data
        assert b'being verified by our expert' in resp.data

    def test_login_page_loads(self, client):
        """GET /login → 200."""
        resp = client.get('/login')
        assert resp.status_code == 200
