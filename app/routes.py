# ============================================================
# FILE: app/routes.py
# PURPOSE: All page routes for MineralLaw.in
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
import datetime as dt
import os
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user, logout_user

from app.models import AuditLog, Mineral, db
from app.fee_calculator import get_rate_for_date, calculate_royalty, calculate_dmf, get_calculation_disclaimer
from app.helpers import gmail_prefill, log_audit
from app.validators import validate_mineral_query, validate_rate_date
from app.tickets import create_ticket

# ------------------------------------------------------------
# SECTION 2: BLUEPRINT
# ------------------------------------------------------------
main = Blueprint('main', __name__)

# ------------------------------------------------------------
# SECTION 3: PUBLIC ROUTES
# ------------------------------------------------------------
@main.route('/')
def home():
    """
    PURPOSE  : Landing page — compliance assessment form
    RECEIVES : None
    RETURNS  : home.html template
    SECURITY : Public route — no login required
    LEGAL    : Disclaimer shown on every page via base.html
    """
    return render_template('home.html')


@main.route('/login')
def login():
    """
    PURPOSE  : Login page — phone OTP primary
    RECEIVES : None
    RETURNS  : login.html template
    SECURITY : Redirects to dashboard if already logged in
    LEGAL    : DPDP consent banner shown before account creation
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    """
    PURPOSE  : Log out current user and clear session
    RECEIVES : None
    RETURNS  : Redirect to home page
    SECURITY : Clears Flask-Login session cookie
    LEGAL    : None
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.home'))


@main.route('/pricing')
def pricing():
    """
    PURPOSE  : Pricing page — Free / Pro / Expert / Enterprise tiers
    RECEIVES : None
    RETURNS  : pricing.html template
    SECURITY : Public route
    LEGAL    : Prices displayed are in INR inclusive of GST
    """
    return render_template('pricing.html')


# ------------------------------------------------------------
# SECTION 4: PROTECTED ROUTES (login required)
# ------------------------------------------------------------
@main.route('/dashboard')
@login_required
def dashboard():
    """
    PURPOSE  : User dashboard — compliance health, deadlines, quick actions
    RECEIVES : None
    RETURNS  : dashboard.html template
    SECURITY : Login required
    LEGAL    : Shows user's own data only — no cross-user data leak
    """
    recent_activity = AuditLog.query.filter_by(user_id=current_user.id).order_by(AuditLog.id.desc()).limit(5).all()
    return render_template('dashboard.html', user=current_user, recent_activity=recent_activity)


@main.route('/calculator')
@login_required
def calculator():
    """
    PURPOSE  : Fee calculator — royalty, DMF, NPV
    RECEIVES : None
    RETURNS  : calculator.html template with DB-sourced mineral list
    SECURITY : Login required — rate data is proprietary
    LEGAL    : Every output shows disclaimer with rate date and notification number
    """
    minerals = Mineral.query.order_by(Mineral.name).all()
    return render_template('calculator.html', minerals=minerals)


@main.route('/calculator/calculate', methods=['POST'])
@login_required
def calculate():
    """
    PURPOSE  : Run royalty + DMF + NPV calculation and return JSON result
    RECEIVES : POST form — mineral_id, area_ha, production_tpa, lease_years, target_date
    RETURNS  : JSON — full calculation breakdown with disclaimer and audit trail
    SECURITY : Login required. All inputs validated before any DB read.
               area_ha and production caps prevent absurd inputs.
    LEGAL    : AuditLog entry written on every calculation (immutable trail).
               Disclaimer generated from the live Rate object — never hardcoded.
               ⚠️ All rates are PLACEHOLDERS until father verifies in Phase 0.
    """
    try:
        mineral_id = int(request.form.get('mineral_id', 0))
        area_ha    = float(request.form.get('area_ha', 0))
        production = float(request.form.get('production_tpa', 0))
        lease_years = int(request.form.get('lease_years', 5))
        target_date_str = request.form.get('target_date', '')
    except ValueError:
        return jsonify({'error': 'Invalid input. Please enter valid numbers.'}), 400

    if mineral_id <= 0 or area_ha <= 0 or production <= 0:
        return jsonify({'error': 'Mineral, area, and production are required.'}), 400
    if area_ha > 500:
        return jsonify({'error': 'Area exceeds 500 ha. Contact expert.'}), 400
    if production > 10_000_000:
        return jsonify({'error': 'Production exceeds limit. Contact expert.'}), 400

    ok, parsed_date, date_err = validate_rate_date(target_date_str)
    if not ok:
        return jsonify({'error': date_err}), 400
    target_date = parsed_date if parsed_date is not None else dt.date.today()

    royalty_rate = get_rate_for_date(mineral_id, 'Rajasthan', 'royalty', target_date)
    if royalty_rate is None:
        return jsonify({
            'error': 'No rate available for this mineral and date. Contact expert.'
        }), 404

    dmf_rate_row = get_rate_for_date(mineral_id, 'Rajasthan', 'dmf', target_date)

    royalty_annual = calculate_royalty(production, float(royalty_rate.value))

    dmf_warning = None
    if dmf_rate_row:
        dmf_annual = calculate_dmf(royalty_annual, Decimal(str(dmf_rate_row.value)))
    else:
        dmf_annual  = Decimal('0')
        dmf_warning = 'DMF rate unavailable for this date — verify with expert'

    total_annual = royalty_annual + dmf_annual

    # NPV annuity: P × [(1 - (1+r)^-n) / r]
    # ⚠️ PLACEHOLDER — father confirms discount rate
    r = Decimal('0.08')
    n = Decimal(str(lease_years))
    annuity_factor = (1 - (1 + r) ** (-n)) / r
    npv = (total_annual * annuity_factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    disclaimer = get_calculation_disclaimer(royalty_rate)

    mineral = db.session.get(Mineral, mineral_id)

    log_audit(
        user_id=current_user.id,
        action='FEE_CALCULATION',
        table_affected='Rate',
        record_id=royalty_rate.id,
        new_value=(
            f"mineral_id={mineral_id}, production={production}, "
            f"area={area_ha}ha, date={target_date}, royalty={royalty_annual}"
        ),
    )

    return jsonify({
        'mineral':        mineral.name,
        'production_tpa': production,
        'area_ha':        area_ha,
        'target_date':    str(target_date),
        'royalty_annual': str(royalty_annual),
        'dmf_annual':     str(dmf_annual),
        'total_annual':   str(total_annual),
        'npv':            str(npv),
        'lease_years':    lease_years,
        'rate_per_tonne': str(royalty_rate.value),
        'rate_info': {
            'notification':   royalty_rate.notification_number,
            'effective_from': str(royalty_rate.effective_from),
        },
        'disclaimer': disclaimer,
        'warning': '⚠️ All rates are placeholders. Father must verify before sharing with any real client.',
        'dmf_warning': dmf_warning,
    })


@main.route('/checklist')
@login_required
def checklist():
    """
    PURPOSE  : Step-by-step compliance checklist for user's mine type
    RECEIVES : None
    RETURNS  : checklist.html template
    SECURITY : Login required
    LEGAL    : Print stylesheet included — users print for government offices
    """
    return render_template('checklist.html')


@main.route('/ask-expert')
@login_required
def ask_expert():
    """
    PURPOSE  : Expert consultation — opens Gmail pre-fill to father
    RECEIVES : query params — mineral (str), query (str)
    RETURNS  : ask_expert.html template with pre-filled Gmail link
    SECURITY : Login required — father's email never exposed in HTML source
    LEGAL    : Advocates Act 1961 — labelled consultation, not legal advice
    """
    mineral = request.args.get('mineral', '')
    query   = request.args.get('query', '')

    subject = f"MineralLaw Consultation — {mineral}" if mineral else "MineralLaw Consultation"
    body_lines = [
        f"Mineral: {mineral}" if mineral else "",
        f"Query: {query}" if query else "",
        "",
        f"Name: {current_user.name or ''}",
        f"Company: {current_user.company_name or ''}",
        f"Phone: {current_user.phone}",
    ]
    body = "\n".join(line for line in body_lines if line is not None)

    gmail_link = gmail_prefill(
        to=os.environ.get('FATHER_EMAIL', ''),
        subject=subject,
        body=body,
    )

    return render_template(
        'ask_expert.html',
        gmail_link=gmail_link,
        mineral=mineral,
        query=query,
    )


@main.route('/ask-expert/submit', methods=['POST'])
@login_required
def ask_expert_submit():
    """
    PURPOSE  : Record a consultation request as a Ticket for the expert queue
    RECEIVES : POST form — mineral (str), query (str)
    RETURNS  : JSON {"status": ...} or {"error": ...}
    SECURITY : login_required. Input validated before DB write.
    LEGAL    : Creates audit-logged Ticket. SLA timer (Celery) tracks response.
    """
    mineral = request.form.get('mineral', '').strip()
    query   = request.form.get('query', '').strip()

    is_valid, error = validate_mineral_query(mineral, query)
    if not is_valid:
        return jsonify({'error': error}), 400

    subject = f"Mining Query — {mineral or 'General'}"
    create_ticket(
        user_id=current_user.id,
        subject=subject,
        description=query,
        mineral_type=mineral or None,
    )

    return jsonify({
        'status': 'Your query has been logged. Expert will respond within 24 hours.'
    })