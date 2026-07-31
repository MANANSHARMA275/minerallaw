"""
Tests for GET /compliance (Chunk 5) — user-facing, read-only compliance
calendar page.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from flask import url_for

from app import db
from app.models import ComplianceEvent
from app.routes import classify_urgency, relative_due_display

from .test_admin import _login, make_user


def make_event(user_id, due_date, event_type='annual_return', status='pending', deleted_at=None):
    event = ComplianceEvent(
        user_id=user_id, event_type=event_type, due_date=due_date,
        status=status, deleted_at=deleted_at,
    )
    db.session.add(event)
    db.session.commit()
    return event


class TestAnonymousBlocked:
    def test_anonymous_get_redirects_to_login(self, client):
        # 9a
        resp = client.get('/compliance')
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '').lower()


class TestRegularUserAccess:
    def test_regular_user_gets_200(self, app, client):
        user = make_user('+919800000407', role='user')
        _login(client, app, user)
        resp = client.get('/compliance')
        assert resp.status_code == 200


class TestOwnershipIsolation:
    def test_user_sees_only_own_events(self, app, client):
        # 9b — core test of the chunk
        user_a = make_user('+919800000401', role='user')
        user_b = make_user('+919800000402', role='user')
        make_event(user_a.id, date(2026, 3, 10), event_type='annual_return')
        make_event(user_b.id, date(2026, 5, 5), event_type='six_monthly_report')

        _login(client, app, user_b)
        resp = client.get('/compliance')
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert '10 Mar 2026' not in body   # user A's event absent
        assert '05 May 2026' in body       # user B's event present
        assert 'Six-monthly compliance report to Regional Office' in body


class TestNavLink:
    def test_nav_link_present_exactly_once(self, app, client):
        user = make_user('+919800000411', role='user')
        _login(client, app, user)
        with app.test_request_context():
            expected_href = f'href="{url_for("main.compliance_calendar")}"'
        resp = client.get('/dashboard')
        body = resp.get_data(as_text=True)
        # F2: the responsive nav renders a desktop-row copy and a mobile-panel
        # copy of every link, CSS-gated by breakpoint (hidden lg:flex /
        # lg:hidden) so only one is ever visible at a time — both are
        # legitimately present in the markup.
        assert body.count(expected_href) == 2


class TestSoftDelete:
    def test_soft_deleted_event_excluded(self, app, client):
        # 9c
        user = make_user('+919800000403', role='user')
        make_event(
            user.id, date(2026, 8, 1),
            deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        _login(client, app, user)
        resp = client.get('/compliance')
        assert '01 Aug 2026' not in resp.get_data(as_text=True)


class TestEmptyState:
    def test_zero_events_shows_empty_state(self, app, client):
        # 9d
        user = make_user('+919800000404', role='user')
        _login(client, app, user)
        resp = client.get('/compliance')
        assert resp.status_code == 200
        assert 'No compliance deadlines yet' in resp.get_data(as_text=True)

    def test_empty_state_has_ask_expert_cta(self, app, client):
        user = make_user('+919800000410', role='user')
        _login(client, app, user)
        with app.test_request_context():
            expected_href = url_for('main.ask_expert')
        resp = client.get('/compliance')
        body = resp.get_data(as_text=True)
        assert 'Talk to an expert' in body
        assert expected_href in body


class TestOrdering:
    def test_events_render_in_urgency_then_date_order(self, app, client):
        # req 4. One user, 5 events, deliberately SHUFFLED insertion order,
        # covering all four urgency bands; 'overdue_early'/'overdue_late'
        # share a band with different due_dates to prove within-band
        # ascending order. 'done_date' has an earlier raw due_date than
        # 'due_soon'/'upcoming' but must still render LAST, proving band
        # order trumps raw due_date.
        user = make_user('+919800000406', role='user')
        today = date.today()

        overdue_early = today - timedelta(days=10)
        overdue_late = today - timedelta(days=3)
        due_soon = today + timedelta(days=3)
        upcoming = today + timedelta(days=20)
        done_date = today + timedelta(days=1)

        # Shuffled insertion order — NOT pre-sorted
        make_event(user.id, upcoming, status='pending')
        make_event(user.id, overdue_early, status='pending')
        make_event(user.id, done_date, status='completed')
        make_event(user.id, due_soon, status='pending')
        make_event(user.id, overdue_late, status='pending')

        _login(client, app, user)
        resp = client.get('/compliance')
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200

        markers = [
            overdue_early.strftime('%d %b %Y'),
            overdue_late.strftime('%d %b %Y'),
            due_soon.strftime('%d %b %Y'),
            upcoming.strftime('%d %b %Y'),
            done_date.strftime('%d %b %Y'),
        ]
        positions = [body.index(m) for m in markers]
        assert positions == sorted(positions), (
            f"Expected render order overdue(early)->overdue(late)->"
            f"due_soon->upcoming->done; got positions {positions} "
            f"for markers {markers}"
        )


class TestUrgencyClassification:
    @pytest.mark.parametrize('due_date,expected', [
        (date(2026, 7, 20), 'overdue'),   # today - 6 days
        (date(2026, 7, 26), 'due_soon'),  # today, days_delta = 0
        (date(2026, 8, 2), 'due_soon'),   # today + 7 (inclusive boundary)
        (date(2026, 8, 3), 'upcoming'),   # today + 8
    ])
    def test_classify_by_due_date(self, due_date, expected):
        # 9e — no freezegun; today is injected directly (repo convention)
        assert classify_urgency(due_date, 'pending', today=date(2026, 7, 26)) == expected

    def test_completed_is_always_done_regardless_of_date(self):
        # 9f
        today = date(2026, 7, 26)
        assert classify_urgency(date(2020, 1, 1), 'completed', today) == 'done'
        assert classify_urgency(date(2030, 1, 1), 'completed', today) == 'done'


class TestRelativeDueDisplay:
    @pytest.mark.parametrize('due_date,status,expected', [
        (date(2026, 7, 16), 'pending', 'Overdue by 10 days'),
        (date(2026, 7, 25), 'pending', 'Overdue by 1 day'),
        (date(2026, 7, 26), 'pending', 'Due today'),
        (date(2026, 7, 27), 'pending', 'Due in 1 day'),
        (date(2026, 8, 2), 'pending', 'Due in 7 days'),
        (date(2020, 1, 1), 'completed', ''),
    ])
    def test_relative_display(self, due_date, status, expected):
        assert relative_due_display(due_date, status, today=date(2026, 7, 26)) == expected


class TestUnknownEventType:
    def test_unknown_event_type_renders_without_raising(self, app, client):
        # 9g
        user = make_user('+919800000405', role='user')
        make_event(user.id, date(2026, 9, 1), event_type='some_new_future_type')
        _login(client, app, user)
        resp = client.get('/compliance')
        assert resp.status_code == 200
        assert 'some_new_future_type' in resp.get_data(as_text=True)
