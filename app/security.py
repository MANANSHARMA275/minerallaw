# ============================================================
# FILE: app/security.py
# PURPOSE: Flask-Talisman security headers + CSP initialization
# LAST UPDATED: Phase 1
# ============================================================

import os

from flask_talisman import Talisman


def init_security(app):
    """
    PURPOSE  : Initialize HTTPS enforcement and all security headers via Talisman
    RECEIVES : app (Flask) — the application instance
    RETURNS  : None — mutates app in place
    SECURITY : CSP prevents XSS, clickjacking, and MIME sniffing.
               HTTPS enforcement active in production only — dev server stays on http.
               Nonce generated per request; injected into script-src and exposed
               via csp_nonce() Jinja2 global for template use.
    LEGAL    : Required for DPDP Act 2023 security safeguard obligation.
               Tighten CSP further in Phase 3 once Tailwind CSS is compiled
               to a static file (removing the need for cdn.tailwindcss.com).
    """
    # PYTEST_CURRENT_TEST is set by pytest during fixture setup, before conftest
    # sets app.config['TESTING'] = True. We cannot rely on app.testing here
    # because conftest assigns it AFTER create_app() returns.
    is_testing = bool(os.environ.get('PYTEST_CURRENT_TEST'))
    is_dev = app.debug or is_testing

    if is_dev:
        # Development / test: no HTTPS redirect, no CSP header.
        # csp_nonce() Jinja2 global is still registered by Talisman so templates
        # can use {{ csp_nonce() }} without NameError in any mode.
        Talisman(
            app,
            force_https=False,
            content_security_policy=False,
        )
        return

    # ── Production: full security headers ───────────────────
    Talisman(
        app,
        force_https=True,
        content_security_policy={
            'default-src': "'self'",
            'script-src': ["'self'", "https://cdn.tailwindcss.com"],
            'style-src': [
                "'self'",
                "'unsafe-inline'",
                # 'unsafe-inline' required: Tailwind CDN injects a <style> tag
                # at runtime, and templates have <style> blocks. Tighten in
                # Phase 3 when Tailwind is compiled to a static file.
                "https://fonts.googleapis.com",
            ],
            'font-src': ["'self'", "https://fonts.gstatic.com"],
            'img-src': ["'self'", "data:"],
            'connect-src': "'self'",
            'frame-ancestors': "'none'",
        },
        content_security_policy_nonce_in=['script-src'],
    )
