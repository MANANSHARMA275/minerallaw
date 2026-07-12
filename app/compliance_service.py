# ============================================================
# FILE: app/compliance_service.py
# PURPOSE: Persist calculated compliance deadlines as ComplianceEvent rows
# LAST UPDATED: Phase 1 — Compliance Automation Chunk 3
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from datetime import datetime, timezone

from app.deadline_calculator import calculate_compliance_deadlines
from app.helpers import log_audit
from app.logger import logger


# ------------------------------------------------------------
# SECTION 2: INTERNAL HELPERS
# ------------------------------------------------------------
def _fetch_active_events(user_id: int) -> list:
    """
    PURPOSE  : Load a user's currently-active (non-soft-deleted) compliance events
    RECEIVES : user_id — int
    RETURNS  : list[ComplianceEvent] — deleted_at IS NULL rows for this user
    SECURITY : Scoped strictly to the given user_id
    LEGAL    : see generate_compliance_events LEGAL note
    """
    from app.models import ComplianceEvent
    return ComplianceEvent.query.filter_by(user_id=user_id, deleted_at=None).all()


def _soft_delete_events(events: list) -> int:
    """
    PURPOSE  : Mark a batch of ComplianceEvent rows as deleted, never hard-delete
    RECEIVES : events — list[ComplianceEvent]
    RETURNS  : int — number of rows marked
    SECURITY : n/a — pure mutation, caller commits
    LEGAL    : Hard DELETE is forbidden — rows remain for audit/history
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for event in events:
        event.deleted_at = now
    return len(events)


def _create_events(user_id: int, deadline_dicts: list) -> int:
    """
    PURPOSE  : Insert new ComplianceEvent rows from calculated deadline dicts
    RECEIVES : user_id — int; deadline_dicts — list[{"event_type","due_date","description"}]
    RETURNS  : int — number of rows added
    SECURITY : n/a — pure mutation, caller commits
    LEGAL    : status/reminder flags use model defaults ('pending', False, False)
    """
    from app.models import ComplianceEvent, db
    for deadline in deadline_dicts:
        db.session.add(ComplianceEvent(
            user_id=user_id,
            event_type=deadline["event_type"],
            due_date=deadline["due_date"],
        ))
    return len(deadline_dicts)


def _log_generation_result(user_id: int, ec_grant_date, is_regeneration: bool,
                            created: int, skipped: int, soft_deleted: int) -> None:
    """
    PURPOSE  : Write the single AuditLog entry for a generation/regeneration call
    RECEIVES : user_id, ec_grant_date, is_regeneration, created, skipped, soft_deleted
    RETURNS  : None
    SECURITY : Requires an active Flask request context — see log_audit
    LEGAL    : see generate_compliance_events LEGAL note
    """
    if is_regeneration:
        log_audit(
            user_id=user_id,
            action='COMPLIANCE_EVENTS_REGENERATED',
            table_affected='ComplianceEvent',
            old_value=f"{soft_deleted} active event(s) superseded",
            new_value=f"{created} created for corrected grant_date={ec_grant_date}",
        )
    else:
        log_audit(
            user_id=user_id,
            action='COMPLIANCE_EVENTS_GENERATED',
            table_affected='ComplianceEvent',
            new_value=f"{created} created, {skipped} skipped for grant_date={ec_grant_date}",
        )


# ------------------------------------------------------------
# SECTION 3: PUBLIC API
# ------------------------------------------------------------
def generate_compliance_events(user_id: int, ec_grant_date, lease_period_years: int = None) -> dict:
    """
    PURPOSE  : Turn calculated compliance deadlines into ComplianceEvent rows
    RECEIVES : user_id — int; ec_grant_date — date; lease_period_years — int or None
    RETURNS  : dict — {"status": "ok"|"error", "created": int, "skipped": int,
               "soft_deleted": int, "message": str (only on error)}
    SECURITY : Writes are scoped to the given user_id only. NOTE:
               log_audit silently no-ops (writes NO AuditLog row) when
               called outside a Flask request context — this MUST be
               resolved before any Celery/background caller uses this
               service.
    LEGAL    : Due dates originate from calculate_compliance_deadlines'
               COMPLIANCE_CONFIG, all verified_by_father=False — these are
               estimates pending Phase 0 Interview Session 2, not
               authoritative filing deadlines. AuditLog rows are immutable
               per log_audit's own retention policy. Whether completed
               events with proof_document_url attached should survive a
               grant-date correction (rather than being superseded with
               the rest) is an open product question pending father
               verification (Phase 0 Interview Session 2).
    """
    from app.models import db
    try:
        fresh_events = calculate_compliance_deadlines(ec_grant_date, lease_period_years)
        fresh_keys = {(e["event_type"], e["due_date"]) for e in fresh_events}

        active_events = _fetch_active_events(user_id)
        active_keys = {(e.event_type, e.due_date) for e in active_events}
        is_regeneration = bool(active_events) and active_keys != fresh_keys

        if is_regeneration:
            soft_deleted = _soft_delete_events(active_events)
            created = _create_events(user_id, fresh_events)
            skipped = 0
        else:
            new_only = [e for e in fresh_events if (e["event_type"], e["due_date"]) not in active_keys]
            created = _create_events(user_id, new_only)
            skipped = len(fresh_events) - created
            soft_deleted = 0

        db.session.commit()
        # BLOCKER (Chunk 4): log_audit no-ops without request context — fix before background use
        _log_generation_result(user_id, ec_grant_date, is_regeneration, created, skipped, soft_deleted)

        return {"status": "ok", "created": created, "skipped": skipped, "soft_deleted": soft_deleted}
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Compliance event generation failed: {exc}")
        return {"status": "error", "created": 0, "skipped": 0, "soft_deleted": 0, "message": str(exc)}
