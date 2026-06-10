"""
Tests for app/helpers.py — gmail_prefill and format_inr.
DO NOT test log_audit here; it requires DB context (see integration tests).
"""
import pytest
from urllib.parse import urlparse, parse_qs

from app.helpers import gmail_prefill, format_inr


# ── gmail_prefill ──────────────────────────────────────────────────────────────

class TestGmailPrefill:

    def test_returns_gmail_compose_url(self):
        url = gmail_prefill("to@example.com", "Hello", "Body text")
        assert url.startswith("https://mail.google.com/mail/")

    def test_to_param_encoded(self):
        url = gmail_prefill("expert@minerallaw.in", "Subject", "Body")
        qs = parse_qs(urlparse(url).query)
        assert qs["to"] == ["expert@minerallaw.in"]

    def test_subject_and_body_encoded(self):
        url = gmail_prefill("a@b.com", "Royalty Query", "Please advise on DMF rates")
        qs = parse_qs(urlparse(url).query)
        assert qs["su"] == ["Royalty Query"]
        assert qs["body"] == ["Please advise on DMF rates"]

    def test_special_characters_encoded(self):
        url = gmail_prefill("a@b.com", "Q&A: rates", "₹10 lakh & NPV")
        assert "Q%26A" in url or "Q&A" not in url.split("?")[0]
        parsed = parse_qs(urlparse(url).query)
        assert "₹10 lakh & NPV" in parsed.get("body", [""])[0]


# ── format_inr ─────────────────────────────────────────────────────────────────

class TestFormatInr:

    def test_small_number_no_commas(self):
        assert format_inr(500) == "₹500"

    def test_thousands_with_indian_grouping(self):
        assert format_inr(4500000) == "₹45,00,000"

    def test_exact_lakh(self):
        assert format_inr(100000) == "₹1,00,000"

    def test_crore(self):
        assert format_inr(10000000) == "₹1,00,00,000"

    def test_decimal_truncated(self):
        assert format_inr(4500000.75) == "₹45,00,000"

    def test_string_input(self):
        assert format_inr("999") == "₹999"

    def test_invalid_returns_zero(self):
        assert format_inr(None) == "₹0"
        assert format_inr("abc") == "₹0"
