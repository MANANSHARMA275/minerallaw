# ============================================================
# FILE: seed_data.py
# PURPOSE: Idempotent development seed — one Limestone mineral with
#          two royalty rates and one DMF rate, all clearly marked as
#          PLACEHOLDER pending father verification in Phase 0.
#          Also seeds a dev superadmin if DEV_SUPERADMIN_PHONE is set.
# RUN:     python seed_data.py
# LAST UPDATED: Phase 1
# ============================================================

import os
from datetime import date
from app import create_app, db
from app.models import Mineral, Rate, User


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
    PURPOSE  : Populate dev database with one Limestone mineral and
               three placeholder rates (2 royalty + 1 DMF).
               Safe to re-run — all writes are guarded by name/key checks.
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

        db.session.commit()

        # ── Final count report ─────────────────────────────────
        mineral_count = Mineral.query.count()
        rate_count = Rate.query.count()
        user_count = User.query.count()
        print(f"\n── Done ──────────────────────────────────────────────")
        print(f"  Mineral rows : {mineral_count}")
        print(f"  Rate rows    : {rate_count}")
        print(f"  User rows    : {user_count}")
        print(f"\n⚠️  All rate values are PLACEHOLDERS — father must verify")
        print(f"   against DMG notifications before client-facing use.\n")


if __name__ == '__main__':
    seed()
