# ============================================================
# FILE: app/admin.py
# PURPOSE: Father's admin panel — rate management, ticket view, user overview
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: ROLE DECORATOR
# ------------------------------------------------------------
from functools import wraps
from datetime import date, datetime, timezone
from decimal import Decimal

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import AuditLog, AuctionStatus, Legislation, Mineral, Rate, Ticket, User, db, get_auction_status
from app.helpers import log_audit
from app.news_importer import run_news_import


def role_required(required_role: str):
    """
    PURPOSE  : Restrict route to specific user roles
    RECEIVES : required_role (str) — 'superadmin' or 'staff'
    RETURNS  : decorator
    SECURITY : superadmin bypasses all role checks
    LEGAL    : Prevents staff accessing rate tables or user PII
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role == 'superadmin':
                return f(*args, **kwargs)
            if current_user.role != required_role:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------------------------------------------
# SECTION 2: BLUEPRINT
# ------------------------------------------------------------
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ------------------------------------------------------------
# SECTION 3: ROUTES
# ------------------------------------------------------------

@admin_bp.route('')
@login_required
@role_required('superadmin')
def overview():
    """
    PURPOSE  : Admin overview — user, ticket, and rate counts
    RECEIVES : None
    RETURNS  : admin_panel.html with stat counts
    SECURITY : superadmin only
    LEGAL    : No PII exposed on overview page
    """
    user_count = User.query.count()
    ticket_count_open = Ticket.query.filter_by(status='open').count()
    rate_count_active = Rate.query.filter_by(effective_to=None).count()
    return render_template(
        'admin_panel.html',
        section='overview',
        user_count=user_count,
        ticket_count_open=ticket_count_open,
        rate_count_active=rate_count_active,
    )


@admin_bp.route('/rates')
@login_required
@role_required('superadmin')
def rates():
    """
    PURPOSE  : Display all rates grouped by mineral for admin review
    RECEIVES : None
    RETURNS  : admin_panel.html with rates list
    SECURITY : superadmin only — rate data is proprietary
    LEGAL    : Historical rates shown read-only to prevent accidental mutation
    """
    all_rates = (
        Rate.query
        .order_by(Rate.mineral_id, Rate.state, Rate.effective_from.desc())
        .all()
    )
    minerals = Mineral.query.order_by(Mineral.name).all()
    return render_template(
        'admin_panel.html',
        section='rates',
        rates=all_rates,
        minerals=minerals,
    )


@admin_bp.route('/rates/update', methods=['POST'])
@login_required
@role_required('superadmin')
def rate_update():
    """
    PURPOSE  : Add a new rate row — NEVER overwrites historical rates
    RECEIVES : mineral_id, state, rate_type, value, unit, notification_number (form)
    RETURNS  : JSON {"status": "Rate updated. Historical record preserved."}
    SECURITY : superadmin only. Input validated before any DB write.
    LEGAL    : Rate update NEVER overwrites — always inserts new row.
               Historical rates must be preserved — past calculations depend on them.
               Wrong rate = rejected application = father's reputation damaged.
    """
    mineral_id          = request.form.get('mineral_id', '').strip()
    state               = request.form.get('state', 'Rajasthan').strip()
    rate_type           = request.form.get('rate_type', '').strip()
    value_str           = request.form.get('value', '').strip()
    unit                = request.form.get('unit', 'per_tonne').strip()
    notification_number = request.form.get('notification_number', '').strip()

    if not all([mineral_id, state, rate_type, value_str]):
        return jsonify({'error': 'mineral_id, state, rate_type, and value are required.'}), 400

    try:
        mineral_id = int(mineral_id)
        value = Decimal(value_str)
        if value <= 0:
            raise ValueError
    except (ValueError, Exception):
        return jsonify({'error': 'value must be a positive number.'}), 400

    # Step 1 — Close the currently active rate (never delete)
    current_rate = Rate.query.filter_by(
        mineral_id=mineral_id,
        state=state,
        rate_type=rate_type,
        effective_to=None,
    ).first()
    if current_rate:
        current_rate.effective_to = date.today()
        db.session.flush()

    # Step 2 — Insert new rate row
    new_rate = Rate(
        mineral_id=mineral_id,
        state=state,
        rate_type=rate_type,
        value=value,
        unit=unit,
        effective_from=date.today(),
        effective_to=None,
        notification_number=notification_number or None,
        verified_by=current_user.id,
    )
    db.session.add(new_rate)
    db.session.commit()

    # Step 3 — Immutable audit trail
    log_audit(
        user_id=current_user.id,
        action='RATE_UPDATED',
        table_affected='Rate',
        record_id=new_rate.id,
        old_value=str(current_rate.value) if current_rate else 'None',
        new_value=value_str,
    )

    return jsonify({'status': 'Rate updated. Historical record preserved.'})


@admin_bp.route('/tickets')
@login_required
@role_required('superadmin')
def tickets():
    """
    PURPOSE  : View all expert consultation tickets
    RECEIVES : None
    RETURNS  : admin_panel.html with tickets list
    SECURITY : superadmin only — user query data is PII
    LEGAL    : SLA compliance — father must respond within 24h
    """
    all_tickets = (
        Ticket.query
        .order_by(Ticket.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        'admin_panel.html',
        section='tickets',
        tickets=all_tickets,
    )


@admin_bp.route('/tickets/<int:ticket_id>/respond', methods=['POST'])
@login_required
@role_required('superadmin')
def ticket_respond(ticket_id):
    """
    PURPOSE  : Mark a ticket as resolved
    RECEIVES : ticket_id (int, URL), response_note (str, form)
    RETURNS  : JSON {"status": "Ticket marked resolved."}
    SECURITY : superadmin only
    LEGAL    : SLA resolution timestamp recorded for audit
    """
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found.'}), 404

    ticket.status = 'resolved'
    ticket.first_response_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        user_id=current_user.id,
        action='TICKET_RESOLVED',
        table_affected='Ticket',
        record_id=ticket_id,
        new_value=request.form.get('response_note', ''),
    )

    return jsonify({'status': 'Ticket marked resolved.'})


@admin_bp.route('/auctions')
@login_required
@role_required('superadmin')
def auctions():
    """
    PURPOSE  : Admin view for auction status — toggle live flag and set banner text
    RECEIVES : None
    RETURNS  : admin_panel.html with auction section and current AuctionStatus
    SECURITY : superadmin only
    LEGAL    : Plain text only — no HTML in status_text; escaped on render
    """
    current_status = get_auction_status()
    return render_template(
        'admin_panel.html',
        section='auctions',
        auction=current_status,
    )


@admin_bp.route('/auctions/update', methods=['POST'])
@login_required
@role_required('superadmin')
def auction_update():
    """
    PURPOSE  : Update auction live status and banner text
    RECEIVES : is_live ('1'/'0'), status_text (str), status_text_hi (str) (form)
    RETURNS  : JSON {"status": "Auction status updated."}
    SECURITY : superadmin only. status_text stored as plain text — no HTML.
    LEGAL    : Every change logged to AuditLog with old→new value.
               No government auction data stored — text is manually set by father.
    """
    is_live = request.form.get('is_live', '0') == '1'
    status_text = request.form.get('status_text', '').strip()[:300] or None
    status_text_hi = request.form.get('status_text_hi', '').strip()[:300] or None

    row = get_auction_status()

    old_value = f"is_live={row.is_live}, status_text={row.status_text!r}"

    row.is_live = is_live
    row.status_text = status_text
    row.status_text_hi = status_text_hi
    row.updated_by = current_user.id
    row.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    new_value = f"is_live={row.is_live}, status_text={row.status_text!r}"

    log_audit(
        user_id=current_user.id,
        action='AUCTION_STATUS_UPDATED',
        table_affected='AuctionStatus',
        record_id=row.id,
        old_value=old_value,
        new_value=new_value,
    )

    return jsonify({'status': 'Auction status updated.'})


@admin_bp.route('/legislation')
@login_required
@role_required('superadmin')
def legislation_list():
    """
    PURPOSE  : List all Legislation entries (published and unpublished) for admin
    RECEIVES : None
    RETURNS  : admin_panel.html with section='legislation'
    SECURITY : superadmin only
    LEGAL    : Unpublished entries are shown here but never on the public page
    """
    entries = (
        Legislation.query
        .order_by(Legislation.category, Legislation.display_order)
        .all()
    )
    return render_template('admin_panel.html', section='legislation', legislation=entries)


def _parse_leg_form():
    """
    PURPOSE  : Coerce Legislation form fields from request.form to column types
    RECEIVES : None — reads current request context
    RETURNS  : (dict, None) on success; (None, error_str) on validation failure
    SECURITY : ORM parameterised queries prevent injection; no raw SQL used
    LEGAL    : last_verified_on is informational — domain expert sets this manually
    """
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    if not title or not category:
        return None, 'title and category are required.'

    date_str = request.form.get('last_verified_on', '').strip()
    last_verified_on = None
    if date_str:
        try:
            last_verified_on = date.fromisoformat(date_str)
        except ValueError:
            return None, 'last_verified_on must be YYYY-MM-DD.'

    try:
        display_order = int(request.form.get('display_order') or 0)
    except ValueError:
        display_order = 0

    return {
        'title':            title,
        'category':         category,
        'summary_en':       request.form.get('summary_en', '').strip() or None,
        'summary_hi':       request.form.get('summary_hi', '').strip() or None,
        'source_reference': request.form.get('source_reference', '').strip() or None,
        'official_url':     request.form.get('official_url', '').strip() or None,
        'last_verified_on': last_verified_on,
        'is_published':     request.form.get('is_published') in ('1', 'on', 'true'),
        'display_order':    display_order,
    }, None


@admin_bp.route('/legislation/create', methods=['POST'])
@login_required
@role_required('superadmin')
def legislation_create():
    """
    PURPOSE  : Create a new Legislation entry
    RECEIVES : form — title, category, summary_en, summary_hi, source_reference,
               official_url, last_verified_on, is_published, display_order
    RETURNS  : JSON {ok, message, id}
    SECURITY : superadmin only. CSRF enforced by Flask-WTF CSRFProtect middleware.
    LEGAL    : is_published defaults False — domain expert controls public visibility
    """
    fields, err = _parse_leg_form()
    if err:
        return jsonify({'ok': False, 'message': err}), 400

    entry = Legislation(**fields)
    db.session.add(entry)
    db.session.commit()

    log_audit(
        user_id=current_user.id,
        action='LEGISLATION_CREATED',
        table_affected='legislation',
        record_id=entry.id,
        new_value=f"title={entry.title!r}, category={entry.category!r}",
    )
    return jsonify({'ok': True, 'message': 'Entry created.', 'id': entry.id})


@admin_bp.route('/legislation/<int:leg_id>/update', methods=['POST'])
@login_required
@role_required('superadmin')
def legislation_update(leg_id):
    """
    PURPOSE  : Update an existing Legislation entry
    RECEIVES : leg_id (URL), same form fields as create
    RETURNS  : JSON {ok, message}
    SECURITY : superadmin only. CSRF enforced. 404 if entry is missing.
    LEGAL    : Every update logged to AuditLog for audit trail
    """
    entry = db.session.get(Legislation, leg_id)
    if not entry:
        return jsonify({'ok': False, 'message': 'Entry not found.'}), 404

    fields, err = _parse_leg_form()
    if err:
        return jsonify({'ok': False, 'message': err}), 400

    old_title = entry.title
    for k, v in fields.items():
        setattr(entry, k, v)
    entry.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        user_id=current_user.id,
        action='LEGISLATION_UPDATED',
        table_affected='legislation',
        record_id=leg_id,
        old_value=f"title={old_title!r}",
        new_value=f"title={entry.title!r}",
    )
    return jsonify({'ok': True, 'message': 'Entry updated.'})


@admin_bp.route('/legislation/<int:leg_id>/delete', methods=['POST'])
@login_required
@role_required('superadmin')
def legislation_delete(leg_id):
    """
    PURPOSE  : Delete a Legislation entry
    RECEIVES : leg_id (URL)
    RETURNS  : JSON {ok, message}
    SECURITY : superadmin only. CSRF enforced by middleware.
    LEGAL    : Deletion logged to AuditLog before the row is removed
    """
    entry = db.session.get(Legislation, leg_id)
    if not entry:
        return jsonify({'ok': False, 'message': 'Entry not found.'}), 404

    log_audit(
        user_id=current_user.id,
        action='LEGISLATION_DELETED',
        table_affected='legislation',
        record_id=leg_id,
        old_value=f"title={entry.title!r}",
    )
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'ok': True, 'message': 'Entry deleted.'})


@admin_bp.route('/legislation/<int:leg_id>/toggle', methods=['POST'])
@login_required
@role_required('superadmin')
def legislation_toggle(leg_id):
    """
    PURPOSE  : Flip is_published on a Legislation entry
    RECEIVES : leg_id (URL)
    RETURNS  : JSON {ok, message, is_published}
    SECURITY : superadmin only. CSRF enforced by middleware.
    LEGAL    : Unpublished entries never appear on the public /legislation page
    """
    entry = db.session.get(Legislation, leg_id)
    if not entry:
        return jsonify({'ok': False, 'message': 'Entry not found.'}), 404

    entry.is_published = not entry.is_published
    entry.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit(
        user_id=current_user.id,
        action='LEGISLATION_TOGGLED',
        table_affected='legislation',
        record_id=leg_id,
        new_value=f"is_published={entry.is_published}",
    )
    label = 'Published.' if entry.is_published else 'Unpublished.'
    return jsonify({'ok': True, 'message': label, 'is_published': entry.is_published})


@admin_bp.route('/news')
@login_required
@role_required('superadmin')
def news():
    """
    PURPOSE  : Admin news management — manual refresh only, no auto-scraping
    RECEIVES : None
    RETURNS  : admin_panel.html with section='news'
    SECURITY : superadmin only
    LEGAL    : Fetch is user-initiated; no scheduled scraping (Q64 posture)
    """
    return render_template('admin_panel.html', section='news')


@admin_bp.route('/news/refresh', methods=['POST'])
@login_required
@role_required('superadmin')
def news_refresh():
    """
    PURPOSE  : Manually trigger the DMG news importer — one page, one fetch, no schedule
    RECEIVES : None (CSRF token only)
    RETURNS  : JSON {"status": "..."} on success, {"error": "..."} on failure
    SECURITY : superadmin only. CSRF enforced by Flask-WTF middleware.
    LEGAL    : User-initiated fetch of a public government page (Q64 posture).
               Every trigger logged to AuditLog with result summary.
    WARNING  : Synchronous network I/O — may block up to ~60 s on retries.
               Gunicorn default timeout is 30 s; a maxed-out retry run will 502.
               Acceptable for a rare manual admin action; configure --timeout 90
               in production if this becomes a problem.
    """
    result = run_news_import()
    log_audit(
        user_id=current_user.id,
        action='NEWS_IMPORT_TRIGGERED',
        table_affected='NewsItem',
        new_value=result['message'],
    )
    if result['status'] == 'ok':
        return jsonify({'status': result['message']})
    return jsonify({'error': result['message']}), 500


@admin_bp.route('/users')
@login_required
@role_required('superadmin')
def users():
    """
    PURPOSE  : View registered users — masked for minimum PII exposure
    RECEIVES : None
    RETURNS  : admin_panel.html with users list
    SECURITY : superadmin only. Full phone numbers never rendered in HTML.
    LEGAL    : DPDP Act 2023 — data minimization. Show last 4 digits only.
    """
    all_users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        'admin_panel.html',
        section='users',
        users=all_users,
    )
