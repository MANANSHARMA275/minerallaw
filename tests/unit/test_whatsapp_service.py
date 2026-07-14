"""
Tests for app/whatsapp.py's send_compliance_reminder service (Chunk 4c-i).

Twilio is mocked exclusively at the app.whatsapp._get_twilio_client()
boundary — see that function's docstring. No test in this suite installs a
real Twilio client, and tests/conftest.py's autouse _block_real_network_calls
fixture guarantees any code path that slips past a gate and tries a real
socket.connect() aborts the test immediately (see TestNetworkTripwireItself,
and TestKillSwitch which relies on this: it never mocks Twilio at all).

TestNoRequestContext deliberately avoids the `app`/`client` fixtures — same
reason as tests/unit/test_audit_log.py and test_compliance_service.py's
TestNoRequestContext: pytest-flask's autouse request-context push would
otherwise mask the very thing being proven (that the service is safe to
call with no Flask request context, e.g. from Celery in Chunk 4c-ii).
"""
import re
import socket
from datetime import date

import pytest

from app import create_app, db
from app.models import AuditLog, ComplianceEvent, User, WhatsAppMessage
from app.whatsapp import send_compliance_reminder

_UNSET = object()


def make_user(phone='+919800000401', consent=_UNSET):
    if consent is _UNSET:
        consent = {"compliance_alerts": True, "ai_analysis": False,
                   "expert_consultation": False, "marketing": False}
    u = User(phone=phone, role='user', subscription_tier='free', consent=consent)
    db.session.add(u)
    db.session.commit()
    return u


def make_event(user_id, event_type='annual_return', due_date=None):
    event = ComplianceEvent(
        user_id=user_id,
        event_type=event_type,
        due_date=due_date or date(2026, 7, 21),
    )
    db.session.add(event)
    db.session.commit()
    return event


class _FakeTwilioMessage:
    def __init__(self, sid='SM_fake_123'):
        self.sid = sid


class _FakeTwilioClient:
    def __init__(self, sid='SM_fake_123', raise_exc=None):
        self._sid = sid
        self._raise_exc = raise_exc
        self.last_call_kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._raise_exc:
            raise self._raise_exc
        return _FakeTwilioMessage(self._sid)


class TestNetworkTripwireItself:

    def test_direct_socket_connect_raises(self):
        with pytest.raises(RuntimeError, match="SAFETY: real network call attempted"):
            socket.socket().connect(('example.com', 80))


class TestKillSwitch:

    def test_kill_switch_off_skips_with_no_twilio_mock_installed(self, app):
        # WHATSAPP_SENDING_ENABLED defaults False; no mock of _get_twilio_client
        # is installed at all. If gate ordering let Twilio get constructed or
        # called, the conftest network tripwire would fail this test.
        user = make_user()
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "skipped_kill_switch"
        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert msg.status == 'skipped_kill_switch'

    def test_kill_switch_off_writes_audit_log(self, app):
        user = make_user()
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        log = AuditLog.query.filter_by(action='WHATSAPP_REMINDER_SKIPPED').first()
        assert log is not None
        assert log.table_affected == 'WhatsAppMessage'
        assert log.record_id == result["message_id"]


class TestKillSwitchConfig:

    def test_unset_env_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv('WHATSAPP_SENDING_ENABLED', raising=False)
        test_app = create_app()
        assert test_app.config['WHATSAPP_SENDING_ENABLED'] is False

    @pytest.mark.parametrize('value', ['1', 'yes', 'TRUEE', 'enabled', ''])
    def test_ambiguous_or_wrong_values_parse_to_false(self, monkeypatch, value):
        monkeypatch.setenv('WHATSAPP_SENDING_ENABLED', value)
        test_app = create_app()
        assert test_app.config['WHATSAPP_SENDING_ENABLED'] is False

    @pytest.mark.parametrize('value', ['true', 'True', 'TRUE', ' true '])
    def test_true_variants_parse_to_true(self, monkeypatch, value):
        monkeypatch.setenv('WHATSAPP_SENDING_ENABLED', value)
        test_app = create_app()
        assert test_app.config['WHATSAPP_SENDING_ENABLED'] is True


class TestConsent:

    def test_no_consent_skips_and_records(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)

        user = make_user(consent={"compliance_alerts": False})
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "skipped_no_consent"
        assert fake_client.last_call_kwargs is None
        log = AuditLog.query.filter_by(action='WHATSAPP_REMINDER_SKIPPED').first()
        assert log is not None

    def test_consent_present_proceeds_to_send(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user(consent={"compliance_alerts": True})
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "sent"

    def test_missing_consent_json_treated_as_no_consent(self, app):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        user = make_user(consent=None)
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "skipped_no_consent"


class TestDuplicateGuard:

    def test_existing_sent_row_returns_already_sent_no_new_row(self, app):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        user = make_user()
        event = make_event(user.id)
        db.session.add(WhatsAppMessage(
            user_id=user.id, compliance_event_id=event.id, reminder_type='7_day',
            to_phone_masked='+91XXXXXX1234', template_key='compliance_reminder_7_day',
            status='sent', twilio_sid='SM_prior',
        ))
        db.session.commit()

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result == {"status": "already_sent", "message_id": None}
        count = WhatsAppMessage.query.filter_by(
            compliance_event_id=event.id, reminder_type='7_day').count()
        assert count == 1

    def test_existing_failed_row_does_not_block_retry(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user()
        event = make_event(user.id)
        db.session.add(WhatsAppMessage(
            user_id=user.id, compliance_event_id=event.id, reminder_type='7_day',
            to_phone_masked='+91XXXXXX1234', template_key='compliance_reminder_7_day',
            status='failed', error_detail='prior failure',
        ))
        db.session.commit()

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "sent"
        count = WhatsAppMessage.query.filter_by(
            compliance_event_id=event.id, reminder_type='7_day').count()
        assert count == 2


class TestSendPath:

    def test_successful_send_records_sent_status_and_sid(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient(sid='SM_abc123')
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user()
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "sent"
        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert msg.twilio_sid == 'SM_abc123'
        assert msg.template_key == 'compliance_reminder_7_day'
        assert msg.body_preview and len(msg.body_preview) <= 160

    def test_twilio_exception_records_failed_and_does_not_raise(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient(raise_exc=Exception("Twilio error for +919876543210"))
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user(phone='+919876543210')
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        assert result["status"] == "failed"
        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert msg.status == 'failed'
        assert '9876543210' not in (msg.error_detail or '')

    def test_twilio_call_uses_whatsapp_prefixed_to_and_configured_from(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user(phone='+919876543210')
        event = make_event(user.id)

        send_compliance_reminder(user.id, event.id, '7_day')

        assert fake_client.last_call_kwargs['to'] == 'whatsapp:+919876543210'
        assert fake_client.last_call_kwargs['from_'] == 'whatsapp:+14155238886'


class TestPIIMasking:

    def test_to_phone_masked_never_has_6_plus_consecutive_digits(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient()
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user(phone='+919876543210')
        event = make_event(user.id)
        send_compliance_reminder(user.id, event.id, '7_day')

        assert WhatsAppMessage.query.count() > 0
        for msg in WhatsAppMessage.query.all():
            assert re.search(r'\d{6,}', msg.to_phone_masked) is None

    def test_to_phone_masked_matches_exact_mask_shape(self, app):
        # Kill switch left off — still exercises _mask_phone via Gate 1's row write.
        user = make_user(phone='+919876543210')
        event = make_event(user.id)

        result = send_compliance_reminder(user.id, event.id, '7_day')

        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert re.fullmatch(r'\+91X{6}\d{4}', msg.to_phone_masked)

    def test_error_detail_is_masked_when_present(self, app, monkeypatch):
        app.config['WHATSAPP_SENDING_ENABLED'] = True
        fake_client = _FakeTwilioClient(raise_exc=Exception("failed for +919876543210"))
        monkeypatch.setattr('app.whatsapp._get_twilio_client', lambda: fake_client)
        monkeypatch.setenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        user = make_user(phone='+919876543210')
        event = make_event(user.id)
        result = send_compliance_reminder(user.id, event.id, '7_day')

        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert re.search(r'\d{6,}', msg.error_detail) is None


class TestModel:

    def test_whatsapp_message_creation_defaults_and_fk_relationships(self, app):
        user = make_user()
        event = make_event(user.id)
        msg = WhatsAppMessage(
            user_id=user.id, compliance_event_id=event.id, reminder_type='7_day',
            to_phone_masked='+91XXXXXX1234', template_key='compliance_reminder_7_day',
            status='sent', twilio_sid='SM_test',
        )
        db.session.add(msg)
        db.session.commit()
        db.session.refresh(msg)

        assert msg.created_at is not None
        assert msg.user_id == user.id
        assert msg in user.whatsapp_messages

    def test_compliance_event_id_nullable(self, app):
        user = make_user()
        msg = WhatsAppMessage(
            user_id=user.id, compliance_event_id=None, reminder_type='7_day',
            to_phone_masked='+91XXXXXX1234', template_key='compliance_reminder_7_day',
            status='skipped_kill_switch',
        )
        db.session.add(msg)
        db.session.commit()  # must not raise

        assert msg.id is not None


class TestPreconditions:

    def test_missing_compliance_event_writes_failed_row(self, app):
        user = make_user()

        result = send_compliance_reminder(user.id, 999999, '7_day')

        assert result["status"] == "error"
        assert result["message_id"] is not None
        msg = db.session.get(WhatsAppMessage, result["message_id"])
        assert msg.status == 'failed'
        assert msg.error_detail == 'missing_compliance_event'
        log = AuditLog.query.filter_by(action='WHATSAPP_REMINDER_FAILED').first()
        assert log is not None

    def test_unknown_user_id_returns_error_no_row(self, app):
        result = send_compliance_reminder(999999, 1, '7_day')

        assert result == {"status": "error", "message_id": None}
        assert WhatsAppMessage.query.count() == 0


class TestNoRequestContext:

    def test_send_compliance_reminder_safe_without_request_context(self):
        standalone_app = create_app()
        assert ":memory:" in standalone_app.config["SQLALCHEMY_DATABASE_URI"], \
            "SAFETY: standalone test app must use in-memory SQLite, never a real DB file"
        with standalone_app.app_context():
            db.create_all()
            try:
                user = make_user(phone='+919800000499')
                event = make_event(user.id)

                result = send_compliance_reminder(user.id, event.id, '7_day')

                assert result["status"] == "skipped_kill_switch"
                log = AuditLog.query.filter_by(action='WHATSAPP_REMINDER_SKIPPED').first()
                assert log is not None
                assert log.ip_address is None
                assert log.user_agent is None
            finally:
                db.session.remove()
                db.drop_all()
