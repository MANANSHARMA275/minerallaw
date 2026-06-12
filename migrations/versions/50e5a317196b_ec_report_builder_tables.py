"""ec report builder tables

Revision ID: 50e5a317196b
Revises: d35d6dec50ab
Create Date: 2026-06-10 15:05:14.953624

REPAIR NOTE (2026-06-12): Original autogenerate re-declared every table
already created by d35d6dec50ab, causing a fresh-DB upgrade to collide.
This file now creates ONLY the three new EC Report Builder tables:
  compliance_report, ec_condition, compliance_response.
All other tables belong to d35d6dec50ab. Revision id and down_revision
are unchanged so the existing dev DB stamp remains valid.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50e5a317196b'
down_revision = 'd35d6dec50ab'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('compliance_report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=True),
    sa.Column('pdf_url', sa.String(length=500), nullable=True),
    sa.Column('parivesh_acknowledgement_url', sa.String(length=500), nullable=True),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['approved_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ec_condition',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ec_document_id', sa.Integer(), nullable=True),
    sa.Column('condition_number', sa.String(length=20), nullable=False),
    sa.Column('category', sa.String(length=10), nullable=False),
    sa.Column('condition_text', sa.Text(), nullable=False),
    sa.Column('requires_monitoring_data', sa.Boolean(), nullable=True),
    sa.Column('requires_photo', sa.Boolean(), nullable=True),
    sa.Column('verified_by_father', sa.Boolean(), nullable=True),
    sa.Column('superseded', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['ec_document_id'], ['document.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('compliance_response',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('condition_id', sa.Integer(), nullable=False),
    sa.Column('self_declaration', sa.String(length=30), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('evidence_document_ids', sa.JSON(), nullable=True),
    sa.Column('previous_response_id', sa.Integer(), nullable=True),
    sa.Column('father_comment', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['condition_id'], ['ec_condition.id'], ),
    sa.ForeignKeyConstraint(['previous_response_id'], ['compliance_response.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['compliance_report.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('compliance_response')
    op.drop_table('ec_condition')
    op.drop_table('compliance_report')
