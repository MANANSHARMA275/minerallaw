# ============================================================
# FILE: app/logger.py
# PURPOSE: Application logger with automatic PII masking (DPDP Act 2023)
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
import re
import logging
import os
from logging.handlers import RotatingFileHandler

# ------------------------------------------------------------
# SECTION 2: PII MASKING (REPLACE 3 from master reference)
# ------------------------------------------------------------
def mask_pii(message: str) -> str:
    """
    PURPOSE  : Auto-mask phone numbers and emails before any log write
    RECEIVES : message (str) — raw log message
    RETURNS  : str — masked message safe for log files
    SECURITY : Word boundaries prevent matching Aadhaar (12 digits) or PAN (10 chars)
    LEGAL    : DPDP Act 2023 — PII must not appear in unprotected log files
    """
    def mask_phone(match):
        prefix = match.group('prefix') or ''
        last4 = match.group('last4')
        if prefix and ('91' in prefix or '+' in prefix):
            return f"+91-XXXXXX{last4}"
        return f"XXXXXX{last4}"

    # Mask Indian phone numbers — word boundaries prevent Aadhaar/PAN false matches
    message = re.sub(
        r'\b(?P<prefix>\+?91[\s.-]*)?(?P<first6>\d{6})(?P<last4>\d{4})\b',
        mask_phone,
        str(message)
    )

    # Mask email addresses
    message = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        '***@***.com',
        message
    )
    return message


# ------------------------------------------------------------
# SECTION 3: CUSTOM FORMATTER
# ------------------------------------------------------------
class PIIMaskingFormatter(logging.Formatter):
    """
    PURPOSE  : Apply PII masking to every log record before writing to disk
    SECURITY : Ensures no phone/email leaks into log files ever
    LEGAL    : DPDP Act 2023 compliance — all handlers use this formatter
    """
    def format(self, record: logging.LogRecord) -> str:
        record.msg = mask_pii(str(record.msg))
        return super().format(record)


# ------------------------------------------------------------
# SECTION 4: LOGGER FACTORY
# ------------------------------------------------------------
def get_logger(name: str = 'minerallaw') -> logging.Logger:
    """
    PURPOSE  : Create or retrieve the application logger with PII masking
    RECEIVES : name (str) — logger namespace
    RETURNS  : logging.Logger — configured with console + rotating file handlers
    SECURITY : RotatingFileHandler prevents disk exhaustion (10MB × 5 backups)
    LEGAL    : /logs/ directory must be in .gitignore — never commit log files
    """
    log = logging.getLogger(name)

    if log.handlers:
        return log  # Already configured — avoid duplicate handlers on hot reload

    log.setLevel(logging.INFO)

    formatter = PIIMaskingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler — visible in Railway logs and local terminal
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    log.addHandler(console)

    # Rotating file handler — 10MB max, keep 5 backup files
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler(
        'logs/minerallaw.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    return log


# Module-level instance — import this everywhere: from app.logger import logger
logger = get_logger()