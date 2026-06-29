"""
Tests for scripts/backfill_news_document_urls.py::backfill_relative_urls.

Verifies:
  - A relative /dmgcms/... URL is converted to the correct absolute URL.
  - A row already holding an absolute URL is left unchanged.
  - Return dict {"updated", "skipped"} is accurate for a mixed batch.
"""
import datetime

import pytest

from app import db
from app.models import NewsDocument, NewsItem
from scripts.backfill_news_document_urls import backfill_relative_urls

_BASE = 'https://mines.rajasthan.gov.in'
_DATE = datetime.date(2026, 1, 1)
_FETCHED = datetime.datetime(2026, 1, 1, 12, 0, 0)


def _make_item(heading: str):
    item = NewsItem(
        heading=heading,
        order_date=_DATE,
        source_url=f'{_BASE}/news',
        dedup_hash=NewsItem.compute_dedup_hash(heading, _DATE),
        fetched_at=_FETCHED,
    )
    db.session.add(item)
    db.session.flush()
    return item


def _make_doc(item, url: str):
    doc = NewsDocument(news_item=item, title='PDF', url=url)
    db.session.add(doc)
    db.session.commit()
    return doc


class TestBackfillRelativeUrls:

    def test_backfill_converts_relative_url(self, app):
        """A root-relative URL must become an absolute government URL."""
        item = _make_item('Relative URL Test')
        doc = _make_doc(item, '/dmgcms/link_to_external_file/test.pdf')

        backfill_relative_urls(_BASE)

        db.session.refresh(doc)
        assert doc.url == f'{_BASE}/dmgcms/link_to_external_file/test.pdf'

    def test_backfill_leaves_absolute_url_unchanged(self, app):
        """A row already holding an absolute URL must not be modified."""
        item = _make_item('Absolute URL Test')
        original = f'{_BASE}/dmgcms/link_to_external_file/already_absolute.pdf'
        doc = _make_doc(item, original)

        backfill_relative_urls(_BASE)

        db.session.refresh(doc)
        assert doc.url == original

    def test_backfill_returns_correct_counts(self, app):
        """One relative + one absolute → {"updated": 1, "skipped": 1}."""
        item1 = _make_item('Count Test Relative')
        _make_doc(item1, '/dmgcms/link_to_external_file/rel.pdf')

        item2 = _make_item('Count Test Absolute')
        _make_doc(item2, f'{_BASE}/dmgcms/link_to_external_file/abs.pdf')

        result = backfill_relative_urls(_BASE)

        assert result == {'updated': 1, 'skipped': 1}

    def test_backfill_idempotent_second_run(self, app):
        """Running backfill twice must produce updated=0 on the second call."""
        item = _make_item('Idempotent Test')
        _make_doc(item, '/dmgcms/link_to_external_file/once.pdf')

        backfill_relative_urls(_BASE)
        result2 = backfill_relative_urls(_BASE)

        assert result2 == {'updated': 0, 'skipped': 1}
