# ============================================================
# FILE: app/fee_calculator.py
# PURPOSE: Royalty / DMF / NPV calculation with Decimal precision
#          and mandatory disclaimer on every output
# LAST UPDATED: Phase 1
# CRITICAL: All rates marked ⚠️ FATHER VERIFY must be confirmed in
#           Phase 0 interview before this calculator goes live for clients
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from sqlalchemy import or_

from app.logger import logger

# ------------------------------------------------------------
# SECTION 2: PLACEHOLDER RATES (used when Rate table is empty)
# ⚠️ THESE ARE SAMPLE VALUES FOR DEVELOPMENT TESTING ONLY
# Father must replace with verified rates in the admin panel
# before any user-facing launch
# ------------------------------------------------------------
PLACEHOLDER_RATES = {
    'limestone': {
        'royalty_per_tonne': Decimal('90'),       # ⚠️ FATHER VERIFY: Rajasthan 2026
        'dmf_rate': Decimal('10'),                # ⚠️ FATHER VERIFY: percentage, 10 = 10%
        'notification': 'PLACEHOLDER — Father must enter verified rate',
        'effective_from': date(2022, 1, 1)
    },
    'stone': {
        'royalty_per_tonne': Decimal('25'),       # ⚠️ FATHER VERIFY
        'dmf_rate': Decimal('10'),
        'notification': 'PLACEHOLDER — Father must enter verified rate',
        'effective_from': date(2022, 1, 1)
    },
    'sand': {
        'royalty_per_tonne': Decimal('40'),       # ⚠️ FATHER VERIFY
        'dmf_rate': Decimal('10'),
        'notification': 'PLACEHOLDER — Father must enter verified rate',
        'effective_from': date(2022, 1, 1)
    },
    'marble': {
        'royalty_per_tonne': Decimal('120'),      # ⚠️ FATHER VERIFY
        'dmf_rate': Decimal('10'),
        'notification': 'PLACEHOLDER — Father must enter verified rate',
        'effective_from': date(2022, 1, 1)
    },
    'granite': {
        'royalty_per_tonne': Decimal('100'),      # ⚠️ FATHER VERIFY
        'dmf_rate': Decimal('10'),
        'notification': 'PLACEHOLDER — Father must enter verified rate',
        'effective_from': date(2022, 1, 1)
    },
}

# NPV discount rate — ⚠️ FATHER VERIFY: which notification mandates this?
DEFAULT_DISCOUNT_RATE = Decimal('0.08')  # 8%


# ------------------------------------------------------------
# SECTION 3: JURISDICTION DETECTION
# ------------------------------------------------------------
def detect_jurisdiction(area_ha: float, mineral_category: str, state: str) -> str:
    """
    PURPOSE  : Determine whether state or central rates apply to this mine
    RECEIVES : area_ha (float), mineral_category (str) — 'minor'|'major'
               state (str)
    RETURNS  : str — 'state' (Rajasthan DMG) or 'central' (IBM)
    SECURITY : No external calls
    LEGAL    : ⚠️ FATHER VERIFY — 5 ha threshold, limestone classification,
               district exceptions. Wrong jurisdiction = wrong rate = rejected application.
    """
    if state.lower() == 'rajasthan' and mineral_category.lower() == 'minor' and area_ha <= 5:
        return 'state'   # Rajasthan DMG rates
    return 'central'     # IBM (Indian Bureau of Mines) rates


# ------------------------------------------------------------
# SECTION 4: RATE LOOKUP
# ------------------------------------------------------------
def get_rate_for_date(
    mineral_id: int,
    state: str,
    rate_type: str,
    target_date: date
):
    """
    PURPOSE  : Return the rate legally valid on a specific past date
    RECEIVES : mineral_id (int), state (str), rate_type (str) — 'royalty'|'dmf'
               target_date (date)
    RETURNS  : Rate object or None
    SECURITY : Read-only query
    LEGAL    : CRITICAL — lease signed 15 March 2019 MUST use 2019 rate.
               Wrong rate = rejected application. effective_to=None means active.
    """
    from app.models import Rate  # Late import avoids circular dependency

    return Rate.query.filter(
        Rate.mineral_id == mineral_id,
        Rate.state == state,
        Rate.rate_type == rate_type,
        Rate.effective_from <= target_date,
        or_(
            Rate.effective_to >= target_date,
            Rate.effective_to.is_(None)
        )
    ).order_by(Rate.effective_from.desc()).first()


# ------------------------------------------------------------
# SECTION 5: CALCULATION FUNCTIONS
# ------------------------------------------------------------
def calculate_royalty(production_tpa: float, rate_per_tonne: float) -> Decimal:
    """
    PURPOSE  : Annual royalty = production × rate per tonne
    RECEIVES : production_tpa (float), rate_per_tonne (float)
    RETURNS  : Decimal — rounded to nearest rupee (ROUND_HALF_UP)
    SECURITY : No external calls
    LEGAL    : ⚠️ FATHER VERIFY rounding — does Rajasthan DMG round at this step
               or at the final total? Wrong rounding = rejected application.
               Always use Decimal(str(float)) — never Decimal(float) directly.
    """
    production = Decimal(str(production_tpa))
    rate = Decimal(str(rate_per_tonne))
    return (production * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def calculate_dmf(royalty: Decimal, dmf_pct: Decimal) -> Decimal:
    """
    PURPOSE  : DMF = royalty × (DMF percentage / 100)
    RECEIVES : royalty (Decimal), dmf_pct (Decimal) — PERCENTAGE e.g. Decimal('10')
               for 10%. This matches how Rate.value is stored and how DMG
               notifications express the rate. Admin panel entries must also be
               in this unit (10 means 10%, not 0.10).
    RETURNS  : Decimal — rounded to nearest rupee (ROUND_HALF_UP)
    SECURITY : No external calls
    LEGAL    : CONVENTION — Rate.value for rate_type='dmf' stores a percentage.
               Computation: dmf = royalty × (value / 100).
               ⚠️ FATHER VERIFY — DMF rate may vary by mine investment category.
    """
    result = royalty * (dmf_pct / Decimal('100'))
    return result.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def calculate_npv(
    annual_payment: Decimal,
    discount_rate: Decimal,
    years: int
) -> Decimal:
    """
    PURPOSE  : NPV of future government payments using annuity formula
    RECEIVES : annual_payment (Decimal), discount_rate (Decimal), years (int)
    RETURNS  : Decimal — NPV rounded to nearest rupee
    SECURITY : No external calls
    LEGAL    : ⚠️ FATHER VERIFY — discount rate per which notification?
               NPV formula: P × [(1 - (1+r)^-n) / r]
    """
    r = float(discount_rate)
    n = years
    p = float(annual_payment)

    annuity_factor = (1 - (1 + r) ** (-n)) / r
    npv = p * annuity_factor

    return Decimal(str(npv)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------
# SECTION 6: DISCLAIMER BUILDER
# ------------------------------------------------------------
def get_calculation_disclaimer(rate) -> str:
    """
    PURPOSE  : Generate mandatory disclaimer for every fee calculation output
    RECEIVES : rate (Rate) — the Rate object used for the calculation
    RETURNS  : str — full disclaimer text, always includes notification number and SEIAA
    SECURITY : No external calls
    LEGAL    : MANDATORY on every output page, every PDF export, every WhatsApp
               message containing a calculation result. Protects against liability.
               Advocates Act 1961 / Bar Council — consultation, not legal advice.
               This string is NEVER hardcoded — always generated from the Rate object.
    """
    return (
        f"Rates verified as of {rate.effective_from.strftime('%d %B %Y')} "
        f"per Notification No. {rate.notification_number}. "
        f"Estimation only — verify with SEIAA before making any government payment."
    )


# ------------------------------------------------------------
# SECTION 7: MAIN CALCULATION ORCHESTRATOR
# ------------------------------------------------------------
def run_full_calculation(
    mineral_name: str,
    state: str,
    area_ha: float,
    production_tpa: float,
    lease_date: date,
    lease_years: int = 5
) -> dict:
    """
    PURPOSE  : Run complete Royalty + DMF + NPV calculation for a mine
    RECEIVES : mineral_name (str), state (str), area_ha (float),
               production_tpa (float), lease_date (date), lease_years (int)
    RETURNS  : dict — full calculation breakdown with disclaimer
    SECURITY : No external calls, all Decimal arithmetic
    LEGAL    : Disclaimer always included in return dict.
               is_placeholder=True shown prominently if no DB rates exist.
    """
    from app.models import Mineral  # Late import

    is_placeholder = False
    royalty_rate = None
    dmf_rate_pct = None
    rate_row = None

    # Try to get rate from DB first
    mineral = Mineral.query.filter(
        Mineral.name.ilike(f'%{mineral_name}%')
    ).first()

    if mineral:
        rate_row = get_rate_for_date(mineral.id, state, 'royalty', lease_date)
        dmf_row = get_rate_for_date(mineral.id, state, 'dmf', lease_date)

        if rate_row:
            royalty_rate = Decimal(str(rate_row.value))

        if dmf_row:
            dmf_rate_pct = Decimal(str(dmf_row.value))

    # Fall back to placeholder rates if DB has no data
    if royalty_rate is None:
        is_placeholder = True
        placeholder = PLACEHOLDER_RATES.get(mineral_name.lower())
        if not placeholder:
            placeholder = list(PLACEHOLDER_RATES.values())[0]

        royalty_rate = placeholder['royalty_per_tonne']
        dmf_rate_pct = placeholder['dmf_rate']
        logger.info(f"Using placeholder rates for {mineral_name} — DB has no verified data")

    if dmf_rate_pct is None:
        dmf_rate_pct = Decimal('10')    # Default 10% as percentage ⚠️ FATHER VERIFY

    # Run calculations
    royalty_annual = calculate_royalty(production_tpa, float(royalty_rate))
    dmf_annual = calculate_dmf(royalty_annual, dmf_rate_pct)
    total_annual = royalty_annual + dmf_annual
    npv = calculate_npv(total_annual, DEFAULT_DISCOUNT_RATE, lease_years)

    if is_placeholder:
        disclaimer = (
            f"⚠️ SAMPLE RATES — These are placeholder values for testing only. "
            f"Do NOT use for actual government submissions. "
            f"Contact an expert to get verified {mineral_name} rates for Rajasthan."
        )
    else:
        disclaimer = get_calculation_disclaimer(rate_row)

    return {
        'mineral': mineral_name.title(),
        'state': state,
        'area_ha': area_ha,
        'production_tpa': int(production_tpa),
        'lease_date': lease_date.strftime('%d %B %Y'),
        'lease_years': lease_years,
        'royalty_rate_per_tonne': float(royalty_rate),
        'dmf_rate_pct': float(dmf_rate_pct),          # already a percentage (e.g. 10.0)
        'royalty_annual': float(royalty_annual),
        'dmf_annual': float(dmf_annual),
        'total_annual': float(total_annual),
        'npv': float(npv),
        'discount_rate_pct': float(DEFAULT_DISCOUNT_RATE * 100),
        'notification_number': rate_row.notification_number if rate_row else 'PLACEHOLDER',
        'disclaimer': disclaimer,
        'is_placeholder': is_placeholder,
        'calculation_timestamp': date.today().strftime('%d %B %Y')
    }