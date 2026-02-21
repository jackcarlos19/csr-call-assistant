import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.models.ruleset import Rule, RuleSet
from app.schemas.events import EventEnvelope


class RuleService:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def evaluate_segment(
        self, session_id, tenant_id: str | None, text: str
    ) -> list[EventEnvelope]:
        events: list[EventEnvelope] = []
        if self.db is not None:
            rules = await self._load_rules(self.db, tenant_id)
        else:
            async with async_session() as db:
                rules = await self._load_rules(db, tenant_id)

        for rule in rules:
            rule_id = str(rule.config.get("id", str(rule.id)))
            kind = rule.kind

            if kind in {"keyword_alert", "prohibited_claim"}:
                patterns = rule.config.get("patterns", [])
                for pattern in patterns:
                    try:
                        matched = re.search(pattern, text, re.IGNORECASE)
                    except re.error:
                        continue
                    if matched:
                        events.append(
                            EventEnvelope(
                                session_id=session_id,
                                type="server.rule_alert",
                                ts_created=datetime.now(timezone.utc),
                                payload={
                                    "rule_id": rule_id,
                                    "kind": kind,
                                    "severity": rule.config.get("severity", "info"),
                                    "message": rule.config.get("message", ""),
                                    "matched_pattern": pattern,
                                },
                            )
                        )
                        break

            if kind == "required_question":
                patterns = rule.config.get("satisfy_patterns", [])
                for pattern in patterns:
                    try:
                        matched = re.search(pattern, text, re.IGNORECASE)
                    except re.error:
                        continue
                    if matched:
                        events.append(
                            EventEnvelope(
                                session_id=session_id,
                                type="server.required_question_status",
                                ts_created=datetime.now(timezone.utc),
                                payload={
                                    "rule_id": rule_id,
                                    "satisfied": True,
                                    "question": rule.config.get("question", rule_id),
                                },
                            )
                        )
                        break

        return events

    async def _load_rules(self, db: AsyncSession, tenant_id: str | None) -> list[Rule]:
        rules_stmt = (
            select(Rule)
            .join(RuleSet, Rule.ruleset_id == RuleSet.id)
            .where(
                Rule.enabled.is_(True),
                RuleSet.status == "active",
            )
        )
        if tenant_id:
            rules_stmt = rules_stmt.where(
                (RuleSet.tenant_id == tenant_id) | (RuleSet.tenant_id.is_(None))
            )
        return (await db.execute(rules_stmt)).scalars().all()
