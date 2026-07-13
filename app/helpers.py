# ============================================================
# FILE: app/helpers.py
# PURPOSE: Shared helper utilities — audit logging
# LAST UPDATED: Phase 1
# ============================================================

from urllib.parse import urlencode

from app.logger import logger


def gmail_prefill(to: str, subject: str, body: str) -> str:
    params = {'view': 'cm', 'to': to, 'su': subject, 'body': body}
    return f"https://mail.google.com/mail/?{urlencode(params)}"


def format_inr(amount) -> str:
    try:
        val = int(amount)
    except (TypeError, ValueError):
        return '₹0'
    s = str(val)
    if len(s) <= 3:
        return f"₹{s}"
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return f"₹{result}"


def log_audit(user_id, action, table_affected=None, record_id=None,
              old_value=None, new_value=None):
    """
    PURPOSE  : Write an immutable AuditLog entry for any data-changing action
    RECEIVES : user_id (int), action (str), table_affected (str, optional),
               record_id (int, optional), old_value (str, optional),
               new_value (str, optional)
    RETURNS  : None
    SECURITY : IP address and User-Agent captured from the live request
               context when one is active; both are None for callers with
               no request context (e.g. Celery/background jobs) — the
               AuditLog row is still always written in that case.
    LEGAL    : AuditLog rows must NEVER be deleted — 7-year retention (GST / DPDP).
    """
    from flask import has_request_context, request
    from app.models import AuditLog, db

    if has_request_context():
        ip_address = request.remote_addr
        user_agent = (request.headers.get('User-Agent', '') or '')[:300]
    else:
        ip_address = None
        user_agent = None

    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            table_affected=table_affected,
            record_id=record_id,
            old_value=old_value,
            new_value=str(new_value) if new_value is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        logger.error(f"Audit log write failed: {exc}")
