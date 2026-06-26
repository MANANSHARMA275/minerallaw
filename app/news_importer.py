# ============================================================
# FILE: app/news_importer.py
# PURPOSE: Fetch, parse, categorise, and dedup-insert DMG
#          "News & Events" postings into NewsItem/NewsDocument
# ============================================================

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from app.logger import logger

# ── Source URL ────────────────────────────────────────────────────────────────

DMG_NEWS_URL = (
    'https://mines.rajasthan.gov.in/dmgcms/page'
    '?menuName=QdpQ6vUZUuo%3B455611%3BO16ylVRa4Q%3D%3D'
)

# ── Category keyword lists (module-level constants) ───────────────────────────

_AUCTION_KEYWORDS = [
    'nilami', 'auction', 'nib', 'bidder', 'letter of intent',
    'नीलामी', 'pre bid',
]

_MINERAL_KEYWORDS = [
    'limestone', 'bajri', 'gypsum', 'manganese', 'marble', 'granite',
    'sandstone', 'iron ore', 'gold block', 'mineral block', 'block summary',
    'बजरी', 'खनिज',
]

_TENDER_KEYWORDS = [
    'tender', 'nit', 'e-nivida', 'quotation', 'outsourcing',
    'निविदा',
]

_STAFF_KEYWORDS = [
    'seniority', 'promotion order', 'transfer order', 'appointment cancel',
    'resignation', 'class employee', 'draftsman', 'rigman', 'driller',
    'pump operator', 'personal secretary', 'establishment officer',
    'administrative officer', 'office order', 'dv order', 'extension',
    'counselling', 'counseling', 'waiting list', 'वरिष्ठता', 'पदोन्नति',
]

_NOTICE_KEYWORDS = [
    'corrigendum', 'addendum', 'sop', 'meeting notice', 'notice',
    'सूचना', 'अधिसूचना', 'नियम', 'शुद्धिपत्र',
    'rules', 'amendment', 'notification', 'policy',
]

# ── Private helpers ───────────────────────────────────────────────────────────

def _encode_pdf_url(href: str) -> str:
    """
    PURPOSE  : Encode spaces (and other illegal chars) in a PDF href without
               double-encoding sequences that are already percent-encoded
    RECEIVES : href (str) — raw href from HTML, may contain literal spaces
    RETURNS  : str — URL with path encoded; safe="/%()": slashes/percent/parens kept
    SECURITY : Never passes user input; called only from parse_news_html
    LEGAL    : N/A
    """
    parts = urlsplit(href)
    encoded_path = quote(parts.path, safe="/%()")
    return urlunsplit((parts.scheme, parts.netloc, encoded_path,
                       parts.query, parts.fragment))


def _filename_from_href(href: str) -> str:
    """
    PURPOSE  : Extract a display title from a URL path when link text is empty
    RECEIVES : href (str) — raw or encoded URL
    RETURNS  : str — last path segment, or the full href if no slash found
    SECURITY : N/A
    LEGAL    : N/A
    """
    return href.rstrip('/').rsplit('/', 1)[-1] or href


# ── Public functions ──────────────────────────────────────────────────────────

def fetch_news_html(url: str) -> str:
    """
    PURPOSE  : Download the DMG News & Events page HTML with retry logic
    RECEIVES : url (str) — source page URL
    RETURNS  : str — raw HTML text of the page
    SECURITY : Polite User-Agent identifies the bot; raises on non-2xx to
               prevent silently processing an error page
    LEGAL    : Fetches publicly available government information; rate limited
               by retry backoff (total=2, backoff_factor=1)
    """
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    headers = {
        'User-Agent': (
            'MineralLawBot/1.0 '
            '(+https://minelaw.in; compliance information service)'
        )
    }
    resp = session.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_news_html(html: str, source_url: str) -> list:
    """
    PURPOSE  : Parse the DMG news HTML table into structured dicts; pure fn
    RECEIVES : html (str) — raw HTML; source_url (str) — stored on each item
    RETURNS  : list[dict] — each dict has heading, order_date, source_url,
               documents (list of {title, url})
    SECURITY : No DB access, no network calls; all inputs are server-controlled
    LEGAL    : Skips (logs) malformed rows; never silently swallows a missing
               table — raises ValueError so the caller can treat it as an error
    """
    soup = BeautifulSoup(html, 'html.parser')

    target_table = None
    for table in soup.find_all('table'):
        headers = {
            th.get_text(strip=True).lower()
            for th in table.find_all('th')
        }
        if 'news heading' in headers and 'order date' in headers:
            target_table = table
            break

    if target_table is None:
        raise ValueError(
            'DMG news table not found — page layout may have changed'
        )

    rows = target_table.find_all('tr')
    results = []

    for tr in rows[1:]:  # skip header row
        cells = tr.find_all('td')
        if len(cells) != 4:
            continue

        heading = cells[1].get_text(strip=True)
        if not heading:
            logger.warning('parse_news_html: skipping row with empty heading')
            continue

        raw_date = cells[3].get_text(strip=True)
        try:
            order_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
        except ValueError:
            logger.warning(
                f'parse_news_html: skipping row — bad date {raw_date!r} '
                f'for heading {heading[:60]!r}'
            )
            continue

        documents = []
        for a in cells[2].find_all('a', href=True):
            href = a['href']
            title = a.get_text(strip=True) or _filename_from_href(href)
            documents.append({'title': title, 'url': _encode_pdf_url(href)})

        results.append({
            'heading': heading,
            'order_date': order_date,
            'source_url': source_url,
            'documents': documents,
        })

    return results


def categorize(heading: str) -> str:
    """
    PURPOSE  : Assign a category label to a DMG news heading
    RECEIVES : heading (str) — news item heading text
    RETURNS  : str — one of: auction, mineral, tender, staff, notice, other
    SECURITY : Pure function; no external calls
    LEGAL    : Priority order keeps owner-relevant items (auction/mineral/tender)
               published ahead of internal HR (staff) items
    """
    h = heading.lower()
    for kw in _AUCTION_KEYWORDS:
        if kw in h:
            return 'auction'
    for kw in _MINERAL_KEYWORDS:
        if kw in h:
            return 'mineral'
    for kw in _TENDER_KEYWORDS:
        if kw in h:
            return 'tender'
    for kw in _STAFF_KEYWORDS:
        if kw in h:
            return 'staff'
    for kw in _NOTICE_KEYWORDS:
        if kw in h:
            return 'notice'
    return 'other'


def import_news_items(parsed: list) -> dict:
    """
    PURPOSE  : Dedup-insert parsed news items and their documents into the DB
    RECEIVES : parsed (list[dict]) — output of parse_news_html
    RETURNS  : dict — {"new": int, "skipped": int, "errors": int}
    SECURITY : ORM-only inserts; no raw SQL; dedup_hash unique constraint is
               enforced in DB and also guarded in-memory for intra-batch dupes
    LEGAL    : is_published=False for category=='staff' keeps internal HR orders
               off the public-facing feed
    """
    from app.models import NewsItem, NewsDocument, db

    new_count = skipped_count = error_count = 0
    seen_hashes: set = set()

    for item_data in parsed:
        try:
            heading = item_data['heading']
            order_date = item_data['order_date']
            dedup_hash = NewsItem.compute_dedup_hash(heading, order_date)

            if dedup_hash in seen_hashes:
                skipped_count += 1
                continue

            if NewsItem.query.filter_by(dedup_hash=dedup_hash).first():
                skipped_count += 1
                continue

            seen_hashes.add(dedup_hash)
            category = categorize(heading)

            news_item = NewsItem(
                heading=heading,
                order_date=order_date,
                category=category,
                source_url=item_data['source_url'],
                dedup_hash=dedup_hash,
                is_published=(category != 'staff'),
                fetched_at=datetime.now(timezone.utc),
            )
            db.session.add(news_item)

            for doc in item_data.get('documents', []):
                db.session.add(NewsDocument(
                    news_item=news_item,
                    title=doc['title'],
                    url=doc['url'],
                ))

            new_count += 1

        except Exception as exc:
            logger.error(f'import_news_items: error on item {item_data.get("heading", "?")!r}: {exc}')
            error_count += 1

    try:
        from app.models import db
        db.session.commit()
    except Exception as exc:
        from app.models import db
        db.session.rollback()
        raise exc

    return {'new': new_count, 'skipped': skipped_count, 'errors': error_count}


def run_news_import() -> dict:
    """
    PURPOSE  : Orchestrate fetch → parse → import; safe to call from Celery
    RECEIVES : None (reads DMG_NEWS_URL module constant)
    RETURNS  : dict — {"status": "ok"|"error", "new", "skipped", "message"}
    SECURITY : Any network or parse failure returns an error dict without
               touching existing NewsItem rows
    LEGAL    : Source URL stored on every inserted row for attribution
    """
    try:
        html = fetch_news_html(DMG_NEWS_URL)
        parsed = parse_news_html(html, DMG_NEWS_URL)
        result = import_news_items(parsed)
        msg = (
            f'News import complete: {result["new"]} new, '
            f'{result["skipped"]} skipped, {result["errors"]} errors'
        )
        logger.info(msg)
        return {'status': 'ok', **result, 'message': msg}
    except Exception as exc:
        msg = str(exc)
        logger.error(f'News import failed: {msg}')
        return {'status': 'error', 'new': 0, 'skipped': 0, 'message': msg}
