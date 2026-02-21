import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.call_session import Base


class RuleSet(Base):
    __tablename__ = "rulesets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    org_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    rules: Mapped[list["Rule"]] = relationship(
        "Rule",
        back_populates="ruleset",
        cascade="all, delete-orphan",
    )


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ruleset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rulesets.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    ruleset: Mapped[RuleSet] = relationship("RuleSet", back_populates="rules")
