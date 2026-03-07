"""Add ad_text to clinics; add patient_name, patient_age to tokens

Revision ID: 003
Revises: 002
Create Date: 2026-03-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clinics", sa.Column("ad_text", sa.String(), nullable=True))
    op.add_column("tokens", sa.Column("patient_name", sa.String(), nullable=True))
    op.add_column("tokens", sa.Column("patient_age", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("clinics", "ad_text")
    op.drop_column("tokens", "patient_name")
    op.drop_column("tokens", "patient_age")
