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
