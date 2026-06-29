"""
Tests for app/news_importer.py:
  - parse_news_html: correct row count, field values, document lists.
  - URL encoding: spaces → %20, no double-encoding.
  - categorize: each heading maps to the expected category.
  - import_news_items: dedup (intra-batch and across runs), is_published flag.
  - run_news_import: fetch-failure resilience, missing-table resilience.

NO test touches the live network; fetch_news_html is patched wherever called.
"""
import datetime
import importlib
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from app import db
from app.models import NewsDocument, NewsItem
from app.news_importer import (
    categorize,
    import_news_items,
    parse_news_html,
    run_news_import,
)

# ── Fixture HTML loaded once at module import ─────────────────────────────────

_FIXTURE_PATH = Path(__file__).parent.parent / 'fixtures' / 'dmg_news_sample.html'
_FIXTURE_HTML = _FIXTURE_PATH.read_text(encoding='utf-8')

_SOURCE_URL = 'https://mines.rajasthan.gov.in/dmgcms/test'

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parsed():
    """Return a fresh parse of the fixture HTML."""
    return parse_news_html(_FIXTURE_HTML, _SOURCE_URL)


def _seed_one_item(app):
    """Insert a single NewsItem directly into the DB; return it."""
    item = NewsItem(
        heading='Pre-existing Item',
        order_date=datetime.date(2025, 1, 1),
        source_url=_SOURCE_URL,
        dedup_hash=NewsItem.compute_dedup_hash('Pre-existing Item', datetime.date(2025, 1, 1)),
        fetched_at=datetime.datetime(2025, 1, 1, 0, 0, 0),
    )
    db.session.add(item)
    db.session.commit()
    return item


# ── Test 1: parse returns 6 row-dicts ─────────────────────────────────────────

class TestParseNewsHtml:

    def test_parse_returns_six_rows(self):
        rows = _parsed()
        assert len(rows) == 6

    def test_first_row_heading_and_date(self):
        rows = _parsed()
        assert rows[0]['heading'] == (
            'Documents related to auction of 5 limestone blocks NIB dated 30-04-2026'
        )
        assert rows[0]['order_date'] == datetime.date(2026, 4, 30)

    def test_first_row_has_two_documents(self):
        rows = _parsed()
        assert len(rows[0]['documents']) == 2

    def test_second_row_heading_and_date(self):
        rows = _parsed()
        assert 'Rigman' in rows[1]['heading']
        assert rows[1]['order_date'] == datetime.date(2026, 5, 4)

    def test_rows_five_and_six_are_identical_heading_date(self):
        rows = _parsed()
        assert rows[4]['heading'] == rows[5]['heading']
        assert rows[4]['order_date'] == rows[5]['order_date']


# ── Test 2: PDF URLs have spaces encoded ──────────────────────────────────────

class TestUrlEncoding:

    def test_first_row_first_url_has_percent20(self):
        rows = _parsed()
        first_url = rows[0]['documents'][0]['url']
        assert '%20' in first_url

    def test_first_row_first_url_has_no_raw_space(self):
        rows = _parsed()
        first_url = rows[0]['documents'][0]['url']
        assert ' ' not in first_url

    def test_second_row_url_encoded(self):
        rows = _parsed()
        url = rows[1]['documents'][0]['url']
        assert '%20' in url
        assert ' ' not in url

    def test_corrigendum_url_preserves_parens(self):
        rows = _parsed()
        # Row 5 (index 4) has "(07)2026" in filename — parens must NOT be encoded
        url = rows[4]['documents'][0]['url']
        assert '(' in url
        assert ')' in url
        assert '%28' not in url  # ( not encoded
        assert '%29' not in url  # ) not encoded

    def test_no_double_encoding(self):
        rows = _parsed()
        # %20 must not become %2520
        for row in rows:
            for doc in row['documents']:
                assert '%2520' not in doc['url']


# ── Test 3: categorize ────────────────────────────────────────────────────────

class TestCategorize:

    def test_limestone_nib_is_auction(self):
        assert categorize(
            'Documents related to auction of 5 limestone blocks NIB dated 30-04-2026'
        ) == 'auction'

    def test_rigman_seniority_is_staff(self):
        assert categorize('Provisional Seniority List date 01-04-2026 - Rigman') == 'staff'

    def test_etender_is_tender(self):
        assert categorize('E-Tender Notice Part-1') == 'tender'

    def test_bajri_auction_is_auction(self):
        # "auction" keyword beats "bajri" (mineral) and "notice"
        assert categorize('Notice-Bajri Auction') == 'auction'

    def test_corrigendum_is_notice(self):
        assert categorize('Corrigendum 01 of Ercc-rcc (07)2026') == 'notice'

    def test_unknown_heading_is_other(self):
        assert categorize('General administrative circular 2026') == 'other'

    # ── Hindi / bilingual headings ─────────────────────────────────────────────

    def test_hindi_auction_notice_is_auction(self):
        # नीलामी (auction) is checked before सूचना (notice) — must win
        assert categorize('नीलामी सूचना') == 'auction'

    def test_hindi_auction_notice_with_number_is_auction(self):
        assert categorize('नीलामी सूचना- 02/2026') == 'auction'

    def test_hindi_notification_with_rules_is_notice(self):
        # अधिसूचना contains सूचना as substring; no higher-priority keyword present
        assert categorize(
            'राजस्थान डीएमएफटी नियम, 2025 दिनांक 12.06.2025 अधिसूचना'
        ) == 'notice'

    def test_hindi_tender_notice_is_tender(self):
        # निविदा (tender) beats सूचना (notice) in priority order
        assert categorize('निविदा सूचना') == 'tender'

    # ── HR leaks fixed ─────────────────────────────────────────────────────────

    def test_counselling_order_is_staff(self):
        assert categorize('Counselling Order- Surveyor & Mines Foreman II') == 'staff'

    def test_waiting_list_is_staff(self):
        assert categorize('Document Verification for MF-II Waiting List') == 'staff'

    # ── English notice keywords ────────────────────────────────────────────────

    def test_rules_amendment_is_notice(self):
        assert categorize('RSMET Rules 2020 and Amendment Rule 2022') == 'notice'


# ── Test 4: import creates 5 items (rows 5+6 dedup to 1) ─────────────────────

class TestImportNewsItems:

    def test_import_creates_five_items(self, app):
        import_news_items(_parsed())
        assert NewsItem.query.count() == 5

    def test_rigman_item_is_not_published(self, app):
        import_news_items(_parsed())
        item = NewsItem.query.filter(NewsItem.heading.contains('Rigman')).first()
        assert item is not None
        assert item.is_published is False

    def test_auction_item_is_published(self, app):
        import_news_items(_parsed())
        item = NewsItem.query.filter(NewsItem.heading.contains('limestone')).first()
        assert item is not None
        assert item.is_published is True

    def test_corrigendum_item_is_published(self, app):
        import_news_items(_parsed())
        item = NewsItem.query.filter(NewsItem.heading.contains('Corrigendum')).first()
        assert item is not None
        assert item.is_published is True

    def test_intra_batch_duplicate_counted_as_skipped(self, app):
        result = import_news_items(_parsed())
        # 6 rows, 1 intra-batch dupe (rows 5&6) → 5 new, 1 skipped
        assert result['new'] == 5
        assert result['skipped'] == 1


# ── Test 5: second import is idempotent ───────────────────────────────────────

class TestImportIdempotent:

    def test_second_run_returns_zero_new(self, app):
        import_news_items(_parsed())
        result = import_news_items(_parsed())
        assert result['new'] == 0

    def test_second_run_total_count_stays_five(self, app):
        import_news_items(_parsed())
        import_news_items(_parsed())
        assert NewsItem.query.count() == 5


# ── Test 6: row 1 produces exactly 2 NewsDocument rows ───────────────────────

class TestNewsDocuments:

    def test_row1_produces_two_documents(self, app):
        import_news_items(_parsed())
        item = NewsItem.query.filter(NewsItem.heading.contains('limestone')).first()
        assert item is not None
        assert len(item.documents) == 2

    def test_document_urls_are_encoded(self, app):
        import_news_items(_parsed())
        item = NewsItem.query.filter(NewsItem.heading.contains('limestone')).first()
        for doc in item.documents:
            assert ' ' not in doc.url
            assert '%20' in doc.url
            assert doc.url.startswith('https://')


# ── Test 7: fetch failure — seeded item survives ──────────────────────────────

class TestFetchFailureResilience:

    def test_fetch_timeout_returns_error_status(self, app):
        _seed_one_item(app)
        with patch(
            'app.news_importer.fetch_news_html',
            side_effect=requests.exceptions.Timeout('timed out'),
        ):
            result = run_news_import()
        assert result['status'] == 'error'

    def test_fetch_timeout_does_not_raise(self, app):
        _seed_one_item(app)
        with patch(
            'app.news_importer.fetch_news_html',
            side_effect=requests.exceptions.Timeout('timed out'),
        ):
            try:
                run_news_import()
            except Exception as exc:
                pytest.fail(f'run_news_import raised unexpectedly: {exc}')

    def test_fetch_timeout_leaves_existing_item_intact(self, app):
        _seed_one_item(app)
        with patch(
            'app.news_importer.fetch_news_html',
            side_effect=requests.exceptions.Timeout('timed out'),
        ):
            run_news_import()
        assert NewsItem.query.count() == 1


# ── Test 8: missing table — returns error, inserts nothing ───────────────────

class TestMissingTableResilience:

    def test_missing_table_returns_error_status(self, app):
        with patch(
            'app.news_importer.fetch_news_html',
            return_value='<html><body><p>no table</p></body></html>',
        ):
            result = run_news_import()
        assert result['status'] == 'error'

    def test_missing_table_inserts_nothing(self, app):
        with patch(
            'app.news_importer.fetch_news_html',
            return_value='<html><body><p>no table</p></body></html>',
        ):
            run_news_import()
        assert NewsItem.query.count() == 0


# ── Test 9: absolute URL resolution ──────────────────────────────────────────

_REL_SOURCE = 'https://mines.rajasthan.gov.in/dmgcms/page?menuName=test'
_GOV_ORIGIN = 'https://mines.rajasthan.gov.in'


class TestAbsoluteUrlResolution:
    """parse_news_html must always store absolute government URLs, never relative paths."""

    _REL_HTML = '''<table>
        <tr><th>Sr. No.</th><th>News Heading</th><th>News Content</th><th>Order Date</th></tr>
        <tr><td>1</td><td>Test Notice</td>
            <td><a href="/dmgcms/link_to_external_file/test file.pdf">test file.pdf</a></td>
            <td>2026-01-01</td></tr>
    </table>'''

    _ABS_HTML = '''<table>
        <tr><th>Sr. No.</th><th>News Heading</th><th>News Content</th><th>Order Date</th></tr>
        <tr><td>1</td><td>Test Notice</td>
            <td><a href="https://mines.rajasthan.gov.in/dmgcms/link_to_external_file/abs.pdf">abs.pdf</a></td>
            <td>2026-01-01</td></tr>
    </table>'''

    def test_relative_href_resolved_to_absolute(self):
        rows = parse_news_html(self._REL_HTML, _REL_SOURCE)
        url = rows[0]['documents'][0]['url']
        assert url.startswith(_GOV_ORIGIN), f'expected absolute URL, got: {url!r}'

    def test_relative_href_resolves_to_correct_path(self):
        rows = parse_news_html(self._REL_HTML, _REL_SOURCE)
        url = rows[0]['documents'][0]['url']
        assert url == f'{_GOV_ORIGIN}/dmgcms/link_to_external_file/test%20file.pdf'

    def test_already_absolute_href_unchanged(self):
        rows = parse_news_html(self._ABS_HTML, _REL_SOURCE)
        url = rows[0]['documents'][0]['url']
        assert url == f'{_GOV_ORIGIN}/dmgcms/link_to_external_file/abs.pdf'

    def test_stored_url_never_starts_with_slash(self, app):
        import_news_items(_parsed())
        for doc in __import__('app.models', fromlist=['NewsDocument']).NewsDocument.query.all():
            assert not doc.url.startswith('/'), f'relative URL stored: {doc.url!r}'
