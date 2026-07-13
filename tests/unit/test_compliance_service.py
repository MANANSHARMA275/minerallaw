"""
Tests for app/compliance_service.py — persistence of calculated compliance
deadlines as ComplianceEvent rows.

generate_compliance_events() calls log_audit() directly. As of Chunk 4a,
log_audit() is context-safe: it always writes an AuditLog row, with
ip_address/user_agent null when no Flask request context is active. The
tests below don't need to wrap calls in test_request_context() for the
AuditLog row to appear — pytest-flask's autouse `_push_request_context`
fixture also means any test using the `app` fixture already runs inside a
request context regardless, so such wrapping was always redundant here. The
one test that actually proves background-safety
(TestNoRequestContext, below) deliberately avoids the `app`/`client`
fixtures — see tests/unit/test_audit_log.py's module docstring for why
that's the only way to get a genuinely context-free call.
"""
from datetime import date, datetime, timezone

from app import create_app, db
from app.models import ComplianceEvent, AuditLog, User
from app.compliance_service import generate_compliance_events


def make_user(phone='+919800000001'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


class TestHappyPath:

    def test_creates_expected_rows(self, app):
        user = make_user()
        result = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

        assert result["status"] == "ok"
        assert result["created"] > 0
        assert result["skipped"] == 0
        assert result["soft_deleted"] == 0

        events = ComplianceEvent.query.filter_by(user_id=user.id).all()
        assert len(events) == result["created"]
        for event in events:
            assert event.status == 'pending'
            assert event.reminder_sent_7_days is False
            assert event.reminder_sent_1_day is False
            assert event.deleted_at is None

    def test_audit_log_entry_written(self, app):
        user = make_user('+919800000002')
        generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

        logs = AuditLog.query.filter_by(user_id=user.id, action='COMPLIANCE_EVENTS_GENERATED').all()
        assert len(logs) == 1
        assert logs[0].table_affected == 'ComplianceEvent'


class TestIdempotency:

    def test_second_identical_call_creates_nothing(self, app):
        user = make_user('+919800000003')
        first = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)
        second = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

        assert second["created"] == 0
        assert second["skipped"] == first["created"]
        assert second["soft_deleted"] == 0
        active_count = ComplianceEvent.query.filter_by(user_id=user.id, deleted_at=None).count()
        assert active_count == first["created"]


class TestRegeneration:

    def test_different_grant_date_soft_deletes_and_recreates(self, app):
        user = make_user('+919800000004')
        first = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)
        second = generate_compliance_events(user.id, date(2026, 3, 1), lease_period_years=1)

        assert second["soft_deleted"] == first["created"]
        assert second["created"] > 0
        assert second["skipped"] == 0

        all_events = ComplianceEvent.query.filter_by(user_id=user.id).all()
        soft_deleted_events = [e for e in all_events if e.deleted_at is not None]
        active_events = [e for e in all_events if e.deleted_at is None]
        assert len(soft_deleted_events) == first["created"]
        assert len(active_events) == second["created"]

        logs = AuditLog.query.filter_by(user_id=user.id, action='COMPLIANCE_EVENTS_REGENERATED').all()
        assert len(logs) == 1
        assert str(first["created"]) in logs[0].old_value
        assert str(second["created"]) in logs[0].new_value


class TestSoftDeleteExcludedFromIdempotency:

    def test_manually_soft_deleted_event_is_not_matched_as_existing(self, app):
        user = make_user('+919800000005')
        first = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

        # Manually soft-delete one active row, same pattern as test_compliance_event.py
        one_event = ComplianceEvent.query.filter_by(user_id=user.id, deleted_at=None).first()
        one_event.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        second = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

        # Active set (N-1) no longer matches fresh set (N) -> regeneration path:
        # the manually-deleted row was never "matched" as already existing.
        assert second["soft_deleted"] == first["created"] - 1
        assert second["created"] == first["created"]

        active_events = ComplianceEvent.query.filter_by(user_id=user.id, deleted_at=None).all()
        assert len(active_events) == first["created"]


class TestNoRequestContext:

    def test_generate_compliance_events_writes_audit_log_without_request_context(self):
        # Deliberately does not take `app`/`client` fixtures — pytest-flask's
        # autouse request-context push (see test_audit_log.py's module
        # docstring) would otherwise mask the very thing this test proves:
        # that generate_compliance_events is safe to call from Celery/
        # background jobs with genuinely no Flask request context.
        standalone_app = create_app()
        assert ":memory:" in standalone_app.config["SQLALCHEMY_DATABASE_URI"], \
            "SAFETY: standalone test app must use in-memory SQLite, never a real DB file"
        with standalone_app.app_context():
            db.create_all()
            try:
                user = User(phone='+919800000006', role='user', subscription_tier='free')
                db.session.add(user)
                db.session.commit()

                result = generate_compliance_events(user.id, date(2026, 1, 15), lease_period_years=1)

                assert result["status"] == "ok"
                assert result["created"] > 0

                events = ComplianceEvent.query.filter_by(user_id=user.id).all()
                assert len(events) == result["created"]

                logs = AuditLog.query.filter_by(user_id=user.id, action='COMPLIANCE_EVENTS_GENERATED').all()
                assert len(logs) == 1
                assert logs[0].ip_address is None
                assert logs[0].user_agent is None
            finally:
                db.session.remove()
                db.drop_all()
