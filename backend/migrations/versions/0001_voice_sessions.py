"""Add minimal consented voice session metadata.

Revision ID: 0001_voice_sessions
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_voice_sessions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_name", sa.String(80), nullable=False, unique=True),
        sa.Column("participant_identity", sa.String(80), nullable=False, unique=True),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("preferred_language", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("consent_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("failure_reason", sa.String(120)),
        sa.Column("dispatch_id", sa.String(80)),
    )
    op.create_index("ix_voice_owner_status", "voice_sessions", ["owner_hash", "status"])


def downgrade() -> None:
    op.drop_index("ix_voice_owner_status", table_name="voice_sessions")
    op.drop_table("voice_sessions")
