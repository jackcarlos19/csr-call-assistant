"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=True),
        sa.Column("org_id", sa.String(length=100), nullable=True),
        sa.Column("location_id", sa.String(length=100), nullable=True),
        sa.Column("campaign_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "call_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("server_seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["call_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "event_id", name="uq_session_event"),
        sa.UniqueConstraint("session_id", "server_seq", name="uq_session_seq"),
    )

    op.create_index("ix_call_events_session_id", "call_events", ["session_id"], unique=False)
    op.create_index("ix_call_events_type", "call_events", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_call_events_type", table_name="call_events")
    op.drop_index("ix_call_events_session_id", table_name="call_events")
    op.drop_table("call_events")
    op.drop_table("call_sessions")
