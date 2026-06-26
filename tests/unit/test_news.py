"""
Tests for the NewsItem + NewsDocument schema:
  - Create, query, field values, relationship (0-N documents).
  - compute_dedup_hash: stable, case/whitespace-insensitive, date-sensitive.
  - Unique constraints: dedup_hash on NewsItem; (news_item_id, url) on NewsDocument.
  - Cascade delete: deleting a NewsItem removes its NewsDocuments.
  - Defaults: is_published=True, created_at populated automatically.
"""
import datetime
import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import NewsDocument, NewsItem


# ── Helpers ───────────────────────────────────────────────────────────────────

_DATE = datetime.date(2025, 3, 10)
_FETCHED = datetime.datetime(2025, 3, 10, 12, 0, 0)


def _make_item(heading='DMG Notice 1', order_date=_DATE,
               dedup_hash=None, **kwargs):
    if dedup_hash is None:
        dedup_hash = NewsItem.compute_dedup_hash(heading, order_date)
    item = NewsItem(
        heading=heading,
        order_date=order_date,
        source_url='https://mines.rajasthan.gov.in/news',
        dedup_hash=dedup_hash,
        fetched_at=_FETCHED,
        **kwargs,
    )
    db.session.add(item)
    return item


def _make_doc(item, title='Order PDF', url='https://mines.raj.gov.in/order.pdf'):
    doc = NewsDocument(news_item=item, title=title, url=url)
    db.session.add(doc)
    return doc


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNewsItemCreation:

    def test_create_news_item_with_two_documents(self, app):
        """Create one NewsItem + two NewsDocuments; re-query and assert all fields."""
        item = _make_item(heading='Auction Notice March 2025')
        _make_doc(item, title='Notice PDF', url='https://gov.in/notice.pdf')
        _make_doc(item, title='Annexure PDF', url='https://gov.in/annexure.pdf')
        db.session.commit()

        fetched = db.session.get(NewsItem, item.id)
        assert fetched is not None
        assert fetched.heading == 'Auction Notice March 2025'
        assert fetched.order_date == _DATE
        assert fetched.category == 'notice'           # default
        assert fetched.source_url == 'https://mines.rajasthan.gov.in/news'
        assert len(fetched.dedup_hash) == 64
        assert fetched.is_published is True            # default
        assert fetched.fetched_at == _FETCHED
        assert isinstance(fetched.created_at, datetime.datetime)
        assert len(fetched.documents) == 2
        titles = {d.title for d in fetched.documents}
        assert titles == {'Notice PDF', 'Annexure PDF'}

    def test_defaults(self, app):
        """is_published defaults True; created_at is set without being specified."""
        item = _make_item()
        db.session.commit()

        fetched = db.session.get(NewsItem, item.id)
        assert fetched.is_published is True
        assert fetched.created_at is not None
        assert isinstance(fetched.created_at, datetime.datetime)


class TestDedupHash:

    def test_hash_is_stable(self):
        """Same heading + date always produces the same hash."""
        h1 = NewsItem.compute_dedup_hash('Tender Notice', _DATE)
        h2 = NewsItem.compute_dedup_hash('Tender Notice', _DATE)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_case_insensitive(self):
        """Different casing → same hash."""
        h1 = NewsItem.compute_dedup_hash('Tender Notice', _DATE)
        h2 = NewsItem.compute_dedup_hash('TENDER NOTICE', _DATE)
        assert h1 == h2

    def test_hash_whitespace_insensitive(self):
        """Extra/collapsed whitespace → same hash."""
        h1 = NewsItem.compute_dedup_hash('Tender  Notice', _DATE)
        h2 = NewsItem.compute_dedup_hash('  Tender Notice  ', _DATE)
        h3 = NewsItem.compute_dedup_hash('Tender Notice', _DATE)
        assert h1 == h2 == h3

    def test_different_date_produces_different_hash(self):
        """Same heading, different date → different hash."""
        h1 = NewsItem.compute_dedup_hash('Tender Notice', datetime.date(2025, 1, 1))
        h2 = NewsItem.compute_dedup_hash('Tender Notice', datetime.date(2025, 1, 2))
        assert h1 != h2


class TestUniqueConstraints:

    def test_dedup_hash_unique_constraint(self, app):
        """Two NewsItems sharing a dedup_hash must raise IntegrityError on commit."""
        shared_hash = NewsItem.compute_dedup_hash('Duplicate Heading', _DATE)
        _make_item(heading='Duplicate Heading', dedup_hash=shared_hash)
        db.session.commit()

        _make_item(heading='Duplicate Heading', dedup_hash=shared_hash)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_url_unique_per_news_item(self, app):
        """Same url attached twice to one NewsItem must raise IntegrityError."""
        item = _make_item()
        db.session.commit()

        shared_url = 'https://gov.in/duplicate.pdf'
        _make_doc(item, title='First', url=shared_url)
        db.session.commit()

        _make_doc(item, title='Second', url=shared_url)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_same_url_on_different_items_is_allowed(self, app):
        """The same PDF url may appear on different NewsItems — only unique per item."""
        shared_url = 'https://gov.in/shared.pdf'
        item1 = _make_item(heading='Item One',
                           dedup_hash=NewsItem.compute_dedup_hash('Item One', _DATE))
        item2 = _make_item(heading='Item Two',
                           order_date=datetime.date(2025, 4, 1),
                           dedup_hash=NewsItem.compute_dedup_hash(
                               'Item Two', datetime.date(2025, 4, 1)))
        db.session.commit()

        _make_doc(item1, title='Doc', url=shared_url)
        _make_doc(item2, title='Doc', url=shared_url)
        db.session.commit()   # must not raise


class TestCascadeDelete:

    def test_deleting_news_item_removes_its_documents(self, app):
        """Cascade='all, delete-orphan': deleting a NewsItem must remove its docs."""
        item = _make_item()
        _make_doc(item, title='Will Be Gone', url='https://gov.in/gone.pdf')
        _make_doc(item, title='Also Gone',   url='https://gov.in/also-gone.pdf')
        db.session.commit()

        item_id = item.id
        db.session.delete(item)
        db.session.commit()

        assert db.session.get(NewsItem, item_id) is None
        remaining = NewsDocument.query.filter_by(news_item_id=item_id).all()
        assert remaining == []
