"""
Shared pytest fixtures for all test suites.
Uses an in-memory SQLite DB — each test function gets a clean slate.

ISOLATION GUARANTEE
-------------------
DATABASE_URL is forced to ':memory:' in os.environ BEFORE create_app() is
called.  Flask-SQLAlchemy 3.x captures the URI during db.init_app(app), so
any config.update() applied afterward comes too late — the engine is already
bound to whatever URI was in os.environ at init time.  Setting the env var
here ensures the engine never points at the real file DB, and the drop_all()
in teardown cannot destroy instance/minerallaw.db.

The safety assertion below makes the suite abort loudly if this invariant is
ever violated (e.g. create_app() gains a new code path that reads a different
source for the URI).
"""

import os

# Force in-memory DB BEFORE create_app() reads os.environ.
# load_dotenv(override=False) inside create_app() will not overwrite this.
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

import pytest
from app import create_app, db as _db


@pytest.fixture(scope='function')
def app():
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })
    with test_app.app_context():
        # Safety assertion — abort the entire suite if the engine is ever
        # pointed at a file DB.  This catches regressions immediately.
        resolved_url = str(_db.engine.url)
        assert ':memory:' in resolved_url, (
            f"Test suite is pointing at a real database: {resolved_url}\n"
            "Tests must only run against sqlite:///:memory:."
        )
        _db.create_all()
        yield test_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()
