# ============================================================
# FILE: seed_rates.py
# PURPOSE: Seed mineral master data and placeholder rates for development
# LAST UPDATED: Phase 1
# RUN: python seed_rates.py
# ============================================================

import sys
from datetime import date
from app import create_app, db
from app.models import Mineral, Rate

app = create_app()

with app.app_context():
    db.create_all()

    # Guard: idempotent — safe to run multiple times
    if Mineral.query.count() > 0:
        print("Already seeded.")
        sys.exit()

    # --------------------------------------------------------
    # MINERALS
    # --------------------------------------------------------
    limestone = Mineral(name='Limestone', category='minor')
    sand      = Mineral(name='Sand',      category='minor')
    granite   = Mineral(name='Granite',   category='minor')

    db.session.add_all([limestone, sand, granite])
    db.session.flush()  # Assign IDs before using them in Rate rows

    # --------------------------------------------------------
    # RATES — Limestone / Rajasthan
    # --------------------------------------------------------

    # Rate 1 — historical royalty
    # ⚠️ PLACEHOLDER — father verifies exact 2019 rate in Phase 0
    rate_2019 = Rate(
        mineral_id=limestone.id,
        state='Rajasthan',
        rate_type='royalty',
        value=70.00,
        unit='per_tonne',
        effective_from=date(2019, 1, 1),
        effective_to=date(2021, 12, 31),
        notification_number='DMG/2019/01',
    )

    # Rate 2 — current royalty
    # ⚠️ PLACEHOLDER — father verifies 2026 rate in Phase 0
    rate_2022 = Rate(
        mineral_id=limestone.id,
        state='Rajasthan',
        rate_type='royalty',
        value=90.00,
        unit='per_tonne',
        effective_from=date(2022, 1, 1),
        effective_to=None,          # None = currently active
        notification_number='DMG/2022/01',
    )

    # Rate 3 — DMF
    # ⚠️ PLACEHOLDER — father confirms DMF % varies by mine size
    rate_dmf = Rate(
        mineral_id=limestone.id,
        state='Rajasthan',
        rate_type='dmf',
        value=10.00,
        unit='percent_of_royalty',
        effective_from=date(2022, 1, 1),
        effective_to=None,
        notification_number='DMG-DMF/2022/01',
    )

    db.session.add_all([rate_2019, rate_2022, rate_dmf])
    db.session.commit()

    print("Seeded: Limestone, Sand, Granite minerals")
    print("Seeded: 2019 royalty (₹70/t), 2022 royalty (₹90/t), 2022 DMF (10%) for Limestone")
    print("⚠️  All rates are PLACEHOLDERS — father must verify before client use")
