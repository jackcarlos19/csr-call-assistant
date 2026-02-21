import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[str] = mapped_column(String(50), default="active")
    tenant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    org_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)
