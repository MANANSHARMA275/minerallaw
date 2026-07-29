"""
Tests for Chunk B2: all in-scope public pages return HTTP 200
and zero literal colour utilities remain in converted templates.
"""
import re
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LITERAL_COLOUR_RE = re.compile(
    r'(?:bg|text|border|hover:bg|hover:text|hover:border)'
    r'-(?:slate|amber|red|blue|green|orange)-\d+'
    r'|(?:bg|text|border|hover:bg|hover:text|hover:border)-(?:white|black)\b'
)

CONVERTED_TEMPLATES = [
    'templates/legislation.html',
    'templates/news.html',
    'templates/pricing.html',
    'templates/calculator.html',
    'templates/checklist.html',
    'templates/auctions.html',
    'templates/login.html',
    'templates/ask_expert.html',
    'templates/dashboard.html',
    'templates/admin_panel.html',
    'templates/admin_deliveries.html',
    'templates/compliance_calendar.html',
    'templates/errors/403.html',
    'templates/errors/429.html',
]


class TestB2PublicPages:

    def test_legislation_page_loads(self, client):
        assert client.get('/legislation').status_code == 200

    def test_news_page_loads(self, client):
        assert client.get('/news').status_code == 200

    def test_pricing_page_loads(self, client):
        assert client.get('/pricing').status_code == 200

    def test_calculator_page_loads(self, client):
        assert client.get('/calculator').status_code in (200, 302)

    def test_checklist_page_loads(self, client):
        assert client.get('/checklist').status_code in (200, 302)

    def test_auctions_page_loads(self, client):
        assert client.get('/auctions').status_code == 200

    def test_login_page_loads(self, client):
        assert client.get('/login').status_code == 200

    def test_ask_expert_page_loads(self, client):
        assert client.get('/ask-expert').status_code in (200, 302)

    def test_compliance_calendar_page_loads(self, client):
        assert client.get('/compliance').status_code in (200, 302)


class TestB2NoLiteralColours:
    """Grep gate: zero literal Tailwind colour utilities across all converted templates."""

    def test_no_literal_colours_remain(self):
        """All converted templates must use only semantic tokens — no literal colour utilities."""
        violations = []
        for rel_path in CONVERTED_TEMPLATES:
            full_path = os.path.join(BASE_DIR, rel_path)
            with open(full_path) as f:
                content = f.read()
            found = LITERAL_COLOUR_RE.findall(content)
            if found:
                violations.append(f"{rel_path}: {sorted(set(found))}")
        assert not violations, (
            "Literal colour utilities remain in converted templates:\n"
            + "\n".join(violations)
        )


class TestB2NoEmoji:
    """Grep gate: zero emoji codepoints across every template — scans all of
    templates/ recursively (a superset of CONVERTED_TEMPLATES plus base.html,
    since home.html's partials carry emoji too and aren't in that list)."""

    EMOJI_RE = re.compile(
        '[\U0001F300-\U0001FAFF\U00002300-\U000023FF\U00002600-\U000027BF\U0000FE0F]'
    )

    def test_no_emoji_remain_in_any_template(self):
        violations = []
        templates_dir = os.path.join(BASE_DIR, 'templates')
        for root, _, files in os.walk(templates_dir):
            for fname in files:
                if not fname.endswith('.html'):
                    continue
                full_path = os.path.join(root, fname)
                with open(full_path, encoding='utf-8') as f:
                    content = f.read()
                found = self.EMOJI_RE.findall(content)
                if found:
                    rel = os.path.relpath(full_path, BASE_DIR)
                    violations.append(f"{rel}: {sorted(set(found))}")
        assert not violations, (
            "Emoji codepoints remain in templates:\n" + "\n".join(violations)
        )
