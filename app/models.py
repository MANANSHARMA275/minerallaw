# ============================================================
# FILE: app/models.py
# PURPOSE: All database models — 9 tables
# LAST UPDATED: Phase 1
# ============================================================

# ------------------------------------------------------------
# SECTION 1: IMPORTS
# ------------------------------------------------------------
from datetime import datetime, timezone
from hashlib import sha256
from flask_login import UserMixin
from app import db

# ------------------------------------------------------------
# SECTION 2: USER TABLE
# ------------------------------------------------------------
class User(UserMixin, db.Model):
    """
    PURPOSE  : Core user table — mine owners and admin accounts
    SECURITY : Password never stored — OTP-only auth
    LEGAL    : DPDP Act 2023 — consent stored per feature, deletion tracked
    """
    __tablename__ = 'user'

    id                       = db.Column(db.Integer, primary_key=True)
    phone                    = db.Column(db.String(15), unique=True, nullable=False)
    email                    = db.Column(db.String(120), unique=True, nullable=True)
    name                     = db.Column(db.String(100), nullable=True)
    company_name             = db.Column(db.String(200), nullable=True)
    gst_number               = db.Column(db.String(15), nullable=True)
    role                     = db.Column(db.String(20), default='user')        # user / staff / superadmin
    subscription_tier        = db.Column(db.String(20), default='free')        # free / pro / expert / enterprise
    google_sub               = db.Column(db.String(200), nullable=True)
    consent                  = db.Column(db.JSON, default=lambda: {
                                    "compliance_alerts": False,
                                    "ai_analysis": False,
                                    "expert_consultation": False,
                                    "marketing": False
                               })
    is_active                = db.Column(db.Boolean, default=True)
    created_at               = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login               = db.Column(db.DateTime, nullable=True)
    data_deletion_requested  = db.Column(db.Boolean, default=False)
    deletion_request_date    = db.Column(db.DateTime, nullable=True)

    # Relationships
    tickets      = db.relationship('Ticket', foreign_keys='[Ticket.user_id]', backref='user', lazy=True)
    documents    = db.relationship('Document', backref='user', lazy=True)
    audit_logs   = db.relationship('AuditLog', backref='user', lazy=True)
    payments     = db.relationship('Payment', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.phone}>'


# ------------------------------------------------------------
# SECTION 3: MINERAL TABLE
# ------------------------------------------------------------
class Mineral(db.Model):
    """
    PURPOSE  : Master list of minerals with EIA categorization
    SECURITY : Read-only for all users except superadmin
    LEGAL    : Categories determine which clearances are required
    """
    __tablename__ = 'mineral'

    id                    = db.Column(db.Integer, primary_key=True)
    name                  = db.Column(db.String(100), nullable=False)
    category              = db.Column(db.String(20), nullable=False)    # major / minor / critical
    eia_category_threshold = db.Column(db.Float, nullable=True)         # hectares threshold for EIA

    rates = db.relationship('Rate', backref='mineral', lazy=True)

    def __repr__(self):
        return f'<Mineral {self.name}>'


# ------------------------------------------------------------
# SECTION 4: RATE TABLE — NEVER UPDATE, ALWAYS INSERT NEW ROW
# ------------------------------------------------------------
class Rate(db.Model):
    """
    PURPOSE  : Historical rate tracking — royalty, DMF, NPV rates
    SECURITY : Superadmin only can add rates
    LEGAL    : CRITICAL — past calculations depend on historical rates.
               A lease from 2019 MUST use the 2019 rate, not current rate.
               effective_to=None means this rate is currently active.
               NEVER update a row. Always insert a new row.
    """
    __tablename__ = 'rate'

    id                  = db.Column(db.Integer, primary_key=True)
    mineral_id          = db.Column(db.Integer, db.ForeignKey('mineral.id'), nullable=False)
    state               = db.Column(db.String(50), nullable=False)
    rate_type           = db.Column(db.String(20), nullable=False)      # royalty / dmf / npv
    value               = db.Column(db.Numeric(10, 2), nullable=False)
    unit                = db.Column(db.String(20), nullable=True)       # per_tonne / per_hectare
    effective_from      = db.Column(db.Date, nullable=False)
    effective_to        = db.Column(db.Date, nullable=True)             # None = currently active
    notification_number = db.Column(db.String(100), nullable=True)
    verified_by         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    superseded          = db.Column(db.Boolean, default=False)
    superseded_reason   = db.Column(db.Text, nullable=True)
    correction_note     = db.Column(db.Text, nullable=True)
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Rate {self.rate_type} {self.value} from {self.effective_from}>'


# ------------------------------------------------------------
# SECTION 5: TICKET TABLE (Ask Expert)
# ------------------------------------------------------------
class Ticket(db.Model):
    """
    PURPOSE  : Expert consultation requests — SLA tracked
    SECURITY : Users see only their own tickets. Staff see all.
    LEGAL    : SLA 24 hours first response. 48h = escalated to father.
    """
    __tablename__ = 'ticket'

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject          = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.Text, nullable=False)
    mineral_type     = db.Column(db.String(100), nullable=True)
    state            = db.Column(db.String(50), nullable=True)
    urgency          = db.Column(db.String(20), default='normal')       # low / normal / high
    status           = db.Column(db.String(20), default='open')         # open / in_progress / resolved / escalated
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sla_deadline     = db.Column(db.DateTime, nullable=True)
    first_response_at = db.Column(db.DateTime, nullable=True)
    resolved_at      = db.Column(db.DateTime, nullable=True)
    satisfaction_score = db.Column(db.Integer, nullable=True)
    assigned_to      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<Ticket #{self.id} {self.status}>'


# ------------------------------------------------------------
# SECTION 6: DOCUMENT TABLE
# ------------------------------------------------------------
class Document(db.Model):
    """
    PURPOSE  : Uploaded PDF tracking — metadata, storage path, AI analysis
    SECURITY : Files stored in AWS S3 Mumbai (DPDP). Never in DB.
    LEGAL    : Hard deleted 30 days after analysis (DPDP data minimization)
    """
    __tablename__ = 'document'

    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename             = db.Column(db.String(200), nullable=False)
    original_filename    = db.Column(db.String(200), nullable=False)
    storage_path         = db.Column(db.String(500), nullable=True)     # S3 URL
    file_size            = db.Column(db.Integer, nullable=True)
    mime_type            = db.Column(db.String(50), nullable=True)
    checksum             = db.Column(db.String(64), nullable=True)      # SHA-256 for cache
    metadata_stripped    = db.Column(db.Boolean, default=False)
    virus_scanned        = db.Column(db.Boolean, default=False)
    scan_result          = db.Column(db.String(20), nullable=True)
    ai_analysis_result   = db.Column(db.Text, nullable=True)
    ai_analysis_cached   = db.Column(db.Boolean, default=False)
    created_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at           = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Document {self.original_filename}>'


# ------------------------------------------------------------
# SECTION 7: COMPLIANCE EVENT TABLE
# ------------------------------------------------------------
class ComplianceEvent(db.Model):
    """
    PURPOSE  : Track compliance deadlines — 6-monthly reports, annual returns
    SECURITY : User sees only their own events
    LEGAL    : WhatsApp reminders sent 7 days and 1 day before due_date
    """
    __tablename__ = 'compliance_event'

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type          = db.Column(db.String(50), nullable=False)
    due_date            = db.Column(db.Date, nullable=False)
    status              = db.Column(db.String(20), default='pending')   # pending / completed / overdue
    reminder_sent_7_days = db.Column(db.Boolean, default=False)
    reminder_sent_1_day  = db.Column(db.Boolean, default=False)
    completed_at        = db.Column(db.DateTime, nullable=True)
    proof_document_url  = db.Column(db.String(500), nullable=True)
    deleted_at          = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<ComplianceEvent {self.event_type} due {self.due_date}>'


# ------------------------------------------------------------
# SECTION 8: PAYMENT TABLE (Phase 3 — structure created now)
# ------------------------------------------------------------
class Payment(db.Model):
    """
    PURPOSE  : Payment records — Razorpay orders and subscriptions
    SECURITY : Never store card details. Razorpay handles PCI compliance.
    LEGAL    : Financial records retained 7 years (GST requirement).
               NEVER deleted even on user data deletion request.
    """
    __tablename__ = 'payment'

    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    razorpay_order_id    = db.Column(db.String(100), nullable=True)
    razorpay_payment_id  = db.Column(db.String(100), nullable=True)
    idempotency_key      = db.Column(db.String(100), unique=True, nullable=True)
    amount               = db.Column(db.Numeric(10, 2), nullable=False)
    gst_amount           = db.Column(db.Numeric(10, 2), nullable=True)
    total_amount         = db.Column(db.Numeric(10, 2), nullable=True)
    status               = db.Column(db.String(20), default='pending')
    subscription_tier    = db.Column(db.String(20), nullable=True)
    invoice_number       = db.Column(db.String(50), nullable=True)
    invoice_pdf_url      = db.Column(db.String(500), nullable=True)
    created_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at              = db.Column(db.DateTime, nullable=True)
    refunded_at          = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Payment ₹{self.total_amount} {self.status}>'


# ------------------------------------------------------------
# SECTION 9: AUDIT LOG — IMMUTABLE, NEVER DELETE
# ------------------------------------------------------------
class AuditLog(db.Model):
    """
    PURPOSE  : Immutable record of every data-changing action
    SECURITY : PostgreSQL trigger prevents UPDATE/DELETE at DB level
    LEGAL    : Legal evidence in disputes. Required for DPDP compliance.
               7-year retention minimum. NEVER delete these records.
    """
    __tablename__ = 'audit_log'

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action         = db.Column(db.String(100), nullable=False)
    table_affected = db.Column(db.String(50), nullable=True)
    record_id      = db.Column(db.Integer, nullable=True)
    old_value      = db.Column(db.Text, nullable=True)
    new_value      = db.Column(db.Text, nullable=True)
    ip_address     = db.Column(db.String(45), nullable=True)
    user_agent     = db.Column(db.String(300), nullable=True)
    timestamp      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<AuditLog {self.action} at {self.timestamp}>'


# ------------------------------------------------------------
# SECTION 10: AUCTION STATUS TABLE — single-row settings pattern
# ------------------------------------------------------------
class AuctionStatus(db.Model):
    """
    PURPOSE  : Superadmin-controlled banner for the public Auctions page.
               Single-row settings table — only one row should ever exist.
               Use get_auction_status() to read/create it.
    SECURITY : Written only via /admin/auctions/update (role_required superadmin)
    LEGAL    : No government data stored here — links point to official portals.
               status_text is plain text; escape on render, no HTML allowed.
    """
    __tablename__ = 'auction_status'

    id              = db.Column(db.Integer, primary_key=True)
    is_live         = db.Column(db.Boolean, default=False, nullable=False)
    status_text     = db.Column(db.String(300), nullable=True)
    status_text_hi  = db.Column(db.String(300), nullable=True)
    updated_by      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_at      = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<AuctionStatus live={self.is_live}>'


def get_auction_status() -> 'AuctionStatus':
    """
    PURPOSE  : Return the single AuctionStatus row, creating a default if absent
    RECEIVES : None — reads from current app context DB session
    RETURNS  : AuctionStatus — guaranteed non-None
    SECURITY : Read path is safe; write path (create default) is idempotent
    LEGAL    : Default row has is_live=False so no false "open" banner on first run
    """
    row = AuctionStatus.query.first()
    if row is None:
        row = AuctionStatus(is_live=False, status_text=None, status_text_hi=None)
        db.session.add(row)
        db.session.commit()
    return row


# ------------------------------------------------------------
# SECTION 11: WORKFLOW STATE TABLE
# ------------------------------------------------------------
class WorkflowState(db.Model):
    """
    PURPOSE  : Track clearance application progress through stages
    SECURITY : User sees only their own workflow
    LEGAL    : History JSON array preserves full audit trail of transitions
    """
    __tablename__ = 'workflow_state'

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    clearance_type  = db.Column(db.String(50), nullable=False)
    current_stage   = db.Column(db.String(100), nullable=False)
    transition_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    next_action     = db.Column(db.String(200), nullable=True)
    assigned_to     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    history         = db.Column(db.JSON, default=list)
    deleted_at      = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<WorkflowState {self.clearance_type} {self.current_stage}>'


# ------------------------------------------------------------
# SECTION 12: EC CONDITION TABLE — EC Report Builder (Phase 2 prep)
# ------------------------------------------------------------
class ECCondition(db.Model):
    """
    PURPOSE  : Store individual conditions from an EC approval letter
    SECURITY : Users see only their own conditions; father manages master list
    LEGAL    : Conditions come verbatim from the EC approval letter.
               Text is never edited after father verification — only superseded.
               A superseded condition is kept for historical audit purposes.
               NEVER delete or update a verified condition row.
    """
    __tablename__ = 'ec_condition'

    id                       = db.Column(db.Integer, primary_key=True)
    user_id                  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ec_document_id           = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    condition_number         = db.Column(db.String(20), nullable=False)
    category                 = db.Column(db.String(10), nullable=False)   # specific / general
    condition_text           = db.Column(db.Text, nullable=False)
    requires_monitoring_data = db.Column(db.Boolean, default=False)
    requires_photo           = db.Column(db.Boolean, default=False)
    verified_by_father       = db.Column(db.Boolean, default=False)
    superseded               = db.Column(db.Boolean, default=False)       # never edit — supersede
    created_at               = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ECCondition {self.condition_number} cat={self.category}>'


# ------------------------------------------------------------
# SECTION 13: COMPLIANCE REPORT TABLE — EC Report Builder (Phase 2 prep)
# ------------------------------------------------------------
class ComplianceReport(db.Model):
    """
    PURPOSE  : Track a 6-monthly EC compliance report from draft to acknowledged
    SECURITY : Users see only their own reports; expert review locks editing
    LEGAL    : Status flow: draft → pending_expert_review → expert_approved
               → finalized → acknowledged. Parivesh URL preserved for evidence.
               Reports must not be deleted after acknowledgement — legal record.
    """
    __tablename__ = 'compliance_report'

    id                            = db.Column(db.Integer, primary_key=True)
    user_id                       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    period_start                  = db.Column(db.Date, nullable=False)
    period_end                    = db.Column(db.Date, nullable=False)
    due_date                      = db.Column(db.Date, nullable=False)
    status                        = db.Column(db.String(30), default='draft')
    # draft → pending_expert_review → expert_approved → finalized → acknowledged
    pdf_url                       = db.Column(db.String(500), nullable=True)
    parivesh_acknowledgement_url  = db.Column(db.String(500), nullable=True)
    approved_by                   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at                   = db.Column(db.DateTime, nullable=True)
    created_at                    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ComplianceReport {self.period_start}–{self.period_end} {self.status}>'


# ------------------------------------------------------------
# SECTION 14: COMPLIANCE RESPONSE TABLE — EC Report Builder (Phase 2 prep)
# ------------------------------------------------------------
class ComplianceResponse(db.Model):
    """
    PURPOSE  : One mine owner's self-declaration for a single EC condition
               within one compliance report period
    SECURITY : Users see only their own responses; father_comment visible after review
    LEGAL    : self_declaration must be exactly one of the five prescribed values.
               Evidence document IDs link to Document table — never embed files here.
               previous_response_id enables pre-fill from the last period.
    """
    __tablename__ = 'compliance_response'

    id                     = db.Column(db.Integer, primary_key=True)
    report_id              = db.Column(db.Integer, db.ForeignKey('compliance_report.id'), nullable=False)
    condition_id           = db.Column(db.Integer, db.ForeignKey('ec_condition.id'), nullable=False)
    self_declaration       = db.Column(db.String(30), nullable=False)
    # exactly one of: Complied / Being Complied / Not Complied /
    #                 Partially Complied / Agreed to Comply
    remarks                = db.Column(db.Text, nullable=True)
    evidence_document_ids  = db.Column(db.JSON, default=list)
    previous_response_id   = db.Column(db.Integer, db.ForeignKey('compliance_response.id'), nullable=True)
    father_comment         = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<ComplianceResponse report={self.report_id} cond={self.condition_id}>'


# ------------------------------------------------------------
# SECTION 15: LEGISLATION TABLE — Rule-Change Digest
# ------------------------------------------------------------
class Legislation(db.Model):
    """
    PURPOSE  : Plain-language summaries of mining rule changes for public display
    SECURITY : is_published=False entries never appear on the public page.
               Only superadmin can create/edit/delete via admin panel.
    LEGAL    : All content is informational only. last_verified_on tracks when
               the domain expert last confirmed accuracy. Never delete entries —
               supersede with updated text so audit trail is preserved in AuditLog.
    """
    __tablename__ = 'legislation'

    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(300), nullable=False)
    category         = db.Column(db.String(100), nullable=False)   # e.g. "2025 Amendment"
    summary_en       = db.Column(db.Text, nullable=True)
    summary_hi       = db.Column(db.Text, nullable=True)
    source_reference = db.Column(db.String(200), nullable=True)    # e.g. "Rule 73A"
    official_url     = db.Column(db.String(500), nullable=True)    # link to gov PDF
    last_verified_on = db.Column(db.Date, nullable=True)
    is_published     = db.Column(db.Boolean, nullable=False, default=False)
    display_order    = db.Column(db.Integer, nullable=False, default=0)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at       = db.Column(db.DateTime,
                                 default=lambda: datetime.now(timezone.utc),
                                 onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Legislation {self.title[:40]!r} published={self.is_published}>'


# ------------------------------------------------------------
# SECTION 16: NEWS ITEM TABLE — DMG News & Events postings
# ------------------------------------------------------------
class NewsItem(db.Model):
    """
    PURPOSE  : One DMG "News & Events" posting — heading, date, category, dedup key
    SECURITY : Populated only by the importer (not user-supplied input).
               dedup_hash prevents double-inserts from the source page.
    LEGAL    : source_url preserved for attribution; content is publicly available
               government information. is_published controls public visibility.
    """
    __tablename__ = 'news_item'

    id           = db.Column(db.Integer, primary_key=True)
    heading      = db.Column(db.Text, nullable=False)
    order_date   = db.Column(db.Date, nullable=False)
    category     = db.Column(db.String(20), nullable=False, default='notice')
    source_url   = db.Column(db.String(500), nullable=False)
    dedup_hash   = db.Column(db.String(64), unique=True, nullable=False, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    fetched_at   = db.Column(db.DateTime, nullable=False)           # set by importer
    created_at   = db.Column(db.DateTime, nullable=False,
                             default=lambda: datetime.now(timezone.utc))

    documents    = db.relationship('NewsDocument', back_populates='news_item',
                                   cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_news_item_order_date', 'order_date'),
    )

    @staticmethod
    def compute_dedup_hash(heading: str, order_date) -> str:
        """
        PURPOSE  : Stable dedup key so the same DMG posting is never inserted twice
        RECEIVES : heading (str) — raw heading text; order_date (datetime.date)
        RETURNS  : str — 64-char lowercase sha256 hex digest
        SECURITY : Importer-only path; no user-supplied input reaches this method
        LEGAL    : N/A
        """
        normalized = ' '.join(heading.split()).lower()
        key = normalized + '|' + order_date.isoformat()
        return sha256(key.encode()).hexdigest()

    def __repr__(self):
        return f'<NewsItem {self.order_date} {self.heading[:40]!r}>'


# ------------------------------------------------------------
# SECTION 17: NEWS DOCUMENT TABLE — PDFs attached to a NewsItem
# ------------------------------------------------------------
class NewsDocument(db.Model):
    """
    PURPOSE  : One PDF attachment for a DMG news item (0–N documents per item)
    SECURITY : url is an official government PDF link; importer-only write path
    LEGAL    : UniqueConstraint on (news_item_id, url) prevents the same PDF
               being attached twice to one item.
    """
    __tablename__ = 'news_document'

    id           = db.Column(db.Integer, primary_key=True)
    news_item_id = db.Column(db.Integer, db.ForeignKey('news_item.id'), nullable=False)
    title        = db.Column(db.String(300), nullable=False)
    url          = db.Column(db.String(1000), nullable=False)
    created_at   = db.Column(db.DateTime, nullable=False,
                             default=lambda: datetime.now(timezone.utc))

    news_item    = db.relationship('NewsItem', back_populates='documents')

    __table_args__ = (
        db.UniqueConstraint('news_item_id', 'url', name='uq_news_document_item_url'),
    )

    def __repr__(self):
        return f'<NewsDocument item={self.news_item_id} {self.title[:30]!r}>'
