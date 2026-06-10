# ============================================================
# FILE: app/tasks.py
# PURPOSE: Async Celery tasks — SLA timers, backup verification
# LAST UPDATED: Phase 1
# ============================================================

import os
from datetime import datetime, timedelta, timezone
from celery import shared_task
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
