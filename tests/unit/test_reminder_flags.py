"""
Tests for app/tasks.py's reminder-flagging logic (Chunk 4b) —
flag_due_reminders() and the flag_due_reminders_task() Celery wrapper.

flag_due_reminders() takes `today` as an injectable parameter specifically
so these tests never touch the real clock (no freezegun/time-machine
needed, neither is installed). A fixed anchor date keeps every case
deterministic regardless of when the suite actually runs.

TestReminderTaskAuditLog deliberately avoids the `app`/`client` fixtures —
same reason as tests/unit/test_audit_log.py and
tests/unit/test_compliance_service.py's TestNoRequestContext: pytest-flask's
autouse request-context push would otherwise mask the very thing being
proven (the task wrapper is safe to call with no Flask request context).

It calls flag_due_reminders_task.run() rather than flag_due_reminders_task()
directly. Once anything in the test session imports celery_worker (e.g.
tests/unit/test_celery_timezone.py), constructing that module's Celery(...)
registers it as Celery's process-global "current app" (set_as_current=True
is the default) and activates ContextTask as its Task base. Any @shared_task
called directly at that point routes through ContextTask.__call__, which
pushes celery_worker.py's OWN internal flask_app context — a different app
than this test's standalone_app — regardless of what this test wraps the
call in. Calling .run() bypasses Task/ContextTask dispatch entirely and
invokes the plain function body under whatever context is already active
(this test's own), which is both what's being tested here and immune to
this cross-test ordering effect.
"""
from datetime import date, datetime, timedelta, timezone

from app import create_app, db
from app.models import AuditLog, ComplianceEvent, User
from app.tasks import flag_due_reminders, flag_due_reminders_task

TODAY = date(2026, 6, 15)


def make_user(phone='+919800000301'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


def make_event(user_id, due_date, status='pending', deleted_at=None):
    event = ComplianceEvent(
        user_id=user_id,
        event_type='annual_return',
        due_date=due_date,
        status=status,
        deleted_at=deleted_at,
    )
    db.session.add(event)
    db.session.commit()
    return event


class TestOutsideWindow:

    def test_ten_days_out_gets_no_flags(self, app):
        user = make_user()
        event = make_event(user.id, TODAY + timedelta(days=10))

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 0, "flagged_1_day": 0}
        assert event.reminder_sent_7_days is False
        assert event.reminder_sent_1_day is False


class TestSevenDayWindow:

    def test_exactly_seven_days_out_flags_seven_day_only(self, app):
        user = make_user('+919800000302')
        event = make_event(user.id, TODAY + timedelta(days=7))

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 1, "flagged_1_day": 0}
        assert event.reminder_sent_7_days is True
        assert event.reminder_sent_1_day is False

    def test_three_days_out_catches_up_seven_day_flag_only(self, app):
        """Window is <=, not ==: a missed Beat run still catches this up."""
        user = make_user('+919800000303')
        event = make_event(user.id, TODAY + timedelta(days=3))

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 1, "flagged_1_day": 0}
        assert event.reminder_sent_7_days is True
        assert event.reminder_sent_1_day is False


class TestOneDayWindow:

    def test_one_day_out_flags_both(self, app):
        user = make_user('+919800000304')
        event = make_event(user.id, TODAY + timedelta(days=1))

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 1, "flagged_1_day": 1}
        assert event.reminder_sent_7_days is True
        assert event.reminder_sent_1_day is True


class TestOverdueEvent:

    def test_overdue_event_flags_both_by_design(self, app):
        """
        Overdue events (due_date < today) fall within both windows since
        days_until_due is negative, satisfying both <= 7 and <= 1. This is
        not special-cased — it's the same comparison as any other event —
        and is documented here as expected behavior, not a bug.
        """
        user = make_user('+919800000305')
        event = make_event(user.id, TODAY - timedelta(days=5))

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 1, "flagged_1_day": 1}
        assert event.reminder_sent_7_days is True
        assert event.reminder_sent_1_day is True


class TestIdempotency:

    def test_second_run_same_today_flips_nothing(self, app):
        user = make_user('+919800000306')
        make_event(user.id, TODAY + timedelta(days=1))

        first = flag_due_reminders(today=TODAY)
        db.session.commit()
        second = flag_due_reminders(today=TODAY)

        assert first == {"flagged_7_day": 1, "flagged_1_day": 1}
        assert second == {"flagged_7_day": 0, "flagged_1_day": 0}


class TestExclusions:

    def test_soft_deleted_and_non_pending_events_untouched(self, app):
        user = make_user('+919800000307')
        soft_deleted_event = make_event(
            user.id, TODAY + timedelta(days=1),
            deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        completed_event = make_event(
            user.id, TODAY + timedelta(days=1), status='completed',
        )

        result = flag_due_reminders(today=TODAY)

        assert result == {"flagged_7_day": 0, "flagged_1_day": 0}
        assert soft_deleted_event.reminder_sent_7_days is False
        assert completed_event.reminder_sent_7_days is False


class TestReminderTaskAuditLog:

    def test_task_wrapper_writes_audit_log_without_request_context(self):
        standalone_app = create_app()
        assert ":memory:" in standalone_app.config["SQLALCHEMY_DATABASE_URI"], \
            "SAFETY: standalone test app must use in-memory SQLite, never a real DB file"
        with standalone_app.app_context():
            db.create_all()
            try:
                user = User(phone='+919800000308', role='user', subscription_tier='free')
                db.session.add(user)
                db.session.commit()

                event = ComplianceEvent(
                    user_id=user.id,
                    event_type='annual_return',
                    due_date=date.today() + timedelta(days=1),
                )
                db.session.add(event)
                db.session.commit()

                result = flag_due_reminders_task.run()

                assert result["status"] == "ok"
                assert result["flagged_7_day"] == 1
                assert result["flagged_1_day"] == 1

                logs = AuditLog.query.filter_by(action='REMINDER_FLAGS_UPDATED').all()
                assert len(logs) == 1
                assert logs[0].user_id is None
                assert logs[0].ip_address is None
                assert logs[0].user_agent is None
                assert '7d: 1 flipped' in logs[0].new_value
                assert '1d: 1 flipped' in logs[0].new_value
            finally:
                db.session.remove()
                db.drop_all()
