"""Add staff_phones to clinics

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clinics", sa.Column("staff_phones", sa.String(), nullable=True))


def downgrade():
    op.drop_column("clinics", "staff_phones")
