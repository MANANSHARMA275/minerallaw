"""
Tests for the public GET /news page:
  - Returns 200 without login (public route).
  - Shows published item headings; hides unpublished staff items.
  - Category filter (?category=auction) narrows results correctly.
  - ?category=staff (or any unknown value) falls back to 'all' and still
    never exposes unpublished items.
  - PDF links carry target="_blank" and rel="noopener".
  - Attribution text is present in every response.

DB is seeded directly — the live importer is never called.
"""
import datetime

import pytest

from app import db
from app.models import NewsDocument, NewsItem

# ── Constants ─────────────────────────────────────────────────────────────────

_DATE    = datetime.date(2026, 4, 30)
_FETCHED = datetime.datetime(2026, 4, 30, 10, 0, 0)
_SOURCE  = 'https://mines.rajasthan.gov.in/news'
_DOC_URL = 'https://mines.rajasthan.gov.in/dmgcms/link_to_external_file/NIB.pdf'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(heading, category, is_published=True, order_date=_DATE):
    item = NewsItem(
        heading=heading,
        order_date=order_date,
        category=category,
        source_url=_SOURCE,
        dedup_hash=NewsItem.compute_dedup_hash(heading, order_date),
        is_published=is_published,
        fetched_at=_FETCHED,
    )
    db.session.add(item)
    db.session.commit()
    return item


def _make_doc(item, title='Auction NIB PDF', url=_DOC_URL):
    doc = NewsDocument(news_item=item, title=title, url=url)
    db.session.add(doc)
    db.session.commit()
    return doc


# ── Fixtures (inline per test class to keep DB clean across tests) ────────────

def _seed(app):
    """Seed one published auction item (with PDF), one published notice, one unpublished staff."""
    auction = _make_item('NIB for Limestone Blocks 2026', 'auction')
    _make_doc(auction, title='NIB Document', url=_DOC_URL)
    notice  = _make_item('Corrigendum Notice April 2026', 'notice',
                         order_date=datetime.date(2026, 4, 28))
    staff   = _make_item('Seniority List Rigman 2026', 'staff', is_published=False)
    return auction, notice, staff


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNewsPagePublicAccess:

    def test_public_page_returns_200_without_login(self, client):
        """GET /news must be accessible to anonymous users."""
        resp = client.get('/news')
        assert resp.status_code == 200

    def test_published_heading_appears(self, app, client):
        """A published item's heading must appear in the page HTML."""
        auction, _, _ = _seed(app)
        resp = client.get('/news')
        assert auction.heading.encode() in resp.data

    def test_unpublished_staff_item_hidden(self, app, client):
        """An unpublished staff item must NEVER appear in the page HTML."""
        _, _, staff = _seed(app)
        resp = client.get('/news')
        assert staff.heading.encode() not in resp.data

    def test_attribution_text_present(self, app, client):
        """Attribution to DMG must appear on every /news response."""
        _seed(app)
        resp = client.get('/news')
        assert b'Department of Mines' in resp.data


class TestNewsCategoryFilter:

    def test_category_filter_shows_matching_item(self, app, client):
        """?category=auction must show the auction item."""
        auction, _, _ = _seed(app)
        resp = client.get('/news?category=auction')
        assert resp.status_code == 200
        assert auction.heading.encode() in resp.data

    def test_category_filter_hides_other_category(self, app, client):
        """?category=auction must NOT show the notice item."""
        _, notice, _ = _seed(app)
        resp = client.get('/news?category=auction')
        assert notice.heading.encode() not in resp.data

    def test_category_staff_falls_back_to_all(self, app, client):
        """?category=staff is not in the published set — must resolve to 'all' with 200."""
        _, _, staff = _seed(app)
        resp = client.get('/news?category=staff')
        assert resp.status_code == 200
        assert staff.heading.encode() not in resp.data

    def test_bogus_category_falls_back_to_all(self, app, client):
        """Any unknown ?category value must resolve to 'all' and return 200."""
        auction, _, _ = _seed(app)
        resp = client.get('/news?category=bogus_value')
        assert resp.status_code == 200
        assert auction.heading.encode() in resp.data


class TestNewsPdfLinks:

    def test_pdf_link_has_target_blank(self, app, client):
        """PDF document links must open in a new tab (target=_blank)."""
        _seed(app)
        resp = client.get('/news')
        assert b'target="_blank"' in resp.data

    def test_pdf_link_has_rel_noopener_noreferrer(self, app, client):
        """PDF document links must carry rel=noopener noreferrer for security."""
        _seed(app)
        resp = client.get('/news')
        assert b'rel="noopener noreferrer"' in resp.data

    def test_pdf_link_url_is_rendered(self, app, client):
        """The document's URL must appear as an href in the response."""
        _seed(app)
        resp = client.get('/news')
        assert _DOC_URL.encode() in resp.data
