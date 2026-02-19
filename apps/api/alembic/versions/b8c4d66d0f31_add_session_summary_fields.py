"""add_session_summary_fields

Revision ID: b8c4d66d0f31
Revises: a3c6041bf6fa
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8c4d66d0f31"
down_revision: Union[str, Sequence[str], None] = "a3c6041bf6fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("call_sessions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("call_sessions", sa.Column("summary", sa.String(length=4000), nullable=True))
    op.add_column("call_sessions", sa.Column("disposition", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("call_sessions", "disposition")
    op.drop_column("call_sessions", "summary")
    op.drop_column("call_sessions", "ended_at")
