# ============================================================
# FILE: app/validators.py
# PURPOSE: Input validation helpers — phone, text, mineral queries
# LAST UPDATED: Phase 1
# ============================================================

import re


def validate_phone(phone: str) -> tuple:
    """
    PURPOSE  : Normalise and validate an Indian mobile number
    RECEIVES : phone (str) — raw input from user
    RETURNS  : tuple[bool, str] — (True, '+91XXXXXXXXXX') or (False, error_msg)
    SECURITY : Strips spaces and dashes before checking; rejects non-numeric junk
    LEGAL    : Phone is PII — caller must not log the returned value
    """
    if not phone:
        return False, 'Phone number is required.'

    cleaned = re.sub(r'[\s\-]', '', phone.strip())

    # Accept +91XXXXXXXXXX
    if re.fullmatch(r'\+91[6-9]\d{9}', cleaned):
        return True, cleaned

    # Accept 91XXXXXXXXXX
    if re.fullmatch(r'91[6-9]\d{9}', cleaned):
        return True, '+' + cleaned

    # Accept bare 10-digit number starting with 6-9
    if re.fullmatch(r'[6-9]\d{9}', cleaned):
        return True, '+91' + cleaned

    return False, 'Enter a valid 10-digit Indian mobile number.'


def validate_text(text: str, max_len: int = 2000) -> tuple:
    """
    PURPOSE  : Sanitise a plain-text input field
    RECEIVES : text (str) — raw user input; max_len (int) — character limit
    RETURNS  : tuple[bool, str] — (True, cleaned_text) or (False, error_msg)
    SECURITY : Strips null bytes that could corrupt DB text columns
    LEGAL    : Does not modify content beyond whitespace and null-byte removal
    """
    if not text:
        return False, 'This field is required.'

    cleaned = text.strip().replace('\x00', '')

    if not cleaned:
        return False, 'This field must not be blank.'

    if len(cleaned) > max_len:
        return False, f'Must be {max_len} characters or fewer (got {len(cleaned)}).'

    return True, cleaned


def validate_mineral_query(mineral: str, query: str) -> tuple:
    """
    PURPOSE  : Validate the Ask-Expert form inputs before ticket creation
    RECEIVES : mineral (str) — optional mineral/mine type, max 100 chars;
               query (str) — required consultation question, 10–2000 chars
    RETURNS  : tuple[bool, str] — (True, '') if valid, (False, reason) if not
    SECURITY : Guards against empty submissions and oversized payloads
    LEGAL    : Ensures every ticket has enough context for the expert to respond
    """
    if mineral and len(mineral.strip()) > 100:
        return False, 'Mineral / mine type must be 100 characters or fewer.'

    if not query or not query.strip():
        return False, 'Please describe your question before submitting.'

    stripped = query.strip()

    if len(stripped) < 10:
        return False, 'Please provide more detail — at least 10 characters.'

    if len(stripped) > 2000:
        return False, 'Query must be 2000 characters or fewer.'

    return True, ''
