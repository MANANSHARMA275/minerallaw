# ============================================================
# FILE: app/error_handlers.py
# PURPOSE: User-friendly error pages for all HTTP errors
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from flask import render_template

# ------------------------------------------------------------
# SECTION 2: ERROR HANDLER REGISTRATION
# ------------------------------------------------------------
def register_error_handlers(app):
    """
    PURPOSE  : Register all HTTP error handlers with the Flask app
    RECEIVES : app (Flask) — the application instance
    RETURNS  : None
    SECURITY : Never expose stack traces to users in production
    LEGAL    : Error pages must not leak PII or internal paths
    """

    @app.errorhandler(404)
    def not_found(e):
        """Page not found"""
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        """Access denied"""
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        """Internal server error — never show stack trace to user"""
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def rate_limited(e):
        """Too many requests — rate limiter triggered"""
        return render_template('errors/429.html'), 429