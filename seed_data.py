# ============================================================
# FILE: seed_data.py
# PURPOSE: Idempotent development seed — one Limestone mineral with
#          two royalty rates and one DMF rate, all clearly marked as
#          PLACEHOLDER pending father verification in Phase 0.
# RUN:     python seed_data.py
# LAST UPDATED: Phase 1
# ============================================================

import sys
from datetime import date
from app import create_app, db
from app.models import Mineral, Rate


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


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def seed() -> None:
    """
    PURPOSE  : Populate dev database with one Limestone mineral and
               three placeholder rates (2 royalty + 1 DMF).
               Safe to re-run — all writes are guarded by name/key checks.
    RECEIVES : None — reads app context from create_app()
    RETURNS  : None
    SECURITY : No user-supplied input; runs only in app context.
               Placeholder data is clearly labelled — never shown as
               verified rates to users.
    LEGAL    : ⚠️ ALL values are PLACEHOLDERS.  Father must verify exact
               rates against DMG notifications before client-facing use.
    """
    app = create_app()
    with app.app_context():
        # db.create_all() is intentional: migration 50e5a317196b was generated
        # when the dev DB already had tables from an earlier db.create_all() call
        # but no alembic_version row. Autogenerate mis-classified all existing
        # tables as "new", so the migration re-declares them. Running flask db
        # upgrade on a fresh empty DB therefore fails after d35d6dec50ab creates
        # the tables (50e5a317196b tries to re-create them — SQLite rejects it),
        # leaving alembic_version recorded but all application tables absent.
        # db.create_all() here bypasses Alembic and is idempotent: it only
        # creates tables that do not yet exist, making this script safe to run
        # as the single dev-setup command: python seed_data.py
        db.create_all()

        print("\n── Minerals ──────────────────────────────────────────")
        limestone = get_or_create_mineral('Limestone', 'minor')

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

        # ⚠️ PLACEHOLDER — DMF stored as decimal multiplier (0.10 = 10 %).
        #    fee_calculator.py uses dmf_row.value directly as the multiplier:
        #        dmf_annual = royalty × dmf_row.value
        #    Father must confirm exact % before client use.
        insert_rate_if_absent(
            notification_number='PLACEHOLDER-DMG-DMF/2022/01',
            mineral_id=limestone.id,
            state='Rajasthan',
            rate_type='dmf',
            value=0.10,                 # 10 % of royalty — DECIMAL MULTIPLIER
            unit='percent_of_royalty',
            effective_from=date(2022, 1, 1),
            effective_to=None,
        )

        db.session.commit()

        # ── Final count report ─────────────────────────────────
        mineral_count = Mineral.query.count()
        rate_count = Rate.query.count()
        print(f"\n── Done ──────────────────────────────────────────────")
        print(f"  Mineral rows : {mineral_count}")
        print(f"  Rate rows    : {rate_count}")
        print(f"\n⚠️  All values are PLACEHOLDERS — father must verify")
        print(f"   against DMG notifications before client-facing use.\n")


if __name__ == '__main__':
    seed()
