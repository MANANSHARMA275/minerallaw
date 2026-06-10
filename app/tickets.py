# ============================================================
# FILE: app/tickets.py
# PURPOSE: Ticket creation for expert consultation queue
# LAST UPDATED: Phase 1
# ============================================================

from datetime import datetime, timezone

from app import db
from app.helpers import log_audit
from app.models import Ticket


def create_ticket(user_id, subject, description,
                  mineral_type=None, state='Rajasthan', urgency='normal'):
    """
    PURPOSE  : Create a support/consultation ticket for the expert queue
    RECEIVES : user_id (int) — authenticated user;
               subject (str) — short summary, max 200 chars;
               description (str) — full question text;
               mineral_type (str|None) — optional mineral name;
               state (str) — defaults to 'Rajasthan';
               urgency (str) — 'low'/'normal'/'high', defaults to 'normal'
    RETURNS  : Ticket — the newly created and committed Ticket object
    SECURITY : Caller must be authenticated — enforced in route, not here
    LEGAL    : Ticket creation logged in AuditLog for SLA tracking
    """
    ticket = Ticket(
        user_id=user_id,
        subject=subject[:200],
        description=description,
        mineral_type=mineral_type,
        state=state,
        urgency=urgency,
        status='open',
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(ticket)
    db.session.commit()

    log_audit(
        user_id=user_id,
        action='TICKET_CREATED',
        table_affected='Ticket',
        record_id=ticket.id,
        new_value=subject[:80],
    )

    return ticket
