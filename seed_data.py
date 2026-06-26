# ============================================================
# FILE: seed_data.py
# PURPOSE: Idempotent development seed — 11 Rajasthan minor minerals
#          (Limestone + 10 new), each with one royalty rate and one DMF
#          rate, all clearly marked as PLACEHOLDER pending father
#          verification in Phase 0.
#          Also seeds a dev superadmin if DEV_SUPERADMIN_PHONE is set.
# RUN:     python seed_data.py
# LAST UPDATED: Phase 1
# ============================================================
#
# SCHEMA NOTE (do not implement yet):
# Rajasthan royalty varies by DISTRICT and by END-USE (e.g. masonry
# stone ₹30 Sikar vs ₹23 other districts; ₹100 for cobbles).  The
# current Rate model is one-rate-per-mineral-per-state.  Father to
# advise in Phase 0 whether district/use-type columns are needed before
# real rates are entered.
# ============================================================

import os
from datetime import date
from app import create_app, db
from app.models import Legislation, Mineral, Rate, User


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def get_or_create_mineral(name: str, category: str) -> Mineral:
    """
    PURPOSE  : Return existing Mineral by name, or insert a new one
    RECEIVES : name (str), category (str) — 'major'|'minor'|'critical'
    RETURNS  : Mineral — the existing or newly flushed row
    SECURITY : Filter by exact name — no SQL injection (SQLAlchemy ORM)
    LEGAL    : N/A
    """
    existing = Mineral.query.filter_by(name=name).first()
    if existing:
        print(f"  Mineral '{name}' already exists (id={existing.id}) — skipping")
        return existing

    mineral = Mineral(name=name, category=category)
    db.session.add(mineral)
    db.session.flush()   # assign id before rate insertion
    print(f"  Mineral '{name}' inserted (id={mineral.id})")
    return mineral


def insert_rate_if_absent(notification_number: str, **kwargs) -> None:
    """
    PURPOSE  : Insert a Rate row only when no row with the same
               notification_number already exists — prevents duplicates
               on repeated runs without ever overwriting existing data.
    RECEIVES : notification_number (str) — natural dedup key;
               **kwargs — remaining Rate column values
    RETURNS  : None
    SECURITY : ORM parameterised query; no raw SQL
    LEGAL    : Immutable-rate rule — Rate rows must never be updated after
               father verification. This function enforces that constraint
               for the seed path.
    """
    exists = Rate.query.filter_by(
        notification_number=notification_number
    ).first()
    if exists:
        print(f"  Rate '{notification_number}' already exists — skipping")
        return

    rate = Rate(notification_number=notification_number, **kwargs)
    db.session.add(rate)
    print(f"  Rate '{notification_number}' inserted")


def seed_legislation() -> None:
    """
    PURPOSE  : Insert 3 PLACEHOLDER Legislation entries for dev/demo purposes.
               Idempotent — skips any entry whose title already exists.
    RECEIVES : None — runs inside an active app context
    RETURNS  : None
    SECURITY : No user-supplied input; dev-only seed
    LEGAL    : ⚠️ ALL summaries are PLACEHOLDER text.
               Domain expert (father) must verify every entry before publishing.
               All entries seeded with is_published=False so they never appear
               on the public page until explicitly toggled in the admin panel.
    """
    _ENTRIES = [
        {
            'title':            '[PLACEHOLDER] MMDR Amendment 2025 — Star-Rated Mining',
            'category':         '2025 Amendment',
            'summary_en':       (
                '[PLACEHOLDER — father to verify] The Mines and Minerals (Development '
                'and Regulation) Amendment 2025 introduces a mandatory star-rating '
                'system for mine operations. Higher-rated mines receive preference in '
                'lease renewals. Exact provisions and effective date to be confirmed.'
            ),
            'summary_hi':       (
                '[PLACEHOLDER — पिता जी से सत्यापित करना है] खान एवं खनिज '
                '(विकास और विनियमन) संशोधन 2025 खनन परिचालन के लिए अनिवार्य '
                'स्टार-रेटिंग प्रणाली प्रस्तुत करता है।'
            ),
            'source_reference': 'MMDR Amendment 2025',
            'official_url':     None,
            'last_verified_on': None,
            'is_published':     False,
            'display_order':    1,
        },
        {
            'title':            '[PLACEHOLDER] Rajasthan Minor Mineral Royalty Revision — G.S.R. 93',
            'category':         'Fees & Royalty',
            'summary_en':       (
                '[PLACEHOLDER — father to verify] Rajasthan government revised royalty '
                'rates for minor minerals via G.S.R. 93. New rates applicable from the '
                'notification date. Exact per-mineral figures and effective date to be '
                'confirmed against the official DMG notification.'
            ),
            'summary_hi':       (
                '[PLACEHOLDER — पिता जी से सत्यापित करना है] राजस्थान सरकार ने '
                'G.S.R. 93 के माध्यम से लघु खनिजों के लिए रॉयल्टी दरें संशोधित '
                'की हैं। सटीक दरें आधिकारिक DMG अधिसूचना से सत्यापित करें।'
            ),
            'source_reference': 'G.S.R. 93',
            'official_url':     None,
            'last_verified_on': None,
            'is_published':     False,
            'display_order':    1,
        },
        {
            'title':            '[PLACEHOLDER] Annual Return Filing Deadline — Rule 44(7)',
            'category':         'Deadlines & Filing',
            'summary_en':       (
                '[PLACEHOLDER — father to verify] Under Rule 44(7) of the Rajasthan '
                'Minor Mineral Concession Rules, lessees must file an annual return of '
                'mineral production by 31 January each year. Failure to file attracts '
                'penalties. Current penalty amount to be confirmed.'
            ),
            'summary_hi':       (
                '[PLACEHOLDER — पिता जी से सत्यापित करना है] राजस्थान लघु खनिज '
                'रियायत नियम 44(7) के तहत पट्टेदारों को प्रति वर्ष 31 जनवरी '
                'तक वार्षिक उत्पादन रिटर्न दाखिल करनी होती है।'
            ),
            'source_reference': 'Rule 44(7)',
            'official_url':     None,
            'last_verified_on': None,
            'is_published':     False,
            'display_order':    1,
        },
    ]
    for data in _ENTRIES:
        if Legislation.query.filter_by(title=data['title']).first():
            print(f"  Legislation '{data['title'][:50]}…' already exists — skipping")
            continue
        db.session.add(Legislation(**data))
        print(f"  Legislation '{data['title'][:50]}…' inserted (is_published=False)")


def seed_superadmin() -> None:
    """
    PURPOSE  : Create a dev superadmin user if DEV_SUPERADMIN_PHONE is set.
               Idempotent — safe to re-run; skips if the phone already exists.
    RECEIVES : None — reads DEV_SUPERADMIN_PHONE from the environment
    RETURNS  : None
    SECURITY : Never hardcodes a phone number. Set DEV_SUPERADMIN_PHONE in
               .env (git-ignored). Never commit a real phone to the repo.
    LEGAL    : Dev-only utility; must not run against a production DB.
    """
    phone = os.environ.get('DEV_SUPERADMIN_PHONE', '').strip()
    if not phone:
        print("  DEV_SUPERADMIN_PHONE not set — skipping superadmin seed")
        print("  (Set it in .env to create a local superadmin account)")
        return

    existing = User.query.filter_by(phone=phone).first()
    if existing:
        if existing.role != 'superadmin':
            existing.role = 'superadmin'
            print(f"  User {phone[-4:]:>4} role upgraded to superadmin")
        else:
            print(f"  Superadmin ****{phone[-4:]} already exists — skipping")
        return

    admin = User(
        phone=phone,
        role='superadmin',
        subscription_tier='free',
    )
    db.session.add(admin)
    print(f"  Superadmin ****{phone[-4:]} created")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def seed() -> None:
    """
    PURPOSE  : Populate dev database with 11 Rajasthan minor minerals
               (Limestone already verified as present; 10 new ones added
               as PLACEHOLDER) each with one royalty Rate and one DMF
               Rate.  Safe to re-run — all writes are guarded by
               name/notification_number checks.
    RECEIVES : None — reads app context from create_app()
    RETURNS  : None
    SECURITY : No user-supplied input; runs only in app context.
               Placeholder data is clearly labelled — never shown as
               verified rates to users.
    LEGAL    : ⚠️ ALL rate values are PLACEHOLDERS.  Father must verify
               exact rates against DMG notifications before client-facing use.
    """
    app = create_app()
    with app.app_context():
        # db.create_all() is intentional: the Alembic migration chain was
        # repaired on 2026-06-12 (50e5a317196b now creates only the 3 EC
        # tables; b7f3a1d9c2e8 adds auction_status). For local dev this
        # script remains the one-command setup — db.create_all() is idempotent
        # and picks up any model changes not yet in a migration.
        db.create_all()

        print("\n── Superadmin ────────────────────────────────────────")
        seed_superadmin()

        print("\n── Legislation (PLACEHOLDER — father to verify) ──────")
        seed_legislation()

        print("\n── Minerals ──────────────────────────────────────────")
        limestone       = get_or_create_mineral('Limestone',     'minor')
        marble          = get_or_create_mineral('Marble',        'minor')
        granite         = get_or_create_mineral('Granite',       'minor')
        sandstone       = get_or_create_mineral('Sandstone',     'minor')
        masonry_stone   = get_or_create_mineral('Masonry Stone', 'minor')
        bajri           = get_or_create_mineral('Bajri',         'minor')
        kankar          = get_or_create_mineral('Kankar',        'minor')
        diorite         = get_or_create_mineral('Diorite',       'minor')
        brick_earth     = get_or_create_mineral('Brick Earth',   'minor')
        ordinary_sand   = get_or_create_mineral('Ordinary Sand', 'minor')
        murram          = get_or_create_mineral('Murram',        'minor')

        print("\n── Rates ─────────────────────────────────────────────")

        # ⚠️ PLACEHOLDER — father verifies exact 2019 royalty rate in Phase 0
        insert_rate_if_absent(
            notification_number='PLACEHOLDER-DMG/2019/01',
            mineral_id=limestone.id,
            state='Rajasthan',
            rate_type='royalty',
            value=70.00,
            unit='per_tonne',
            effective_from=date(2019, 1, 1),
            effective_to=date(2021, 12, 31),
        )

        # ⚠️ PLACEHOLDER — father verifies current royalty rate in Phase 0
        insert_rate_if_absent(
            notification_number='PLACEHOLDER-DMG/2022/01',
            mineral_id=limestone.id,
            state='Rajasthan',
            rate_type='royalty',
            value=90.00,
            unit='per_tonne',
            effective_from=date(2022, 1, 1),
            effective_to=None,          # None = currently active
        )

        # ⚠️ PLACEHOLDER — DMF stored as PERCENTAGE (10.00 = 10%).
        #    CONVENTION: Rate.value for rate_type='dmf' is a percentage.
        #    calculate_dmf() computes: royalty × (value / 100).
        #    Father must confirm exact % before client use.
        insert_rate_if_absent(
            notification_number='PLACEHOLDER-DMG-DMF/2019/01',
            mineral_id=limestone.id,
            state='Rajasthan',
            rate_type='dmf',
            value=10.00,                # 10% — PERCENTAGE CONVENTION
            unit='percent',
            effective_from=date(2019, 1, 1),
            effective_to=date(2021, 12, 31),
        )

        # ⚠️ PLACEHOLDER — father verifies current DMF rate in Phase 0
        insert_rate_if_absent(
            notification_number='PLACEHOLDER-DMG-DMF/2022/01',
            mineral_id=limestone.id,
            state='Rajasthan',
            rate_type='dmf',
            value=10.00,                # 10% — PERCENTAGE CONVENTION
            unit='percent',
            effective_from=date(2022, 1, 1),
            effective_to=None,
        )

        # ── New minor minerals — ALL PLACEHOLDER rates ─────────
        # Each entry: one royalty rate (50.00/tonne) + one DMF rate (10%).
        # Values are deliberately fake. Father verifies against official
        # DMG Rajasthan royalty schedule before any client-facing use.
        _NEW_MINERALS = [
            ('MARBLE',        marble),
            ('GRANITE',       granite),
            ('SANDSTONE',     sandstone),
            ('MASONRY-STONE', masonry_stone),
            ('BAJRI',         bajri),
            ('KANKAR',        kankar),
            ('DIORITE',       diorite),
            ('BRICK-EARTH',   brick_earth),
            ('ORDINARY-SAND', ordinary_sand),
            ('MURRAM',        murram),
        ]
        for key, mineral in _NEW_MINERALS:
            # ⚠️ PLACEHOLDER royalty — father verifies exact rate
            insert_rate_if_absent(
                notification_number=f'PLACEHOLDER-DMG-{key}/2022/01',
                mineral_id=mineral.id,
                state='Rajasthan',
                rate_type='royalty',
                value=50.00,
                unit='per_tonne',
                effective_from=date(2022, 1, 1),
                effective_to=None,
            )
            # ⚠️ PLACEHOLDER DMF — 10% convention, father confirms
            insert_rate_if_absent(
                notification_number=f'PLACEHOLDER-DMG-DMF-{key}/2022/01',
                mineral_id=mineral.id,
                state='Rajasthan',
                rate_type='dmf',
                value=10.00,            # 10% — PERCENTAGE CONVENTION
                unit='percent',
                effective_from=date(2022, 1, 1),
                effective_to=None,
            )

        db.session.commit()

        # ── Final count report ─────────────────────────────────
        mineral_count     = Mineral.query.count()
        rate_count        = Rate.query.count()
        user_count        = User.query.count()
        legislation_count = Legislation.query.count()
        print(f"\n── Done ──────────────────────────────────────────────")
        print(f"  Mineral rows     : {mineral_count}")
        print(f"  Rate rows        : {rate_count}")
        print(f"  User rows        : {user_count}")
        print(f"  Legislation rows : {legislation_count}")
        print(f"\n⚠️  All rate values are PLACEHOLDERS — father must verify")
        print(f"   against DMG notifications before client-facing use.")
        print(f"⚠️  All legislation entries are PLACEHOLDER and is_published=False.")
        print(f"   Father must verify and publish via the admin panel.\n")


if __name__ == '__main__':
    seed()
