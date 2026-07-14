# ============================================================
# FILE: app/whatsapp.py
# PURPOSE: Deliver compliance-reminder WhatsApp messages via Twilio, gated by
#          a kill switch, consent, and a duplicate-send guard — every real
#          attempt (sent/failed/skipped) leaves a WhatsAppMessage audit row
# LAST UPDATED: Phase 1 — Chunk 4c-i
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
import os

from app.helpers import log_audit
from app.logger import logger


# ------------------------------------------------------------
# SECTION 2: TEMPLATES — isolated so approved Twilio template text can
# swap in later without touching gate logic
# ------------------------------------------------------------
REMINDER_TYPE_TO_TEMPLATE_KEY = {
    '7_day': 'compliance_reminder_7_day',
    '1_day': 'compliance_reminder_1_day',
}

REMINDER_TEMPLATES = {
    'compliance_reminder_7_day': (
        "Reminder: your {event_type} filing is due on {due_date}. "
        "7 days remaining. Log in to MineralLaw.in to review."
    ),
    'compliance_reminder_1_day': (
        "URGENT: your {event_type} filing is due TOMORROW ({due_date}). "
        "Log in to MineralLaw.in immediately."
    ),
}


# ------------------------------------------------------------
# SECTION 3: INTERNAL HELPERS
# ------------------------------------------------------------
def _mask_phone(phone: str) -> str:
    """
    PURPOSE  : Mask a phone number for storage/display, keeping only last 4 digits
    RECEIVES : phone (str) — raw number, e.g. '+919876543210'
    RETURNS  : str — e.g. '+91XXXXXX3210' if a '+' prefix is present,
               else 'XXXXXX3210'. Numbers of 4 chars or fewer are fully masked.
    SECURITY : Never return more than the last 4 characters unmasked
    LEGAL    : DPDP data minimization — to_phone_masked is the only phone
               fragment persisted on WhatsAppMessage
    """
    phone = phone or ''
    prefix = ''
    digits = phone
    if digits.startswith('+'):
        prefix = digits[:3]
        digits = digits[3:]
    if len(digits) <= 4:
        return prefix + 'X' * len(digits)
    last4 = digits[-4:]
    return f"{prefix}{'X' * (len(digits) - 4)}{last4}"


def _render_body(template_key: str, event) -> str:
    """
    PURPOSE  : Fill a reminder template with the ComplianceEvent's fields
    RECEIVES : template_key (str), event (ComplianceEvent)
    RETURNS  : str — rendered message body
    SECURITY : No PII beyond what the user themselves owns (event_type, due_date)
    LEGAL    : n/a — informational reminder text
    """
    return REMINDER_TEMPLATES[template_key].format(
        event_type=event.event_type, due_date=event.due_date
    )


def _mask_error(exc: Exception) -> str:
    """
    PURPOSE  : Convert a raw exception into a storable, PII-masked error_detail
    RECEIVES : exc (Exception)
    RETURNS  : str — masked, truncated to fit error_detail's 300-char column
    SECURITY : Routes text through app.logger.mask_pii before storage/truncation
    LEGAL    : Twilio error messages sometimes echo the `to=` phone back — must be masked
    """
    from app.logger import mask_pii
    return mask_pii(str(exc))[:300]


def _record_message(user_id, compliance_event_id, reminder_type, to_phone_masked,
                     template_key, body_preview, status, twilio_sid=None, error_detail=None):
    """
    PURPOSE  : Insert + flush (not commit) one WhatsAppMessage row
    RECEIVES : see WhatsAppMessage columns
    RETURNS  : WhatsAppMessage — the new row (id populated after flush)
    SECURITY : Caller is responsible for commit + log_audit sequencing
    LEGAL    : One row per real attempt, including skips — audit trail requirement
    """
    from app.models import WhatsAppMessage, db
    msg = WhatsAppMessage(
        user_id=user_id, compliance_event_id=compliance_event_id,
        reminder_type=reminder_type, to_phone_masked=to_phone_masked,
        template_key=template_key, body_preview=body_preview, status=status,
        twilio_sid=twilio_sid, error_detail=error_detail,
    )
    db.session.add(msg)
    db.session.flush()
    return msg


def _already_sent(compliance_event_id, reminder_type) -> bool:
    """
    PURPOSE  : Duplicate-guard check — has a 'sent' row already been recorded?
    RECEIVES : compliance_event_id (int|None), reminder_type (str)
    RETURNS  : bool
    SECURITY : n/a — read-only
    LEGAL    : A 'failed' prior attempt must NOT count as already-sent (retry allowed)
    """
    from app.models import WhatsAppMessage
    return WhatsAppMessage.query.filter_by(
        compliance_event_id=compliance_event_id,
        reminder_type=reminder_type,
        status='sent',
    ).first() is not None


def _is_sending_enabled() -> bool:
    """
    PURPOSE  : Read the WHATSAPP_SENDING_ENABLED kill switch from app config
    RECEIVES : None
    RETURNS  : bool
    SECURITY : Defaults closed (False) on any unset/malformed value
    LEGAL    : n/a
    """
    from flask import current_app
    return bool(current_app.config.get('WHATSAPP_SENDING_ENABLED', False))


def _get_twilio_client():
    """
    PURPOSE  : Construct a Twilio REST client from env credentials
    RECEIVES : None
    RETURNS  : twilio.rest.Client
    SECURITY : Credentials read from env only, never logged. Tests mock this
               function directly — no real client is ever constructed in the suite.
    LEGAL    : n/a
    """
    from twilio.rest import Client
    return Client(
        os.environ.get('TWILIO_ACCOUNT_SID'),
        os.environ.get('TWILIO_AUTH_TOKEN'),
    )


def _send_and_record(user, event, compliance_event_id, reminder_type, template_key) -> dict:
    """
    PURPOSE  : GATE 4 — actually call Twilio and record the outcome row
    RECEIVES : user (User), event (ComplianceEvent), compliance_event_id,
               reminder_type, template_key
    RETURNS  : dict — {"status": "sent"|"failed", "message_id": int}
    SECURITY : to=/from= use env-configured whatsapp: numbers; full phone
               never leaves this function except in the outbound Twilio call
    LEGAL    : Twilio SID retained as delivery proof
    """
    from app.models import db

    body = _render_body(template_key, event)
    masked_phone = _mask_phone(user.phone)

    try:
        client = _get_twilio_client()
        result = client.messages.create(
            to=f"whatsapp:{user.phone}",
            from_=os.environ.get('TWILIO_WHATSAPP_NUMBER'),
            body=body,
        )
        msg = _record_message(user.id, compliance_event_id, reminder_type, masked_phone,
                               template_key, body[:160], status='sent', twilio_sid=result.sid)
        db.session.commit()
        log_audit(user.id, 'WHATSAPP_REMINDER_SENT', table_affected='WhatsAppMessage',
                   record_id=msg.id, new_value=f"sid={result.sid}")
        return {"status": "sent", "message_id": msg.id}
    except Exception as exc:
        db.session.rollback()
        masked_error = _mask_error(exc)
        msg = _record_message(user.id, compliance_event_id, reminder_type, masked_phone,
                               template_key, body[:160], status='failed', error_detail=masked_error)
        db.session.commit()
        log_audit(user.id, 'WHATSAPP_REMINDER_FAILED', table_affected='WhatsAppMessage',
                   record_id=msg.id, new_value=masked_error)
        return {"status": "failed", "message_id": msg.id}


# ------------------------------------------------------------
# SECTION 4: PUBLIC API
# ------------------------------------------------------------
def send_compliance_reminder(user_id: int, compliance_event_id: int, reminder_type: str) -> dict:
    """
    PURPOSE  : Send (or skip) one WhatsApp compliance reminder, recording a
               WhatsAppMessage row for every real attempt (sent/failed/skipped_*)
    RECEIVES : user_id (int), compliance_event_id (int), reminder_type (str) — '7_day'/'1_day'
    RETURNS  : dict — {"status": "sent"|"failed"|"skipped_no_consent"|
               "skipped_kill_switch"|"already_sent"|"error", "message_id": int|None}
    SECURITY : Full phone number only ever touches memory (User.phone) and the
               Twilio API call itself — never persisted; to_phone_masked only.
               Never raises — retry policy is decided by the caller (Chunk 4c-ii).
    LEGAL    : One audit-trail row per real attempt; already_sent is a pure
               read with no new evidence needed since a prior 'sent' row
               already documents the successful attempt. A precondition
               failure (bad reminder_type / unresolvable compliance_event_id)
               still writes a 'failed' row when user_id resolves, since
               logfiles rotate but WhatsAppMessage rows are the durable
               audit trail; only an unresolvable user_id (FK requires a
               real user) falls back to logger-only.
    """
    from app.models import ComplianceEvent, User, db

    template_key = REMINDER_TYPE_TO_TEMPLATE_KEY.get(reminder_type)
    user = db.session.get(User, user_id)
    event = db.session.get(ComplianceEvent, compliance_event_id) if compliance_event_id else None

    if user is None:
        logger.error(f"send_compliance_reminder: unknown user_id={user_id}")
        return {"status": "error", "message_id": None}

    if template_key is None or event is None:
        reason = 'invalid_reminder_type' if template_key is None else 'missing_compliance_event'
        msg = _record_message(user_id, None, reminder_type, _mask_phone(user.phone),
                               'n/a', None, status='failed', error_detail=reason)
        db.session.commit()
        log_audit(user_id, 'WHATSAPP_REMINDER_FAILED', table_affected='WhatsAppMessage',
                   record_id=msg.id, new_value=reason)
        return {"status": "error", "message_id": msg.id}

    # GATE 1 — kill switch. No Twilio client is constructed while this is off.
    if not _is_sending_enabled():
        msg = _record_message(user_id, compliance_event_id, reminder_type,
                               _mask_phone(user.phone), template_key, None,
                               status='skipped_kill_switch')
        db.session.commit()
        log_audit(user_id, 'WHATSAPP_REMINDER_SKIPPED', table_affected='WhatsAppMessage',
                   record_id=msg.id, new_value='kill switch off')
        return {"status": "skipped_kill_switch", "message_id": msg.id}

    # GATE 2 — consent
    if not (user.consent or {}).get('compliance_alerts'):
        msg = _record_message(user_id, compliance_event_id, reminder_type,
                               _mask_phone(user.phone), template_key, None,
                               status='skipped_no_consent')
        db.session.commit()
        log_audit(user_id, 'WHATSAPP_REMINDER_SKIPPED', table_affected='WhatsAppMessage',
                   record_id=msg.id, new_value='consent.compliance_alerts is false')
        return {"status": "skipped_no_consent", "message_id": msg.id}

    # GATE 3 — duplicate guard. No row written for the short-circuit.
    if _already_sent(compliance_event_id, reminder_type):
        return {"status": "already_sent", "message_id": None}

    # GATE 4 — send
    return _send_and_record(user, event, compliance_event_id, reminder_type, template_key)
