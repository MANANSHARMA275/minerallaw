"""
One-time backfill: resolve the 90 existing root-relative NewsDocument URLs
to absolute government URLs.

Run manually (never via the importer or tests):
    flask shell -c "from scripts.backfill_news_document_urls import backfill_relative_urls; ..."
  or simply:
    python scripts/backfill_news_document_urls.py

Operates on whichever DB the app context is bound to (locally: SQLite at instance/minerallaw.db).
Idempotent — safe to run twice; already-absolute rows are skipped.
"""
from urllib.parse import urljoin


def backfill_relative_urls(base_url: str) -> dict:
    """
    PURPOSE  : Fix existing NewsDocument rows whose url is root-relative, not absolute.
    RECEIVES : base_url (str) — e.g. 'https://mines.rajasthan.gov.in'
    RETURNS  : dict — {"updated": int, "skipped": int}
    SECURITY : ORM-only update; no raw SQL; skips rows already starting with 'http'.
    LEGAL    : Canonical government URLs preserved — no self-hosting or downloading.
    """
    from app.models import NewsDocument, db

    updated = skipped = 0
    docs = NewsDocument.query.all()

    for doc in docs:
        if doc.url.startswith('http'):
            skipped += 1
        else:
            doc.url = urljoin(base_url, doc.url)
            updated += 1

    if updated:
        db.session.commit()

    return {"updated": updated, "skipped": skipped}


if __name__ == '__main__':
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app import create_app
    from app.news_importer import DMG_NEWS_URL
    from urllib.parse import urlsplit

    # Derive origin (scheme + host) from the importer's source constant — single source of truth.
    parsed = urlsplit(DMG_NEWS_URL)
    base = f'{parsed.scheme}://{parsed.netloc}'

    app = create_app()
    with app.app_context():
        result = backfill_relative_urls(base)
    print(result)
