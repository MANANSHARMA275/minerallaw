"""
Tests for app/tasks.py's reminder-delivery logic (Chunk 4c-ii) —
deliver_due_reminders() and its wiring into flag_due_reminders_task().

Follows tests/unit/test_reminder_flags.py's make_user/make_event/TODAY
anchor convention (deterministic, no freezegun) and
tests/unit/test_whatsapp_service.py's Twilio boundary
(monkeypatch app.whatsapp._get_twilio_client) so no real network call is
ever attempted — tests/conftest.py's autouse network tripwire would fail
the suite immediately if one slipped through.

TestFlagPhaseFailure deliberately avoids the `app`/`client` fixtures for
the same reason as test_reminder_flags.py's TestReminderTaskAuditLog and
test_whatsapp_service.py's TestNoRequestContext: it calls
flag_due_reminders_task.run() directly to bypass ContextTask/ Celery
dispatch, which would otherwise push a different Flask app context than
this test's own standalone_app.
"""
from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import AuditLog, ComplianceEvent, User, WhatsAppMessage
from app.tasks import deliver_due_reminders, flag_due_reminders_task

TODAY = date(2026, 6, 15)


def make_user(phone='+919800000501', consent=None):
    if consent is None:
        consent = {"compliance_alerts": True, "ai_analysis": False,
                   "expert_consultation": False, "marketing": False}
    u = User(phone=phone, role='user', subscription_tier='free', consent=consent)
    db.session.add(u)
    db.session.commit()
    return u


def make_event(user_id, due_date=None, status='pending', deleted_at=None,
                reminder_sent_7_days=False, reminder_sent_1_day=False):
    event = ComplianceEvent(
        user_id=user_id,
        event_type='annual_return',
        due_date=due_date or TODAY,
        status=status,
        deleted_at=deleted_at,
        reminder_sent_7_days=reminder_sent_7_days,
        reminder_sent_1_day=reminder_sent_1_day,
    )
    db.session.add(event)
    db.session.commit()
    return event


class _FakeTwilioMessage:
    def __init__(self, sid='SM_fake_501'):
        self.sid = sid


class _FakeTwilioClient:
    def __init__(self, sid='SM_fake_501', raise_exc=None):
        self._sid = sid
        self._raise_exc = raise_exc
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if self._raise_exc:
            raise self._raise_exc
        return _FakeTwilioMessage(self._sid)


class TestDeliveryBasic:

    def test_two_owed_events_both_delivered(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user1 = make_user('+919800000502')
        user2 = make_user('+919800000503')
        make_event(user1.id, reminder_sent_7_days=True)
        make_event(user2.id, reminder_sent_1_day=True)

        result = deliver_due_reminders(today=TODAY)

        assert result["sent"] == 2
        assert fake_client.calls == 2


class TestPartialFailureIsolation:

    def test_one_send_fails_other_still_delivered(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user1 = make_user('+919800000504')
        user2 = make_user('+919800000505')
        make_event(user1.id, reminder_sent_7_days=True)
        make_event(user2.id, reminder_sent_7_days=True)

        # First Twilio call raises, every subsequent call succeeds — proves
        # one event's Twilio failure doesn't stop the other from being sent,
        # regardless of which event the query visits first.
        state = {'calls': 0}

        class _AlternatingClient:
            def __init__(self):
                self.messages = self

            def create(self, **kwargs):
                state['calls'] += 1
                if state['calls'] == 1:
                    raise Exception("Twilio down")
                return _FakeTwilioMessage()

        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: _AlternatingClient())

        result = deliver_due_reminders(today=TODAY)

        assert result["failed"] == 1
        assert result["sent"] == 1
        assert state['calls'] == 2


class TestDuplicateGuard:

    def test_already_sent_event_not_resent(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)

        user = make_user('+919800000506')
        event = make_event(user.id, reminder_sent_7_days=True)
        db.session.add(WhatsAppMessage(
            user_id=user.id, compliance_event_id=event.id, reminder_type='7_day',
            to_phone_masked='+91XXXXXX0506', template_key='compliance_reminder_7_day',
            status='sent', twilio_sid='SM_prior',
        ))
        db.session.commit()

        result = deliver_due_reminders(today=TODAY)

        assert result["already_sent"] == 1
        assert result["sent"] == 0
        assert fake_client.calls == 0
        assert WhatsAppMessage.query.filter_by(
            compliance_event_id=event.id, reminder_type='7_day').count() == 1


class TestUnflaggedExcluded:

    def test_event_with_no_flags_not_attempted(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)

        user = make_user('+919800000507')
        make_event(user.id)  # both flags False

        result = deliver_due_reminders(today=TODAY)

        assert sum(result.values()) == 0
        assert fake_client.calls == 0


class TestExclusions:

    def test_soft_deleted_and_completed_events_excluded(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)

        user = make_user('+919800000508')
        make_event(user.id, reminder_sent_7_days=True, reminder_sent_1_day=True,
                   deleted_at=date(2026, 1, 1))
        make_event(user.id, reminder_sent_7_days=True, reminder_sent_1_day=True,
                   status='completed')

        result = deliver_due_reminders(today=TODAY)

        assert sum(result.values()) == 0
        assert fake_client.calls == 0


class TestKillSwitchOff:

    def test_kill_switch_off_all_skipped_no_twilio_constructed(self, app):
        # WHATSAPP_SENDING_ENABLED defaults False; no _get_twilio_client mock
        # installed at all. If gate ordering let Twilio get constructed, the
        # conftest network tripwire would fail this test.
        user = make_user('+919800000509')
        make_event(user.id, reminder_sent_7_days=True)

        result = deliver_due_reminders(today=TODAY)

        assert result["skipped_kill_switch"] == 1
        assert sum(v for k, v in result.items() if k != "skipped_kill_switch") == 0


class TestDefensiveIsolation:

    def test_unexpected_exception_from_send_is_isolated_and_counted_as_error(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True

        user1 = make_user('+919800000510')
        user2 = make_user('+919800000511')
        make_event(user1.id, reminder_sent_7_days=True)
        make_event(user2.id, reminder_sent_7_days=True)

        call_count = {'n': 0}

        def flaky_send(user_id, compliance_event_id, reminder_type):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise RuntimeError("unexpected boundary failure")
            return {"status": "sent", "message_id": 1}

        monkeypatch.setattr('app.whatsapp.send_compliance_reminder', flaky_send)

        result = deliver_due_reminders(today=TODAY)

        assert result["error"] == 1
        assert result["sent"] == 1


class TestReturnShape:

    def test_return_has_exactly_six_documented_keys(self, app):
        result = deliver_due_reminders(today=TODAY)

        assert set(result.keys()) == {
            "sent", "failed", "skipped_no_consent",
            "skipped_kill_switch", "already_sent", "error",
        }


class TestFullMorningRunIntegration:

    def test_flag_then_deliver_then_batch_audit(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient(sid='SM_morning_run')
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user('+919800000512')
        event = make_event(user.id, due_date=TODAY + timedelta(days=1))

        result = flag_due_reminders_task.run(today=TODAY)

        assert result["status"] == "ok"
        assert result["flagged_7_day"] == 1
        assert result["flagged_1_day"] == 1
        assert result["delivered"]["sent"] == 2  # both 7_day and 1_day fire

        db.session.refresh(event)
        assert event.reminder_sent_7_days is True
        assert event.reminder_sent_1_day is True

        sent_messages = WhatsAppMessage.query.filter_by(
            compliance_event_id=event.id, status='sent').all()
        assert len(sent_messages) == 2

        flag_log = AuditLog.query.filter_by(action='REMINDER_FLAGS_UPDATED').first()
        assert flag_log is not None

        deliver_log = AuditLog.query.filter_by(action='REMINDERS_DELIVERED').first()
        assert deliver_log is not None
        assert deliver_log.user_id is None
        assert deliver_log.table_affected == 'WhatsAppMessage'
        assert 'sent: 2' in deliver_log.new_value


class TestFlagPhaseFailure:

    def test_flag_phase_failure_skips_delivery_entirely(self, monkeypatch):
        standalone_app = create_app()
        assert ":memory:" in standalone_app.config["SQLALCHEMY_DATABASE_URI"], \
            "SAFETY: standalone test app must use in-memory SQLite, never a real DB file"
        with standalone_app.app_context():
            db.create_all()
            try:
                def raise_flag(today=None):
                    raise RuntimeError("flag phase exploded")

                monkeypatch.setattr('app.tasks.flag_due_reminders', raise_flag)

                result = flag_due_reminders_task.run()

                assert result["status"] == "error"
                assert result["flagged_7_day"] == 0
                assert result["flagged_1_day"] == 0
                assert result["delivered"] == {"status": "not_attempted"}
                assert "flag phase exploded" in result["message"]

                assert AuditLog.query.filter_by(action='REMINDERS_DELIVERED').count() == 0
            finally:
                db.session.remove()
                db.drop_all()
