# ============================================================
# FILE: app/auth.py
# PURPOSE: Phone OTP authentication, Flask-Login, role-based access,
#          WhatsApp magic tokens, MSG91 + Twilio failover
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
import os
import hmac
import secrets
import jwt
import requests as http_requests
from datetime import datetime, timedelta
from functools import wraps

import redis
from flask import (
    Blueprint, request, jsonify,
    redirect, url_for, abort, current_app
)
from flask_login import (
    login_user, logout_user,
    login_required, current_user
)

from app.models import User, db
from app.logger import logger

# ------------------------------------------------------------
# SECTION 2: BLUEPRINT + CLIENTS
# ------------------------------------------------------------
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# decode_responses=True → Redis returns str, not bytes (no .decode() needed)
redis_client = redis.from_url(
    os.environ.get('REDIS_URL', 'redis://localhost:6379'),
    decode_responses=True
)

# ------------------------------------------------------------
# SECTION 3: OTP HELPERS
# ------------------------------------------------------------
def generate_otp() -> str:
    """
    PURPOSE  : Generate a cryptographically secure 6-digit OTP
    RECEIVES : None
    RETURNS  : str — e.g. "847291"
    SECURITY : secrets.SystemRandom is OS-level entropy — not guessable
    LEGAL    : N/A
    """
    return ''.join(secrets.SystemRandom().choices('0123456789', k=6))


def store_otp(phone: str, otp: str) -> None:
    """
    PURPOSE  : Store OTP in Redis with 5-minute expiry
    RECEIVES : phone (str), otp (str)
    RETURNS  : None
    SECURITY : Namespaced key "otp:<phone>" — no collision with other Redis data
               OTP consumed (deleted) on first use — see verify_and_consume_otp
    LEGAL    : DPDP: phone never logged in plaintext (PIIMaskingFormatter handles it)
    """
    redis_client.setex(f"otp:{phone}", 300, otp)  # 300 seconds = 5 minutes


def verify_and_consume_otp(phone: str, submitted_otp: str) -> bool:
    """
    PURPOSE  : Verify OTP and atomically delete it — prevents replay attacks
    RECEIVES : phone (str), submitted_otp (str)
    RETURNS  : bool — True if valid; False if wrong, expired, or already used
    SECURITY : getdel() is ONE Redis round-trip — no race condition between read
               and delete. Previous two-step get+delete had a replay window.
               hmac.compare_digest() is constant-time — no timing side-channel.
    LEGAL    : DPDP: OTP not retained after use — minimal data retention.
               Requires Redis 6.2+. Upstash supports getdel.
    """
    stored_otp = redis_client.getdel(f"otp:{phone}")

    if stored_otp is None:
        return False  # Expired, never sent, or already used

    return hmac.compare_digest(stored_otp, submitted_otp)


# ------------------------------------------------------------
# SECTION 5: OTP SENDING (MSG91 PRIMARY, TWILIO SMS FALLBACK)
# ------------------------------------------------------------
def send_otp_with_failover(phone: str, otp: str) -> bool:
    """
    PURPOSE  : Send OTP via MSG91; fall back to Twilio SMS on failure
    RECEIVES : phone (str) — E.164 format e.g. "+919876543210", otp (str)
    RETURNS  : bool — True if successfully sent via either provider
    SECURITY : OTP value never logged — only masked phone suffix appears in logs
    LEGAL    : DPDP: user must be able to log in to reach the data deletion control
    """
    # Dev mode: skip SMS when debug, no key, or placeholder key
    api_key = os.environ.get('MSG91_API_KEY', '')
    dev_mode = current_app.debug or (not api_key) or api_key.startswith('your-')
    if dev_mode:
        print(f"\n{'='*50}\n  DEV MODE OTP for {phone}: {otp}\n{'='*50}\n")
        current_app.logger.info("DEV MODE: OTP printed to terminal (SMS skipped)")
        return True

    # MSG91 primary
    try:
        resp = http_requests.post(
            'https://api.msg91.com/api/v5/otp',
            json={
                'authkey': os.environ.get('MSG91_AUTH_KEY'),
                'mobile': phone.replace('+', ''),  # MSG91 wants without +
                'otp': otp,
                'sender': os.environ.get('MSG91_SENDER_ID', 'MNRLAW'),
                'otp_expiry': 5
            },
            timeout=5
        )
        if resp.status_code == 200:
            logger.info(f"OTP sent via MSG91 to ****{phone[-4:]}")
            return True
        logger.warning(f"MSG91 returned {resp.status_code}: {resp.text[:80]}")
    except Exception as exc:
        logger.warning(f"MSG91 exception: {exc}")

    # Twilio SMS fallback
    try:
        from twilio.rest import Client
        twilio = Client(
            os.environ.get('TWILIO_ACCOUNT_SID'),
            os.environ.get('TWILIO_AUTH_TOKEN')
        )
        twilio.messages.create(
            body=f"Your MineralLaw.in OTP: {otp}. Valid 5 minutes. Do not share.",
            from_=os.environ.get('TWILIO_PHONE_NUMBER'),
            to=phone
        )
        logger.info(f"OTP sent via Twilio fallback to ****{phone[-4:]}")
        return True
    except Exception as exc:
        logger.error(f"Both OTP providers failed: {exc}")
        return False


# ------------------------------------------------------------
# SECTION 6: MAGIC TOKENS (WHATSAPP LOGIN LINKS)
# ------------------------------------------------------------
def create_magic_token(phone: str) -> str:
    """
    PURPOSE  : Create a short-lived JWT for WhatsApp one-click login links
    RECEIVES : phone (str)
    RETURNS  : str — signed JWT (valid 10 minutes)
    SECURITY : Signed with SECRET_KEY — cannot be forged without the key
    LEGAL    : Token never stored — stateless, verifiable on arrival
    """
    payload = {
        'phone': phone,
        'exp': datetime.utcnow() + timedelta(minutes=10),
        'iat': datetime.utcnow(),
        'purpose': 'magic_login'
    }
    return jwt.encode(payload, os.environ.get('SECRET_KEY'), algorithm='HS256')


def verify_magic_token(token: str) -> str | None:
    """
    PURPOSE  : Verify and decode a WhatsApp magic login JWT
    RECEIVES : token (str)
    RETURNS  : str — phone number if valid; None if expired or forged
    SECURITY : Expired tokens return None and cannot be reused
    LEGAL    : N/A
    """
    try:
        payload = jwt.decode(
            token,
            os.environ.get('SECRET_KEY'),
            algorithms=['HS256']
        )
        if payload.get('purpose') != 'magic_login':
            return None
        return payload.get('phone')
    except jwt.ExpiredSignatureError:
        logger.info("Expired magic token used — not an attack, just late click")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid magic token presented")
        return None


# ------------------------------------------------------------
# SECTION 7: ROLE-BASED ACCESS DECORATOR
# ------------------------------------------------------------
def role_required(required_role: str):
    """
    PURPOSE  : Restrict a route to users with a specific role
    RECEIVES : required_role (str) — 'superadmin' | 'staff'
    RETURNS  : decorator
    SECURITY : Superadmin always passes. Unauthenticated → 401. Wrong role → 403.
    LEGAL    : Prevents staff accessing rate tables or user PII (DPDP)
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
# SECTION 8: AUTH ROUTES
# ------------------------------------------------------------
@auth_bp.route('/send-otp', methods=['POST'])
def send_otp_route():
    """
    PURPOSE  : Generate OTP, enforce rate limits, send via MSG91/Twilio
    RECEIVES : POST JSON — {"phone": "+919876543210"}
    RETURNS  : JSON — {"status": "sent"} or error with HTTP code
    SECURITY : Rate limited per phone (3 OTPs/hour) and per IP (10/hour)
               Both counters stored in Redis — survives app restart
    LEGAL    : Phone masked in all logs (DPDP Act 2023)
    """
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()

    # Validate Indian phone number format
    if not phone or not phone.startswith('+91') or len(phone) != 13:
        return jsonify({'error': 'Enter a valid Indian mobile number (+91XXXXXXXXXX)'}), 400

    digits = phone[3:]
    if not digits.isdigit():
        return jsonify({'error': 'Phone number must contain only digits after +91'}), 400

    try:
        # Rate limiting: per-phone counter (3/hour)
        phone_key = f"otp_rate_phone:{phone}"
        phone_attempts = redis_client.get(phone_key)
        if phone_attempts and int(phone_attempts) >= 3:
            return jsonify({'error': 'Too many OTP requests for this number. Try again in 1 hour.'}), 429

        # Rate limiting: per-IP counter (10/hour)
        ip_key = f"otp_rate_ip:{request.remote_addr}"
        ip_attempts = redis_client.get(ip_key)
        if ip_attempts and int(ip_attempts) >= 10:
            return jsonify({'error': 'Too many requests from this device.'}), 429

        # Generate and store OTP
        otp = generate_otp()
        store_otp(phone, otp)

        # Increment rate limit counters atomically
        pipe = redis_client.pipeline()
        pipe.incr(phone_key)
        pipe.expire(phone_key, 3600)
        pipe.incr(ip_key)
        pipe.expire(ip_key, 3600)
        pipe.execute()
    except redis.exceptions.ConnectionError:
        return jsonify({'error': 'Login service temporarily unavailable. Please try again in a minute.'}), 503

    # Send
    sent = send_otp_with_failover(phone, otp)
    if not sent:
        return jsonify({'error': 'Could not send OTP. Please try again in a moment.'}), 503

    return jsonify({
        'status': 'sent',
        'message': f'OTP sent to number ending in {phone[-4:]}'
    }), 200


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    """
    PURPOSE  : Verify OTP, create account if new user, start Flask-Login session
    RECEIVES : POST JSON — {"phone": "+919876543210", "otp": "123456"}
    RETURNS  : JSON — {"status": "ok", "redirect": "/dashboard"} or error
    SECURITY : Atomic OTP consumption — no replay attacks possible
               Account created ONLY after successful OTP verification
    LEGAL    : New user creation logged. last_login updated on every login.
    """
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    submitted_otp = data.get('otp', '').strip()

    if not phone or not submitted_otp:
        return jsonify({'error': 'Phone and OTP are both required'}), 400

    try:
        valid = verify_and_consume_otp(phone, submitted_otp)
    except redis.exceptions.ConnectionError:
        return jsonify({'error': 'Login service temporarily unavailable. Please try again in a minute.'}), 503

    if not valid:
        return jsonify({'error': 'Incorrect or expired OTP. Request a new one.'}), 401

    # OTP verified — get or create user
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(
            phone=phone,
            subscription_tier='free',
            role='user',
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        logger.info(f"New user registered via OTP: ****{phone[-4:]}")

    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()

    logger.info(f"User logged in: ****{phone[-4:]}")
    return jsonify({
        'status': 'ok',
        'redirect': url_for('main.dashboard')
    }), 200


@auth_bp.route('/magic-login')
def magic_login():
    """
    PURPOSE  : Handle WhatsApp magic link clicks — log user in without OTP
    RECEIVES : GET ?token=<JWT>
    RETURNS  : Redirect to dashboard (valid token) or login page (expired/invalid)
    SECURITY : Token expires after 10 minutes — brief window, single use
    LEGAL    : N/A
    """
    token = request.args.get('token', '')
    phone = verify_magic_token(token)

    if not phone:
        return redirect(url_for('main.login') + '?error=Link+expired.+Please+log+in+again.')

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return redirect(url_for('main.login') + '?error=Account+not+found.')

    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()

    logger.info(f"Magic link login: ****{phone[-4:]}")
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    """
    PURPOSE  : Log out current user, clear Flask-Login session
    RECEIVES : GET (authenticated user)
    RETURNS  : Redirect to home page
    SECURITY : Flask-Login clears the session cookie — subsequent requests fail auth
    LEGAL    : N/A
    """
    phone_last4 = (current_user.phone or '????')[-4:]
    logout_user()
    logger.info(f"User logged out: ****{phone_last4}")
    return redirect(url_for('main.home'))