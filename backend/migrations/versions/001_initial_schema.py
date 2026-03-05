"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clinics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("whatsapp_number", sa.String(), nullable=False),
        sa.Column("wa_phone_number_id", sa.String(), nullable=True),
        sa.Column("owner_email", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=True, server_default="free"),
        sa.Column("opening_time", sa.String(), nullable=True, server_default="09:00"),
        sa.Column("closing_time", sa.String(), nullable=True, server_default="22:00"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinics_id", "clinics", ["id"])
    op.create_index("ix_clinics_slug", "clinics", ["slug"], unique=True)

    op.create_table(
        "clinic_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True, server_default="receptionist"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinic_users_id", "clinic_users", ["id"])
    op.create_index("ix_clinic_users_clinic_id", "clinic_users", ["clinic_id"])

    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("specialty", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctors_id", "doctors", ["id"])
    op.create_index("ix_doctors_clinic_id", "doctors", ["clinic_id"])

    op.create_table(
        "queue_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("current_serving", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_issued_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_reset_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_state_id", "queue_state", ["id"])
    op.create_index("ix_queue_state_clinic_id", "queue_state", ["clinic_id"])
    op.create_index("ix_queue_state_doctor_id", "queue_state", ["doctor_id"])

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("patient_phone", sa.String(), nullable=True),
        sa.Column("token_type", sa.String(), nullable=True, server_default="whatsapp"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tokens_id", "tokens", ["id"])
    op.create_index("ix_tokens_clinic_id", "tokens", ["clinic_id"])
    op.create_index("ix_tokens_doctor_id", "tokens", ["doctor_id"])
    op.create_index("ix_tokens_patient_phone", "tokens", ["patient_phone"])
    op.create_index("ix_tokens_date", "tokens", ["date"])

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_phone", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_complaints_id", "complaints", ["id"])
    op.create_index("ix_complaints_clinic_id", "complaints", ["clinic_id"])

    op.create_table(
        "conversation_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_phone", sa.String(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(), nullable=True, server_default="idle"),
        sa.Column("temp_data", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_state_id", "conversation_state", ["id"])
    op.create_index("ix_conversation_state_patient_phone", "conversation_state", ["patient_phone"])
    op.create_index("ix_conversation_state_clinic_id", "conversation_state", ["clinic_id"])


def downgrade():
    op.drop_table("conversation_state")
    op.drop_table("complaints")
    op.drop_table("tokens")
    op.drop_table("queue_state")
    op.drop_table("doctors")
    op.drop_table("clinic_users")
    op.drop_table("clinics")
