"""
Tests for app/tickets.py and app/validators.py.
"""
import pytest

from app import db
from app.models import AuditLog, Ticket, User
from app.tickets import create_ticket
from app.validators import validate_mineral_query, validate_phone


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_user(phone='+919876543210'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


# ── Ticket creation ────────────────────────────────────────────────────────────

class TestCreateTicket:

    def test_creates_open_ticket(self, app):
        user = make_user()
        ticket = create_ticket(user.id, 'Test subject', 'Test description body')
        assert Ticket.query.count() == 1
        assert ticket.status == 'open'
        assert ticket.subject == 'Test subject'
        assert ticket.description == 'Test description body'

    def test_create_ticket_logs_audit(self, app):
        user = make_user('+910000000099')
        create_ticket(user.id, 'Audit test subject', 'Full description here.')
        count = AuditLog.query.filter_by(action='TICKET_CREATED').count()
        assert count == 1


# ── Phone validation ───────────────────────────────────────────────────────────

class TestValidatePhone:

    def test_normalises_10_digit(self):
        ok, result = validate_phone('9876543210')
        assert ok is True
        assert result == '+919876543210'

    def test_accepts_plus91_prefix(self):
        ok, result = validate_phone('+919876543210')
        assert ok is True
        assert result == '+919876543210'

    def test_accepts_91_prefix(self):
        ok, result = validate_phone('919876543210')
        assert ok is True
        assert result == '+919876543210'

    def test_rejects_junk(self):
        ok, msg = validate_phone('hello')
        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0

    def test_rejects_empty(self):
        ok, msg = validate_phone('')
        assert ok is False

    def test_strips_spaces_and_dashes(self):
        ok, result = validate_phone('98765 43-210')
        assert ok is True
        assert result == '+919876543210'


# ── Mineral query validation ───────────────────────────────────────────────────

class TestValidateMineralQuery:

    def test_rejects_short_query(self):
        ok, msg = validate_mineral_query('Limestone', 'hi')
        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0

    def test_accepts_valid(self):
        ok, msg = validate_mineral_query(
            'Limestone', 'What is the royalty rate for 2026?'
        )
        assert ok is True
        assert msg == ''

    def test_accepts_empty_mineral(self):
        ok, msg = validate_mineral_query('', 'What are the DMF rules for minor minerals?')
        assert ok is True
        assert msg == ''

    def test_rejects_empty_query(self):
        ok, msg = validate_mineral_query('Sandstone', '')
        assert ok is False

    def test_rejects_oversized_query(self):
        ok, msg = validate_mineral_query('Limestone', 'x' * 2001)
        assert ok is False
