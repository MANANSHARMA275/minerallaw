"""
Shared pytest fixtures for all test suites.
Uses an in-memory SQLite DB — each test function gets a clean slate.
"""

import pytest
from app import create_app, db as _db


@pytest.fixture(scope='function')
def app():
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()
