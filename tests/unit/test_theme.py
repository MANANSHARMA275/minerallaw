"""
Tests for Chunk B1: semantic colour-token system + dark/light toggle.
Verifies the partial split renders correctly and the theme toggle infrastructure is present.
"""


class TestTheme:

    def test_home_renders_after_partial_split(self, client):
        """GET / → 200 after home.html split into partials."""
        assert client.get('/').status_code == 200

    def test_theme_toggle_button_present(self, client):
        """Base template must include a theme-toggle button with correct id and aria-label."""
        body = client.get('/').data.decode()
        assert 'id="theme-toggle-btn"' in body
        assert 'aria-label="Toggle dark mode"' in body

    def test_theme_storage_key_present(self, client):
        """JS (served inline or via main.js reference) must reference the minerallaw_theme key."""
        body = client.get('/').data.decode()
        assert 'minerallaw_theme' in body

    def test_home_hero_present_after_split(self, client):
        """Hero headline default text is rendered — confirms _hero.html is actually included."""
        body = client.get('/').data.decode()
        assert 'Rajasthan Mining Compliance, Done Right the First Time' in body

    def test_home_legislation_band_present_after_split(self, client):
        """Legislation band CTA link is rendered after partial extraction."""
        assert b'/legislation' in client.get('/').data


class TestScrollRevealProgressiveEnhancement:
    """
    Chunk E2 — the scroll-reveal/stagger mechanism must be progressive
    enhancement: JS ADDS the pre-reveal hidden state, so the raw
    server-rendered HTML (which the Flask test client never executes JS
    against) must show every section's content in full, never hidden.
    """

    def test_home_page_content_visible_without_js(self, client):
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'Where Compliance Goes Wrong' in body
        assert 'Wrong Rate Applied' in body
        assert 'Missed Deadlines' in body
        assert 'Unexpected Penalties' in body
        # reveal-pending/is-revealed are added exclusively by JS (reveal.js);
        # their absence here proves the server-rendered page never hides
        # content by default — a JS failure leaves everything visible.
        assert 'reveal-pending' not in body
        assert 'is-revealed' not in body
