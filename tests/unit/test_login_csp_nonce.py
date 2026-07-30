"""
Regression test for login.html's inline <script> CSP nonce.

The nonce was missing entirely until this fix, which never surfaced in the
normal test suite because app/security.py disables CSP whenever
PYTEST_CURRENT_TEST is set (see init_security's is_dev check) — the same
reason it never surfaced in local dev (app.debug=True has the same effect).
This test boots an isolated app instance with that check forced False, so
Talisman takes its production branch and actually emits a nonce'd CSP header,
then verifies the nonce in that header matches the nonce rendered into the
template — exactly what a browser's CSP engine checks before running the
script.
"""
import os
import re

import pytest

from app import create_app, db as _db


@pytest.fixture
def prod_csp_client():
    """
    Fresh app instance with Talisman's production CSP branch active, isolated
    from the shared `app` fixture so it doesn't affect other tests' CSP-off
    behavior. PYTEST_CURRENT_TEST is removed for the duration of app creation
    so init_security's is_dev check evaluates False; it is restored
    afterward. Flask's test client talks to the WSGI app directly (no real
    socket), so Talisman's force_https redirect is avoided by requesting
    over a spoofed https scheme via base_url.
    """
    saved = os.environ.pop('PYTEST_CURRENT_TEST', None)
    try:
        test_app = create_app()
        test_app.config.update({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SERVER_NAME': 'localhost',
        })
        with test_app.app_context():
            _db.create_all()
            yield test_app.test_client()
            _db.session.remove()
            _db.drop_all()
    finally:
        if saved is not None:
            os.environ['PYTEST_CURRENT_TEST'] = saved


class TestLoginCspNonce:

    def test_login_script_nonce_matches_csp_header(self, prod_csp_client):
        """Nonce in the CSP response header must match login's own <script> tag's nonce.

        base.html (the layout login.html extends) already carries several
        correctly-nonced <script> tags of its own, so a regex matching *any*
        nonced script on the page would pass even if login's block-scripts
        <script> were missing its nonce. Anchor specifically on the OTP
        script's distinctive first statement (`let currentPhone`) so this
        test fails the way it should have caught the original bug.
        """
        resp = prod_csp_client.get('/login', base_url='https://localhost')
        assert resp.status_code == 200

        csp = resp.headers.get('Content-Security-Policy')
        assert csp, "Expected a Content-Security-Policy header under production CSP config"

        header_nonce = re.search(r"'nonce-([^']+)'", csp)
        assert header_nonce, f"No nonce found in CSP script-src: {csp}"

        html = resp.get_data(as_text=True)
        login_script_tag = re.search(r'<script([^>]*)>\s*let currentPhone', html)
        assert login_script_tag, "Could not find login.html's OTP <script> block in the response"

        script_nonce = re.search(r'nonce="([^"]+)"', login_script_tag.group(1))
        assert script_nonce, "login.html's inline <script> is missing a nonce attribute"

        assert header_nonce.group(1) == script_nonce.group(1)
