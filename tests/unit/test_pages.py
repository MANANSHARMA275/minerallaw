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

    def test_login_page_loads(self, client):
        """GET /login → 200."""
        resp = client.get('/login')
        assert resp.status_code == 200
