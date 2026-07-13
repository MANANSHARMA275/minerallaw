"""
Tests for app/helpers.py::log_audit's request-context handling (Chunk 4a).

Not in test_helpers.py — that file is fixture-free and its own docstring
says "DO NOT test log_audit here."

NOTE on fixture choice for the no-context test below: pytest-flask installs
an autouse fixture (`_push_request_context`, see
.venv/lib/*/site-packages/pytest_flask/plugin.py) that pushes a REAL Flask
request context for ANY test that resolves the `app` fixture — even if the
test itself never calls client.get/post or test_request_context(). A test
that uses `app` and simply omits an explicit context manager would still
have a request context (via pytest-flask) and would NOT exercise the
no-context code path at all. The only way to genuinely test "no request
context" is to avoid the `app`/`client` fixtures entirely and build a
standalone Flask app, entered only via app_context() (never a request
context). Do not "simplify" test_log_audit_with_no_request_context back
into using the `app` fixture — that would silently defeat it.
"""
from app import create_app, db
from app.models import AuditLog, User
from app.helpers import log_audit


def make_user(phone='+919800000101'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


class TestLogAuditWithRequestContext:

    def test_captures_ip_and_user_agent(self, app):
        user = make_user()
        with app.test_request_context(
            environ_base={'REMOTE_ADDR': '203.0.113.9'},
            headers={'User-Agent': 'pytest-diagnostic/1.0'},
        ):
            log_audit(user_id=user.id, action='AUDIT_CONTEXT_TEST', table_affected='Test')

        entry = AuditLog.query.filter_by(action='AUDIT_CONTEXT_TEST').one()
        assert entry.ip_address == '203.0.113.9'
        assert entry.user_agent == 'pytest-diagnostic/1.0'


class TestLogAuditWithNoRequestContext:

    def test_writes_row_with_null_ip_and_user_agent(self):
        # Deliberately does not take `app`/`client` fixtures — see module
        # docstring for why.
        standalone_app = create_app()
        assert ":memory:" in standalone_app.config["SQLALCHEMY_DATABASE_URI"], \
            "SAFETY: standalone test app must use in-memory SQLite, never a real DB file"
        with standalone_app.app_context():
            db.create_all()
            try:
                user = User(phone='+919800000102', role='user', subscription_tier='free')
                db.session.add(user)
                db.session.commit()

                log_audit(user_id=user.id, action='AUDIT_NO_CONTEXT_TEST', table_affected='Test')

                entry = AuditLog.query.filter_by(action='AUDIT_NO_CONTEXT_TEST').one()
                assert entry.ip_address is None
                assert entry.user_agent is None
            finally:
                db.session.remove()
                db.drop_all()
