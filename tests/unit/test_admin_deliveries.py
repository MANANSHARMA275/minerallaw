"""
Tests for app/admin.py's GET /admin/deliveries route (Chunk 4d) — a
strictly read-only WhatsApp delivery log for the superadmin.

Superadmin-only / non-superadmin-403 / anonymous-redirect coverage lives in
tests/security/test_access_control.py's parametrized lists ('/admin/deliveries'
was added there); this file covers rendering, filtering, pagination, and the
PII-masking discipline extended to the UI layer.
"""
from datetime import date

from app import db
from app.models import ComplianceEvent, User, WhatsAppMessage

from .test_admin import _login, make_user


def make_message(user_id, status='sent', reminder_type='7_day',
                  compliance_event_id=None, to_phone_masked='+91XXXXXX0001',
                  template_key='compliance_reminder_7_day', body_preview='reminder text',
                  error_detail=None):
    msg = WhatsAppMessage(
        user_id=user_id, compliance_event_id=compliance_event_id,
        reminder_type=reminder_type, to_phone_masked=to_phone_masked,
        template_key=template_key, body_preview=body_preview, status=status,
        error_detail=error_detail,
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def make_event(user_id, event_type='annual_return', due_date=None):
    event = ComplianceEvent(
        user_id=user_id, event_type=event_type, due_date=due_date or date(2026, 7, 21),
    )
    db.session.add(event)
    db.session.commit()
    return event


class TestSuperadminAccess:

    def test_superadmin_get_returns_200(self, app, client):
        admin = make_user('+919810000001', role='superadmin')
        _login(client, app, admin)

        resp = client.get('/admin/deliveries')

        assert resp.status_code == 200


class TestRendersRows:

    def test_multiple_statuses_appear_in_response(self, app, client):
        admin = make_user('+919810000002', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000003')
        make_message(user.id, status='sent', to_phone_masked='+91XXXXXX1111')
        make_message(user.id, status='failed', to_phone_masked='+91XXXXXX2222')
        make_message(user.id, status='skipped_kill_switch', to_phone_masked='+91XXXXXX3333')

        resp = client.get('/admin/deliveries')
        body = resp.data.decode()

        assert '+91XXXXXX1111' in body
        assert '+91XXXXXX2222' in body
        assert '+91XXXXXX3333' in body
        assert 'sent' in body
        assert 'failed' in body
        assert 'skipped_kill_switch' in body


class TestStatusFilter:

    def test_status_filter_shows_matching_hides_others(self, app, client):
        admin = make_user('+919810000004', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000005')
        make_message(user.id, status='sent', to_phone_masked='+91XXXXXX4444')
        make_message(user.id, status='failed', to_phone_masked='+91XXXXXX5555')

        resp = client.get('/admin/deliveries?status=failed')
        body = resp.data.decode()

        assert '+91XXXXXX5555' in body
        assert '+91XXXXXX4444' not in body

    def test_unknown_status_falls_back_to_all_no_500(self, app, client):
        admin = make_user('+919810000006', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000007')
        make_message(user.id, status='sent', to_phone_masked='+91XXXXXX6666')

        resp = client.get('/admin/deliveries?status=bogus_junk')

        assert resp.status_code == 200
        assert '+91XXXXXX6666' in resp.data.decode()


class TestUserIdFilter:

    def test_user_id_filter_scopes_correctly(self, app, client):
        admin = make_user('+919810000008', role='superadmin')
        _login(client, app, admin)
        user_a = make_user('+919810000009')
        user_b = make_user('+919810000010')
        make_message(user_a.id, to_phone_masked='+91XXXXXX7777')
        make_message(user_b.id, to_phone_masked='+91XXXXXX8888')

        resp = client.get(f'/admin/deliveries?user_id={user_a.id}')
        body = resp.data.decode()

        assert '+91XXXXXX7777' in body
        assert '+91XXXXXX8888' not in body

    def test_junk_user_id_falls_back_no_500(self, app, client):
        admin = make_user('+919810000011', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000012')
        make_message(user.id, to_phone_masked='+91XXXXXX9999')

        resp = client.get('/admin/deliveries?user_id=abc')

        assert resp.status_code == 200
        assert '+91XXXXXX9999' in resp.data.decode()


class TestPagination:

    def test_page_1_shows_fifty_page_2_shows_remainder(self, app, client):
        admin = make_user('+919810000013', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000014')
        for i in range(51):
            make_message(user.id, to_phone_masked=f'+91XXXXXX{9000 + i}'[-13:])

        page1 = client.get('/admin/deliveries')
        page2 = client.get('/admin/deliveries?page=2')

        assert page1.status_code == 200
        assert page2.status_code == 200
        assert WhatsAppMessage.query.count() == 51

    def test_out_of_range_page_returns_200_empty_not_error(self, app, client):
        admin = make_user('+919810000015', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000016')
        make_message(user.id)

        resp = client.get('/admin/deliveries?page=999')

        assert resp.status_code == 200
        assert 'No delivery records found.' in resp.data.decode()


class TestPIIMasking:

    def test_full_phone_number_never_appears_only_masked_form(self, app, client):
        admin = make_user('+919810000017', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919876543299')
        make_message(user.id, to_phone_masked='+91XXXXXX3299')

        resp = client.get('/admin/deliveries')
        body = resp.data.decode()

        assert '9876543299' not in body
        assert '+91XXXXXX3299' in body


class TestEmptyState:

    def test_no_rows_renders_empty_state(self, app, client):
        admin = make_user('+919810000018', role='superadmin')
        _login(client, app, admin)

        resp = client.get('/admin/deliveries')

        assert resp.status_code == 200
        assert 'No delivery records found.' in resp.data.decode()


class TestComplianceEventJoin:

    def test_event_present_shows_type_and_due_date_null_shows_dash(self, app, client):
        admin = make_user('+919810000019', role='superadmin')
        _login(client, app, admin)
        user = make_user('+919810000020')
        event = make_event(user.id, event_type='annual_return', due_date=date(2026, 8, 1))
        make_message(user.id, compliance_event_id=event.id, to_phone_masked='+91XXXXXX1010')
        make_message(user.id, compliance_event_id=None, to_phone_masked='+91XXXXXX2020')

        resp = client.get('/admin/deliveries')
        body = resp.data.decode()

        assert 'annual_return' in body
        assert '01 Aug 2026' in body
        assert '—' in body
