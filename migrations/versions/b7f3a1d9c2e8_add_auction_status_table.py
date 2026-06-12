"""add auction_status table

Revision ID: b7f3a1d9c2e8
Revises: 50e5a317196b
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f3a1d9c2e8'
down_revision = '50e5a317196b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auction_status',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('is_live', sa.Boolean(), nullable=False),
    sa.Column('status_text', sa.String(length=300), nullable=True),
    sa.Column('status_text_hi', sa.String(length=300), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('auction_status')
