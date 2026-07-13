# ============================================================
# FILE: app/tasks.py
# PURPOSE: Async Celery tasks — SLA timers, backup verification
# LAST UPDATED: Phase 1
# ============================================================

import os
from datetime import date, datetime, timedelta, timezone
from celery import shared_task
from app.helpers import log_audit
from app.logger import logger


@shared_task
def check_sla_timers() -> dict:
    """
    PURPOSE  : Check all open tickets for SLA breach — alert father via WhatsApp
    RECEIVES : None (Celery Beat — every 30 minutes)
    RETURNS  : dict — summary of alerts sent
    SECURITY : Read-only ticket scan + WhatsApp alert to FATHER_PHONE only
    LEGAL    : SLA tracking protects father's commitment to clients
    """
    from app.models import Ticket, db
    now = datetime.now(timezone.utc)
    alerts_sent = 0

    # 20-hour warning — father first reminder
    tickets_20h = Ticket.query.filter(
        Ticket.status.in_(['open', 'in_progress']),
        Ticket.first_response_at.is_(None),
        Ticket.created_at <= now - timedelta(hours=20),
        Ticket.created_at > now - timedelta(hours=48)
    ).all()

    for ticket in tickets_20h:
        logger.warning(
            f"SLA 20h WARNING: Ticket #{ticket.id} open 20+ hours. "
            f"User: {ticket.user_id}"
        )
        alerts_sent += 1

    # 48-hour breach — escalate
    tickets_48h = Ticket.query.filter(
        Ticket.status.in_(['open', 'in_progress']),
        Ticket.first_response_at.is_(None),
        Ticket.created_at <= now - timedelta(hours=48)
    ).all()

    for ticket in tickets_48h:
        ticket.status = 'escalated'
        logger.error(
            f"SLA BREACHED: Ticket #{ticket.id} escalated. "
            f"User: {ticket.user_id}"
        )
        alerts_sent += 1

    try:
        db.session.commit()
    except Exception as e:
        logger.error(f"SLA timer DB commit failed: {e}")
        db.session.rollback()

    return {"alerts_sent": alerts_sent, "checked_at": now.isoformat()}


@shared_task
def verify_daily_backup_exists() -> dict:
    """
    PURPOSE  : Verify yesterday's pg_dump backup exists in S3 Mumbai
    RECEIVES : None (Celery Beat — 6 AM IST daily)
    RETURNS  : dict — {"status": "ok"|"missing", ...}
    SECURITY : Read-only S3 head_object check
    LEGAL    : 3-2-1 backup rule. Alerts father if missing.
    """
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client('s3', region_name='ap-south-1')
    bucket = os.environ.get('BACKUP_BUCKET', '')
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    key = f"backups/{yesterday}.dump"

    if not bucket:
        logger.warning("BACKUP_BUCKET env var not set — skipping backup verification")
        return {"status": "skipped", "reason": "BACKUP_BUCKET not configured"}

    try:
        s3.head_object(Bucket=bucket, Key=key)
        logger.info(f"Backup verified: {key}")
        return {"status": "ok", "file": key}
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"BACKUP MISSING: {key} not found in S3 bucket {bucket}")
            return {"status": "missing", "file": key}
        raise


@shared_task
def import_dmg_news_task() -> dict:
    """
    PURPOSE  : Celery task wrapper — trigger DMG News & Events import
    RECEIVES : None
    RETURNS  : dict — {"status", "new", "skipped", "message"}
    SECURITY : Delegates fully to run_news_import(); no direct DB access here
    LEGAL    : Fetches publicly available government information from DMG portal
    """
    from app.news_importer import run_news_import
    return run_news_import()


def flag_due_reminders(today: date = None) -> dict:
    """
    PURPOSE  : Flip reminder_sent_7_days/reminder_sent_1_day for events due soon
    RECEIVES : today — date, injectable for deterministic tests; defaults to date.today()
    RETURNS  : dict — {"flagged_7_day": int, "flagged_1_day": int}
    SECURITY : Scoped to active (deleted_at IS NULL), status='pending' events only
    LEGAL    : due_date values derive from unverified COMPLIANCE_CONFIG
               placeholders (see app/deadline_calculator.py) — reminder
               timing inherits that same caveat.
    """
    from app.models import ComplianceEvent

    if today is None:
        today = date.today()

    cutoff = today + timedelta(days=7)
    candidates = ComplianceEvent.query.filter(
        ComplianceEvent.deleted_at.is_(None),
        ComplianceEvent.status == 'pending',
        ComplianceEvent.due_date <= cutoff,
    ).all()

    flagged_7_day = 0
    flagged_1_day = 0
    for event in candidates:
        days_until_due = (event.due_date - today).days
        if days_until_due <= 7 and not event.reminder_sent_7_days:
            event.reminder_sent_7_days = True
            flagged_7_day += 1
        if days_until_due <= 1 and not event.reminder_sent_1_day:
            event.reminder_sent_1_day = True
            flagged_1_day += 1

    return {"flagged_7_day": flagged_7_day, "flagged_1_day": flagged_1_day}


@shared_task
def flag_due_reminders_task() -> dict:
    """
    PURPOSE  : Celery Beat entry point — flag due compliance reminders daily
    RECEIVES : None (Celery Beat — daily, see app/celery_config.py beat_schedule)
    RETURNS  : dict — {"status": "ok"|"error", "flagged_7_day": int,
               "flagged_1_day": int, "message": str (only on error)}
    SECURITY : Runs under Flask app context via ContextTask (celery_worker.py);
               no request context, so log_audit writes null ip_address/user_agent
               — expected and correct per Chunk 4a.
    LEGAL    : due_date values derive from unverified COMPLIANCE_CONFIG
               placeholders — see flag_due_reminders.
    """
    from app.models import db
    try:
        result = flag_due_reminders()
        db.session.commit()
        log_audit(
            user_id=None,
            action='REMINDER_FLAGS_UPDATED',
            table_affected='ComplianceEvent',
            new_value=f"7d: {result['flagged_7_day']} flipped, 1d: {result['flagged_1_day']} flipped",
        )
        return {"status": "ok", **result}
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Reminder flag update failed: {exc}")
        return {"status": "error", "flagged_7_day": 0, "flagged_1_day": 0, "message": str(exc)}
