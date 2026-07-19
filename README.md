# MineralLaw.in — Mining Compliance SaaS

A B2B compliance platform for Indian minor-mineral lease holders. MineralLaw tracks
statutory deadlines (annual returns, EC renewals, dead rent, and other filings) and
delivers automated WhatsApp reminders — so small mining businesses never face a
shutdown because of missed paperwork.

Built on 30 years of Rajasthan mining-law consultancy expertise. Currently in active
development; the compliance automation and WhatsApp delivery pipeline are complete and
under supervised testing ahead of launch.

> **Status:** Pre-launch · Active development · 301 passing tests

---

## Why this exists

Every existing mining-compliance tool in India serves government officials or large
corporations. The small lease holder — running a business on a mid-range Android phone,
WhatsApp-first, with no compliance staff — has nothing. One missed deadline can suspend
their operations. MineralLaw is built for exactly that user.

## What is built so far

**Compliance automation pipeline**
- `ComplianceEvent` model with a rule-based deadline calculator (anchor dates +
  `relativedelta` offsets, centralised in a reviewable `COMPLIANCE_CONFIG`)
- Fingerprint-based idempotency — regenerating events never creates duplicates
- Scheduled Celery Beat task flags due reminders with window semantics,
  timezone-safe (`Asia/Kolkata`)
- Every statutory rule carries a verification flag until confirmed by a
  domain expert

**WhatsApp delivery infrastructure**
- Two-phase delivery task with full failure handling
- Four independent safety locks: network tripwire, kill switch (default off),
  DPDP consent check, and a database-level duplicate guard
- PII-minimised by design — phone numbers stored masked in delivery records
- Read-only superadmin delivery log with pagination and filtering

**Content & public pages**
- News/Events auto-importer from the DMG public page (fetch, parse, categorise
  with Hindi keyword support, dedupe)
- Bilingual Legislation Digest with admin CRUD (RMMCR Amendment 2025 entries)
- Public site with dark/light theming and a superadmin dashboard

## Engineering standards

- **301 automated tests** (`pytest tests/ -v` — the full suite runs at every stage,
  never a subset)
- Specification-driven development: structured plans are written and reviewed before
  any code, AI coding agents are directed against those plans, and every claim is
  independently verified in the terminal before commit
- Critical requirements are enforced by tests or grep checks, not prose
- Database migrations round-tripped on scratch databases before use; dev database
  backed up before every upgrade
- Nonce-based CSP, global CSRF, rate limiting, bcrypt, parameterised queries
- Every function documented with PURPOSE / RECEIVES / RETURNS / SECURITY / LEGAL

## Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| Database | PostgreSQL · SQLAlchemy · Flask-Migrate |
| Async & scheduling | Celery · Celery Beat · Redis |
| Messaging | WhatsApp (Twilio) |
| Testing | Pytest |
| Hosting | Railway |

## Running locally

```bash
git clone https://github.com/MANANSHARMA275/minerallaw.git
cd minerallaw
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your own values — never commit .env
flask db upgrade
python seed_data.py
flask run --port 8000       # port 5000 is occupied by AirPlay on macOS
```

Run the test suite:

```bash
pytest tests/ -v
```

## Roadmap

- Supervised pipeline dry run and first production delivery log entries
- AI-assisted document analysis (Claude API) with mandatory
  "Verify with Expert" badging
- Fee calculator (NPV / DMF / Royalty) with historical rate tracking
- Payments (Razorpay) and public launch

## Legal & privacy posture

Designed around India's DPDP Act 2023: explicit consent before any WhatsApp
communication, per-feature consent controls, immutable audit logging, and
PII-masked application logs. All AI-generated guidance will carry a
"Verify with Expert" notice (Advocates Act, 1961).

---

*Co-founded and engineered by [Manan Sharma](https://github.com/MANANSHARMA275) —
MCA (AI & ML), MIT-WPU Pune.*
