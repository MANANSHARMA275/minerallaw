"""
Tests for the ComplianceEvent model — Compliance Automation Chunk 1.
Schema-only tests (no routes, no reminder/Celery logic yet).
"""
from datetime import date, datetime, timezone

from app import db
from app.models import ComplianceEvent, User


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_user(phone='+919800000001'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


class TestComplianceEventDefaults:

    def test_creation_and_defaults(self, app):
        """Only required fields set — the rest must fall back to their defaults."""
        user = make_user()
        event = ComplianceEvent(
            user_id=user.id,
            event_type='six_monthly_report',
            due_date=date(2026, 12, 31),
        )
        db.session.add(event)
        db.session.commit()

        assert ComplianceEvent.query.count() == 1
        assert event.status == 'pending'
        assert event.reminder_sent_7_days is False
        assert event.reminder_sent_1_day is False
        assert event.completed_at is None
        assert event.proof_document_url is None
        assert event.created_at is not None
        assert event.deleted_at is None


class TestComplianceEventSoftDelete:

    def test_deleted_at_round_trips_and_excludes_from_active_filter(self, app):
        """Setting deleted_at persists across a refetch and is excludable via filter_by."""
        user = make_user('+919800000002')
        event = ComplianceEvent(
            user_id=user.id,
            event_type='annual_return',
            due_date=date(2026, 3, 31),
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        event.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        fetched = db.session.get(ComplianceEvent, event_id)
        assert fetched.deleted_at is not None

        active = ComplianceEvent.query.filter_by(deleted_at=None).all()
        assert active == []


class TestComplianceEventUserRelationship:

    def test_fk_relationship_to_user(self, app):
        """user_id resolves back to the owning User via the backref both ways."""
        user = make_user('+919800000003')
        event = ComplianceEvent(
            user_id=user.id,
            event_type='six_monthly_report',
            due_date=date(2026, 6, 30),
        )
        db.session.add(event)
        db.session.commit()

        assert event.user_id == user.id
        assert event.user.id == user.id
        assert event in user.compliance_events
