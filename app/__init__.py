# ============================================================
# FILE: app/__init__.py
# PURPOSE: Flask application factory — initializes all extensions
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
import os
import logging
from datetime import timedelta

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# ------------------------------------------------------------
# SECTION 2: EXTENSION INSTANCES
# ------------------------------------------------------------
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# ------------------------------------------------------------
# SECTION 3: APP FACTORY
# ------------------------------------------------------------
def create_app():
    """
    PURPOSE  : Create and configure the Flask application
    RECEIVES : None
    RETURNS  : Flask app instance
    SECURITY : ProxyFix required for Railway reverse proxy
               Without it, Twilio webhook signature verification fails silently in production
    LEGAL    : Session cookies enforced HTTPS-only (DPDP security safeguard)
    """
    load_dotenv()

    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # ------------------------------------------------------------
    # SECTION 4: CONFIGURATION
    # ------------------------------------------------------------
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

    # Database — SQLite for local dev, PostgreSQL on Railway
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///minerallaw_dev.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Connection pooling — PostgreSQL only (SQLite does not support this)
    if database_url.startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 20,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True   # Prevents stale connections on Railway
        }

    # Session security
    app.config['SESSION_COOKIE_SECURE'] = not app.debug   # HTTPS only in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True           # JS cannot read cookie
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'         # Allows WhatsApp magic link logins
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # CSRF
    app.config['WTF_CSRF_ENABLED'] = True

    # ------------------------------------------------------------
    # SECTION 5: PROXY FIX — CRITICAL, DO NOT REMOVE
    # Railway sits behind a reverse proxy. Without ProxyFix:
    # request.url = Railway internal URL (http://0.0.0.0:PORT/...)
    # Twilio signs webhooks against public URL — every verification fails
    # ------------------------------------------------------------
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )

    # ------------------------------------------------------------
    # SECTION 6: INITIALIZE EXTENSIONS
    # ------------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Import models to register user_loader with Flask-Login
    from app import models  # noqa
    login_manager.login_message = 'Please log in to access this page.'

    # ------------------------------------------------------------
    # SECTION 7: REGISTER BLUEPRINTS
    # ------------------------------------------------------------
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    return app 