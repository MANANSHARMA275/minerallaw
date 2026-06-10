"""
Tests for EC Report Builder models — ECCondition, ComplianceReport, ComplianceResponse.
Phase 2 prep: schema-only tests (no routes yet).
"""
import pytest
from datetime import date

from app import db
from app.models import (
    ComplianceReport,
    ComplianceResponse,
    ECCondition,
    User,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_user(phone='+919800000001'):
    u = User(phone=phone, role='user', subscription_tier='free')
    db.session.add(u)
    db.session.commit()
    return u


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestComplianceReport:

    def test_default_status_is_draft(self, app):
        """ComplianceReport must start in 'draft' status."""
        user = make_user()
        report = ComplianceReport(
            user_id=user.id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 6, 30),
            due_date=date(2026, 7, 30),
        )
        db.session.add(report)
        db.session.commit()

        assert ComplianceReport.query.count() == 1
        assert report.status == 'draft'


class TestECCondition:

    def test_supersede_not_edit(self, app):
        """
        EC conditions are never edited — a superseded row stays, a new row is added.
        Assert count == 2 after superseding the original and inserting a replacement.
        """
        user = make_user('+919800000002')

        original = ECCondition(
            user_id=user.id,
            condition_number='SC-01',
            category='specific',
            condition_text='Plantation of 200 trees per hectare required.',
            verified_by_father=True,
        )
        db.session.add(original)
        db.session.commit()

        # Supersede — never update condition_text
        original.superseded = True
        replacement = ECCondition(
            user_id=user.id,
            condition_number='SC-01',
            category='specific',
            condition_text='Plantation of 250 trees per hectare required (revised 2026).',
            verified_by_father=False,
        )
        db.session.add(replacement)
        db.session.commit()

        assert ECCondition.query.count() == 2
        superseded = ECCondition.query.filter_by(superseded=True).first()
        assert superseded is not None
        active = ECCondition.query.filter_by(superseded=False).first()
        assert '250 trees' in active.condition_text


class TestComplianceResponse:

    def test_links_to_previous_period(self, app):
        """
        previous_response_id enables pre-fill from the last report period.
        Verify the FK resolves back to response1.
        """
        user = make_user('+919800000003')

        condition = ECCondition(
            user_id=user.id,
            condition_number='GC-01',
            category='general',
            condition_text='Submit water usage data monthly.',
        )
        db.session.add(condition)

        report1 = ComplianceReport(
            user_id=user.id,
            period_start=date(2025, 7, 1),
            period_end=date(2025, 12, 31),
            due_date=date(2026, 1, 30),
        )
        report2 = ComplianceReport(
            user_id=user.id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 6, 30),
            due_date=date(2026, 7, 30),
        )
        db.session.add_all([report1, report2])
        db.session.flush()

        response1 = ComplianceResponse(
            report_id=report1.id,
            condition_id=condition.id,
            self_declaration='Complied',
            remarks='Water logs submitted via MOEF portal.',
        )
        db.session.add(response1)
        db.session.flush()

        response2 = ComplianceResponse(
            report_id=report2.id,
            condition_id=condition.id,
            self_declaration='Complied',
            previous_response_id=response1.id,
        )
        db.session.add(response2)
        db.session.commit()

        fetched = db.session.get(ComplianceResponse, response2.id)
        assert fetched.previous_response_id == response1.id
