# ============================================================
# FILE: app/routes.py
# PURPOSE: All page routes for MineralLaw.in
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user

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
    return render_template('dashboard.html', user=current_user)


@main.route('/calculator')
@login_required
def calculator():
    """
    PURPOSE  : Fee calculator — royalty, DMF, NPV
    RECEIVES : None
    RETURNS  : calculator.html template
    SECURITY : Login required — rate data is proprietary
    LEGAL    : Every output shows disclaimer with rate date and notification number
    """
    return render_template('calculator.html')


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
    RECEIVES : None
    RETURNS  : ask_expert.html template
    SECURITY : Login required — father's email never exposed in HTML source
    LEGAL    : Advocates Act 1961 — labelled consultation, not legal advice
    """
    return render_template('ask_expert.html')